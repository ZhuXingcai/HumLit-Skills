import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core import source_citation as SC  # noqa: E402


def test_seven_categories():
    assert set(SC.SOURCE_CATEGORIES) == {
        "ancient", "archive", "gazetteer", "epigraph", "periodical", "genealogy", "oral"
    }


def test_template_has_category_and_readme():
    tpl = SC.build_source_template("ancient")
    assert tpl["source_category"] == "ancient"
    assert "_README" in tpl


def test_validate_rejects_bad_category():
    res = SC.validate_source_entry({"source_category": "xxx", "title": "x"})
    assert any("source_category" in e for e in res["errors"])


def test_validate_requires_title():
    res = SC.validate_source_entry({"source_category": "ancient"})
    assert res["errors"]


def test_validate_warns_missing_fields():
    res = SC.validate_source_entry({"source_category": "ancient", "title": "明儒学案"})
    assert res["errors"] == []
    assert res["warnings"]  # 缺出版社/年份等


def test_archive_uses_doc_title_as_title():
    res = SC.validate_source_entry({"source_category": "archive", "doc_title": "为奏报某事"})
    assert res["errors"] == []
