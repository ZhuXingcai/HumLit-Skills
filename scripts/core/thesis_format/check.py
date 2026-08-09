from __future__ import annotations

from typing import Any, Dict, List, Optional

from .model import DocModel


def _issue(dimension: str, severity: str, code: str, message: str,
           expected: Any = None, actual: Any = None,
           locator: Optional[str] = None, fixable: bool = False) -> Dict[str, Any]:
    return {"dimension": dimension, "severity": severity, "code": code,
            "expected": expected, "actual": actual, "locator": locator,
            "fixable": fixable, "message": message}


def _check_page(model: DocModel, profile: Dict[str, Any], issues: List[Dict]) -> Optional[bool]:
    ok = True
    missing_required = False
    page = profile.get("page", {})
    for side, exp in (page.get("margin_cm") or {}).items():
        act = model.page_margin_cm.get(side)
        if exp is None:
            continue
        if act is None:
            missing_required = True
            continue
        if abs(act - exp) > 0.05:
            issues.append(_issue("page", "error", "MARGIN_MISMATCH",
                                 f"{side} 页边距应为 {exp}cm，实际 {act}cm",
                                 exp, act, f"页边距.{side}", True))
            ok = False
    expected_paper = page.get("paper")
    if expected_paper is not None:
        if model.paper is None:
            missing_required = True
        elif model.paper != expected_paper:
            issues.append(_issue("page", "warning", "PAPER_MISMATCH",
                                 f"纸张应为 {expected_paper}，实际 {model.paper}",
                                 expected_paper, model.paper, "纸张", True))
            ok = False
    if missing_required:
        return None
    return ok


def _check_body(model: DocModel, profile: Dict[str, Any], issues: List[Dict]) -> Optional[bool]:
    ok = True
    missing_required = False
    body = profile.get("body", {})
    if body.get("font_cjk") is not None:
        if model.body_font_cjk is None:
            missing_required = True
        elif model.body_font_cjk != body["font_cjk"]:
            issues.append(_issue("body", "error", "FONT_CJK_MISMATCH",
                                 f"正文中文字体应为 {body['font_cjk']}，实际 {model.body_font_cjk}",
                                 body["font_cjk"], model.body_font_cjk, "正文默认样式", True))
            ok = False
    if body.get("font_latin") is not None:
        if model.body_font_latin is None:
            missing_required = True
        elif model.body_font_latin != body["font_latin"]:
            issues.append(_issue("body", "error", "FONT_LATIN_MISMATCH",
                                 f"正文西文字体应为 {body['font_latin']}，实际 {model.body_font_latin}",
                                 body["font_latin"], model.body_font_latin, "正文默认样式", True))
            ok = False
    if body.get("size_pt") is not None:
        if model.body_size_pt is None:
            missing_required = True
        elif abs(model.body_size_pt - body["size_pt"]) > 0.1:
            issues.append(_issue("body", "error", "FONT_SIZE_MISMATCH",
                                 f"正文字号应为 {body['size_pt']}pt，实际 {model.body_size_pt}pt",
                                 body["size_pt"], model.body_size_pt, "正文默认样式", True))
            ok = False
    if body.get("line_spacing") is not None:
        if model.line_spacing is None:
            missing_required = True
        elif abs(model.line_spacing - body["line_spacing"]) > 0.01:
            issues.append(_issue("body", "error", "LINE_SPACING_MISMATCH",
                                 f"行距应为 {body['line_spacing']}，实际 {model.line_spacing}",
                                 body["line_spacing"], model.line_spacing, "正文默认样式", True))
            ok = False
    if missing_required:
        return None
    return ok


def _check_structure(model: DocModel, profile: Dict[str, Any], issues: List[Dict]) -> bool:
    ok = True
    struct = profile.get("structure", {})
    titles = model.section_titles
    found = []  # (order, index_in_titles)
    for sec in struct.get("required_sections", []):
        pats = sec.get("title_patterns", [])
        hit_idx = next((i for i, t in enumerate(titles)
                        if any(pp in t for pp in pats)), None)
        if hit_idx is None:
            if sec.get("required", True):
                label = pats[0] if pats else sec.get("id", "?")
                issues.append(_issue("structure", "error", "SECTION_MISSING",
                                     f"缺少必需章节：{label}", label, None, None, False))
                ok = False
        else:
            found.append((sec.get("order", 0), hit_idx))
    if struct.get("enforce_order") and len(found) >= 2:
        by_order = [idx for _o, idx in sorted(found, key=lambda x: x[0])]
        if by_order != sorted(by_order):
            issues.append(_issue("structure", "warning", "SECTION_ORDER",
                                 "章节出现顺序与规范要求不一致", None, None, None, False))
            ok = False
    return ok


def _check_headings(model: DocModel, profile: Dict[str, Any], issues: List[Dict]) -> bool:
    ok = True
    prev = 0
    for h in model.headings:
        if h.level > prev + 1 and prev != 0:
            issues.append(_issue("headings", "warning", "HEADING_LEVEL_SKIP",
                                 f"标题层级从 {prev} 跳到 {h.level}：\"{h.text[:20]}\"",
                                 prev + 1, h.level, h.text[:30], False))
            ok = False
        prev = h.level
    return ok


def _check_references(model: DocModel, profile: Dict[str, Any], issues: List[Dict]) -> bool:
    ok = True
    refs = profile.get("references", {})
    listed = len(model.references)
    intext = sorted(set(model.intext_ref_numbers))
    if refs.get("require_intext_match"):
        for n in intext:
            if n > listed:
                issues.append(_issue("references", "warning", "INTEXT_REF_UNMATCHED",
                                     f"正文引用[{n}]在文末列表（共 {listed} 条）中不存在",
                                     None, None, f"正文[{n}]", False))
                ok = False
    if refs.get("require_sequential") and intext:
        expected = list(range(1, len(intext) + 1))
        if intext != expected:
            issues.append(_issue("references", "warning", "REF_NOT_SEQUENTIAL",
                                 f"正文引用编号不连续：{intext}", expected, intext, "正文引用", False))
            ok = False
    return ok


def _check_toc(model: DocModel, profile: Dict[str, Any], issues: List[Dict]) -> bool:
    ok = True
    if not model.toc_entries:
        return ok  # 无目录条目（可能是域代码生成），结构维度已覆盖缺失判断
    body_titles = [h.text for h in model.headings
                   if h.text not in ("目录", "参考文献", "References")]
    toc_blob = "\n".join(model.toc_entries)
    for title in body_titles:
        core_title = title.strip()
        if core_title and core_title not in toc_blob:
            issues.append(_issue("toc", "warning", "TOC_MISMATCH",
                                 f"正文标题\"{core_title[:20]}\"未出现在目录中",
                                 core_title, None, "目录", False))
            ok = False
    return ok


def check_format(model: DocModel, profile: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    passed: List[str] = []
    unknown: List[str] = []
    observed = set(getattr(model, "observed_dimensions", []) or [])
    for dim, fn in (("page", _check_page), ("body", _check_body),
                    ("structure", _check_structure), ("headings", _check_headings),
                    ("references", _check_references), ("toc", _check_toc)):
        if dim not in observed:
            unknown.append(dim)
            continue
        result = fn(model, profile, issues)
        if result is None:
            unknown.append(dim)
        elif result:
            passed.append(dim)
    summary = {
        "total": len(issues),
        "error": sum(1 for i in issues if i["severity"] == "error"),
        "warning": sum(1 for i in issues if i["severity"] == "warning"),
        "passed_dimensions": passed,
        "unknown_dimensions": unknown,
    }
    return {"summary": summary, "issues": issues}
