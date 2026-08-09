"""qual_coding.py - 质性研究编码辅助（编码簿关键词命中标注 + 频次/共现）。

脚本只做确定性的"编码簿里写明的关键词/正则在文本何处出现"的机械统计，保证
编码过程可审计、可复现；开放式编码、主题归纳、理论饱和判断交研究者与 Agent。
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List

SCHEMA_VERSION = "1.0"

_TEMPLATE: Dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "name": "编码簿（codebook）",
    "codes": [
        {"code": "信任", "keywords": ["信任", "相信", "靠得住"],
         "patterns": [], "memo": "受访者对医生/机构的信任表述"},
        {"code": "就医决策", "keywords": ["就医", "看病", "挂号"],
         "patterns": [], "memo": "就医行为与决策过程"},
    ],
}


def build_codebook_template() -> Dict[str, Any]:
    tpl = copy.deepcopy(_TEMPLATE)
    tpl["_README"] = ("由研究者/Agent 维护：每个 code 配 keywords（字面词）与/或 patterns（正则），"
                      "脚本据此做确定性命中标注与频次/共现统计；开放式编码与主题归纳由研究者完成。"
                      "下划线字段为说明，校验时忽略。memo 为编码定义备注。")
    return tpl


def validate_codebook(cb: Any) -> List[Dict[str, str]]:
    """校验编码簿，返回错误列表（空即合法）。"""
    errors: List[Dict[str, str]] = []
    if not isinstance(cb, dict):
        return [{"field": "<root>", "message": "编码簿顶层必须是 JSON 对象"}]
    codes = cb.get("codes")
    if not isinstance(codes, list) or not codes:
        return [{"field": "codes", "message": "codes 必须是非空列表"}]
    seen = set()
    for i, c in enumerate(codes):
        if not isinstance(c, dict):
            errors.append({"field": f"codes[{i}]", "message": "每个编码必须是对象"})
            continue
        name = str(c.get("code") or "").strip()
        if not name:
            errors.append({"field": f"codes[{i}].code", "message": "缺少编码名 code"})
        elif name in seen:
            errors.append({"field": f"codes[{i}].code", "message": f"编码名重复: {name}"})
        else:
            seen.add(name)
        kws = c.get("keywords") or []
        pats = c.get("patterns") or []
        if not kws and not pats:
            errors.append({"field": f"codes[{i}]", "message": f"编码 {name or i} 需至少一个 keywords 或 patterns"})
        for p in pats:
            try:
                re.compile(p)
            except re.error as e:
                errors.append({"field": f"codes[{i}].patterns", "message": f"正则非法 {p!r}: {e}"})
    return errors


def load_codebook(path: str) -> Dict[str, Any]:
    import json
    from pathlib import Path
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("编码簿顶层必须是 JSON 对象")
    return raw


_PARA_SPLIT_RE = re.compile(r"\n\s*\n+")


def split_paragraphs(text: str) -> List[str]:
    """按空行切段；单换行不切（保留段内换行）。"""
    if not text:
        return []
    parts = [p.strip() for p in _PARA_SPLIT_RE.split(text)]
    return [p for p in parts if p]


def _iter_keyword_hits(para: str, keyword: str):
    """返回 keyword 在 para 中所有命中的起止位置（不重叠）。"""
    if not keyword:
        return
    start = 0
    while True:
        idx = para.find(keyword, start)
        if idx < 0:
            return
        yield idx, idx + len(keyword), keyword
        start = idx + len(keyword)


def _excerpt(para: str, start: int, end: int, pad: int = 10) -> str:
    a = max(0, start - pad)
    b = min(len(para), end + pad)
    s = para[a:b].replace("\n", " ").strip()
    return ("…" if a > 0 else "") + s + ("…" if b < len(para) else "")


def code_text(text: str, codebook: Dict[str, Any]) -> Dict[str, Any]:
    """按编码簿扫描文本 → {summary, codes, cooccurrence}。"""
    paragraphs = split_paragraphs(text or "")
    code_defs = [c for c in (codebook.get("codes") or []) if isinstance(c, dict) and c.get("code")]

    # 每个编码：命中明细、命中段集合
    agg: Dict[str, Dict[str, Any]] = {
        c["code"]: {"code": c["code"], "hits": 0, "paragraphs": set(), "matches": []}
        for c in code_defs
    }
    # 段落 → 命中的编码集合（用于共现）
    para_codes: List[set] = []

    for pi, para in enumerate(paragraphs, start=1):
        here: set = set()
        for c in code_defs:
            name = c["code"]
            hit_spans: List[tuple] = []
            for kw in (c.get("keywords") or []):
                hit_spans.extend(_iter_keyword_hits(para, str(kw)))
            for pat in (c.get("patterns") or []):
                try:
                    for m in re.finditer(pat, para):
                        if m.group(0):
                            hit_spans.append((m.start(), m.end(), m.group(0)))
                except re.error:
                    continue
            if not hit_spans:
                continue
            hit_spans.sort(key=lambda t: t[0])
            for s, e, token in hit_spans:
                agg[name]["hits"] += 1
                if len(agg[name]["matches"]) < 50:
                    agg[name]["matches"].append(
                        {"locator": f"第{pi}段", "excerpt": _excerpt(para, s, e), "keyword": token})
            agg[name]["paragraphs"].add(pi)
            here.add(name)
        para_codes.append(here)

    # 共现：同段内编码两两计数
    cooc: Dict[tuple, int] = {}
    for here in para_codes:
        names = sorted(here)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                cooc[(names[i], names[j])] = cooc.get((names[i], names[j]), 0) + 1

    codes_out = []
    total_hits = 0
    for c in code_defs:
        a = agg[c["code"]]
        total_hits += a["hits"]
        codes_out.append({
            "code": a["code"], "hits": a["hits"],
            "paragraphs": len(a["paragraphs"]), "matches": a["matches"],
        })
    codes_out.sort(key=lambda x: x["hits"], reverse=True)

    cooccurrence = [{"a": k[0], "b": k[1], "count": v}
                    for k, v in sorted(cooc.items(), key=lambda kv: kv[1], reverse=True)]

    coded = sum(1 for h in para_codes if h)
    return {
        "summary": {
            "paragraphs": len(paragraphs),
            "coded_paragraphs": coded,
            "uncoded_paragraphs": len(paragraphs) - coded,
            "codes": len(code_defs),
            "total_hits": total_hits,
        },
        "codes": codes_out,
        "cooccurrence": cooccurrence,
    }
