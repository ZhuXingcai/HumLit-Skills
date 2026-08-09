import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core import journal_fit as JF  # noqa: E402


def test_default_profile_has_required_blocks():
    p = JF.DEFAULT_PROFILE
    assert p["schema_version"]
    assert "length" in p and "abstract" in p and "keywords" in p
    assert "references" in p and "anonymous" in p


def test_build_template_has_readme():
    tpl = JF.build_template()
    assert "_README" in tpl
    assert tpl["schema_version"]


def test_load_profile_deep_merges_defaults(tmp_path):
    f = tmp_path / "p.json"
    f.write_text('{"name": "某C刊", "length": {"max_chars": 12000}}', encoding="utf-8")
    p = JF.load_profile(str(f))
    assert p["name"] == "某C刊"
    assert p["length"]["max_chars"] == 12000
    # 未覆盖字段取默认
    assert "min_chars" in p["length"]
    assert "min" in p["keywords"]


def test_validate_rejects_non_dict():
    errs = JF.validate_profile([1, 2])
    assert errs


def test_validate_requires_schema_version():
    errs = JF.validate_profile({"name": "x"})
    assert any("schema_version" in e["field"] for e in errs)


def test_validate_rejects_bad_length_range():
    p = dict(JF.DEFAULT_PROFILE)
    p = {**p, "length": {"min_chars": 9000, "max_chars": 1000}}
    errs = JF.validate_profile(p)
    assert any("length" in e["field"] for e in errs)


def test_validate_accepts_default():
    assert JF.validate_profile(JF.DEFAULT_PROFILE) == []


def test_count_chars_counts_cjk_and_alnum_only():
    # 7 CJK（研究方法与+设计）+ 4 字母 + 3 数字 = 14；空格/中文标点不计
    n = JF.count_chars("研究方法与，  abcd 123。设计")
    assert n == 7 + 4 + 3
