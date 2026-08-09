import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core import journal_fit as JF  # noqa: E402


def test_detect_fund_leak_with_grant_number():
    text = "本文系国家社会科学基金重大项目（17ZDA158）阶段性成果。"
    leaks = JF.detect_anonymity_leaks(text)
    assert any(l["type"] == "fund_leak" for l in leaks)


def test_detect_fund_leak_en_number():
    text = "This work was supported by NSFC (No. 12BZS034)."
    leaks = JF.detect_anonymity_leaks(text)
    assert any(l["type"] == "fund_leak" for l in leaks)


def test_detect_ack_named():
    text = "致谢\n\n感谢导师王某某教授的悉心指导。"
    leaks = JF.detect_anonymity_leaks(text)
    assert any(l["type"] == "ack_named" for l in leaks)


def test_detect_author_info():
    text = "作者简介：张三（1990—），男，山东人，博士研究生。"
    leaks = JF.detect_anonymity_leaks(text)
    assert any(l["type"] == "author_info" for l in leaks)


def test_detect_self_institution():
    text = "笔者所在的某某大学历史学院近年开展了相关调查。"
    leaks = JF.detect_anonymity_leaks(text)
    assert any(l["type"] == "self_institution" for l in leaks)


def test_clean_anonymous_text_no_leak():
    text = "本研究采用质性方法，对若干案例进行了分析与比较。结论具有一定推广价值。"
    leaks = JF.detect_anonymity_leaks(text)
    assert leaks == []


class _Model:
    references = ["ref"] * 20


def test_check_journal_fit_all_ok():
    text = (
        "摘要：本文研究中文期刊投稿适配问题，提出了一套自查方法，"
        "并通过案例验证其有效性，对研究生投稿具有参考价值实践意义重大十分突出。\n\n"
        "Abstract: This paper studies journal submission fit.\n\n"
        "关键词：投稿；适配；自查；期刊\n\n"
        + "正文内容。" * 2000
    )
    rep = JF.check_journal_fit(text, _Model(), JF.DEFAULT_PROFILE)
    assert rep["summary"]["keywords"] == 4
    assert rep["metrics"]["keywords"]["ok"] is True
    assert rep["metrics"]["references"]["ok"] is True
    assert rep["anonymity"]["required"] is True


def test_check_journal_fit_flags_short_body_and_few_keywords():
    text = "摘要：太短。\n\n关键词：仅一个\n\n正文很短。"
    rep = JF.check_journal_fit(text, _Model(), JF.DEFAULT_PROFILE)
    assert rep["metrics"]["length"]["ok"] is False
    assert rep["metrics"]["keywords"]["ok"] is False
    assert any(i["type"] == "length_below_min" for i in rep["issues"])


def test_check_journal_fit_missing_en_abstract_when_required():
    text = "摘要：这是一段足够长的中文摘要内容用于测试。\n\n关键词：甲；乙；丙\n\n正文。"
    prof = {**JF.DEFAULT_PROFILE, "abstract": {"min_chars": 5, "max_chars": 500, "require_en": True}}
    rep = JF.check_journal_fit(text, _Model(), prof)
    assert any(i["type"] == "abstract_missing_en" for i in rep["issues"])


def test_check_journal_fit_leak_is_error_when_anonymous():
    text = "本文系教育部项目（19YJA770010）成果。\n\n关键词：甲；乙；丙\n\n正文。"
    rep = JF.check_journal_fit(text, _Model(), JF.DEFAULT_PROFILE)
    leaks = rep["anonymity"]["leaks"]
    assert leaks and all(l["severity"] == "error" for l in leaks)


def test_check_journal_fit_leak_is_warning_when_not_anonymous():
    text = "本文系教育部项目（19YJA770010）成果。\n\n关键词：甲；乙；丙\n\n正文。"
    prof = {**JF.DEFAULT_PROFILE, "anonymous": False}
    rep = JF.check_journal_fit(text, _Model(), prof)
    leaks = rep["anonymity"]["leaks"]
    assert leaks and all(l["severity"] == "warning" for l in leaks)
