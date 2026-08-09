import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core.blind_review import rubric as R  # noqa: E402
from core.blind_review import signals as S  # noqa: E402
from core.thesis_format.model import DocModel, Heading  # noqa: E402


def _model():
    return DocModel(
        headings=[Heading(1, "摘要"), Heading(1, "第一章 绪论"),
                  Heading(1, "第二章 研究现状综述"), Heading(1, "第三章 研究设计"),
                  Heading(1, "结论"), Heading(1, "参考文献")],
        section_titles=["摘要", "第一章 绪论", "第二章 研究现状综述", "第三章 研究设计", "结论", "参考文献"],
        references=["张三. 测试[J]. 学报, 2024.", "李四. 再测[J]. 学报, 2018.",
                    "王五. 三测[J]. 学报, 2025."],
        intext_ref_numbers=[1, 2, 3],
    )


def test_compute_signals_has_four_dimensions():
    rep = S.compute_signals(_model(), R.DEFAULT_RUBRIC,
                            full_text="本文创新点在于提出新框架。采用问卷与内容分析方法。基于场域理论分析。")
    assert set(rep["signals"].keys()) == {"选题与综述", "创新性及论文价值", "基础理论与科研能力", "学术规范与写作水平"}
    assert rep["signals"]["选题与综述"]["weight"] == 20


def test_reference_signals():
    rep = S.compute_signals(_model(), R.DEFAULT_RUBRIC, full_text="")
    m = rep["signals"]["选题与综述"]["measurable"]
    assert m["reference_count"] == 3
    assert m["lit_review_present"] is True
    # 2024/2025 在近5年(以2026基准)，2018 不在 → 2/3
    assert 0.6 <= m["refs_last5y_ratio"] <= 0.7


def test_innovation_and_method_signals():
    rep = S.compute_signals(_model(), R.DEFAULT_RUBRIC,
                            full_text="本文创新点：提出新模型。采用问卷调查与内容分析。基于布迪厄场域理论。")
    inv = rep["signals"]["创新性及论文价值"]["measurable"]
    assert inv["innovation_statement_found"] is True
    cap = rep["signals"]["基础理论与科研能力"]["measurable"]
    assert "问卷" in cap["method_keywords"]
    assert cap["theory_framework_found"] is True


def test_format_check_embedded_when_provided():
    fmt = {"summary": {"error": 2, "warning": 5}}
    rep = S.compute_signals(_model(), R.DEFAULT_RUBRIC, full_text="", format_report=fmt)
    nw = rep["signals"]["学术规范与写作水平"]["measurable"]
    assert nw["format_check"] == {"error": 2, "warning": 5}


def test_integrity_flag_on_retracted():
    m = _model()
    m.references.append("某. 撤稿研究[J]. 学报, 2020.")
    rep = S.compute_signals(m, R.DEFAULT_RUBRIC, full_text="见文献[4]（retracted）。")
    assert rep["integrity_flags"]
