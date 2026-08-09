import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core import theory_catalog as TC  # noqa: E402


def test_builtin_theories_nonempty_and_well_formed():
    assert len(TC.THEORIES) >= 20
    for t in TC.THEORIES:
        for k in ("id", "name", "proposer", "discipline", "concepts", "keywords", "summary"):
            assert k in t, f"{t.get('id')} 缺字段 {k}"
        assert isinstance(t["keywords"], list) and t["keywords"]


def test_theory_ids_unique():
    ids = [t["id"] for t in TC.THEORIES]
    assert len(ids) == len(set(ids))


def test_disciplines_cover_builtin():
    used = {t["discipline"] for t in TC.THEORIES}
    assert used.issubset(set(TC.DISCIPLINES))


def test_list_theories_filter_by_discipline():
    socio = TC.list_theories(TC.THEORIES, discipline="社会学")
    assert socio and all(t["discipline"] == "社会学" for t in socio)


def test_list_theories_filter_by_query():
    res = TC.list_theories(TC.THEORIES, query="社会资本")
    assert any("社会资本" in t["name"] or "社会资本" in t["keywords"] for t in res)


def test_match_theories_scores_and_orders():
    res = TC.match_theories(TC.THEORIES, ["社会资本", "信任", "弱关系"], top=5)
    assert res
    # 得分非递增
    scores = [r["score"] for r in res]
    assert scores == sorted(scores, reverse=True)
    assert all(r["score"] >= 1 for r in res)
    assert all("matched" in r for r in res)


def test_match_theories_empty_keywords_returns_empty():
    assert TC.match_theories(TC.THEORIES, [], top=5) == []


def test_match_theories_no_hit():
    res = TC.match_theories(TC.THEORIES, ["完全不相关的虚构词xyz"], top=5)
    assert res == []


def test_merge_libraries_override_and_append():
    base = [{"id": "a", "name": "A", "keywords": ["x"]}]
    extra = [{"id": "a", "name": "A2", "keywords": ["y"]}, {"id": "b", "name": "B", "keywords": ["z"]}]
    merged = TC.merge_libraries(base, extra)
    by_id = {t["id"]: t for t in merged}
    assert by_id["a"]["name"] == "A2"
    assert "b" in by_id


def test_load_library_accepts_list_and_dict(tmp_path):
    import json
    f1 = tmp_path / "l1.json"
    f1.write_text(json.dumps([{"id": "x", "name": "X", "keywords": ["k"]}]), encoding="utf-8")
    assert TC.load_library(str(f1))[0]["id"] == "x"
    f2 = tmp_path / "l2.json"
    f2.write_text(json.dumps({"theories": [{"id": "y", "name": "Y", "keywords": ["k"]}]}), encoding="utf-8")
    assert TC.load_library(str(f2))[0]["id"] == "y"
