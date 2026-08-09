import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cli.registry import COMMANDS  # noqa: E402


def _cases():
    data = json.loads(
        (ROOT / "evals" / "skill-routing-cases.json").read_text(encoding="utf-8")
    )
    assert data["schema_version"] == 1
    return data["cases"]


def test_skill_eval_set_has_positive_and_negative_coverage():
    cases = _cases()
    assert len(cases) >= 15
    assert any(case["should_trigger"] for case in cases)
    assert any(not case["should_trigger"] for case in cases)
    assert len({case["id"] for case in cases}) == len(cases)


def test_positive_routing_cases_match_router_and_registry():
    router = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for case in _cases():
        if not case["should_trigger"]:
            continue
        fragment = case["fragment"]
        command = case["command"]
        assert (ROOT / fragment).is_file(), case["id"]
        assert fragment in router, case["id"]
        assert command in COMMANDS, case["id"]
        assert re.search(rf"`?{re.escape(command)}`?", router), case["id"]


def test_skill_frontmatter_exposes_all_positive_intents_and_negative_boundary():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    required_terms = [
        "文献",
        "下载论文",
        "文献综述",
        "引用",
        "Word",
        "论文格式",
        "盲审",
        "史料",
        "中文润色",
        "C刊",
        "质性编码",
        "理论框架",
    ]
    for term in required_terms:
        assert term in frontmatter
    assert "general web search" in frontmatter
    assert "code documentation" in frontmatter


def test_v115_semantic_self_review_is_complete_but_not_independent():
    expected = {case["id"]: case for case in _cases()}
    reviewed = {}
    result_path = ROOT / "evals" / "results" / "v1.0.0-semantic.jsonl"
    for line in result_path.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        reviewed[item["id"]] = item

    assert set(reviewed) == set(expected)
    trigger_correct = 0
    fragment_correct = 0
    command_correct = 0
    positives = 0
    for case_id, case in expected.items():
        result = reviewed[case_id]
        trigger_correct += result["trigger"] == case["should_trigger"]
        if not case["should_trigger"]:
            continue
        positives += 1
        fragment_correct += result["fragment"] == case["fragment"]
        command_correct += (
            result["command"] == case["command"]
            or result.get("clarify") is True
        )

    assert trigger_correct / len(expected) == 1.0
    assert fragment_correct / positives == 1.0
    assert command_correct / positives >= 0.9
    summary = json.loads(
        (ROOT / "evals" / "results" / "v1.0.0-summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["independent_evaluator"] is False
