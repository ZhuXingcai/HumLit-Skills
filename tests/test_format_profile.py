import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core.thesis_format import profile as P  # noqa: E402


def test_template_is_valid():
    tpl = P.build_template()
    assert tpl["schema_version"] == P.SCHEMA_VERSION
    assert P.validate_profile(tpl) == []


def test_validate_rejects_missing_schema_version():
    errs = P.validate_profile({"name": "x"})
    assert any(e["field"] == "schema_version" for e in errs)


def test_validate_rejects_bad_reference_style():
    bad = P.build_template()
    bad["references"]["style"] = "not-a-style"
    errs = P.validate_profile(bad)
    assert any(e["field"] == "references.style" for e in errs)


def test_validate_rejects_duplicate_heading_levels():
    bad = P.build_template()
    bad["headings"] = [{"level": 1}, {"level": 1}]
    errs = P.validate_profile(bad)
    assert any(e["field"] == "headings" for e in errs)


def test_load_profile_merges_defaults(tmp_path):
    import json
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"schema_version": "1.0", "name": "极简",
                             "body": {"font_cjk": "仿宋"}}), encoding="utf-8")
    prof = P.load_profile(str(p))
    assert prof["body"]["font_cjk"] == "仿宋"       # 用户值保留
    assert prof["body"]["font_latin"] == "Times New Roman"  # 默认补齐
    assert prof["page"]["paper"] == "A4"
