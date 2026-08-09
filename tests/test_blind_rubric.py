import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core.blind_review import rubric as R  # noqa: E402


def test_template_is_valid():
    tpl = R.build_rubric_template()
    assert tpl["schema_version"] == R.SCHEMA_VERSION
    assert R.validate_rubric(tpl) == []


def test_default_weights_sum_to_100():
    total = sum(d["weight"] for d in R.DEFAULT_RUBRIC["dimensions"])
    assert total == 100


def test_validate_rejects_missing_schema_version():
    errs = R.validate_rubric({"dimensions": []})
    assert any(e["field"] == "schema_version" for e in errs)


def test_validate_rejects_bad_weight_sum():
    bad = R.build_rubric_template()
    bad["dimensions"][0]["weight"] = 5
    errs = R.validate_rubric(bad)
    assert any(e["field"] == "dimensions.weight" for e in errs)


def test_validate_rejects_duplicate_grades():
    bad = R.build_rubric_template()
    bad["grade_bands"] = [{"grade": "A", "min": 90}, {"grade": "A", "min": 80}]
    errs = R.validate_rubric(bad)
    assert any(e["field"] == "grade_bands" for e in errs)


def test_load_rubric_merges_defaults(tmp_path):
    import json
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"schema_version": "1.0", "name": "某校5维"}), encoding="utf-8")
    r = R.load_rubric(str(p))
    assert r["name"] == "某校5维"
    assert len(r["dimensions"]) == 4  # 默认补齐
