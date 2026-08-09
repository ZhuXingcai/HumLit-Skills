import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core.thesis_format import profile as P  # noqa: E402
from core.thesis_format import check as C  # noqa: E402
from core.thesis_format.model import DocModel, Heading  # noqa: E402


def _compliant_model():
    return DocModel(
        paper="A4",
        page_margin_cm={"top": 2.54, "bottom": 2.54, "left": 3.17, "right": 3.17},
        body_font_cjk="宋体", body_font_latin="Times New Roman",
        body_size_pt=12.0, line_spacing=1.5,
        observed_dimensions=["page", "body", "structure", "headings", "references", "toc"],
        headings=[Heading(1, "摘要"), Heading(1, "Abstract"), Heading(1, "目录"),
                  Heading(1, "第一章 引言"), Heading(1, "参考文献")],
        section_titles=["摘要", "Abstract", "目录", "第一章 引言", "参考文献"],
        references=["张三. 测试[J]. 学报, 2024.", "李四. 再测[J]. 学报, 2025."],
        intext_ref_numbers=[1, 2],
    )


def test_compliant_model_has_no_errors():
    prof = P.build_template()
    rep = C.check_format(_compliant_model(), prof)
    assert rep["summary"]["error"] == 0
    assert "page" in rep["summary"]["passed_dimensions"]
    assert "body" in rep["summary"]["passed_dimensions"]


def test_font_mismatch_is_fixable_error():
    prof = P.build_template()
    m = _compliant_model()
    m.body_font_cjk = "仿宋"
    rep = C.check_format(m, prof)
    hit = [i for i in rep["issues"] if i["code"] == "FONT_CJK_MISMATCH"]
    assert hit and hit[0]["severity"] == "error" and hit[0]["fixable"] is True


def test_missing_required_section_is_unfixable_error():
    prof = P.build_template()
    m = _compliant_model()
    m.section_titles = [t for t in m.section_titles if t != "Abstract"]
    m.headings = [h for h in m.headings if h.text != "Abstract"]
    rep = C.check_format(m, prof)
    hit = [i for i in rep["issues"] if i["code"] == "SECTION_MISSING"]
    assert hit and hit[0]["severity"] == "error" and hit[0]["fixable"] is False


def test_intext_ref_without_list_entry_warns():
    prof = P.build_template()
    m = _compliant_model()
    m.intext_ref_numbers = [1, 2, 9]  # 9 超出列表条数
    rep = C.check_format(m, prof)
    hit = [i for i in rep["issues"] if i["code"] == "INTEXT_REF_UNMATCHED"]
    assert hit and hit[0]["severity"] == "warning"


def test_heading_level_skip_warns():
    prof = P.build_template()
    m = _compliant_model()
    m.headings.append(Heading(3, "1.1.1 无父级"))  # 缺 level 2 直接跳到 3
    rep = C.check_format(m, prof)
    assert any(i["code"] == "HEADING_LEVEL_SKIP" for i in rep["issues"])
