"""知网检索条件模型的离线单元测试。不触网、不依赖 Selenium。"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core.cnki.query import (  # noqa: E402
    ERR_INVALID_EXPRESSION,
    ERR_TOO_MANY_CONDITIONS,
    CnkiCondition,
    CnkiQueryError,
    build_legacy_conditions,
    join_terms,
    normalize_value,
    parse_condition,
    quote_term,
    validate_conditions,
    validate_professional_expression,
    validate_value_syntax,
)


def _cond(**kwargs):
    base = {"field": "主题", "value": "人工智能"}
    base.update(kwargs)
    return CnkiCondition(**base)


# ── 条件解析 ─────────────────────────────────────────


def test_parse_condition_two_parts_defaults():
    cond = parse_condition("篇名|乡村振兴")
    assert cond.field == "篇名"
    assert cond.value == "乡村振兴"
    assert cond.logic == "并且"
    assert cond.match is None


def test_parse_condition_three_parts_logic_alias():
    cond = parse_condition("关键词|OR|数据挖掘")
    assert cond.logic == "或者"


def test_parse_condition_four_parts_with_match():
    cond = parse_condition("作者|并且|精确|邱均平")
    assert cond.field == "作者"
    assert cond.match == "精确"
    assert cond.value == "邱均平"


def test_parse_condition_field_alias():
    assert parse_condition("来源|中国社会科学").field == "文献来源"
    assert parse_condition("机构|清华大学").field == "作者单位"


def test_parse_condition_rejects_unknown_field():
    with pytest.raises(CnkiQueryError) as exc:
        parse_condition("不存在的字段|人工智能")
    assert exc.value.code == ERR_INVALID_EXPRESSION


def test_parse_condition_rejects_empty():
    with pytest.raises(CnkiQueryError):
        parse_condition("")


# ── 条件校验 ─────────────────────────────────────────


def test_theme_field_rejects_match_mode():
    with pytest.raises(CnkiQueryError) as exc:
        validate_conditions([_cond(match="精确")])
    assert "相关度匹配" in str(exc.value)


def test_non_theme_field_accepts_match_mode():
    conds = validate_conditions([_cond(field="篇名", match="精确")])
    assert conds[0].match == "精确"


def test_too_many_conditions():
    with pytest.raises(CnkiQueryError) as exc:
        validate_conditions([_cond() for _ in range(11)])
    assert exc.value.code == ERR_TOO_MANY_CONDITIONS


def test_ten_conditions_is_allowed():
    assert len(validate_conditions([_cond() for _ in range(10)])) == 10


def test_empty_conditions_rejected():
    with pytest.raises(CnkiQueryError):
        validate_conditions([])


def test_empty_value_rejected():
    with pytest.raises(CnkiQueryError):
        validate_conditions([_cond(value="   ")])


def test_value_over_120_chars_rejected():
    with pytest.raises(CnkiQueryError) as exc:
        validate_conditions([_cond(value="甲" * 121)])
    assert "120" in str(exc.value)


# ── 同字段组合：构造、规范化、校验 ─────────────────────


def test_join_terms_spaces_around_operator():
    assert join_terms(["生成式AI", "AIGC"], "+") == "生成式AI + AIGC"
    assert join_terms(["广告", "营销"], "*") == "广告 * 营销"


def test_join_terms_quotes_terms_with_spaces():
    assert (
        join_terms(["digital library", "information service"], "*")
        == "'digital library' * 'information service'"
    )


def test_quote_term_protects_special_characters():
    assert quote_term("2+3") == "'2+3'"
    assert quote_term("人工智能") == "人工智能"


def test_join_terms_rejects_bad_operator():
    with pytest.raises(CnkiQueryError):
        join_terms(["甲", "乙"], "AND")


def test_normalize_value_collapses_existing_spaces():
    assert normalize_value("人工智能  +   AIGC") == "人工智能 + AIGC"


def test_operator_without_spaces_is_rejected():
    with pytest.raises(CnkiQueryError) as exc:
        validate_value_syntax("人工智能+AIGC")
    assert "空一个字节" in str(exc.value)


def test_operator_with_spaces_is_accepted():
    validate_value_syntax("(生成式AI + AIGC) * 广告")


def test_hyphen_inside_latin_term_is_not_an_operator():
    validate_value_syntax("COVID-19")


def test_quoted_special_term_is_accepted():
    validate_value_syntax("'2+3' * 人才培养")


def test_cjk_minus_without_spaces_is_rejected():
    with pytest.raises(CnkiQueryError):
        validate_value_syntax("大数据-人工智能")


# ── 旧参数映射 ───────────────────────────────────────


def test_build_legacy_conditions_maps_all_three():
    conds = build_legacy_conditions(
        "教育改革", field="摘要", author="张三", journal="中国社会科学"
    )
    assert [c.field for c in conds] == ["摘要", "作者", "文献来源"]
    assert len(validate_conditions(conds)) == 3


def test_build_legacy_conditions_keyword_only():
    conds = build_legacy_conditions("深度学习")
    assert len(conds) == 1
    assert conds[0].field == "主题"


# ── 专业检索表达式 ───────────────────────────────────


@pytest.mark.parametrize(
    "expr",
    [
        "SU %= 知识管理 OR TKA = 知识管理",
        "KY = 知识管理 AND AU = 邱均平",
        "AU = 钱伟长 AND (AF = 清华大学 OR AF = 上海大学)",
        "TI = 大数据 NOT TI = 大数据集",
        "YE BETWEEN ('2010', '2018')",
        "FT = '人工智能 /NEAR 10 推荐算法'",
        "SU%=('生成式AI+AIGC') AND SU%=('广告+营销')",
    ],
)
def test_valid_professional_expressions(expr):
    assert validate_professional_expression(expr) == expr


@pytest.mark.parametrize(
    "expr",
    [
        "",
        "   ",
        "随便一段没有字段代码的文字",
        "SU %= 知识管理 AND (TI = 大数据",
        "FT = '人工智能 # 推荐算法",
        "SU %= 知识管理\nAND TI = 大数据",
    ],
)
def test_invalid_professional_expressions(expr):
    with pytest.raises(CnkiQueryError) as exc:
        validate_professional_expression(expr)
    assert exc.value.code == ERR_INVALID_EXPRESSION


def test_condition_to_dict_shape():
    cond = parse_condition("篇名|并且|模糊|人工智能")
    assert cond.to_dict() == {
        "field": "篇名",
        "value": "人工智能",
        "logic": "并且",
        "match": "模糊",
    }
