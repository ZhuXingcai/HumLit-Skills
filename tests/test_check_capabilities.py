import argparse
import io
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cli import env_cmd  # noqa: E402


def run_check(monkeypatch, tmp_path, *, driver_ok=False, cnki_ok=True):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODEX_SANDBOX_NETWORK_DISABLED", "1")
    monkeypatch.setattr(env_cmd, "_check_browser", lambda _subprocess: (True, "Edge"))
    monkeypatch.setattr(
        env_cmd,
        "_check_driver",
        lambda: (
            driver_ok,
            "Selenium Manager 已就绪；首次知网操作将按需获取匹配的 chromedriver"
            if driver_ok
            else "driver missing",
        ),
    )
    monkeypatch.setattr(env_cmd, "_check_cnki", lambda: (cnki_ok, "accessible" if cnki_ok else "blocked"))
    monkeypatch.setattr(env_cmd, "_check_update", lambda: None)

    out = io.StringIO()
    with redirect_stdout(out):
        env_cmd.cmd_check(argparse.Namespace(fix=False))
    return json.loads(out.getvalue())


def test_codex_sandbox_driver_failure_requests_escalation(monkeypatch, tmp_path):
    data = run_check(monkeypatch, tmp_path, driver_ok=False)

    caps = data["capabilities"]
    assert caps["cnki_feasible"] is False
    assert caps["needs_escalation"] is True
    assert caps["reason_code"] == "browser_or_driver_requires_host_permission"
    assert caps["agent_action"] == "rerun_same_command_with_escalated_permissions"
    assert "retry_command" in caps


def test_check_distinguishes_connector_readiness_from_runtime_verification(monkeypatch, tmp_path):
    data = run_check(monkeypatch, tmp_path, driver_ok=True)
    sources = data["capabilities"]["sources"]

    assert sources["openalex"]["maturity"] == "conditional_live"
    assert sources["openalex"]["connector_available"] is True
    assert sources["openalex"]["runtime_verified"] is None
    assert sources["openalex"]["availability_scope"] == "local_connector_only"

    assert sources["cnki"]["maturity"] == "conditional_desktop"
    assert sources["cnki"]["runtime_verified"] is None
    assert sources["cnki"]["availability_scope"] == "local_prerequisites_only"
    assert sources["cnki"]["driver_mode"] == "selenium_manager_on_demand"

    assert sources["base"]["maturity"] == "experimental"
    assert sources["base"]["available"] is False
    assert sources["base"]["opt_in_only"] is True
    assert sources["base"]["runtime_verified"] is None


def test_check_reports_pdf_dependency_and_uses_stable_api_workflow(monkeypatch, tmp_path):
    data = run_check(monkeypatch, tmp_path, driver_ok=True)
    caps = data["capabilities"]

    assert caps["pdf_tools"] is True
    assert caps["workflows"]["topic_research"]["steps"][0] == (
        "search '{topic}' --source api --async-search --limit 30 --project {project}"
    )
    assert "citation_suggestion" not in caps["workflows"]


def test_project_local_selenium_cache_is_preferred_in_codex(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODEX_SANDBOX_NETWORK_DISABLED", "1")
    monkeypatch.delenv("SE_CACHE_PATH", raising=False)

    from core.cnki import driver

    driver._ensure_selenium_cache()

    expected = tmp_path / ".humlit" / "selenium-cache"
    assert os.environ["SE_CACHE_PATH"] == str(expected)
    assert expected.is_dir()


def test_local_development_version_newer_than_remote_is_not_update(monkeypatch):
    monkeypatch.setattr(env_cmd, "__version__", "1.14.0")
    monkeypatch.setattr(
        env_cmd,
        "_fetch_json",
        lambda url, timeout=5: {"tag_name": "v1.13.0"},
    )

    update = env_cmd._check_update()

    assert update == {
        "update_available": False,
        "current": "1.14.0",
        "latest": "1.13.0",
    }
