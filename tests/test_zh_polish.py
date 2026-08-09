import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core import zh_polish as Z  # noqa: E402


def test_split_sentences_cjk():
    s = Z.split_sentences("第一句。第二句！第三句？")
    assert len(s) == 3


def test_long_sentence_detected():
    long = "在" + "这个问题非常复杂" * 12 + "。"  # >80 字
    rep = Z.diagnose(long, max_sentence=80)
    assert any(i["type"] == "long_sentence" for i in rep["issues"])


def test_colloquial_detected():
    rep = Z.diagnose("其实这个问题的话挺复杂的。")
    assert any(i["type"] == "colloquial" for i in rep["issues"])


def test_subjective_detected():
    rep = Z.diagnose("我觉得这个理论很重要。")
    assert any(i["type"] == "subjective" for i in rep["issues"])


def test_punct_mix_detected():
    rep = Z.diagnose("研究表明,这个结论成立。")  # 中文间英文逗号
    assert any(i["type"] == "punct_mix" for i in rep["issues"])


def test_clean_academic_sentence_no_false_positive():
    rep = Z.diagnose("本文基于制度理论分析了组织变革的机制。")
    types = {i["type"] for i in rep["issues"]}
    assert "colloquial" not in types
    assert "subjective" not in types
    assert "punct_mix" not in types


def test_summary_counts():
    rep = Z.diagnose("其实这个问题的话很复杂。本文分析了相关机制。")
    assert rep["summary"]["sentences"] == 2
    assert rep["summary"]["issues"] >= 1
    assert "by_type" in rep["summary"]
