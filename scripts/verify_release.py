#!/usr/bin/env python3
"""Fail-fast release checks for HumLit Skills."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cli._common import __version__  # noqa: E402
from cli.registry import COMMANDS  # noqa: E402


def _version_from(pattern: str, path: Path) -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise AssertionError(f"version not found in {path}")
    return match.group(1)


def verify_versions(expected: str) -> None:
    versions = {
        "runtime": __version__,
        "SKILL.md": _version_from(r"^\s+version:\s*([0-9.]+)\s*$", ROOT / "SKILL.md"),
        "manifest.yaml": _version_from(r"^version:\s*([0-9.]+)\s*$", ROOT / "manifest.yaml"),
        "pyproject.toml": _version_from(r'^version\s*=\s*"([0-9.]+)"\s*$', ROOT / "pyproject.toml"),
        "literature.py": _version_from(r"\(v([0-9.]+)\)", SCRIPTS / "literature.py"),
    }
    mismatches = {name: value for name, value in versions.items() if value != expected}
    if mismatches:
        raise AssertionError(f"version mismatch: expected {expected}, got {mismatches}")


def verify_identity() -> str:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    manifest = (ROOT / "manifest.yaml").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    setup = (ROOT / "setup.md").read_text(encoding="utf-8")
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    required = {
        "SKILL.md": "name: humlit-skills",
        "manifest.yaml": "name: humlit-skills",
        "pyproject.toml": 'name = "humlit-skills"',
        "console command": 'humlit = "literature:main"',
        "setup repository": "ZhuXingcai/HumLit-Skills",
        "MIT license": "MIT License",
        "HumLit copyright": "HumLit Skills Contributors",
    }
    observed = {
        "SKILL.md": skill,
        "manifest.yaml": manifest,
        "pyproject.toml": pyproject,
        "console command": pyproject,
        "setup repository": setup,
        "MIT license": license_text,
        "HumLit copyright": license_text,
    }
    missing = [
        label for label, marker in required.items()
        if marker not in observed[label]
    ]
    if missing:
        raise AssertionError(f"HumLit identity contract missing: {missing}")
    if (ROOT / "docs" / "superpowers").exists():
        raise AssertionError("internal superpowers plans must not be published")
    if (ROOT / "NOTICE").exists():
        raise AssertionError("standalone project must not publish a lineage notice")
    verify_standalone_identity()
    return "humlit-skills"


def verify_standalone_identity() -> None:
    old_brand = "Scholar" + " Kit"
    old_slug = "scholar" + "-kit"
    old_owner = "lott" + "shin"
    removed_score = "quality" + "_score"
    env_prefix = "SCHOLAR"
    removed_env = {
        f"{env_prefix}_{suffix}"
        for suffix in (
            "REQUEST_INTERVAL",
            "CACHE_TTL_DAYS",
            "MAILTO",
            "SAVE_DIR",
            "BROWSER",
            "BATCH_WINDOW_SIZE",
            "CNKI_DIRECT_DOMAINS",
            "DRIVER_PATH",
            "DEBUG_PORT",
            "KIT_NO_STEALTH",
            "SKIP_NETWORK_CHECK",
        )
    }
    forbidden = {old_brand.casefold(), old_slug, old_owner, removed_score}
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
    ).decode("utf-8").split("\0")
    violations = []
    for relative in filter(None, tracked):
        if relative == "LICENSE":
            continue
        path = ROOT / relative
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        folded = text.casefold()
        markers = sorted(
            marker for marker in forbidden
            if marker in folded
        )
        markers.extend(
            name for name in removed_env
            if name in text
        )
        if markers:
            violations.append({"path": relative, "markers": markers})
    if violations:
        raise AssertionError(
            f"standalone identity contains removed compatibility markers: {violations}"
        )


def verify_router() -> None:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    manifest = (ROOT / "manifest.yaml").read_text(encoding="utf-8")
    cases = json.loads(
        (ROOT / "evals" / "skill-routing-cases.json").read_text(encoding="utf-8")
    )["cases"]
    for case in cases:
        if not case["should_trigger"]:
            continue
        fragment = case["fragment"]
        command = case["command"]
        if not (ROOT / fragment).is_file():
            raise AssertionError(f"missing fragment: {fragment}")
        if fragment not in skill or fragment not in manifest:
            raise AssertionError(f"fragment not routed consistently: {fragment}")
        if command not in COMMANDS:
            raise AssertionError(f"unregistered command: {command}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_routing_evaluation(
    expected: str,
    *,
    require_independent: bool = False,
) -> str:
    results_dir = ROOT / "evals" / "results"
    independent_path = (
        results_dir / f"v{expected}-independent-summary.json"
    )
    summary_path = (
        independent_path
        if independent_path.exists()
        else results_dir / f"v{expected}-summary.json"
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not summary.get("independent_evaluator"):
        if require_independent:
            raise AssertionError(
                "independent routing evaluation is required; "
                "the available artifact is self-review only"
            )
        return "self_review_only"

    evaluator = summary.get("evaluator") or {}
    required_evaluator = {"provider", "model", "run_id"}
    if not all(evaluator.get(field) for field in required_evaluator):
        raise AssertionError("independent evaluator provenance is incomplete")
    if not summary.get("evaluated_at"):
        raise AssertionError("independent evaluator timestamp is missing")
    if not summary.get("request_sha256") or not summary.get("results_sha256"):
        raise AssertionError("independent evaluator artifact hashes are missing")

    inputs = summary.get("inputs") or {}
    current_hashes = {
        "skill_sha256": _sha256(ROOT / "SKILL.md"),
        "cases_sha256": _sha256(
            ROOT / "evals" / "skill-routing-cases.json"
        ),
        "rubric_sha256": _sha256(ROOT / "evals" / "README.md"),
    }
    mismatches = {
        key: {"expected": value, "artifact": inputs.get(key)}
        for key, value in current_hashes.items()
        if inputs.get(key) != value
    }
    if mismatches:
        raise AssertionError(
            f"independent routing evaluation inputs are stale: {mismatches}"
        )
    return "independent_verified"


def verify_capability_contract() -> int:
    data = json.loads(
        (ROOT / "evals" / "capability-contract.json").read_text(encoding="utf-8")
    )
    if data.get("schema_version") != 1:
        raise AssertionError("unsupported capability contract schema")
    required = {
        "id", "maturity", "commands", "when_to_use", "when_not_to_use",
        "inputs", "output_contract", "failure_modes", "smoke",
    }
    covered = set()
    capabilities = data.get("capabilities", [])
    for capability in capabilities:
        missing = required - set(capability)
        if missing:
            raise AssertionError(
                f"capability {capability.get('id')} missing fields: {sorted(missing)}"
            )
        unknown = set(capability["commands"]) - set(COMMANDS)
        if unknown:
            raise AssertionError(
                f"capability {capability['id']} has unknown commands: {sorted(unknown)}"
            )
        covered.update(capability["commands"])
    if covered != set(COMMANDS):
        raise AssertionError(
            f"capability contract command mismatch: "
            f"missing={sorted(set(COMMANDS) - covered)}"
        )
    return len(capabilities)


def verify_dependency_contract() -> None:
    files = [
        ROOT / "pyproject.toml",
        SCRIPTS / "requirements.txt",
        SCRIPTS / "requirements.lock",
    ]
    for path in files:
        if "pypdf" not in path.read_text(encoding="utf-8").lower():
            raise AssertionError(f"pdf-meta dependency missing from {path}")


def verify_smoke_evidence(expected: str) -> None:
    path = ROOT / "evals" / "results" / f"v{expected}-e2e-smoke.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != expected:
        raise AssertionError(f"smoke evidence version mismatch: {data.get('version')}")
    if data.get("offline", {}).get("status") != "success":
        raise AssertionError("offline smoke evidence is not successful")
    if data.get("test_suite", {}).get("failed") != 0:
        raise AssertionError("smoke evidence records failing tests")


def verify_command_help() -> None:
    for command, module_name in COMMANDS.items():
        module = importlib.import_module(module_name)
        if not hasattr(module, "add_parser"):
            raise AssertionError(f"{module_name} has no add_parser")
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "literature.py"), command, "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise AssertionError(f"{command} --help failed: {result.stderr}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--require-independent-routing-eval",
        action="store_true",
    )
    args = parser.parse_args()
    verify_versions(args.version)
    project_name = verify_identity()
    verify_router()
    routing_evaluation = verify_routing_evaluation(
        args.version,
        require_independent=args.require_independent_routing_eval,
    )
    capability_count = verify_capability_contract()
    verify_dependency_contract()
    verify_smoke_evidence(args.version)
    verify_command_help()
    print(json.dumps({
        "status": "success",
        "project": project_name,
        "version": args.version,
        "commands": len(COMMANDS),
        "capabilities": capability_count,
        "routing_evaluation": routing_evaluation,
        "routing_cases": len(json.loads(
            (ROOT / "evals" / "skill-routing-cases.json").read_text(encoding="utf-8")
        )["cases"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
