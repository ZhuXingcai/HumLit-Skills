from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class SectionGuess:
    title: str
    level: int
    kind: str  # heading | toc | references


_KNOWN_SECTION_RE = re.compile(
    r"^\s*(摘\s*要|Abstract|ABSTRACT|目\s*录|参考文献|References|致\s*谢|附\s*录)\s*$",
    re.IGNORECASE,
)
_CHAPTER_RE = re.compile(
    r"^\s*((第[一二三四五六七八九十百\d]+[章节篇])|([一二三四五六七八九十]+、)|(\d+(\.\d+)*[、.．]))\s*.+$"
)


def guess_plain_heading(text: str) -> Optional[SectionGuess]:
    s = (text or "").strip()
    if not s:
        return None
    if len(s) > 60:
        return None
    known = _KNOWN_SECTION_RE.match(s)
    if known:
        normalized = re.sub(r"\s+", "", s)
        if normalized == "目录":
            return SectionGuess(title="目录", level=1, kind="toc")
        if normalized.lower() == "references" or normalized == "参考文献":
            return SectionGuess(title=s, level=1, kind="references")
        return SectionGuess(title=s, level=1, kind="heading")
    if _CHAPTER_RE.match(s):
        return SectionGuess(title=s, level=1, kind="heading")
    return None


def markdown_heading(line: str) -> Optional[SectionGuess]:
    s = (line or "").strip()
    m = re.match(r"^(#{1,6})\s+(.+)$", s)
    if m:
        title = m.group(2).strip()
        kind = "heading"
        normalized = re.sub(r"\s+", "", title)
        if normalized == "目录":
            kind = "toc"
        elif normalized == "参考文献" or title.lower() == "references":
            kind = "references"
        return SectionGuess(title=title, level=len(m.group(1)), kind=kind)
    return guess_plain_heading(s)


def docx_heading_level(style_name: str, paragraph_text: str) -> Optional[int]:
    style = style_name or ""
    m = re.search(r"(Heading|标题)\s*([1-6])", style, re.IGNORECASE)
    if m:
        return int(m.group(2))
    if guess_plain_heading(paragraph_text):
        return 1
    return None
