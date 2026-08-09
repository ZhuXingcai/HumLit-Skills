from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .model import DocModel, Heading, Caption
from .sections import markdown_heading, docx_heading_level, guess_plain_heading

_FIG_RE = re.compile(r"^\s*(图|Figure|Fig\.?)\s*[\dA-Za-z]+([\-.][\dA-Za-z]+)*")
_TAB_RE = re.compile(r"^\s*(表|Table)\s*[\dA-Za-z]+([\-.][\dA-Za-z]+)*")
_REF_HEAD_RE = re.compile(r"^\s*(参考文献|References)\s*$", re.IGNORECASE)
_TOC_HEAD_RE = re.compile(r"^\s*目\s*录\s*$")
_INTEXT_RE = re.compile(r"\[\^?(\d+)\]")


def _strip_ref_index(s: str) -> str:
    return re.sub(r"^\[\d+\]\s*", "", s).strip()


def _repeats_toc_entry(text: str, toc_entries: list[str]) -> bool:
    return text.strip() in toc_entries


def inspect_markdown(text: str) -> DocModel:
    m = DocModel()
    m.observed_dimensions = ["structure", "headings", "references", "toc", "figures", "tables"]
    state = "body"  # body | ref | toc
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            continue
        if state == "toc" and not s.startswith("#"):
            if m.toc_entries and _repeats_toc_entry(s, m.toc_entries) and guess_plain_heading(s):
                state = "body"
            else:
                m.toc_entries.append(s)
                continue
        hg = markdown_heading(s)
        if hg:
            title = hg.title
            m.headings.append(Heading(level=hg.level, text=title))
            m.section_titles.append(title)
            if hg.kind == "references":
                state = "ref"
            elif hg.kind == "toc":
                state = "toc"
            else:
                state = "body"
            continue
        if state == "ref":
            m.references.append(_strip_ref_index(s))
            continue
        if _FIG_RE.match(s):
            m.figure_captions.append(Caption("figure", s))
        if _TAB_RE.match(s):
            m.table_captions.append(Caption("table", s))
        for num in _INTEXT_RE.findall(s):
            m.intext_ref_numbers.append(int(num))
    return m


def _eastasia_font(style) -> Optional[str]:
    try:
        from docx.oxml.ns import qn
        rpr = style.element.rPr
        if rpr is None:
            return None
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            return None
        return rfonts.get(qn("w:eastAsia"))
    except Exception:
        return None


def _paper_name(width_cm: float, height_cm: float) -> str:
    short, long = sorted((width_cm, height_cm))
    if abs(short - 21.0) < 0.3 and abs(long - 29.7) < 0.3:
        return "A4"
    if abs(short - 21.59) < 0.3 and abs(long - 27.94) < 0.3:
        return "Letter"
    return f"non-A4 ({width_cm:.2f}x{height_cm:.2f}cm)"


def inspect_docx(path: str) -> DocModel:
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(str(path))
    m = DocModel()
    m.observed_dimensions = ["structure", "headings", "references", "toc", "figures", "tables"]

    sec = doc.sections[0]

    def _cm(v):
        return round(v.cm, 2) if v is not None else None

    m.page_margin_cm = {
        "top": _cm(sec.top_margin), "bottom": _cm(sec.bottom_margin),
        "left": _cm(sec.left_margin), "right": _cm(sec.right_margin),
    }
    if sec.page_width and sec.page_height:
        m.paper = _paper_name(sec.page_width.cm, sec.page_height.cm)
    if any(v is not None for v in m.page_margin_cm.values()) or m.paper is not None:
        m.observed_dimensions.append("page")

    normal = doc.styles["Normal"]
    m.body_font_latin = normal.font.name
    m.body_font_cjk = _eastasia_font(normal)
    if normal.font.size:
        m.body_size_pt = round(normal.font.size.pt, 1)
    m.line_spacing = normal.paragraph_format.line_spacing
    if any(v is not None for v in (m.body_font_latin, m.body_font_cjk, m.body_size_pt, m.line_spacing)):
        m.observed_dimensions.append("body")

    state = "body"
    toc_after_blank = False
    for p in doc.paragraphs:
        txt = p.text.strip()
        style = p.style.name if p.style else ""
        if not txt:
            if state == "toc":
                toc_after_blank = True
            continue
        if state == "toc":
            if (
                _repeats_toc_entry(txt, m.toc_entries)
                or (
                    toc_after_blank
                    and m.toc_entries
                    and txt == m.toc_entries[0]
                    and guess_plain_heading(txt)
                )
            ):
                state = "body"
                toc_after_blank = False
            else:
                m.toc_entries.append(txt)
                toc_after_blank = False
                continue
        lvl = docx_heading_level(style, txt)
        if lvl is not None:
            guessed = guess_plain_heading(txt)
            if guessed and guessed.kind == "references":
                state = "ref"; m.section_titles.append(txt); continue
            if guessed and guessed.kind == "toc":
                state = "toc"; toc_after_blank = False; m.section_titles.append(txt); continue
            state = "body"
            h = Heading(level=lvl, text=txt)
            if p.runs:
                r0 = p.runs[0]
                h.size_pt = round(r0.font.size.pt, 1) if r0.font.size else None
                h.bold = r0.font.bold
            m.headings.append(h)
            m.section_titles.append(txt)
            continue
        if state == "ref":
            m.references.append(_strip_ref_index(txt)); continue
        if _FIG_RE.match(txt):
            m.figure_captions.append(Caption("figure", txt))
        if _TAB_RE.match(txt):
            m.table_captions.append(Caption("table", txt))
        for num in _INTEXT_RE.findall(txt):
            m.intext_ref_numbers.append(int(num))

    try:
        refs = doc.element.body.findall(".//" + qn("w:footnoteReference"))
        m.footnote_count = len(refs)
    except Exception:
        m.footnote_count = 0

    return m
