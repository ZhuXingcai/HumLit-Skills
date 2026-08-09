from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List

SCHEMA_VERSION = "1.0"

DEFAULT_RUBRIC: Dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "name": "教育部学术学位硕士（内置默认）",
    "degree_level": "master",
    "grade_bands": [
        {"grade": "A", "label": "通过，可答辩", "min": 90},
        {"grade": "B", "label": "小修后答辩", "min": 75},
        {"grade": "C", "label": "较大修改后答辩", "min": 70},
        {"grade": "D", "label": "不通过", "min": 0},
    ],
    "dimensions": [
        {"id": "topic_review", "name": "选题与综述", "weight": 20,
         "measurable_signals": ["reference_count", "refs_last5y_ratio", "review_section_chars", "lit_review_present"],
         "human_judgment": ["选题前沿性与价值", "综述评述深度（非罗列）"]},
        {"id": "innovation", "name": "创新性及论文价值", "weight": 30,
         "measurable_signals": ["innovation_statement_found"],
         "human_judgment": ["创新层次是否达学位要求", "学术/应用价值真实性"]},
        {"id": "theory_capability", "name": "基础理论与科研能力", "weight": 30,
         "measurable_signals": ["method_keywords", "theory_framework_found", "chapter_count", "body_chars"],
         "human_judgment": ["论证严密性", "理论运用深度", "数据/材料可靠性"]},
        {"id": "norms_writing", "name": "学术规范与写作水平", "weight": 20,
         "measurable_signals": ["format_check", "intext_ref_unmatched"],
         "human_judgment": ["语言流畅度", "学术表达规范度"]},
    ],
    "integrity_veto": True,
}


def build_rubric_template() -> Dict[str, Any]:
    tpl = copy.deepcopy(DEFAULT_RUBRIC)
    tpl["_README"] = ("由 Agent 按用户提供的学校/期刊评审标准填写。dimensions.weight 之和必须=100。"
                      "measurable_signals 为脚本可算项，human_judgment 为需评审人判断项。"
                      "下划线开头字段为说明，校验时忽略。")
    return tpl


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_rubric(path: str) -> Dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("rubric 顶层必须是 JSON 对象")
    return _deep_merge(copy.deepcopy(DEFAULT_RUBRIC), raw)


def validate_rubric(r: Any) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
    if not isinstance(r, dict):
        return [{"field": "<root>", "message": "rubric 顶层必须是 JSON 对象"}]
    if not r.get("schema_version"):
        errors.append({"field": "schema_version", "message": "缺少 schema_version"})

    dims = r.get("dimensions")
    if not isinstance(dims, list) or not dims:
        errors.append({"field": "dimensions", "message": "dimensions 必须是非空数组"})
    else:
        total = 0
        for i, d in enumerate(dims):
            if not isinstance(d, dict) or "id" not in d or "name" not in d or "weight" not in d:
                errors.append({"field": f"dimensions[{i}]", "message": "每个维度需含 id/name/weight"})
                continue
            try:
                total += float(d["weight"])
            except (TypeError, ValueError):
                errors.append({"field": f"dimensions[{i}].weight", "message": "weight 必须是数值"})
        if abs(total - 100) > 0.01:
            errors.append({"field": "dimensions.weight", "message": f"维度权重之和必须为 100，当前 {total}"})

    bands = r.get("grade_bands")
    if isinstance(bands, list) and bands:
        grades = [b.get("grade") for b in bands if isinstance(b, dict)]
        if len(grades) != len(set(grades)):
            errors.append({"field": "grade_bands", "message": "grade 不得重复"})

    return errors
