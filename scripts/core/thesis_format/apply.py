from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def _set_eastasia(style, name: str) -> None:
    from docx.oxml.ns import qn
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), name)


def apply_to_docx(path: str, profile: Dict[str, Any], output: str) -> Dict[str, Any]:
    """在既有 .docx 上原地重排样式（保留正文内容），另存为 output。"""
    try:
        from docx import Document
        from docx.shared import Pt, Cm
    except ImportError:
        return {"status": "error", "code": "MISSING_DEPENDENCY", "message": "缺少 python-docx 依赖"}

    src = Path(path)
    if not src.exists():
        return {"status": "error", "code": "FILE_NOT_FOUND", "message": f"文件不存在: {path}"}

    try:
        doc = Document(str(src))
    except Exception as e:
        return {"status": "error", "code": "DOCX_PARSE_FAILED", "message": f"docx 解析失败: {e}"}

    applied = []

    page = profile.get("page", {})
    margin = page.get("margin_cm", {})
    if margin:
        sec = doc.sections[0]
        if "top" in margin: sec.top_margin = Cm(margin["top"])
        if "bottom" in margin: sec.bottom_margin = Cm(margin["bottom"])
        if "left" in margin: sec.left_margin = Cm(margin["left"])
        if "right" in margin: sec.right_margin = Cm(margin["right"])
        applied.append({"dimension": "page", "action": "设置页边距"})

    body = profile.get("body", {})
    if body:
        style = doc.styles["Normal"]
        if body.get("font_latin"):
            style.font.name = body["font_latin"]
        if body.get("font_cjk"):
            _set_eastasia(style, body["font_cjk"])
        if body.get("size_pt"):
            style.font.size = Pt(body["size_pt"])
        pf = style.paragraph_format
        if body.get("line_spacing"):
            pf.line_spacing = body["line_spacing"]
        if "space_after_pt" in body:
            pf.space_after = Pt(body["space_after_pt"])
        if body.get("first_line_indent_char"):
            pf.first_line_indent = Cm(0.37 * body["first_line_indent_char"])
        applied.append({"dimension": "body", "action": "设置正文字体/字号/行距/缩进"})

    headings = {h.get("level"): h for h in profile.get("headings", []) if isinstance(h, dict)}
    if headings:
        for lvl, hcfg in headings.items():
            try:
                hs = doc.styles[f"Heading {lvl}"]
            except (KeyError, TypeError):
                continue
            if hcfg.get("font_cjk"):
                _set_eastasia(hs, hcfg["font_cjk"])
            if hcfg.get("size_pt"):
                hs.font.size = Pt(hcfg["size_pt"])
            if "bold" in hcfg:
                hs.font.bold = hcfg["bold"]
        applied.append({"dimension": "headings", "action": "设置各级标题样式"})

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc.save(str(out_path))
    except Exception as e:
        return {"status": "error", "code": "IO_ERROR", "message": f"保存失败: {e}"}

    return {"status": "success", "output": str(out_path), "applied": applied,
            "skipped": [{"dimension": "structure", "reason": "缺章节/正文不臆造，需人工补"},
                        {"dimension": "references", "reason": "正文-列表对应需人工核对"}],
            "warnings": []}


def apply_from_markdown(md_text: str, profile: Dict[str, Any], output: str) -> Dict[str, Any]:
    """按 profile 从 Markdown 生成合规 .docx（复用 _common 的参数化写入器）。"""
    from cli._common import _write_docx_from_markdown
    res = _write_docx_from_markdown(md_text, Path(output), profile=profile)
    if res.get("status") in ("success", "warning"):
        res.setdefault("applied", [{"dimension": "all", "action": "按 profile 生成"}])
        res.setdefault("skipped", [])
    return res
