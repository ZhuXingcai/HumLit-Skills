import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
ENTRY = SCRIPTS / "literature.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core import theory_catalog as TC  # noqa: E402


def _fields(errors):
    return {e["field"] for e in errors}


def _valid_theory(**overrides):
    theory = {
        "id": "custom",
        "name": "自定义理论",
        "discipline": "社会学",
        "keywords": ["平台"],
        "summary": "说明",
    }
    theory.update(overrides)
    return theory


def test_validate_library_requires_core_fields():
    errors = TC.validate_library([{"id": "bad", "keywords": ["平台"]}])
    fields = _fields(errors)
    assert "theories[0].name" in fields
    assert "theories[0].discipline" in fields
    assert "theories[0].summary" in fields


def test_validate_library_requires_list_root():
    errors = TC.validate_library({"theories": []})
    assert errors == [{"field": "<root>", "message": "理论库必须是列表"}]


def test_validate_library_requires_object_entries():
    errors = TC.validate_library(["not an object"])
    assert errors == [{"field": "theories[0]", "message": "每条理论必须是对象"}]


def test_validate_library_rejects_empty_keywords_duplicate_ids_and_invalid_discipline():
    errors = TC.validate_library([
        {"id": "dup", "name": "A", "discipline": "社会学", "keywords": [], "summary": "s"},
        {"id": "dup", "name": "B", "discipline": "不存在", "keywords": ["平台"], "summary": "s"},
    ])
    fields = _fields(errors)
    assert "theories[0].keywords" in fields
    assert "theories[1].id" in fields
    assert "theories[1].discipline" in fields


def test_validate_library_rejects_non_string_scalar_required_fields():
    errors = TC.validate_library([
        _valid_theory(id=123, name=True, discipline=456, summary=7.89)
    ])
    fields = _fields(errors)
    assert "theories[0].id" in fields
    assert "theories[0].name" in fields
    assert "theories[0].discipline" in fields
    assert "theories[0].summary" in fields


def test_validate_library_rejects_non_string_and_blank_keywords():
    errors = TC.validate_library([
        _valid_theory(keywords=["平台", 123, "", "  ", {"bad": "value"}])
    ])
    assert "theories[0].keywords" in _fields(errors)


def test_validate_library_accepts_minimal_valid_entry():
    errors = TC.validate_library([
        {"id": "custom", "name": "自定义理论", "discipline": "社会学", "keywords": ["平台"], "summary": "说明"}
    ])
    assert errors == []


def test_theory_catalog_rejects_bad_custom_library(tmp_path):
    lib = tmp_path / "bad.json"
    lib.write_text(json.dumps([{"id": "bad", "keywords": ["平台"]}], ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(ENTRY), "theory-catalog", "--library", str(lib)],
        capture_output=True,
        text=True, encoding="utf-8",
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["status"] == "error"
    assert out["code"] == "LIBRARY_INVALID"
    assert any(e["field"] == "theories[0].name" for e in out["errors"])


@pytest.mark.parametrize(
    ("library", "expected_field"),
    [
        ({}, "<root>"),
        ({"theories": {}}, "theories"),
        ({"theories": "bad"}, "theories"),
    ],
)
def test_theory_catalog_rejects_malformed_custom_library_wrapper(tmp_path, library, expected_field):
    lib = tmp_path / "bad-wrapper.json"
    lib.write_text(json.dumps(library, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(ENTRY), "theory-catalog", "--library", str(lib)],
        capture_output=True,
        text=True, encoding="utf-8",
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["status"] == "error"
    assert out["code"] == "LIBRARY_INVALID"
    assert any(e["field"] == expected_field for e in out["errors"])


@pytest.mark.parametrize("bad_id", [["bad"], {"bad": "id"}])
def test_theory_catalog_rejects_non_string_id_without_traceback(tmp_path, bad_id):
    lib = tmp_path / "bad-id.json"
    lib.write_text(
        json.dumps([
            _valid_theory(id=bad_id)
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(ENTRY), "theory-catalog", "--library", str(lib)],
        capture_output=True,
        text=True, encoding="utf-8",
    )
    assert r.returncode == 0
    assert "Traceback" not in r.stderr
    out = json.loads(r.stdout)
    assert out["status"] == "error"
    assert out["code"] == "LIBRARY_INVALID"
    assert any(e["field"] == "theories[0].id" for e in out["errors"])
