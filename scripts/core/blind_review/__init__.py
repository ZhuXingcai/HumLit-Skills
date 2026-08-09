"""blind_review - 盲审模拟引擎（rubric 驱动，脚本算信号、Agent 评审）。"""
from __future__ import annotations

from .rubric import (
    SCHEMA_VERSION, DEFAULT_RUBRIC, build_rubric_template,
    load_rubric, validate_rubric,
)
from .signals import compute_signals
