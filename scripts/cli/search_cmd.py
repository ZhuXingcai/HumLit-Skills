from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.search import (
    search_openalex, search_semantic_scholar, search_arxiv,
    search_nssd, search_dblp, search_base, search_all,
    resolve_crossref, resolve_unpaywall,
    get_citations, analyze_trends, search_with_fallback, SearchSourceError,
    interleave_results_by_source,
)
from core.paths import state_path
from core.formatter import export_papers, generate_reference_list, citation_preview
from cli._common import (
    CITATION_STYLE_CHOICES,
    _output, _enhance_error, _is_cnki_paper, _load_session, _save_session,
    _session_file, _session_project, _project_dir, _safe_project_name,
    _download_item_to_paper, _download_report_path, _paper_lookup_by_url,
    _merge_fallback_download, attach_download_report, build_download_report,
)

# ── CNKI 搜索缓存 ─────────────────────────────────────

_CNKI_CACHE_TTL_MINUTES = 30


def _cnki_cache_key(args) -> str:
    import hashlib
    key_parts = f"{args.query}|{args.core}|{args.year_from}|{args.year_to}|{args.author}|{args.journal}|{getattr(args, 'doc_type', '')}|{getattr(args, 'field', '')}|{args.sort}|{args.pages}|{getattr(args, 'cite_enrich', 0)}"
    return hashlib.md5(key_parts.encode()).hexdigest()


def _cnki_cache_get(args) -> Optional[list]:
    cache_dir = state_path("cache")
    cache_file = cache_dir / f"cnki_{_cnki_cache_key(args)}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            from datetime import datetime, timedelta
            cached_at = datetime.fromisoformat(data.get("_cached_at", ""))
            if datetime.now() - cached_at < timedelta(minutes=_CNKI_CACHE_TTL_MINUTES):
                return data.get("results")
        except Exception:
            pass
    return None


def _cnki_cache_set(args, results: list):
    from datetime import datetime
    cache_dir = state_path("cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"cnki_{_cnki_cache_key(args)}.json"
    data = {"_cached_at": datetime.now().isoformat(), "results": results}
    try:
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


# ── search 命令 ───────────────────────────────────────

def cmd_search(args):
    source = args.source or "cnki"
    if source not in ("cnki", "openalex", "semantic", "arxiv", "nssd", "dblp", "base", "api", "all"):
        _output({"status": "error", "code": "UNKNOWN_SOURCE",
                 "message": f"未知数据源: {source}"})
        return

    want_download = getattr(args, "download", False)
    if want_download and source != "cnki":
        _output({"status": "error", "code": "DOWNLOAD_SOURCE_MISMATCH",
                 "message": "--download 仅支持 --source cnki"})
        return

    results = []
    reuse_driver = None
    cnki_error = None
    source_statuses: Dict[str, Dict[str, Any]] = {}

    if source in ("cnki", "all"):
        from core.cnki import search_cnki

        # 检查 CNKI 搜索缓存
        cached_cnki = _cnki_cache_get(args) if not want_download else None
        if cached_cnki is not None:
            print("[cnki] 使用缓存结果", file=__import__('sys').stderr)
            results.extend(cached_cnki)
            source_statuses["cnki"] = {
                "status": "success" if cached_cnki else "empty",
                "count": len(cached_cnki),
                "cached": True,
            }
        else:
            keep = want_download and source == "cnki"
            cnki_ret = search_cnki(
                keyword=args.query,
                core=args.core,
                year_from=args.year_from,
                year_to=args.year_to,
                author=args.author,
                journal=args.journal,
                doc_type=getattr(args, "doc_type", None),
                field=getattr(args, "field", None),
                sort=args.sort or "relevance",
                pages=args.pages or 1,
                cite_enrich=getattr(args, "cite_enrich", 0),
                _keep_driver=keep,
            )
            if keep and isinstance(cnki_ret, tuple):
                cnki_results, reuse_driver = cnki_ret
            else:
                cnki_results = cnki_ret

            if cnki_results and not (len(cnki_results) == 1 and cnki_results[0].get("status") == "error"):
                results.extend(cnki_results)
                _cnki_cache_set(args, cnki_results)
                source_statuses["cnki"] = {"status": "success", "count": len(cnki_results)}
            elif cnki_results and cnki_results[0].get("status") == "error":
                if source == "cnki":
                    # 增强错误信息
                    enhanced_error = _enhance_error(cnki_results[0], {"query": args.query})
                    _output(enhanced_error)
                    if reuse_driver:
                        try: reuse_driver.quit()
                        except Exception: pass
                    return
                # source == "all" 时知网失败不阻断，记录错误后继续 API 搜索
                cnki_error = cnki_results[0]
                source_statuses["cnki"] = {
                    "status": "error",
                    "code": cnki_error.get("code", "CNKI_SEARCH_FAILED"),
                    "message": cnki_error.get("message", "知网搜索失败"),
                }
            else:
                source_statuses["cnki"] = {"status": "empty", "count": 0}

    try:
        has_keyword = bool(args.query and args.query.strip())

        api_limit = args.limit if args.limit is not None else 10

        # 获取字段参数（API 源使用英文字段名）
        field_param = "default"
        if hasattr(args, "field") and args.field:
            field_map = {"篇名": "title", "摘要": "abstract", "主题": "default"}
            field_param = field_map.get(args.field, "default")

        # 获取高级过滤参数
        author_filter = getattr(args, "author_filter", None)
        journal_filter = getattr(args, "journal_filter", None)
        field_of_study = getattr(args, "field_of_study", None)
        page = getattr(args, "page", 1)
        enable_fallback = getattr(args, "enable_fallback", False)
        async_search = getattr(args, "async_search", False)
        api_search_completed = False

        def run_api_source(source_name, search_func):
            try:
                found = search_func()
            except SearchSourceError as exc:
                source_statuses[source_name] = exc.as_dict()
                return
            results.extend(found)
            source_statuses[source_name] = {
                "status": "success" if found else "empty",
                "count": len(found),
            }

        # 稳定公开源可并发执行；all 额外包含前面的 CNKI 分支。
        if has_keyword and async_search and source in ("api", "all"):
            from core.search_async import search_all_sync

            print("[async] 使用异步并发搜索...", file=__import__('sys').stderr)
            async_result = search_all_sync(
                query=args.query,
                limit=api_limit,
                year_from=args.year_from,
                year_to=args.year_to,
                sort=args.sort or "relevance",
                sources=["openalex", "semantic_scholar", "arxiv", "nssd", "dblp"],
                field=field_param,
                journal=journal_filter,
                author=author_filter,
                field_of_study=field_of_study,
                page=page,
            )

            results.extend(async_result.get("results", []))
            source_statuses.update(async_result.get("source_statuses", {}))
            api_search_completed = True
            print(f"[async] 完成，耗时 {async_result.get('elapsed_ms', 0)} ms，"
                  f"使用数据源: {', '.join(async_result.get('sources_used', []))}",
                  file=__import__('sys').stderr)

        # 如果启用降级且指定了单一 API 源，使用 search_with_fallback
        elif has_keyword and enable_fallback and source in ("openalex", "semantic", "arxiv", "nssd", "dblp", "base"):
            fallback_result = search_with_fallback(
                query=args.query,
                primary_source=source,
                limit=api_limit,
                year_from=args.year_from,
                year_to=args.year_to,
                sort=args.sort or "relevance",
                field=field_param,
                journal=journal_filter,
                author=author_filter,
                field_of_study=field_of_study,
                page=page,
            )
            source_statuses.update(fallback_result.get("source_statuses", {}))

            if fallback_result.get("results"):
                results.extend(fallback_result["results"])
                actual_source = fallback_result.get("source") or source
                source_statuses.setdefault(actual_source, {
                    "status": "success", "count": len(fallback_result["results"]),
                })
                # 如果发生了降级，记录警告信息
                if fallback_result.get("fallback"):
                    print(f"[fallback] {fallback_result['original_source']} 失败，已切换到 {fallback_result['source']}",
                          file=__import__('sys').stderr)
            elif fallback_result.get("error"):
                print(f"[fallback] {fallback_result['error']}", file=__import__('sys').stderr)
                source_statuses.setdefault(source, {
                    "status": "error",
                    "code": "SOURCE_UNAVAILABLE",
                    "message": fallback_result["error"],
                })
            else:
                source_statuses.setdefault(source, {"status": "empty", "count": 0})
            api_search_completed = True

        # 否则使用原有的直接调用方式
        elif has_keyword and source in ("openalex", "api", "all"):
            run_api_source("openalex", lambda: search_openalex(
                    args.query, limit=api_limit,
                    year_from=args.year_from, year_to=args.year_to,
                    sort=args.sort or "relevance",
                    field=field_param,
                    journal=journal_filter,
                    author=author_filter,
                    field_of_study=field_of_study,
                    page=page,
                ))

        if not api_search_completed and has_keyword and source in ("semantic", "api", "all"):
            run_api_source("semantic_scholar", lambda: search_semantic_scholar(
                    args.query, limit=api_limit,
                    year_from=args.year_from, year_to=args.year_to,
                    sort=args.sort or "relevance",
                    field=field_param,
                    journal=journal_filter,
                    author=author_filter,
                    field_of_study=field_of_study,
                    page=page,
                ))

        if not api_search_completed and has_keyword and source in ("arxiv", "api", "all"):
            run_api_source("arxiv", lambda: search_arxiv(
                    args.query, limit=api_limit, sort_by=args.sort or "relevance",
                    year_from=args.year_from, year_to=args.year_to,
                    page=page,
                ))

        if not api_search_completed and has_keyword and source in ("nssd", "api", "all"):
            run_api_source("nssd", lambda: search_nssd(
                    args.query, limit=api_limit,
                    year_from=args.year_from, year_to=args.year_to,
                ))

        if not api_search_completed and has_keyword and source in ("dblp", "api", "all"):
            run_api_source("dblp", lambda: search_dblp(
                    args.query, limit=api_limit,
                    year_from=args.year_from, year_to=args.year_to,
                ))

        if not api_search_completed and has_keyword and source == "base":
            run_api_source("base", lambda: search_base(
                    args.query, limit=api_limit,
                    year_from=args.year_from, year_to=args.year_to,
                ))

        # 使用改进的去重函数（基于 DOI 和标题）
        from core.search import deduplicate_results, calculate_retrieval_priority_score
        deduped = deduplicate_results(results)

        # 检索优先级只衡量元数据完整性、影响力线索与获取便利性，不评价学术质量。
        for paper in deduped:
            score = calculate_retrieval_priority_score(paper)
            paper["retrieval_priority_score"] = score

        if args.sort == "citations":
            deduped.sort(key=lambda x: x.get("cited_by", 0), reverse=True)
        elif args.sort == "date":
            deduped.sort(key=lambda x: x.get("year") or 0, reverse=True)
        elif args.sort == "priority":
            deduped.sort(key=lambda x: x.get("retrieval_priority_score", 0), reverse=True)
        elif source in ("api", "all"):
            deduped = interleave_results_by_source(deduped)

        if args.limit is not None:
            effective_limit = args.limit
        elif args.pages and args.pages > 1 and source in ("cnki", "all"):
            effective_limit = args.pages * 20
        else:
            effective_limit = 20
        deduped = deduped[:effective_limit]

        # --enrich: 对知网结果自动补全卷期页码
        enrich_n = getattr(args, "enrich", 0)
        if enrich_n and enrich_n > 0:
            cnki_papers = [(i, p) for i, p in enumerate(deduped)
                           if _is_cnki_paper(p) and p.get("url") and not p.get("pages")]
            to_enrich = cnki_papers[:enrich_n]
            if to_enrich:
                print(f"[enrich] 正在补全 {len(to_enrich)} 篇论文的卷期页码...",
                      file=__import__('sys').stderr)
                from core.cnki import get_detail
                for idx, p in to_enrich:
                    detail = get_detail(p["url"])
                    if detail and detail.get("status") != "error":
                        for k in ("volume", "issue", "pages", "doi", "year", "journal", "authors"):
                            if detail.get(k) and not p.get(k):
                                p[k] = detail[k]
                    time.sleep(1)

        failed_sources = {
            name: status
            for name, status in source_statuses.items()
            if status.get("status") == "error"
        }
        completed_sources = {
            name: status
            for name, status in source_statuses.items()
            if status.get("status") in {"success", "empty"}
        }

        if len(deduped) == 0:
            if failed_sources and not completed_sources:
                first_error = next(iter(failed_sources.values()))
                _output({
                    "status": "error",
                    "code": first_error.get("code", "SOURCE_UNAVAILABLE"),
                    "message": "检索未完成，所有请求的数据源均不可用",
                    "count": 0,
                    "results": [],
                    "source_statuses": source_statuses,
                })
            elif failed_sources:
                _output({
                    "status": "partial",
                    "code": "PARTIAL_SOURCE_FAILURE",
                    "message": "部分数据源失败；已成功查询的数据源无匹配结果",
                    "count": 0,
                    "results": [],
                    "source_statuses": source_statuses,
                })
            else:
                no_results_error = {
                    "status": "warning",
                    "code": "NO_RESULTS",
                    "message": f"未找到匹配 '{args.query}' 的结果",
                    "count": 0,
                    "results": [],
                    "source_statuses": source_statuses,
                }
                _output(_enhance_error(no_results_error, {"query": args.query}))
            return

        _save_session(deduped, append=getattr(args, "append", False), project=_session_project(args))

        # 为每条结果添加引用预览
        for p in deduped:
            p["citation_preview"] = citation_preview(p)

        search_output = {
            "status": "partial" if failed_sources else "success",
            "count": len(deduped),
            "results": deduped,
            "source_statuses": source_statuses,
        }
        if cnki_error and source == "all":
            search_output["cnki_error"] = {"code": cnki_error.get("code"), "message": cnki_error.get("message")}
        if args.export:
            content = export_papers(deduped, args.export, args.output)
            if isinstance(content, dict) and content.get("status") == "error":
                search_output["export_error"] = content
            else:
                search_output.update({"format": args.export, "output_file": args.output,
                                      "content": content})

        if want_download and reuse_driver:
            from core.config import get as cfg_get
            from core.cnki import batch_download_cnki

            dl_dir = getattr(args, "download_dir", None) or cfg_get("save_dir", "./papers")
            dl_top_n = getattr(args, "download_top_n", None)
            dl_papers = deduped[:dl_top_n] if dl_top_n else deduped
            dl_urls = [p.get("url") for p in dl_papers if isinstance(p, dict) and p.get("url")]
            if dl_urls:
                dl_format = getattr(args, "download_file_format", "pdf") or "pdf"
                dl_result = batch_download_cnki(
                    dl_urls,
                    save_dir=dl_dir,
                    file_format=dl_format,
                    _driver=reuse_driver,
                )
                fallback_format = getattr(args, "download_fallback_format", None)
                if fallback_format:
                    failed_urls = [
                        err.get("url") for err in (dl_result.get("errors") or [])
                        if isinstance(err, dict)
                        and err.get("url")
                        and err.get("code") == "DOWNLOAD_BTN_NOT_FOUND"
                    ]
                    if failed_urls:
                        fallback_result = batch_download_cnki(
                            failed_urls,
                            save_dir=dl_dir,
                            file_format=fallback_format,
                            _driver=reuse_driver,
                        )
                        dl_result = _merge_fallback_download(dl_result, fallback_result)
                if not getattr(args, "download_no_report", False):
                    dl_result = attach_download_report(
                        dl_result,
                        save_dir=dl_dir,
                        session_papers=dl_papers,
                        requested_urls=dl_urls,
                        citation_style=getattr(args, "download_citation_style", "gbt7714") or "gbt7714",
                        file_format=dl_format,
                        report_output=getattr(args, "download_report_output", None),
                    )
                reuse_driver = None
                search_output["download"] = dl_result
            else:
                search_output["download"] = {"status": "warning", "code": "NO_DOWNLOAD_URLS",
                                             "message": "搜索结果中无可下载 URL"}

        _output(search_output)

    finally:
        if reuse_driver is not None:
            try:
                reuse_driver.quit()
            except Exception:
                pass


# ── batch-search 命令 ─────────────────────────────────

def cmd_batch_search(args):
    """批量搜索：浏览器只启动一次，循环搜索多个关键词"""
    from core.cnki import batch_search_cnki
    keywords = list(args.queries) if args.queries else []

    if args.query_file:
        qf = Path(args.query_file)
        if not qf.exists():
            _output({"status": "error", "code": "FILE_NOT_FOUND", "message": f"关键词文件不存在: {args.query_file}"})
            return
        qf_text = None
        for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312", "gb18030"):
            try:
                qf_text = qf.read_text(encoding=enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if qf_text is None:
            _output({"status": "error", "code": "ENCODING_ERROR",
                     "message": f"关键词文件编码无法识别: {args.query_file}"})
            return
        for line in qf_text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                keywords.append(line)

    if not keywords:
        _output({"status": "error", "code": "NO_KEYWORDS",
                 "message": "未提供关键词"})
        return

    result = batch_search_cnki(
        keywords=keywords,
        core=args.core,
        author=getattr(args, "author", None),
        journal=getattr(args, "journal", None),
        doc_type=getattr(args, "doc_type", None),
        field=getattr(args, "field", None),
        year_from=args.year_from,
        year_to=args.year_to,
        sort=args.sort or "relevance",
        pages=args.pages or 1,
    )

    if result.get("status") in ("success", "partial") and result.get("results"):
        _save_session(result.get("results") or [], append=args.append, project=_session_project(args))

    if args.export and result.get("results"):
        content = export_papers(result["results"], args.export, args.output)
        if isinstance(content, dict) and content.get("status") == "error":
            _output(content)
            return
        export_output = {"status": result.get("status", "success"),
                         "count": len(result["results"]),
                         "format": args.export, "output_file": args.output,
                         "content": content}
        if result.get("errors"):
            export_output["errors"] = result["errors"]
        _output(export_output)
    else:
        _output(result)


# ── citations 命令 ────────────────────────────────────

def cmd_citations(args):
    """引文网络分析：获取论文的前向/后向引用"""
    paper_id = args.paper_id
    if not paper_id:
        _output({"status": "error", "code": "NO_PAPER_ID",
                 "message": "请提供论文标识（DOI、URL 或 arXiv ID）"})
        return

    direction = args.direction or "both"
    limit = args.limit or 20

    print(f"[citations] 查询 {paper_id} 的引文网络（方向: {direction}）...",
          file=sys.stderr)

    result = get_citations(paper_id, direction=direction, limit=limit)

    if "error" in result:
        _output({"status": "error", "code": "RESOLVE_FAILED",
                 "message": result["error"]})
        return

    paper = result.get("paper", {})
    citing = result.get("citing", [])
    references = result.get("references", [])
    status = "success" if paper else "partial"

    _output({
        "status": status,
        "paper": paper,
        "citing_count": len(citing),
        "references_count": len(references),
        "citing": citing,
        "references": references,
    })


# ── trends 命令 ───────────────────────────────────────

def cmd_trends(args):
    """研究趋势分析：基于当前会话数据进行聚合统计"""
    papers = _load_session(_session_project(args))
    if not papers:
        _output({"status": "error", "code": "NO_SESSION_DATA",
                 "message": "没有可分析的论文，请先执行 search、batch-search 或 import"})
        return

    print(f"[trends] 分析 {len(papers)} 篇论文的研究趋势...", file=sys.stderr)

    result = analyze_trends(papers)
    _output({"status": "success", "project": _session_project(args), **result})


# ── 子命令注册 ────────────────────────────────────────


def add_parser(sub):
    p_search = sub.add_parser("search", help="搜索文献")
    p_search.add_argument("query", help="搜索关键词")
    p_search.add_argument("--source", default="cnki",
                          help="数据源: cnki/openalex/semantic/arxiv/nssd/dblp/api/all；base 为实验入口 (默认 cnki)")
    p_search.add_argument("--limit", type=int, default=None, help="结果数量限制（默认 20，多页时自动扩展）")
    p_search.add_argument("--core",
                          help="知网侧边栏来源类别，逗号分隔: 北大核心,CSSCI,AMI,WJCI,CSCD,EI")
    p_search.add_argument("--doc-type",
                          choices=["journal", "master", "doctor", "thesis",
                                   "conference", "newspaper"],
                          help="文献类型筛选: journal/master/doctor/thesis/conference/newspaper")
    p_search.add_argument("--field", default=None,
                          help="搜索字段: 主题(默认)/篇名/关键词/摘要/全文/作者/来源")
    p_search.add_argument("--year-from", type=int, help="起始年份")
    p_search.add_argument("--year-to", type=int, help="截止年份")
    p_search.add_argument("--author", help="作者（知网高级搜索）")
    p_search.add_argument("--journal", help="期刊名（知网高级搜索）")
    p_search.add_argument("--author-filter", help="作者过滤（API 源）")
    p_search.add_argument("--journal-filter", help="期刊过滤（API 源）")
    p_search.add_argument("--field-of-study", help="学科领域过滤（API 源）")
    p_search.add_argument("--page", type=int, default=1, help="页码（API 源分页，默认第 1 页）")
    p_search.add_argument("--sort", choices=["relevance", "date", "citations", "priority"],
                          default="relevance", help="排序方式")
    p_search.add_argument("--pages", type=int, default=1, help="知网抓取页数")
    p_search.add_argument("--enable-fallback", action="store_true",
                          help="启用 API 降级：主数据源失败时自动切换到备用数据源")
    p_search.add_argument("--async-search", action="store_true",
                          help="启用异步并发搜索（--source api/all，默认稳定公开源集合）")
    p_search.add_argument("--export", help="直接导出: bibtex/ris/markdown/json/excel")
    p_search.add_argument("--output", help="导出文件路径")
    p_search.add_argument("--download", action="store_true",
                          help="搜索后直接下载（仅 --source cnki）")
    p_search.add_argument("--download-dir", default="./papers",
                          help="下载目录（配合 --download，默认 ./papers）")
    p_search.add_argument("--download-top-n", type=int, default=None,
                          help="下载前 N 篇（配合 --download，默认全部）")
    p_search.add_argument("--download-file-format", choices=["pdf", "caj"], default="pdf",
                          help="下载文件格式（配合 --download，默认 pdf）")
    p_search.add_argument("--download-fallback-format", "--fallback-format",
                          dest="download_fallback_format", choices=["caj"], default=None,
                          help="主格式失败时的兜底格式；例如 PDF 按钮不存在时尝试 CAJ")
    p_search.add_argument("--download-citation-style", choices=CITATION_STYLE_CHOICES,
                          default="gbt7714", help="下载清单引用格式（配合 --download）")
    p_search.add_argument("--download-report-output",
                          help="下载清单输出路径（配合 --download，默认写入下载目录）")
    p_search.add_argument("--download-no-report", action="store_true",
                          help="不生成下载清单（配合 --download）")
    p_search.add_argument("--enrich", type=int, default=0, metavar="N",
                          help="自动补全前 N 篇知网论文的卷期页码（需访问详情页）")
    p_search.add_argument("--cite-enrich", type=int, default=0, metavar="N",
                          help="搜索时点击前 N 篇知网引用按钮，快速补全 GB/T 引用和页码")
    p_search.add_argument("--append", action="store_true",
                          help="追加到已有会话结果（而非覆盖）")
    p_search.add_argument("--project", help="课题文献库名称；指定后读写 .humlit/projects/<project>/session.json")
    p_search.set_defaults(func=cmd_search)

    p_batch = sub.add_parser("batch-search", help="批量知网搜索（一次启动浏览器）")
    p_batch.add_argument("queries", nargs="*", help="搜索关键词列表")
    p_batch.add_argument("--query-file", help="关键词文件路径（每行一个关键词）")
    p_batch.add_argument("--core",
                         help="知网侧边栏来源类别，逗号分隔: 北大核心,CSSCI,AMI,WJCI,CSCD,EI")
    p_batch.add_argument("--doc-type",
                         choices=["journal", "master", "doctor", "thesis",
                                  "conference", "newspaper"],
                         help="文献类型筛选: journal/master/doctor/thesis/conference/newspaper")
    p_batch.add_argument("--field", default=None,
                         help="搜索字段: 主题(默认)/篇名/关键词/摘要/全文/作者/来源")
    p_batch.add_argument("--author", help="作者（对每组关键词生效）")
    p_batch.add_argument("--journal", help="期刊名（对每组关键词生效）")
    p_batch.add_argument("--year-from", type=int, help="起始年份")
    p_batch.add_argument("--year-to", type=int, help="截止年份")
    p_batch.add_argument("--sort", choices=["relevance", "date", "citations", "priority"],
                         default="relevance", help="排序方式")
    p_batch.add_argument("--pages", type=int, default=1, help="每组关键词抓取页数")
    p_batch.add_argument("--export", help="直接导出: bibtex/ris/markdown/json/excel")
    p_batch.add_argument("--output", help="导出文件路径")
    p_batch.add_argument("--append", action="store_true",
                         help="追加到已有会话结果（而非覆盖）")
    p_batch.add_argument("--project", help="课题文献库名称")
    p_batch.set_defaults(func=cmd_batch_search)

    p_cite_net = sub.add_parser("citations", help="引文网络分析（前向/后向引用）")
    p_cite_net.add_argument("paper_id", help="论文标识（DOI、Semantic Scholar URL、arXiv ID 等）")
    p_cite_net.add_argument("--direction", choices=["citing", "cited", "both"], default="both",
                            help="引用方向：citing=谁引了它，cited=它引了谁，both=双向（默认）")
    p_cite_net.add_argument("--limit", type=int, default=20,
                            help="每个方向最多返回条数（默认 20）")
    p_cite_net.set_defaults(func=cmd_citations)

    p_trends = sub.add_parser("trends", help="研究趋势分析（基于会话中的搜索结果）")
    p_trends.add_argument("--project", help="课题文献库名称")
    p_trends.set_defaults(func=cmd_trends)
