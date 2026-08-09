from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Heading:
    level: int
    text: str
    size_pt: Optional[float] = None
    bold: Optional[bool] = None
    font_cjk: Optional[str] = None


@dataclass
class Caption:
    kind: str          # "figure" | "table"
    text: str
    size_pt: Optional[float] = None


@dataclass
class DocModel:
    """与 python-docx 解耦的论文结构中间模型。字段为 None 表示未能探测。"""
    paper: Optional[str] = None
    page_margin_cm: Dict[str, Optional[float]] = field(default_factory=dict)
    body_font_cjk: Optional[str] = None
    body_font_latin: Optional[str] = None
    body_size_pt: Optional[float] = None
    line_spacing: Optional[float] = None
    observed_dimensions: List[str] = field(default_factory=list)
    headings: List[Heading] = field(default_factory=list)
    section_titles: List[str] = field(default_factory=list)
    toc_entries: List[str] = field(default_factory=list)
    figure_captions: List[Caption] = field(default_factory=list)
    table_captions: List[Caption] = field(default_factory=list)
    footnote_count: int = 0
    references: List[str] = field(default_factory=list)
    intext_ref_numbers: List[int] = field(default_factory=list)
