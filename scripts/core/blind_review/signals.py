from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.thesis_format.model import DocModel

_REVIEW_TITLE_RE = re.compile(r"(综述|研究现状|文献回顾|文献综述|literature review)", re.IGNORECASE)
_INNOVATION_RE = re.compile(r"(创新点|创新之处|本文创新|主要创新|主要贡献|研究创新)")
_THEORY_RE = re.compile(r"(理论框架|分析框架|以[\u4e00-\u9fff]{2,}理论|基于[\u4e00-\u9fff]{2,}理论|[\u4e00-\u9fff]{2,}视角下)")
_RETRACTED_RE = re.compile(r"(撤稿|retracted)", re.IGNORECASE)
_NON_BODY_TITLES = ("摘要", "abstract", "目录", "致谢", "致 谢", "参考文献", "references", "附录", "appendix")

_METHOD_KEYWORDS = [
    "问卷", "访谈", "内容分析", "话语分析", "案例", "扎根", "实验", "统计",
    "回归", "质性", "定量", "定性", "田野", "民族志", "文本分析", "比较研究",
    "深度访谈", "焦点小组", "结构方程", "社会网络分析",
]


def _count_chars(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def _refs_last5y_ratio(references: List[str], now_year: int) -> float:
    if not references:
        return 0.0
    recent = 0
    for ref in references:
        years = [int(y) for y in re.findall(r"(?:19|20)\d{2}", ref)]
        if years and max(years) >= now_year - 4:
            recent += 1
    return round(recent / len(references), 3)


def _body_chapter_count(model: DocModel) -> int:
    count = 0
    for h in model.headings:
        if h.level != 1:
            continue
        low = h.text.strip().lower()
        if any(t in low for t in _NON_BODY_TITLES):
            continue
        count += 1
    return count


def compute_signals(model: DocModel, rubric: Dict[str, Any],
                    full_text: str = "", format_report: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    now_year = datetime.now().year
    text = full_text or ""

    ref_count = len(model.references)
    lit_present = any(_REVIEW_TITLE_RE.search(t) for t in model.section_titles)
    # 综述章节正文长度无法从 DocModel 精确切分，用全文匹配兜底
    review_chars = _count_chars(text) if (lit_present and text) else 0

    intext = sorted(set(model.intext_ref_numbers))
    intext_unmatched = sum(1 for n in intext if n > ref_count)

    method_hits = [kw for kw in _METHOD_KEYWORDS if kw in text]
    inv_match = _INNOVATION_RE.search(text)

    signals_by_id = {
        "topic_review": {
            "reference_count": ref_count,
            "refs_last5y_ratio": _refs_last5y_ratio(model.references, now_year),
            "review_section_chars": review_chars,
            "lit_review_present": lit_present,
        },
        "innovation": {
            "innovation_statement_found": bool(inv_match),
            "innovation_locator": inv_match.group(0) if inv_match else None,
        },
        "theory_capability": {
            "method_keywords": method_hits,
            "theory_framework_found": bool(_THEORY_RE.search(text)),
            "chapter_count": _body_chapter_count(model),
            "body_chars": _count_chars(text),
        },
        "norms_writing": {
            "format_check": (format_report or {}).get("summary") if format_report else None,
            "intext_ref_unmatched": intext_unmatched,
        },
    }

    signals: Dict[str, Any] = {}
    for dim in rubric.get("dimensions", []):
        did = dim.get("id")
        name = dim.get("name", did)
        signals[name] = {
            "weight": dim.get("weight"),
            "measurable": signals_by_id.get(did, {}),
            "needs_human_judgment": dim.get("human_judgment", []),
        }

    integrity_flags: List[str] = []
    for idx, ref in enumerate(model.references, 1):
        if _RETRACTED_RE.search(ref):
            integrity_flags.append(f"疑似撤稿引用: 参考文献[{idx}]")
    if _RETRACTED_RE.search(text):
        integrity_flags.append("正文出现撤稿线索词，请人工核查")

    hints = []
    if not lit_present:
        hints.append("未检出文献综述/研究现状章节")
    if format_report and (format_report.get("summary", {}).get("error", 0) > 0):
        hints.append(f"格式硬错误 {format_report['summary']['error']} 处待修")
    if intext_unmatched > 0:
        hints.append(f"{intext_unmatched} 处正文引用编号超出文末列表")
    if ref_count < 30:
        hints.append(f"参考文献仅 {ref_count} 条，硕士学位论文通常偏少")
    readiness_hint = "；".join(hints) if hints else "结构、参考文献与关键要素基本就绪"

    return {
        "rubric": rubric.get("name"),
        "signals": signals,
        "integrity_flags": integrity_flags,
        "grade_bands": rubric.get("grade_bands", []),
        "readiness_hint": readiness_hint,
    }
