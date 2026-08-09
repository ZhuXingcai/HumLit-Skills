import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cli.registry import COMMANDS  # noqa: E402
from core.workflows import WORKFLOW_TEMPLATES  # noqa: E402


CONTRACT = ROOT / "evals" / "capability-contract.json"
ALLOWED_MATURITY = {
    "stable_offline",
    "conditional_live",
    "conditional_desktop",
    "agent_assisted",
    "experimental",
}


def _contract():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    return data


def test_capability_contract_is_complete_and_actionable():
    data = _contract()
    capabilities = data["capabilities"]

    assert len({item["id"] for item in capabilities}) == len(capabilities)
    covered_commands = set()
    for item in capabilities:
        assert item["maturity"] in ALLOWED_MATURITY, item["id"]
        assert item["when_to_use"], item["id"]
        assert item["when_not_to_use"], item["id"]
        assert item["inputs"], item["id"]
        assert item["output_contract"], item["id"]
        assert item["failure_modes"], item["id"]
        assert item["smoke"], item["id"]
        assert set(item["commands"]).issubset(COMMANDS), item["id"]
        covered_commands.update(item["commands"])

    assert covered_commands == set(COMMANDS)


def test_experimental_and_agent_assisted_boundaries_are_explicit():
    by_id = {item["id"]: item for item in _contract()["capabilities"]}

    base = by_id["base_search"]
    assert base["maturity"] == "experimental"
    assert base["opt_in_only"] is True

    for capability_id in (
        "evidence_scaffolding",
        "blind_review",
        "academic_polishing",
        "qualitative_coding",
        "theory_framework",
    ):
        assert by_id[capability_id]["maturity"] == "agent_assisted"
        assert by_id[capability_id]["human_or_agent_completion_required"] is True


def test_removed_citation_suggestion_is_not_advertised_as_executable_workflow():
    assert "citation_suggestion" not in WORKFLOW_TEMPLATES

    env_source = (SCRIPTS / "cli" / "env_cmd.py").read_text(encoding="utf-8")
    assert '"citation_suggestion": {' not in env_source
