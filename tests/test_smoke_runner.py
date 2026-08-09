import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts" / "smoke_test.py"


def test_offline_smoke_runner_closes_representative_user_loops():
    result = subprocess.run(
        [sys.executable, str(SMOKE), "--mode", "offline"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert payload["mode"] == "offline"
    assert payload["failed"] == 0
    assert {
        "research_library",
        "document_io",
        "format_and_review",
        "humanities_tools",
        "workflow_routing",
    }.issubset({item["id"] for item in payload["checks"]})
