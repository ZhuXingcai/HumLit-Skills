"""thesis_format - 学位论文/期刊格式规范引擎（profile 驱动，纯逻辑）。"""
from __future__ import annotations

from .profile import (
    SCHEMA_VERSION, DEFAULT_PROFILE, build_template,
    load_profile, validate_profile,
)
from .model import DocModel, Heading, Caption
from .inspect import inspect_docx, inspect_markdown
from .check import check_format
from .apply import apply_to_docx, apply_from_markdown
