import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core import source_citation as SC  # noqa: E402


def test_ancient_footnote():
    e = {"source_category": "ancient", "author": "［清］黄宗羲", "title": "明儒学案",
         "juan": "卷十二", "section": "崇仁学案", "editor": "沈芝盈点校",
         "place": "北京", "publisher": "中华书局", "year": "1985", "page": "256"}
    fn = SC.format_source_footnote(e, 1)
    assert fn.startswith("①")
    assert "《明儒学案》" in fn
    assert "卷十二" in fn
    assert "中华书局" in fn
    assert "第256页" in fn
    assert fn.rstrip().endswith("。")


def test_ancient_gbt7714():
    e = {"source_category": "ancient", "author": "［清］黄宗羲", "title": "明儒学案",
         "editor": "沈芝盈", "place": "北京", "publisher": "中华书局", "year": "1985"}
    ref = SC.format_source_gbt7714(e, 1)
    assert ref.startswith("[1]")
    assert "[M]" in ref
    assert "中华书局" in ref


def test_archive_footnote_uses_doc_title_and_archive():
    e = {"source_category": "archive", "doc_title": "为奏报某事", "doc_date": "光绪二十年三月",
         "archive": "中国第一历史档案馆", "fonds": "军机处录副奏折", "file_no": "03-1234-056"}
    fn = SC.format_source_footnote(e, 1)
    assert "《为奏报某事》" in fn
    assert "中国第一历史档案馆" in fn
    assert "03-1234-056" in fn


def test_periodical_footnote():
    e = {"source_category": "periodical", "article_title": "时评", "periodical": "申报",
         "pub_date": "1895-04-17", "column": "第2版"}
    fn = SC.format_source_footnote(e, 3)
    assert fn.startswith("③")
    assert "《时评》" in fn
    assert "《申报》" in fn


def test_epigraph_gbt7714_uses_z_tag():
    e = {"source_category": "epigraph", "title": "某某碑", "inscription_date": "万历三十年",
         "collected_in": "金石萃编卷十"}
    ref = SC.format_source_gbt7714(e, 2)
    assert "[Z]" in ref


def test_format_source_entry_both_includes_warnings():
    e = {"source_category": "ancient", "title": "明儒学案"}  # 缺很多字段
    out = SC.format_source_entry(e, 1, style="both")
    assert "footnote" in out and "gbt7714" in out
    assert out["warnings"]


def test_ancient_gbt7714_no_duplicate_role_word():
    e = {"source_category": "ancient", "title": "明儒学案", "author": "黄宗羲",
         "editor": "沈芝盈点校", "publisher": "中华书局", "place": "北京", "year": "1985"}
    ref = SC.format_source_gbt7714(e, 1)
    assert "点校, 点校" not in ref
    assert "沈芝盈点校" in ref


def test_format_source_entry_single_style():
    e = {"source_category": "ancient", "title": "明儒学案", "publisher": "中华书局", "year": "1985", "author": "黄宗羲"}
    out = SC.format_source_entry(e, 1, style="footnote")
    assert "footnote" in out and "gbt7714" not in out
