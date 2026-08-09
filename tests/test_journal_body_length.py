import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core import journal_fit as JF  # noqa: E402
from core.thesis_format.inspect import inspect_markdown  # noqa: E402


def _body_only_profile(max_chars=20):
    return {
        **JF.DEFAULT_PROFILE,
        "length": {"min_chars": 1, "max_chars": max_chars, "scope": "body_only"},
        "abstract": {"min_chars": 1, "max_chars": 100, "require_en": False},
        "keywords": {"min": 1, "max": 5},
        "references": {"min": 0},
    }


def test_journal_length_excludes_abstract_keywords_ack_and_references():
    long_reference = "参考文献标题" * 100
    text = f"""摘要：这是摘要内容，不应计入正文字数。

关键词：甲；乙；丙

# 一、引言
正文甲乙丙。

# 致谢
感谢某某教授。

# 参考文献
[1] {long_reference}
"""
    profile = {
        **JF.DEFAULT_PROFILE,
        "length": {"min_chars": 1, "max_chars": 20, "scope": "body_only"},
        "abstract": {"min_chars": 1, "max_chars": 100, "require_en": False},
        "keywords": {"min": 1, "max": 5},
        "references": {"min": 1},
    }
    report = JF.check_journal_fit(text, inspect_markdown(text), profile)
    assert report["summary"]["body_chars"] < 20
    assert report["summary"]["total_chars"] > report["summary"]["body_chars"]
    assert report["metrics"]["length"]["ok"] is True


def test_journal_length_can_use_total_scope():
    text = "摘要：摘要。\n\n关键词：甲；乙；丙\n\n# 一、引言\n正文。\n\n# 参考文献\n[1] " + ("长文献" * 100)
    profile = {
        **JF.DEFAULT_PROFILE,
        "length": {"min_chars": 1, "max_chars": 20, "scope": "total"},
        "abstract": {"min_chars": 1, "max_chars": 100, "require_en": False},
        "keywords": {"min": 1, "max": 5},
        "references": {"min": 1},
    }
    report = JF.check_journal_fit(text, inspect_markdown(text), profile)
    assert report["summary"]["total_chars"] == report["summary"]["body_chars"]
    assert report["metrics"]["length"]["ok"] is False


def test_journal_length_excludes_lettered_appendix_after_body():
    long_appendix = "访谈提纲附录内容" * 100
    text = f"""摘要：这是摘要内容，不应计入正文字数。

关键词：甲；乙；丙

# 一、引言
正文甲乙丙。

# 附录A 访谈提纲
{long_appendix}
"""
    report = JF.check_journal_fit(text, inspect_markdown(text), _body_only_profile())
    assert report["summary"]["body_chars"] == JF.count_chars("# 一、引言\n正文甲乙丙。")
    assert report["metrics"]["length"]["ok"] is True


def test_journal_length_starts_at_unnumbered_intro_after_multi_paragraph_abstract():
    text = """摘要：这是摘要第一段，不应计入正文字数。

这是摘要第二段，也不应计入正文字数。

关键词：甲；乙；丙

# 引言
正文甲乙丙。
"""
    report = JF.check_journal_fit(text, inspect_markdown(text), _body_only_profile())
    assert report["summary"]["body_chars"] == JF.count_chars("# 引言\n正文甲乙丙。")
    assert report["metrics"]["length"]["ok"] is True


def test_journal_length_starts_at_unnumbered_research_method_heading():
    text = """摘要：这是摘要第一段，不应计入正文字数。

这是摘要第二段，也不应计入正文字数。

关键词：甲；乙；丙

# 研究方法
正文甲乙丙。
"""
    report = JF.check_journal_fit(text, inspect_markdown(text), _body_only_profile())
    assert report["summary"]["body_chars"] == JF.count_chars("# 研究方法\n正文甲乙丙。")
    assert report["metrics"]["length"]["ok"] is True


@pytest.mark.parametrize(
    ("stop_heading", "tail"),
    [
        ("参考文献：", "[1] 参考文献内容一。\n[2] 参考文献内容二。"),
        ("# 参考文献：", "[1] 参考文献内容一。\n[2] 参考文献内容二。"),
        ("References:", "[1] Reference one.\n[2] Reference two."),
        ("致谢：", "感谢甲老师。\n感谢乙老师。"),
    ],
)
def test_journal_length_stops_at_colon_suffixed_reference_and_ack_headings(stop_heading, tail):
    text = f"""摘要：这是摘要内容，不应计入正文字数。

关键词：甲；乙；丙

# 一、引言
正文甲乙丙。

{stop_heading}
{tail}
"""
    report = JF.check_journal_fit(text, inspect_markdown(text), _body_only_profile())
    assert report["summary"]["body_chars"] == JF.count_chars("# 一、引言\n正文甲乙丙。")
    assert report["metrics"]["length"]["ok"] is True


@pytest.mark.parametrize(
    "stop_heading",
    [
        "参 考 文 献",
        "参考文献（按姓氏排序）",
        "# 参考文献（按姓氏排序）",
        "五、参考文献",
        "5. 参考文献",
        "三、致谢",
        "Appendix A",
        "Appendix A: Supplementary materials",
        "Appendix A Supplementary materials",
        "Appendix 1 Supplementary materials",
    ],
)
def test_journal_length_stops_at_real_world_non_body_heading_variants(stop_heading):
    text = f"""摘要：这是摘要内容，不应计入正文字数。

关键词：甲；乙；丙

# 一、引言
正文甲乙丙。

{stop_heading}
[1] 参考文献内容一。
[2] 参考文献内容二。
"""
    report = JF.check_journal_fit(text, inspect_markdown(text), _body_only_profile())
    assert report["summary"]["body_chars"] == JF.count_chars("# 一、引言\n正文甲乙丙。")
    assert report["metrics"]["length"]["ok"] is True


@pytest.mark.parametrize(
    "body_heading",
    [
        "五、参考文献综述",
        "三、致谢行为研究",
        "Appendix theory",
        "References review",
        "Acknowledgements behavior",
    ],
)
def test_journal_length_does_not_stop_at_body_headings_that_contain_non_body_words(body_heading):
    text = f"""摘要：这是摘要内容，不应计入正文字数。

关键词：甲；乙；丙

{body_heading}
正文甲乙丙。
"""
    report = JF.check_journal_fit(text, inspect_markdown(text), _body_only_profile())
    assert report["summary"]["body_chars"] == JF.count_chars(f"{body_heading}\n正文甲乙丙。")


def test_journal_length_fallback_excludes_title_author_abstract_and_keywords_front_matter():
    text = """数字史学研究的方法更新
张三
某某大学历史学院

摘要：这是摘要第一段，不应计入正文字数。

这是摘要第二段，也不应计入正文字数。

关键词：数字史学；史料；方法

正文第一段甲乙丙。

正文第二段丁戊己。
"""
    report = JF.check_journal_fit(text, inspect_markdown(text), _body_only_profile())
    expected = "正文第一段甲乙丙。\n\n正文第二段丁戊己。"
    assert report["summary"]["body_chars"] == JF.count_chars(expected)
    assert report["metrics"]["length"]["ok"] is True


def test_journal_length_starts_at_parenthesized_chinese_intro_heading():
    text = """标题行不应计入正文
作者行不应计入正文

摘要：摘要内容不应计入正文字数。

关键词：甲；乙；丙

（一）引言
正文甲乙丙。
"""
    report = JF.check_journal_fit(text, inspect_markdown(text), _body_only_profile())
    assert report["summary"]["body_chars"] == JF.count_chars("（一）引言\n正文甲乙丙。")
    assert report["metrics"]["length"]["ok"] is True
