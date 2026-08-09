import hashlib
import importlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import verify_release  # noqa: E402


def test_release_identity_contract_is_humlit():
    assert verify_release.verify_identity() == "humlit-skills"


def test_independent_routing_gate_rejects_self_review_artifact():
    with pytest.raises(AssertionError, match="independent"):
        verify_release.verify_routing_evaluation(
            "1.0.0",
            require_independent=True,
        )


def test_routing_evaluator_bundle_has_traceable_input_hashes(tmp_path):
    evaluator = importlib.import_module("evaluate_routing")
    bundle_path = tmp_path / "routing-evaluation-request.json"

    result = evaluator.build_evaluation_request(
        skill_path=ROOT / "SKILL.md",
        cases_path=ROOT / "evals" / "skill-routing-cases.json",
        rubric_path=ROOT / "evals" / "README.md",
        output_path=bundle_path,
    )

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert result["status"] == "success"
    assert bundle["schema_version"] == 1
    assert bundle["evaluation_type"] == "independent_semantic_routing"
    assert bundle["inputs"]["skill_sha256"] == hashlib.sha256(
        (ROOT / "SKILL.md").read_bytes()
    ).hexdigest()
    assert bundle["inputs"]["cases_sha256"] == hashlib.sha256(
        (ROOT / "evals" / "skill-routing-cases.json").read_bytes()
    ).hexdigest()
    assert bundle["inputs"]["rubric_sha256"] == hashlib.sha256(
        (ROOT / "evals" / "README.md").read_bytes()
    ).hexdigest()
    assert bundle["payload"]["skill_markdown"].startswith("---")
    assert json.loads(bundle["payload"]["cases_json"])["cases"]
    assert "Independent LLM Semantic Review" in bundle["payload"]["rubric_markdown"]
    assert bundle["instructions"]["independent_evaluator_required"] is True
    assert "results" not in bundle


def test_ci_matrix_covers_supported_operating_systems_and_core_checks():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    for runner in ("ubuntu-latest", "macos-latest", "windows-latest"):
        assert runner in workflow
    assert "runs-on: ${{ matrix.os }}" in workflow
    assert "python -m pip install --no-deps ." in workflow
    assert "run: humlit --version" in workflow
    assert "python -m pytest -q" in workflow
    assert "python scripts/verify_release.py --version 1.0.0" in workflow
    assert "python scripts/smoke_test.py --mode offline" in workflow
