import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core.formatter import format_gbt7714, generate_reference_list  # noqa: E402


def test_gbt7714_routes_ancient_source():
    e = {"source_category": "ancient", "author": "［清］黄宗羲", "title": "明儒学案",
         "publisher": "中华书局", "place": "北京", "year": "1985"}
    ref = format_gbt7714(e, 1)
    assert "[M]" in ref and "中华书局" in ref


def test_gbt7714_archive_uses_a_tag():
    e = {"source_category": "archive", "doc_title": "为奏报某事",
         "archive": "中国第一历史档案馆", "file_no": "03-1234-056"}
    ref = format_gbt7714(e, 1)
    assert "[A]" in ref and "03-1234-056" in ref


def test_normal_paper_unchanged():
    p = {"authors": "张三", "title": "人工智能研究", "journal": "情报学报",
         "year": 2024, "doc_type": "journal"}
    ref = format_gbt7714(p, 1)
    assert "[J]" in ref and "情报学报" in ref


def test_reference_list_mixed():
    papers = [
        {"authors": "张三", "title": "AI研究", "journal": "情报学报", "year": 2024, "doc_type": "journal"},
        {"source_category": "ancient", "author": "黄宗羲", "title": "明儒学案", "publisher": "中华书局", "year": "1985"},
    ]
    out = generate_reference_list(papers, "gbt7714")
    assert "[J]" in out and "[M]" in out
