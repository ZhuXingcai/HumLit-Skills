from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

try:
    from cli._common import CITATION_STYLE_CHOICES
except Exception:  # 包独立可测，import 失败时兜底
    CITATION_STYLE_CHOICES = ["gbt7714", "gb", "apa", "mla", "chicago", "footnote"]

SCHEMA_VERSION = "1.0"

DEFAULT_PROFILE: Dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "name": "通用学术格式（内置默认）",
    "doc_kind": "thesis",
    "page": {
        "paper": "A4",
        "margin_cm": {"top": 2.54, "bottom": 2.54, "left": 3.17, "right": 3.17},
    },
    "body": {
        "font_latin": "Times New Roman", "font_cjk": "宋体",
        "size_pt": 12, "line_spacing": 1.5,
        "first_line_indent_char": 2, "space_after_pt": 0,
    },
    "headings": [
        {"level": 1, "font_cjk": "黑体", "size_pt": 16, "bold": True, "align": "center", "numbering": "第%章"},
        {"level": 2, "font_cjk": "黑体", "size_pt": 14, "bold": True, "align": "left", "numbering": "%1.%2"},
        {"level": 3, "font_cjk": "黑体", "size_pt": 12, "bold": True, "align": "left", "numbering": "%1.%2.%3"},
    ],
    "structure": {
        "required_sections": [
            {"id": "abstract_zh", "title_patterns": ["摘要"], "order": 2, "required": True},
            {"id": "abstract_en", "title_patterns": ["Abstract", "ABSTRACT"], "order": 4, "required": True},
            {"id": "toc", "title_patterns": ["目录"], "order": 6, "required": True},
            {"id": "references", "title_patterns": ["参考文献", "References"], "order": 90, "required": True},
            {"id": "acknowledge", "title_patterns": ["致谢", "致 谢"], "order": 95, "required": False},
        ],
        "enforce_order": True,
    },
    "references": {
        "style": "gbt7714", "numbered": True,
        "require_sequential": True, "require_intext_match": True,
        "hanging_indent_char": 2,
    },
    "footnotes": {"location": "footnote", "marker_style": "number", "numbering": "per_page"},
    "figures": {"caption_prefix": "图", "caption_position": "below", "numbering": "chapter", "caption_size_pt": 10.5, "align": "center"},
    "tables": {"caption_prefix": "表", "caption_position": "above", "numbering": "chapter", "caption_size_pt": 10.5, "align": "center"},
}


def build_template() -> Dict[str, Any]:
    """返回一份可直接编辑的 profile 模板（深拷贝默认值，含使用说明）。"""
    import copy
    tpl = copy.deepcopy(DEFAULT_PROFILE)
    tpl["_README"] = ("由 Agent 按用户提供的学校/期刊格式要求填写。字号用 pt："
                      "小四=12 五号=10.5 小五=9。下划线开头字段为说明，校验时忽略。"
                      "字段含义见 static/fragments/task/format.md。")
    return tpl


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_profile(path: str) -> Dict[str, Any]:
    """读 profile JSON 并用默认值补齐缺省字段（宽进严出）。"""
    import copy
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("profile 顶层必须是 JSON 对象")
    return _deep_merge(copy.deepcopy(DEFAULT_PROFILE), raw)


def validate_profile(p: Any) -> List[Dict[str, str]]:
    """校验 profile，返回错误列表（空列表即合法）。下划线字段忽略。"""
    errors: List[Dict[str, str]] = []
    if not isinstance(p, dict):
        return [{"field": "<root>", "message": "profile 顶层必须是 JSON 对象"}]
    if not p.get("schema_version"):
        errors.append({"field": "schema_version", "message": "缺少 schema_version"})

    refs = p.get("references")
    if isinstance(refs, dict) and "style" in refs and refs["style"] not in CITATION_STYLE_CHOICES:
        errors.append({"field": "references.style",
                       "message": f"style 必须是 {CITATION_STYLE_CHOICES} 之一"})

    fn = p.get("footnotes")
    if isinstance(fn, dict) and fn.get("location") not in (None, "footnote", "endnote"):
        errors.append({"field": "footnotes.location", "message": "location 必须是 footnote 或 endnote"})

    for key in ("figures", "tables"):
        d = p.get(key)
        if isinstance(d, dict) and d.get("numbering") not in (None, "chapter", "continuous"):
            errors.append({"field": f"{key}.numbering", "message": "numbering 必须是 chapter 或 continuous"})

    headings = p.get("headings")
    if isinstance(headings, list):
        levels = [h.get("level") for h in headings if isinstance(h, dict)]
        if len(levels) != len(set(levels)):
            errors.append({"field": "headings", "message": "heading level 不得重复"})

    return errors
