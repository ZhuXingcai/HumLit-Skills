"""source_citation.py - 史料规范引用（古籍/档案/方志/碑刻/报刊/家谱/口述）。

脚本负责确定性格式化（脚注体 + GB/T 7714 史料著录），Agent 负责从原书/档案
信息填出条目字段。
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List

SOURCE_CATEGORIES: Dict[str, str] = {
    "ancient": "古籍",
    "archive": "档案",
    "gazetteer": "方志",
    "epigraph": "碑刻金石",
    "periodical": "报刊",
    "genealogy": "家谱",
    "oral": "口述",
}

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "ancient": {"source_category": "ancient", "author": "［朝代］著者", "title": "书名",
                "juan": "卷次，如 卷十二", "section": "篇/章/门类", "editor": "点校/整理者",
                "edition": "版本性质，如 点校本/影印本", "place": "出版地", "publisher": "出版社",
                "year": "出版年", "volume_ce": "第X册", "page": "页码"},
    "archive": {"source_category": "archive", "doc_title": "文件题名", "doc_date": "文件日期",
                "archive": "馆藏机构", "fonds": "全宗名", "file_no": "档号/案卷号/件号"},
    "gazetteer": {"source_category": "gazetteer", "author": "纂修者", "title": "方志名",
                  "juan": "卷次", "section": "门类", "edition": "版本，如 光绪刻本/影印本",
                  "place": "出版地", "publisher": "出版社", "year": "出版年", "page": "页码"},
    "epigraph": {"source_category": "epigraph", "title": "碑刻/墓志名", "inscription_date": "立石年代",
                 "location_found": "出土地/现藏地", "collected_in": "收录文献，如 《金石萃编》卷X",
                 "page": "页码"},
    "periodical": {"source_category": "periodical", "author": "作者（可缺）", "article_title": "文章题名",
                   "periodical": "报刊名", "pub_date": "出版日期，如 1895-04-17", "column": "版次/栏目"},
    "genealogy": {"source_category": "genealogy", "title": "家谱/族谱名", "juan": "卷次",
                  "editor": "纂修者", "edition": "版本，如 民国刻本", "year": "纂修年", "page": "页码"},
    "oral": {"source_category": "oral", "narrator": "口述者", "title": "访谈主题/题名",
             "interviewer": "访谈者", "interview_place": "访谈地点", "interview_date": "访谈日期",
             "archive": "收藏/整理单位（可缺）"},
}

_RECOMMENDED: Dict[str, List[str]] = {
    "ancient": ["author", "publisher", "year"],
    "archive": ["archive", "file_no", "doc_date"],
    "gazetteer": ["edition", "year"],
    "epigraph": ["inscription_date", "collected_in"],
    "periodical": ["periodical", "pub_date"],
    "genealogy": ["editor", "year"],
    "oral": ["narrator", "interview_date"],
}

_TITLE_FIELDS = ("title", "doc_title", "article_title")
_FIELD_CN = {
    "author": "著者", "publisher": "出版社", "year": "出版年", "archive": "馆藏机构",
    "file_no": "档号", "doc_date": "文件日期", "edition": "版本", "inscription_date": "立石年代",
    "collected_in": "收录文献", "periodical": "报刊名", "pub_date": "出版日期",
    "editor": "纂修/点校者", "narrator": "口述者", "interview_date": "访谈日期",
}


def build_source_template(category: str) -> Dict[str, Any]:
    if category not in TEMPLATES:
        raise ValueError(f"未知史料类型: {category}")
    tpl = copy.deepcopy(TEMPLATES[category])
    tpl["_README"] = (f"{SOURCE_CATEGORIES[category]}史料条目模板，由 Agent 据原书/档案信息填写；"
                      "史料常残缺，缺字段会给 warning 但不阻断。下划线字段为说明。")
    return tpl


def _entry_title(entry: Dict[str, Any]) -> str:
    for f in _TITLE_FIELDS:
        if str(entry.get(f) or "").strip():
            return str(entry[f]).strip()
    return ""


def validate_source_entry(entry: Any) -> Dict[str, List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    if not isinstance(entry, dict):
        return {"errors": ["条目必须是 JSON 对象"], "warnings": []}
    cat = entry.get("source_category")
    if cat not in SOURCE_CATEGORIES:
        errors.append(f"source_category 必须是 {list(SOURCE_CATEGORIES)} 之一")
        return {"errors": errors, "warnings": warnings}
    if not _entry_title(entry):
        errors.append("缺少题名（title/doc_title/article_title 至少一个）")
    for f in _RECOMMENDED.get(cat, []):
        if not str(entry.get(f) or "").strip():
            warnings.append(f"缺少{_FIELD_CN.get(f, f)}")
    return {"errors": errors, "warnings": warnings}


def _circled(n: int) -> str:
    if 1 <= n <= 20:
        return chr(0x2460 + n - 1)
    return f"({n})"


def _book_title(s: str) -> str:
    return f"《{s}》"


def format_source_footnote(entry: Dict[str, Any], index: int = 1) -> str:
    """中文脚注体（正文脚注用）。"""
    cat = entry.get("source_category")
    mark = _circled(index)
    g = lambda k: str(entry.get(k) or "").strip()  # noqa: E731

    if cat == "archive":
        parts = [_book_title(g("doc_title") or "佚名文件")]
        if g("doc_date"):
            parts.append(g("doc_date"))
        tail = []
        if g("archive"):
            tail.append(f"{g('archive')}藏")
        if g("fonds"):
            tail.append(g("fonds"))
        seg = "，".join(parts + tail)
        if g("file_no"):
            seg += f"，档号{g('file_no')}"
        return f"{mark} {seg}。"

    if cat == "periodical":
        seg = _book_title(g("article_title") or g("title") or "佚名")
        if g("author"):
            seg = f"{g('author')}：{seg}"
        if g("periodical"):
            seg += f"，{_book_title(g('periodical'))}"
        if g("pub_date"):
            seg += f"{g('pub_date')}"
        if g("column"):
            seg += f"，{g('column')}"
        return f"{mark} {seg}。"

    if cat == "epigraph":
        seg = _book_title(g("title") or "佚名碑刻")
        if g("inscription_date"):
            seg += f"，{g('inscription_date')}立"
        if g("location_found"):
            seg += f"，{g('location_found')}藏"
        if g("collected_in"):
            seg += f"，收入{_book_title(g('collected_in'))}"
        if g("page"):
            seg += f"，第{g('page')}页"
        return f"{mark} {seg}。"

    if cat == "oral":
        seg = _book_title(g("title") or "口述访谈")
        if g("narrator"):
            seg = f"{g('narrator')}口述：{seg}"
        if g("interviewer"):
            seg += f"，{g('interviewer')}访谈"
        if g("interview_place"):
            seg += f"，{g('interview_place')}"
        if g("interview_date"):
            seg += f"，{g('interview_date')}"
        return f"{mark} {seg}。"

    # ancient / gazetteer / genealogy 同构（古籍式）
    seg = ""
    if g("author"):
        seg += f"{g('author')}："
    seg += _book_title(g("title") or "佚名")
    if g("juan"):
        seg += g("juan")
    if g("section"):
        seg += _book_title(g("section"))
    if g("editor"):
        seg += f"，{g('editor')}"
    bits = []
    if g("place"):
        bits.append(g("place"))
    if g("publisher"):
        bits.append(g("publisher"))
    if bits:
        seg += "，" + "：".join(bits)
    if g("year"):
        seg += f"，{g('year')}年"
    if g("volume_ce"):
        seg += f"，{g('volume_ce')}"
    if g("page"):
        seg += f"，第{g('page')}页"
    return f"{mark} {seg}。"


_GBT_SOURCE_TAG = {
    "ancient": "M", "gazetteer": "M", "genealogy": "M",
    "archive": "A", "epigraph": "Z", "periodical": "N", "oral": "Z",
}


def format_source_gbt7714(entry: Dict[str, Any], index: int = 1) -> str:
    """GB/T 7714-2015 史料著录（文末参考文献用）。"""
    cat = entry.get("source_category")
    tag = _GBT_SOURCE_TAG.get(cat, "Z")
    g = lambda k: str(entry.get(k) or "").strip()  # noqa: E731

    if cat == "archive":
        ref = f"[{index}] {g('doc_title') or '佚名文件'}[{tag}]. "
        tail = []
        if g("archive"):
            tail.append(f"{g('archive')}藏")
        if g("fonds"):
            tail.append(g("fonds"))
        ref += "，".join(tail)
        if g("file_no"):
            ref += f"：{g('file_no')}"
        if g("doc_date"):
            ref += f"，{g('doc_date')}"
        return ref.rstrip("，. ") + "."

    if cat == "periodical":
        author = g("author") or " "
        ref = f"[{index}] {author}. {g('article_title') or g('title')}[{tag}]. {g('periodical')}"
        if g("pub_date"):
            ref += f", {g('pub_date')}"
        if g("column"):
            ref += f"({g('column')})"
        return ref.rstrip(", ") + "."

    if cat == "epigraph":
        ref = f"[{index}] {g('title') or '佚名碑刻'}[{tag}]. "
        if g("inscription_date"):
            ref += f"{g('inscription_date')}立. "
        if g("collected_in"):
            ref += g("collected_in")
        return ref.rstrip(". ") + "."

    if cat == "oral":
        ref = f"[{index}] {g('narrator') or '佚名'}. {g('title') or '口述访谈'}[{tag}]. "
        if g("interview_place"):
            ref += g("interview_place")
        if g("interview_date"):
            ref += f", {g('interview_date')}"
        return ref.rstrip(", . ") + "."

    # ancient / gazetteer / genealogy
    author = g("author")
    ref = f"[{index}] {author + '. ' if author else ''}{g('title') or '佚名'}[{tag}]. "
    if g("editor"):
        editor = g("editor")
        if re.search(r"(点校|校注|校释|整理|辑校|笺注|译注|辑)$", editor):
            ref += f"{editor}. "
        else:
            ref += f"{editor}, 点校. "
    bits = []
    if g("place"):
        bits.append(g("place"))
    if g("publisher"):
        bits.append(g("publisher"))
    if bits:
        ref += "：".join(bits) if len(bits) == 2 else bits[0]
        if g("year"):
            ref += f", {g('year')}"
    elif g("year"):
        ref += g("year")
    return ref.rstrip("：, . ") + "."


def format_source_entry(entry: Dict[str, Any], index: int = 1, style: str = "both") -> Dict[str, Any]:
    v = validate_source_entry(entry)
    out: Dict[str, Any] = {"index": index, "source_category": entry.get("source_category")}
    if v["errors"]:
        out["errors"] = v["errors"]
        return out
    if style in ("footnote", "both"):
        out["footnote"] = format_source_footnote(entry, index)
    if style in ("gbt7714", "both"):
        out["gbt7714"] = format_source_gbt7714(entry, index)
    out["warnings"] = v["warnings"]
    return out
