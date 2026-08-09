import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core import qual_coding as QC  # noqa: E402


def test_template_has_codes_and_readme():
    tpl = QC.build_codebook_template()
    assert "_README" in tpl
    assert isinstance(tpl["codes"], list) and tpl["codes"]
    assert "code" in tpl["codes"][0]


def test_validate_rejects_non_dict():
    assert QC.validate_codebook([1, 2])


def test_validate_requires_codes_list():
    assert QC.validate_codebook({"name": "x"})


def test_validate_requires_keywords_or_patterns():
    errs = QC.validate_codebook({"codes": [{"code": "信任"}]})
    assert errs


def test_validate_accepts_good_codebook():
    cb = {"codes": [{"code": "信任", "keywords": ["信任", "相信"]}]}
    assert QC.validate_codebook(cb) == []


def test_validate_flags_bad_pattern():
    cb = {"codes": [{"code": "x", "patterns": ["("]}]}
    errs = QC.validate_codebook(cb)
    assert any("patterns" in e["field"] for e in errs)


def test_split_paragraphs():
    paras = QC.split_paragraphs("第一段。\n\n第二段。\n\n\n第三段。")
    assert len(paras) == 3


def test_code_text_counts_hits_and_paragraphs():
    cb = {"name": "cb", "codes": [
        {"code": "信任", "keywords": ["信任", "相信"]},
        {"code": "就医", "keywords": ["就医", "看病"]},
    ]}
    text = (
        "我比较信任社区医生，所以有病先去看病。\n\n"
        "不太相信网上的信息。\n\n"
        "天气不错。"
    )
    rep = QC.code_text(text, cb)
    codes = {c["code"]: c for c in rep["codes"]}
    # 信任：para1 命中"信任" + para2 命中"相信" = 2 次，跨 2 段
    assert codes["信任"]["hits"] == 2
    assert codes["信任"]["paragraphs"] == 2
    # 就医：para1 命中"看病" = 1 次（"就医"未出现）
    assert codes["就医"]["hits"] == 1
    assert rep["summary"]["paragraphs"] == 3


def test_code_text_cooccurrence_same_paragraph():
    cb = {"codes": [
        {"code": "信任", "keywords": ["信任"]},
        {"code": "就医", "keywords": ["就医"]},
    ]}
    text = "我信任医生所以及时就医。\n\n今天天气好。"
    rep = QC.code_text(text, cb)
    co = {(c["a"], c["b"]): c["count"] for c in rep["cooccurrence"]}
    assert co.get(("信任", "就医")) == 1 or co.get(("就医", "信任")) == 1


def test_code_text_uncoded_paragraphs():
    cb = {"codes": [{"code": "信任", "keywords": ["信任"]}]}
    text = "我信任医生。\n\n无关内容。\n\n还是无关。"
    rep = QC.code_text(text, cb)
    assert rep["summary"]["coded_paragraphs"] == 1
    assert rep["summary"]["uncoded_paragraphs"] == 2


def test_code_text_pattern_match():
    cb = {"codes": [{"code": "数字", "patterns": [r"\d+元"]}]}
    text = "挂号花了50元。\n\n没花钱。"
    rep = QC.code_text(text, cb)
    codes = {c["code"]: c for c in rep["codes"]}
    assert codes["数字"]["hits"] == 1


def test_code_text_empty_hits_ok():
    cb = {"codes": [{"code": "信任", "keywords": ["信任"]}]}
    rep = QC.code_text("完全无关的内容。", cb)
    assert rep["summary"]["total_hits"] == 0
