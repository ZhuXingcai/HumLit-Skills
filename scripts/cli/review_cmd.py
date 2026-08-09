from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.formatter import generate_reference_list
from core.paths import state_path
from cli._common import (
    _output, _load_session, _save_session, _session_project,
    _safe_project_name, _project_dir, _session_file, _is_cnki_paper,
    _write_docx_from_markdown, CITATION_STYLE_CHOICES,
)



def _paper_year(paper: Dict[str, Any]) -> Any:
    return paper.get("year") or str(paper.get("date", ""))[:4]


def _paper_summary(paper: Dict[str, Any], index: int) -> Dict[str, Any]:
    return {
        "index": index,
        "title": paper.get("title", ""),
        "authors": paper.get("authors", ""),
        "journal": paper.get("journal", ""),
        "year": _paper_year(paper),
        "cited_by": paper.get("cited_by", 0),
        "source": paper.get("source", ""),
        "tags": paper.get("tags", []),
        "note": paper.get("note", ""),
    }


def _paper_evidence(paper: Dict[str, Any], index: int) -> Dict[str, Any]:
    abstract = str(paper.get("abstract") or "").strip()
    keywords = paper.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.replace("；", ";").replace("，", ";").split(";") if k.strip()]
    evidence = {
        "index": index,
        "title": paper.get("title", ""),
        "authors": paper.get("authors", ""),
        "journal": paper.get("journal", ""),
        "year": _paper_year(paper),
        "source": paper.get("source", ""),
        "doi": paper.get("doi", ""),
        "url": paper.get("url", ""),
        "keywords": keywords[:8],
        "abstract_excerpt": abstract[:220],
        "trace_status": "abstract" if abstract else "metadata_only",
    }
    if paper.get("pages"):
        evidence["pages"] = paper.get("pages")
    return evidence


def _review_terms(topic: str, paper: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    raw_terms = [topic, paper.get("title", ""), paper.get("journal", "")]
    keywords = paper.get("keywords") or []
    if isinstance(keywords, list):
        raw_terms.extend(str(k) for k in keywords)
    elif isinstance(keywords, str):
        raw_terms.extend(keywords.replace("；", ";").replace("，", ";").split(";"))
    for text in raw_terms:
        for token in str(text).replace("：", " ").replace(":", " ").replace("——", " ").split():
            token = token.strip(" ，。；;、,.()（）[]【】《》<>\"'")
            if len(token) >= 2 and token not in terms:
                terms.append(token)
    return terms[:12]


def _review_query_terms(topic: str) -> List[str]:
    stopwords = {
        "the", "and", "of", "in", "on", "for", "to", "with", "from", "via", "a", "an",
        "中的", "问题", "研究", "基于", "视域", "视角", "下的",
    }
    normalized = topic.lower()
    for sep in "：:，,；;、/\\()（）[]【】《》<>\"'\n\t":
        normalized = normalized.replace(sep, " ")
    terms = []
    for token in normalized.split():
        token = token.strip(" .-_—")
        if len(token) >= 3 and token not in stopwords and token not in terms:
            terms.append(token)
    for phrase in re.findall(r"[一-鿿]{2,}", topic):
        if phrase not in stopwords and phrase not in terms:
            terms.append(phrase)
    compact = topic.lower().replace(" ", "")
    if compact and compact not in terms:
        terms.append(compact)
    return terms


def _review_quality_flags(paper: Dict[str, Any], relevance: int) -> List[str]:
    title = str(paper.get("title") or "")
    source = str(paper.get("source") or "")
    flags = []
    if "retracted" in title.lower() or "撤稿" in title:
        flags.append("retracted")
    if relevance <= 0:
        flags.append("low_relevance")
    if not paper.get("abstract"):
        flags.append("needs_fulltext_check")
    if source in ("CNKI", "CNKI-export") and not paper.get("abstract"):
        flags.append("cnki_read_detail_recommended")
    return flags


def _review_candidates(papers: List[Dict[str, Any]], topic: str) -> List[Dict[str, Any]]:
    query_terms = _review_query_terms(topic)
    candidates = []
    for idx, paper in enumerate(papers, 1):
        title = str(paper.get("title") or "").lower()
        abstract = str(paper.get("abstract") or "").lower()
        keywords = str(paper.get("keywords") or "").lower()
        journal = str(paper.get("journal") or "").lower()
        text = " ".join((title, abstract, keywords, journal))
        relevance = 0
        for term in query_terms:
            if term in title:
                relevance += 40
            if term in keywords:
                relevance += 25
            if term in abstract:
                relevance += 10
            if term in journal:
                relevance += 5
        if topic.lower() in text:
            relevance += 80
        if not query_terms:
            relevance = 1
        metadata_score = 0
        if paper.get("abstract"):
            metadata_score += 2
        if paper.get("keywords"):
            metadata_score += 1
        cited_score = min(int(paper.get("cited_by") or 0), 50)
        flags = _review_quality_flags(paper, relevance)
        sort_relevance = relevance - 1000 if "retracted" in flags else relevance
        candidates.append({
            "index": idx,
            "paper": paper,
            "relevance": relevance,
            "sort_relevance": sort_relevance,
            "metadata_score": metadata_score,
            "cited_score": cited_score,
            "flags": flags,
        })
    candidates.sort(
        key=lambda item: (
            item["sort_relevance"], item["metadata_score"],
            item["cited_score"], item["paper"].get("year") or ""
        ),
        reverse=True,
    )
    return candidates


def _select_review_papers(papers: List[Dict[str, Any]], topic: str, limit: int) -> List[Dict[str, Any]]:
    candidates = _review_candidates(papers, topic)
    relevant = [item for item in candidates if item["relevance"] > 0 and "retracted" not in item["flags"]]
    selected_pool = relevant or candidates
    return selected_pool[:limit]


def _cluster_label_for_paper(paper: Dict[str, Any], topic: str) -> str:
    generic = {
        "研究", "分析", "方法", "问题", "视角", "视域", "evidence",
        "study", "analysis", "method", "research",
    }
    keywords = paper.get("keywords") or []
    if isinstance(keywords, str):
        keywords = re.split(r"[;,；，、]", keywords)
    for keyword in keywords:
        label = str(keyword).strip()
        if len(label) >= 2 and label.lower() not in generic:
            return label[:32]

    text = " ".join(
        str(paper.get(key, "")) for key in ("title", "abstract", "journal")
    ).lower()
    for term in _review_query_terms(topic):
        if term.lower() in text and term.lower() not in generic:
            return term[:32]

    title = re.sub(r"\s+", " ", str(paper.get("title") or "")).strip()
    if title:
        return title[:32]
    return "其他相关研究"


def _review_clusters(selected: List[Dict[str, Any]], topic: str) -> List[Dict[str, Any]]:
    clusters: Dict[str, List[Dict[str, Any]]] = {}
    for item in selected:
        label = _cluster_label_for_paper(item["paper"], topic)
        clusters.setdefault(label, []).append(item)
    result = []
    for label, items in sorted(clusters.items(), key=lambda kv: len(kv[1]), reverse=True):
        evidence = []
        claims = []
        for item in items:
            p = item["paper"]
            abstract = str(p.get("abstract") or "").strip()
            if abstract:
                claims.append(abstract[:90])
            evidence.append({
                "index": item["index"],
                "title": p.get("title", ""),
                "trace_status": "abstract" if abstract else "metadata_only",
                "abstract_excerpt": abstract[:160],
            })
        synthesis = ""
        if claims:
            synthesis = "；".join(claims[:3])
        result.append({
            "label": label,
            "count": len(items),
            "papers": evidence,
            "synthesis": synthesis,
        })
    return result


def _review_gaps(papers: List[Dict[str, Any]], topic: str) -> List[Dict[str, Any]]:
    total = len(papers)
    dimensions = [
        (
            "摘要或全文证据覆盖不足",
            "证据可追溯性",
            lambda paper: bool(paper.get("abstract") or paper.get("fulltext")),
        ),
        (
            "关键词元数据覆盖不足",
            "关键词元数据",
            lambda paper: bool(paper.get("keywords")),
        ),
        (
            "年份信息覆盖不足",
            "时间元数据",
            lambda paper: bool(_paper_year(paper)),
        ),
    ]
    gaps = []
    for title, dimension, predicate in dimensions:
        matches = [
            index for index, paper in enumerate(papers, 1) if predicate(paper)
        ]
        coverage = len(matches) / total if total else 0
        if coverage < 0.8:
            gaps.append({
                "title": title,
                "dimension": dimension,
                "matched_count": len(matches),
                "total": total,
                "evidence_indices": matches[:10],
                "coverage_ratio": round(coverage, 3),
                "claim_scope": "corpus_coverage_signal",
                "basis": (
                    f"当前文献库 {total} 篇中，{dimension}可观测记录为 "
                    f"{len(matches)} 篇；这只表示当前库覆盖，不代表真实研究空白。"
                ),
            })
    if not gaps:
        gaps.append({
            "title": "当前库未发现明显元数据缺口",
            "dimension": "检索覆盖",
            "matched_count": total,
            "total": total,
            "evidence_indices": list(range(1, min(total, 10) + 1)),
            "coverage_ratio": 1.0 if total else 0.0,
            "claim_scope": "corpus_coverage_signal",
            "basis": (
                "当前文献库的摘要、关键词和年份字段覆盖较完整；"
                "仍需扩展数据库并核对全文后才能判断学术研究空白。"
            ),
        })
    return gaps


def _build_review_markdown(topic: str, project: Optional[str], selected: List[Dict[str, Any]], total: int, diagnostics: List[Dict[str, Any]] = None, clusters: List[Dict[str, Any]] = None, gaps: List[Dict[str, Any]] = None) -> str:
    diagnostics = diagnostics or selected
    sources = sorted({item["paper"].get("source", "未获取") or "未获取" for item in selected})
    years = [str(_paper_year(item["paper"])) for item in selected if _paper_year(item["paper"])]
    year_range = f"{min(years)}-{max(years)}" if years else "未获取"
    close_reading = [item for item in selected if item.get("relevance", 0) > 0 and "retracted" not in item.get("flags", [])][:5]
    needs_check = [item for item in selected if "needs_fulltext_check" in item.get("flags", [])]
    risky = [item for item in diagnostics if "retracted" in item.get("flags", []) or "low_relevance" in item.get("flags", [])]
    lines = [
        f"# {topic} 文献综述材料",
        "",
        "## 检索证据",
        f"- 课题文献库：{project or '默认 session'}",
        f"- 分析文献数：{len(selected)} / {total}",
        f"- 数据来源：{', '.join(sources) if sources else '未获取'}",
        f"- 年份范围：{year_range}",
        "- 说明：以下内容基于文献题录、关键词和摘要生成；缺少摘要的条目标注为待核对原文。",
        "",
        "## 推荐精读文献",
    ]
    if close_reading:
        for item in close_reading:
            paper = item["paper"]
            lines.append(f"- [{item['index']}] {paper.get('title', '未获取')}（相关性分：{item.get('relevance', 0)}）")
    else:
        lines.append("- 暂无高相关文献；建议调整关键词重新检索。")
    lines.extend(["", "## 待核对原文"])
    if needs_check:
        for item in needs_check:
            paper = item["paper"]
            hint = "；建议先执行 read-detail --project <课题名> --indices " + str(item["index"]) if paper.get("source") in ("CNKI", "CNKI-export") else ""
            lines.append(f"- [{item['index']}] {paper.get('title', '未获取')}：当前缺少摘要或全文{hint}")
    else:
        lines.append("- 暂无。")
    lines.extend(["", "## 可能不相关或需剔除文献"])
    if risky:
        for item in risky:
            paper = item["paper"]
            flags = "、".join(item.get("flags") or [])
            lines.append(f"- [{item['index']}] {paper.get('title', '未获取')}：{flags}")
    else:
        lines.append("- 暂无明显撤稿或低相关条目。")
    lines.extend(["", "## 主题聚类"])
    if clusters:
        for cluster in clusters:
            lines.append(f"### {cluster['label']}（{cluster['count']} 篇）")
            if cluster.get("synthesis"):
                lines.append(f"该主题下的文献主要围绕“{topic}”展开，现有摘要显示：{cluster['synthesis']}。")
            else:
                lines.append("该主题下文献当前多为题录信息，具体观点仍需补充摘要或原文后核对。")
            lines.append("")
            lines.append("代表文献与证据：")
            for paper in cluster["papers"]:
                status = "摘要可追溯" if paper.get("trace_status") == "abstract" else "待核对原文"
                excerpt = f"；摘要依据：{paper['abstract_excerpt']}" if paper.get("abstract_excerpt") else ""
                lines.append(f"- [{paper['index']}] {paper.get('title', '未获取')}：{status}{excerpt}")
            lines.append("")
    else:
        lines.append("- 未启用聚类；可使用 `--cluster` 生成主题聚类章节。")
    lines.extend(["## 研究空白提示"])
    if gaps:
        for gap in gaps:
            indices = ",".join(str(i) for i in gap.get("evidence_indices", [])) or "无"
            lines.extend([
                f"### {gap['title']}",
                f"- 检索证据：{gap['basis']}",
                f"- 相关文献序号：{indices}",
            ])
    else:
        lines.append("- 未启用研究空白分析；可使用 `--gaps` 基于当前文献库生成统计提示。")
    lines.extend(["", "## 主题线索"])
    for item in selected:
        paper = item["paper"]
        idx = item["index"]
        terms = "、".join(_review_terms(topic, paper)[:6]) or "待提取"
        suffix = ""
        if item.get("flags"):
            suffix = f"（提示：{'、'.join(item['flags'])}）"
        lines.extend([
            f"- [{idx}] {paper.get('title', '未获取')}：{terms}{suffix}",
        ])
    lines.extend(["", "## 综述草稿", ""])
    for item in selected:
        paper = item["paper"]
        idx = item["index"]
        abstract = str(paper.get("abstract") or "").strip()
        if "retracted" in item.get("flags", []):
            point = "该文献标题显示可能为撤稿文献，不建议作为正面证据使用，仅可作为剔除或风险提示。"
        elif abstract:
            point = abstract[:180]
        else:
            point = "该文献当前仅有题录信息，具体观点需补充摘要或原文后核对。"
        lines.extend([
            f"### 线索 {idx}：{paper.get('title', '未获取')}",
            f"围绕“{topic}”，该文献可作为相关研究线索。{point}",
            "",
            "证据：",
            f"- 作者：{paper.get('authors', '未获取') or '未获取'}",
            f"- 来源：{paper.get('journal', '未获取') or '未获取'}，{_paper_year(paper) or '未获取'}",
            f"- 相关性分：{item.get('relevance', 0)}",
            f"- 追溯状态：{'摘要可追溯' if abstract else '待核对原文'}",
            "",
        ])
    lines.extend(["## 参考文献线索"])
    for item in selected:
        p = item["paper"]
        lines.append(f"[{item['index']}] {p.get('authors', '未获取') or '未获取'}. {p.get('title', '未获取') or '未获取'}. {p.get('journal', '未获取') or '未获取'}, {_paper_year(p) or '未获取'}.")
    return "\n".join(lines)


def _paper_write_excerpt(paper: Dict[str, Any], limit: int = 120) -> str:
    text = str(paper.get("abstract") or paper.get("summary") or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def _evidence_indices(items: List[Dict[str, Any]], limit: int = 5) -> str:
    return "".join(f"[{item['index']}]" for item in items[:limit])


def _cluster_evidence_indices(cluster: Dict[str, Any], limit: int = 5) -> str:
    return "".join(f"[{paper['index']}]" for paper in cluster.get("papers", [])[:limit])


def _build_review_outline(topic: str, clusters: List[Dict[str, Any]], gaps: List[Dict[str, Any]]) -> str:
    lines = [f"# {topic} 文献综述大纲", "", "## 一、研究背景与问题提出"]
    intro_indices = _cluster_evidence_indices(clusters[0]) if clusters else ""
    lines.append(f"- 交代“{topic}”的研究缘起、核心概念和现实背景{intro_indices}。")
    lines.append("- 明确本文综述的对象、范围和资料来源。")
    lines.extend(["", "## 二、研究脉络与主题分支"])
    if clusters:
        for i, cluster in enumerate(clusters, 1):
            indices = _cluster_evidence_indices(cluster)
            lines.append(f"- {i}. {cluster['label']}：梳理该方向的主要问题、代表观点和证据边界{indices}。")
    else:
        lines.append("- 当前文献库尚未形成稳定主题分支，建议先扩展检索。")
    lines.extend(["", "## 三、研究不足与后续方向"])
    for gap in gaps[:4]:
        indices = "".join(f"[{i}]" for i in gap.get("evidence_indices", [])[:5]) or "（需补检索）"
        lines.append(f"- {gap['title']}：{gap['basis']}，证据线索 {indices}。")
    lines.extend(["", "## 四、段落证据映射", "- 写作时每个实质段落需保留证据编号，并对缺摘要文献标注“待核对原文”。"])
    return "\n".join(lines)


def _build_review_section(topic: str, selected: List[Dict[str, Any]], clusters: List[Dict[str, Any]], gaps: List[Dict[str, Any]], section: str) -> str:
    section_key = section.strip() if section else "文献综述"
    draft = _build_review_draft(topic, selected, clusters, gaps, mode="draft")
    if section_key in ("研究背景", "背景", "问题提出"):
        usable = [item for item in selected if item.get("relevance", 0) > 0 and "retracted" not in item.get("flags", [])]
        indices = _evidence_indices(usable)
        return "\n".join([
            f"# {topic}：研究背景",
            "",
            f"围绕“{topic}”，当前文献库提供了若干概念、对象、方法和案例线索{indices}。不同记录在摘要、关键词和原文可追溯性上并不均衡，因此本段只能作为证据脚手架；后续写作需要区分摘要可追溯证据与待核对原文证据，并回到本领域文献补足背景判断。",
            "",
            "## 段落证据映射",
            *[f"- [{item['index']}] {item['paper'].get('title', '未获取')}：{'摘要可追溯' if item['paper'].get('abstract') else '待核对原文'}，相关性分 {item.get('relevance', 0)}" for item in usable],
        ])
    if section_key in ("研究不足", "不足", "未来方向", "后续方向"):
        lines = [f"# {topic}：研究不足与后续方向", ""]
        for gap in gaps[:4]:
            indices = "".join(f"[{i}]" for i in gap.get("evidence_indices", [])[:5]) or "（当前库无直接证据）"
            lines.append(f"从现有文献库的覆盖情况看，{gap['title']}仍值得进一步展开。{gap['basis']}，相关证据序号为{indices}。这一不足并不意味着相关研究不存在，而是提示后续检索应在该维度上补充数据库、关键词和原文核对。")
        return "\n\n".join(lines)
    for cluster in clusters:
        if section_key in cluster["label"] or cluster["label"] in section_key:
            indices = _cluster_evidence_indices(cluster)
            body = cluster.get("synthesis") or "该方向下部分文献仍缺少摘要，现阶段只能作为题录线索处理。"
            return "\n".join([
                f"# {topic}：{cluster['label']}",
                "",
                f"在{cluster['label']}这一分支中，相关文献主要提供了关于“{topic}”的概念、对象或案例线索{indices}。{body}。由于该分支内部证据密度可能不均，写作时应优先使用摘要可追溯文献，并将缺少摘要的条目标注为待核对原文。",
                "",
                "## 段落证据映射",
                *[f"- [{paper['index']}] {paper.get('title', '未获取')}：{'摘要可追溯' if paper.get('trace_status') == 'abstract' else '待核对原文'}" for paper in cluster.get("papers", [])],
            ])
    return draft


def _build_review_draft(topic: str, selected: List[Dict[str, Any]], clusters: List[Dict[str, Any]], gaps: List[Dict[str, Any]], mode: str = "draft", section: str = "") -> str:
    usable = [item for item in selected if item.get("relevance", 0) > 0 and "retracted" not in item.get("flags", [])]
    cluster_list = clusters or _review_clusters(usable, topic)
    if mode == "outline":
        return _build_review_outline(topic, cluster_list, gaps)
    if mode == "section" or section:
        return _build_review_section(topic, selected, cluster_list, gaps, section)

    lines = [f"# {topic} 文献综述初稿", "", "## 一、研究背景与问题提出"]
    if not usable:
        lines.append("当前文献库中尚未形成足够高相关、可追溯的文献基础，建议扩大检索或补充摘要后再生成综述初稿。")
    else:
        intro_indices = _evidence_indices(usable)
        sources = sorted({item["paper"].get("source", "未获取") or "未获取" for item in usable})
        lines.append(
            f"围绕“{topic}”，当前文献库已经形成以{ '、'.join(cluster['label'] for cluster in cluster_list[:4]) }为主的若干研究分支{intro_indices}。从资料来源看，相关证据主要来自{ '、'.join(sources) }；从证据质量看，部分文献具有摘要支撑，部分条目仍需继续补充详情页或原文。因而，后续写作应把已有摘要作为直接论证基础，把题录信息作为待核对线索。"
        )
        lines.extend(["", "## 二、研究脉络与主题分支"])
        for cluster in cluster_list:
            indices = _cluster_evidence_indices(cluster)
            if cluster.get("synthesis"):
                body = cluster["synthesis"]
                evidence_note = "这些摘要能够为该分支的基本判断提供初步依据"
            else:
                body = "该分支目前主要由题录信息构成，尚不足以支撑细节性结论"
                evidence_note = "相关判断需在补充摘要或全文后再强化"
            lines.extend([
                f"### {cluster['label']}",
                f"{cluster['label']}是“{topic}”研究中的一个重要切面{indices}。现有材料显示，{body}。因此，写作时可将该分支作为综述的一个层次展开，但需要注意证据边界：{evidence_note}。",
                "",
            ])
        lines.extend(["## 三、研究不足与后续方向"])
        for i, gap in enumerate(gaps[:4], 1):
            indices = "".join(f"[{idx}]" for idx in gap.get("evidence_indices", [])[:5]) or "（当前库无直接证据）"
            lines.append(f"{i}. {gap['title']}。{gap['basis']}，相关证据序号为{indices}。这一提示只反映当前文献库的覆盖情况，后续应通过扩展关键词、数据库和原文核对进一步确认。")
    lines.append("")
    lines.append("## 四、段落证据映射")
    for item in usable:
        p = item["paper"]
        status = "摘要可追溯" if p.get("abstract") else "待核对原文"
        excerpt = _paper_write_excerpt(p, 80)
        excerpt_text = f"；摘要线索：{excerpt}" if excerpt else ""
        lines.append(f"- [{item['index']}] {p.get('title', '未获取')}：{status}，相关性分 {item.get('relevance', 0)}{excerpt_text}")
    return "\n".join(lines)


def _auto_detail_for_review(papers: List[Dict[str, Any]], candidates: List[Dict[str, Any]], detail_top_n: int, project: Optional[str]) -> Dict[str, Any]:
    from core.cnki import batch_read_detail
    targets = []
    for item in candidates:
        paper = item["paper"]
        if item.get("relevance", 0) <= 0 or "retracted" in item.get("flags", []):
            continue
        if _is_cnki_paper(paper) and paper.get("url") and not paper.get("abstract"):
            targets.append(item)
        if len(targets) >= detail_top_n:
            break
    if not targets:
        return {"attempted": 0, "updated": 0, "indices": []}

    selected = [item["paper"] for item in targets]
    enriched = batch_read_detail(papers=selected, top_n=len(selected), fulltext=False)
    enriched_map = {p.get("url", ""): p for p in enriched if isinstance(p, dict) and p.get("url")}
    updated = list(papers)
    updated_count = 0
    for item in targets:
        idx = item["index"] - 1
        url = updated[idx].get("url", "")
        detail = enriched_map.get(url)
        if not detail:
            continue
        before_had_abstract = bool(updated[idx].get("abstract"))
        merged = dict(updated[idx])
        for k, v in detail.items():
            if k == "fulltext":
                continue
            if v:
                merged[k] = v
        if merged.get("abstract") and not before_had_abstract:
            updated_count += 1
        updated[idx] = merged
    _save_session(updated, project=project)
    return {
        "attempted": len(targets),
        "updated": updated_count,
        "indices": [item["index"] for item in targets],
    }


def _review_write_inputs(papers: List[Dict[str, Any]], topic: str, limit: int) -> tuple:
    selected = _select_review_papers(papers, topic, limit)
    clusters = _review_clusters(selected, topic)
    gaps = _review_gaps(papers, topic)
    return selected, clusters, gaps


def _append_references(markdown: str, selected: List[Dict[str, Any]], style: str = "gbt7714") -> str:
    papers = [item["paper"] for item in selected]
    refs = generate_reference_list(papers, style)
    if refs:
        markdown = markdown.rstrip() + "\n\n## 参考文献\n" + refs.strip() + "\n"
    return markdown


def _sentence_evidence_indices(text: str) -> List[int]:
    return [int(i) for i in re.findall(r"\[(\d+)\]", text)]


def _validation_body(markdown: str) -> str:
    body = re.sub(r"## 参考文献[\s\S]*$", "", markdown)
    body = re.sub(r"## [一二三四五六七八九十、]*段落证据映射[\s\S]*$", "", body)
    return body


def _claim_sentences(markdown: str) -> List[Dict[str, Any]]:
    body = _validation_body(markdown)
    claims = []
    section = "正文"
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            section = stripped.lstrip("#").strip()
            continue
        if stripped.startswith("-"):
            stripped = stripped.lstrip("- ").strip()
        for raw in re.split(r"(?<=[。！？.!?])\s*", stripped):
            sentence = raw.strip()
            if len(sentence) < 12:
                continue
            claims.append({
                "section": section,
                "claim": sentence[:260],
                "evidence_indices": _sentence_evidence_indices(sentence),
            })
    return claims


def _paper_validation_text(paper: Dict[str, Any]) -> str:
    keywords = paper.get("keywords") or ""
    if isinstance(keywords, list):
        keywords = " ".join(str(k) for k in keywords)
    parts = [
        paper.get("title", ""),
        paper.get("journal", ""),
        keywords,
        paper.get("abstract", ""),
        paper.get("fulltext", ""),
    ]
    return " ".join(str(part) for part in parts if part).lower()


def _claim_terms(claim: str) -> List[str]:
    terms = []
    stopwords = {"研究", "文献", "相关", "现有", "显示", "因此", "这一", "进行", "通过", "围绕", "当前", "方面", "中的", "需要", "判断", "证据"}
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", claim.lower()):
        if token not in terms:
            terms.append(token)
    for phrase in re.findall(r"[一-鿿]{2,}", claim):
        if phrase in stopwords:
            continue
        for size in (6, 5, 4, 3, 2):
            if len(phrase) < size:
                continue
            for i in range(0, len(phrase) - size + 1):
                token = phrase[i:i + size]
                if token in stopwords:
                    continue
                if token not in terms:
                    terms.append(token)
                if len(terms) >= 24:
                    return terms
    return terms[:24]


def _support_for_claim(claim: Dict[str, Any], evidence_by_index: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    indices = claim.get("evidence_indices", [])
    if not indices:
        return {"support_level": "unsupported", "reason": "该论断未附证据编号", "matched_terms": []}
    invalid = [index for index in indices if index not in evidence_by_index]
    if invalid:
        return {"support_level": "invalid", "reason": f"证据编号不存在：{invalid}", "matched_terms": []}

    terms = _claim_terms(claim.get("claim", ""))
    matched_terms = []
    missing_abstract = False
    risky = False
    best_overlap = 0
    for index in indices:
        item = evidence_by_index[index]
        paper = item["paper"]
        flags = item.get("flags", [])
        text = _paper_validation_text(paper)
        overlap_terms = [term for term in terms if term in text]
        best_overlap = max(best_overlap, len(overlap_terms))
        for term in overlap_terms:
            if term not in matched_terms:
                matched_terms.append(term)
        if not paper.get("abstract") or "needs_fulltext_check" in flags:
            missing_abstract = True
        if "retracted" in flags:
            risky = True

    if risky:
        return {"support_level": "invalid", "reason": "引用了疑似撤稿文献，不应作为正面证据", "matched_terms": matched_terms[:8]}
    if missing_abstract:
        return {"support_level": "needs_fulltext_check", "reason": "引用文献缺少摘要或全文证据，需核对原文", "matched_terms": matched_terms[:8]}
    if not terms:
        return {"support_level": "medium", "reason": "论断缺少可提取关键词，但引用编号有效", "matched_terms": []}
    if best_overlap >= 2:
        return {"support_level": "strong", "reason": "论断关键词与引用文献题名/摘要/关键词存在较好匹配", "matched_terms": matched_terms[:8]}
    if best_overlap == 1:
        return {"support_level": "medium", "reason": "论断与引用文献存在有限词项匹配，建议核对表述是否过强", "matched_terms": matched_terms[:8]}
    return {"support_level": "weak", "reason": "未在引用文献题名/摘要/关键词中找到明显词项支撑", "matched_terms": []}


def _validate_writing(markdown: str, selected: List[Dict[str, Any]]) -> Dict[str, Any]:
    evidence_by_index = {item["index"]: item for item in selected}
    usable_indices = {
        item["index"] for item in selected
        if item.get("relevance", 0) > 0 and "retracted" not in item.get("flags", [])
    }
    claims = _claim_sentences(markdown)
    claim_results = []
    counts = {"strong": 0, "medium": 0, "weak": 0, "needs_fulltext_check": 0, "unsupported": 0, "invalid": 0}
    for claim in claims:
        support = _support_for_claim(claim, evidence_by_index)
        level = support["support_level"]
        counts[level] = counts.get(level, 0) + 1
        claim_results.append({
            "section": claim["section"],
            "claim": claim["claim"],
            "evidence_indices": claim["evidence_indices"],
            **support,
        })

    body = _validation_body(markdown)
    cited_indices = set(_sentence_evidence_indices(body))
    invalid_indices = sorted({index for index in cited_indices if index not in evidence_by_index})
    weak_claims = [item for item in claim_results if item["support_level"] in ("weak", "needs_fulltext_check")]
    unsupported_claims = [item for item in claim_results if item["support_level"] == "unsupported"]
    invalid_claims = [item for item in claim_results if item["support_level"] == "invalid"]
    unused_usable = sorted(usable_indices - cited_indices)

    issues = []
    if invalid_indices:
        issues.append({"type": "invalid_evidence_index", "indices": invalid_indices, "message": "正文引用了不存在于本次写作证据集的编号"})
    if unsupported_claims:
        issues.append({"type": "unsupported_claim", "count": len(unsupported_claims), "examples": unsupported_claims[:5], "message": "存在未附证据编号的实质性论断"})
    if weak_claims:
        issues.append({"type": "weak_or_unverified_support", "count": len(weak_claims), "examples": weak_claims[:8], "message": "部分论断与引用证据匹配较弱，或需核对原文"})
    if invalid_claims:
        issues.append({"type": "invalid_support", "count": len(invalid_claims), "examples": invalid_claims[:5], "message": "部分论断引用了无效或高风险证据"})
    if unused_usable:
        issues.append({"type": "unused_relevant_evidence", "indices": unused_usable[:12], "message": "部分高相关证据未进入正文论证，可按需补充"})

    score = 100
    score -= min(counts.get("unsupported", 0) * 8, 32)
    score -= min(counts.get("weak", 0) * 6, 30)
    score -= min(counts.get("needs_fulltext_check", 0) * 5, 25)
    score -= min(counts.get("invalid", 0) * 18, 45)
    score = max(score, 0)
    status = "success" if score >= 80 and not invalid_claims else "warning"
    recommendations = []
    if unsupported_claims:
        recommendations.append("为未附编号的论断补充 [证据序号]，或删除无法由当前文献库支撑的判断。")
    if weak_claims:
        recommendations.append("对弱匹配或缺摘要证据执行 read-detail/read-detail --fulltext，并收紧过强表述。")
    if invalid_claims:
        recommendations.append("移除无效编号或疑似撤稿文献，改用摘要可追溯的高相关文献。")
    if unused_usable:
        recommendations.append("检查未使用的高相关文献，必要时补充到相应段落。")
    return {
        "status": status,
        "score": score,
        "evidence_count": len(selected),
        "cited_evidence_count": len(cited_indices),
        "checked_claims": len(claim_results),
        "support_counts": counts,
        "claim_results": claim_results[:30],
        "issues": issues,
        "recommendations": recommendations,
    }


def cmd_write(args):
    papers = _load_session(_session_project(args))
    if not papers:
        _output({"status": "error", "code": "NO_SESSION_DATA", "message": "没有可写作的文献，请先执行 search、batch-search 或 import"})
        return
    topic = args.topic or _session_project(args) or "当前课题"
    limit = min(args.limit or 12, len(papers))
    selected, clusters, gaps = _review_write_inputs(papers, topic, limit)
    mode = getattr(args, "mode", "draft") or "draft"
    section = getattr(args, "section", "") or ""
    if section and mode == "draft":
        mode = "section"
    markdown = _build_review_draft(topic, selected, clusters, gaps, mode=mode, section=section)
    if args.with_citations:
        markdown = _append_references(markdown, selected, args.citation_style or "gbt7714")
    validation = _validate_writing(markdown, selected) if getattr(args, "validate", False) else None

    output_path = Path(args.output) if args.output else None
    if args.format == "docx":
        if output_path is None:
            output_path = Path("review.docx")
        elif output_path.suffix.lower() != ".docx":
            output_path = output_path.with_suffix(".docx")
        result = _write_docx_from_markdown(markdown, output_path)
        result.update({"project": _session_project(args), "topic": topic, "mode": mode, "section": section or None, "format": "docx", "validation": validation})
        _output(result)
        return

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    if args.raw:
        print(markdown)
    else:
        _output({
            "status": "success",
            "project": _session_project(args),
            "topic": topic,
            "mode": mode,
            "section": section or None,
            "format": "markdown",
            "output_file": str(output_path) if output_path else None,
            "validation": validation,
            "markdown": markdown,
        })


def _topic_methods(label: str, gap_title: str) -> List[str]:
    text = (label + " " + gap_title).lower()
    methods = []
    if any(term in text for term in ("模型", "算法", "model", "algorithm")):
        methods.extend(["模型构建", "计算分析", "验证性研究"])
    if any(term in text for term in ("实验", "experiment", "causal", "因果")):
        methods.extend(["实验研究", "因果识别", "稳健性检验"])
    if any(term in text for term in ("访谈", "质性", "田野", "interview", "qualitative")):
        methods.extend(["访谈研究", "案例研究", "质性分析"])
    if not methods:
        methods.extend(["文献综述", "实证研究", "比较研究"])
    return list(dict.fromkeys(methods))[:4]


def _build_topics(topic: str, papers: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    candidates = _review_candidates(papers, topic)
    selected = [item for item in candidates if item.get("relevance", 0) > 0 and "retracted" not in item.get("flags", [])][:max(limit, 1)]
    clusters = _review_clusters(selected, topic)
    gaps = _review_gaps(papers, topic)
    suggestions = []
    for cluster in clusters[:4]:
        cluster_indices = [paper["index"] for paper in cluster.get("papers", [])[:5]]
        matched_gap = None
        for gap in gaps:
            if gap.get("evidence_indices"):
                if set(cluster_indices) & set(gap.get("evidence_indices", [])):
                    matched_gap = gap
                    break
        if matched_gap is None and gaps:
            matched_gap = gaps[min(len(suggestions), len(gaps) - 1)]
        gap_title = matched_gap.get("title", "需进一步明确研究空白") if matched_gap else "需进一步明确研究空白"
        evidence_indices = sorted(set(cluster_indices + (matched_gap.get("evidence_indices", [])[:5] if matched_gap else [])))
        if not evidence_indices:
            evidence_indices = cluster_indices
        risks = []
        if not evidence_indices:
            risks.append("当前文献库证据不足，需先补充检索")
        if any("metadata_only" == paper.get("trace_status") for paper in cluster.get("papers", [])):
            risks.append("部分证据仅有题录信息，需补摘要或原文")
        if matched_gap and matched_gap.get("matched_count", 0) == 0:
            risks.append("该方向当前库无直接命中文献，不能直接断言真实研究空白")
        suggestions.append({
            "title": f"{topic}中的{cluster['label']}研究",
            "rationale": f"当前文献库中“{cluster['label']}”聚类包含 {cluster.get('count', 0)} 篇线索；{matched_gap.get('basis', '需结合更多检索证据判断研究空间') if matched_gap else '需结合更多检索证据判断研究空间'}",
            "evidence_indices": evidence_indices[:8],
            "possible_methods": _topic_methods(cluster["label"], gap_title),
            "risks": risks or ["需在开题前继续核对核心文献和原文证据"],
            "followup_search": [topic, cluster["label"], gap_title],
        })
    if not suggestions:
        suggestions.append({
            "title": f"{topic}的研究现状与问题重构",
            "rationale": f"当前文献库共有 {len(papers)} 篇记录，但高相关聚类不足，适合先做综述型选题或扩大检索。",
            "evidence_indices": [],
            "possible_methods": ["文献综述", "关键词扩展检索", "题录筛选"],
            "risks": ["证据基础不足，不能直接进入实证设计"],
            "followup_search": [topic, f"{topic} 研究现状", f"{topic} 研究空白"],
        })
    return suggestions[:limit]


def cmd_topics(args):
    papers = _load_session(_session_project(args))
    if not papers:
        _output({"status": "error", "code": "NO_SESSION_DATA", "message": "没有可生成选题的数据，请先执行 search、batch-search 或 import"})
        return
    topic = args.topic or _session_project(args) or "当前课题"
    suggestions = _build_topics(topic, papers, args.limit or 8)
    _output({
        "status": "success",
        "project": _session_project(args),
        "topic": topic,
        "total": len(papers),
        "count": len(suggestions),
        "topics": suggestions,
    })


def cmd_validate(args):
    papers = _load_session(_session_project(args))
    if not papers:
        _output({"status": "error", "code": "NO_SESSION_DATA", "message": "没有可校验的文献，请先执行 search、batch-search 或 import"})
        return
    topic = args.topic or _session_project(args) or "当前课题"
    limit = min(args.limit or 12, len(papers))
    selected, clusters, gaps = _review_write_inputs(papers, topic, limit)
    if args.file:
        markdown = Path(args.file).read_text(encoding="utf-8")
    else:
        markdown = _build_review_draft(topic, selected, clusters, gaps, mode="draft")
    validation = _validate_writing(markdown, selected)
    validation.update({
        "project": _session_project(args),
        "topic": topic,
        "checked_file": args.file,
    })
    _output(validation)


def cmd_review(args):
    papers = _load_session(_session_project(args))
    if not papers:
        _output({"status": "error", "code": "NO_SESSION_DATA", "message": "没有可生成综述的文献，请先执行 search、batch-search 或 import"})
        return
    topic = args.topic or _session_project(args) or "当前课题"
    limit = min(args.limit or 12, len(papers))
    candidates = _review_candidates(papers, topic)
    auto_detail = None
    if getattr(args, "auto_detail", False):
        detail_top_n = max(getattr(args, "detail_top_n", 5) or 5, 1)
        print(f"[review] 自动补全高相关知网文献摘要（最多 {detail_top_n} 篇）...", file=sys.stderr)
        auto_detail = _auto_detail_for_review(papers, candidates, detail_top_n, _session_project(args))
        if auto_detail.get("attempted"):
            papers = _load_session(_session_project(args))
            candidates = _review_candidates(papers, topic)
    selected = _select_review_papers(papers, topic, limit)
    clusters = _review_clusters(selected, topic) if getattr(args, "cluster", False) else None
    gaps = _review_gaps(papers, topic) if getattr(args, "gaps", False) else None
    evidence = []
    for item in selected:
        entry = _paper_evidence(item["paper"], item["index"])
        entry["relevance"] = item.get("relevance", 0)
        entry["flags"] = item.get("flags", [])
        evidence.append(entry)
    markdown = _build_review_markdown(topic, _session_project(args), selected, len(papers), candidates, clusters, gaps)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
    if args.raw:
        print(markdown)
    else:
        _output({
            "status": "success",
            "project": _session_project(args),
            "topic": topic,
            "count": len(selected),
            "total": len(papers),
            "output_file": args.output,
            "auto_detail": auto_detail,
            "clusters": clusters,
            "gaps": gaps,
            "evidence": evidence,
            "markdown": markdown,
        })


def cmd_projects(args):
    base = state_path("projects")
    projects = []
    if base.exists():
        for project_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            papers = _load_session(project_dir.name)
            projects.append({
                "name": project_dir.name,
                "count": len(papers),
                "session_file": str(project_dir / "session.json"),
            })
    _output({"status": "success", "count": len(projects), "projects": projects})


def cmd_library(args):
    papers = _load_session(_session_project(args))
    if not papers:
        _output({"status": "error", "code": "NO_SESSION_DATA", "message": "没有可查看的文献，请先执行 search、batch-search 或 import"})
        return
    limit = args.limit or len(papers)
    rows = [_paper_summary(p, i + 1) for i, p in enumerate(papers[:limit])]
    _output({"status": "success", "project": _session_project(args), "count": len(papers), "results": rows})


def add_parser(sub):
    # projects
    p_projects = sub.add_parser("projects", help="列出课题文献库")
    p_projects.set_defaults(func=cmd_projects)

    # library
    p_library = sub.add_parser("library", help="查看当前或指定课题文献库")
    p_library.add_argument("--project", help="课题文献库名称")
    p_library.add_argument("--limit", type=int, help="最多显示前 N 篇")
    p_library.set_defaults(func=cmd_library)

    # review
    p_review = sub.add_parser("review", help="基于会话/课题文献库生成可追溯综述材料")
    p_review.add_argument("--topic", help="综述主题；默认使用 --project 或当前课题")
    p_review.add_argument("--project", help="课题文献库名称")
    p_review.add_argument("--limit", type=int, default=12, help="最多纳入前 N 篇相关文献（默认 12）")
    p_review.add_argument("--output", help="输出 Markdown 文件路径")
    p_review.add_argument("--auto-detail", action="store_true", help="生成综述前自动补全高相关知网文献摘要")
    p_review.add_argument("--detail-top-n", type=int, default=5, help="配合 --auto-detail，最多补全 N 篇知网文献（默认 5）")
    p_review.add_argument("--cluster", action="store_true", help="按主题聚类组织综述材料")
    p_review.add_argument("--gaps", action="store_true", help="基于当前文献库统计生成研究空白提示")
    p_review.add_argument("--raw", action="store_true", help="直接输出 Markdown 文本")
    p_review.set_defaults(func=cmd_review)

    # write
    p_write = sub.add_parser("write", help="基于课题文献库生成可追溯的综述大纲或有边界初稿")
    p_write.add_argument("--project", help="课题文献库名称")
    p_write.add_argument("--topic", help="写作主题；默认使用 --project 或当前课题")
    p_write.add_argument("--limit", type=int, default=12, help="最多纳入前 N 篇相关文献（默认 12）")
    p_write.add_argument("--format", choices=["markdown", "md", "docx"], default="markdown", help="输出格式：markdown/md/docx")
    p_write.add_argument("--mode", choices=["outline", "draft", "section"], default="draft", help="写作模式：outline 大纲 / draft 正文 / section 单节")
    p_write.add_argument("--section", help="只生成指定章节，如 研究背景、研究不足、某个主题聚类名称")
    p_write.add_argument("--output", help="输出文件路径")
    p_write.add_argument("--with-citations", action="store_true", help="附加参考文献列表")
    p_write.add_argument("--citation-style", default="gbt7714", choices=CITATION_STYLE_CHOICES)
    p_write.add_argument("--validate", action="store_true", help="同时输出写作证据质量校验报告")
    p_write.add_argument("--raw", action="store_true", help="直接输出 Markdown 文本")
    p_write.set_defaults(func=cmd_write)

    p_validate = sub.add_parser("validate", help="检查综述证据编号、风险项和词项重叠")
    p_validate.add_argument("--project", help="课题文献库名称")
    p_validate.add_argument("--topic", help="写作主题；默认使用 --project 或当前课题")
    p_validate.add_argument("--limit", type=int, default=12, help="最多纳入前 N 篇相关文献（默认 12）")
    p_validate.add_argument("--file", help="待校验的 Markdown 文件；缺省时校验当前自动生成草稿")
    p_validate.set_defaults(func=cmd_validate)

    p_topics = sub.add_parser("topics", help="基于当前文献库生成待验证的选题假设")
    p_topics.add_argument("--project", help="课题文献库名称")
    p_topics.add_argument("--topic", help="选题方向；默认使用 --project 或当前课题")
    p_topics.add_argument("--limit", type=int, default=6, help="最多生成 N 个选题建议（默认 6）")
    p_topics.set_defaults(func=cmd_topics)
