#!/usr/bin/env python3
"""Prepare and validate auditable, externally evaluated routing artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable


ROOT = Path(__file__).resolve().parents[1]


def _routing_cases(data: Dict[str, Any]) -> list:
    return list(data.get("cases", [])) + list(
        data.get("extended_cases", [])
    )


def _portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _atomic_json_write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        Path(temp_name).unlink(missing_ok=True)
        raise


def build_evaluation_request(
    *,
    skill_path: Path,
    cases_path: Path,
    rubric_path: Path,
    output_path: Path,
) -> Dict[str, Any]:
    skill_text = skill_path.read_text(encoding="utf-8")
    cases_text = cases_path.read_text(encoding="utf-8")
    rubric_text = rubric_path.read_text(encoding="utf-8")
    cases = json.loads(cases_text)
    request = {
        "schema_version": 1,
        "evaluation_type": "independent_semantic_routing",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(_routing_cases(cases)),
        "inputs": {
            "skill_path": _portable_path(skill_path),
            "cases_path": _portable_path(cases_path),
            "rubric_path": _portable_path(rubric_path),
            "skill_sha256": _sha256(skill_path),
            "cases_sha256": _sha256(cases_path),
            "rubric_sha256": _sha256(rubric_path),
        },
        "payload": {
            "skill_markdown": skill_text,
            "cases_json": cases_text,
            "rubric_markdown": rubric_text,
        },
        "instructions": {
            "independent_evaluator_required": True,
            "implementation_session_must_not_evaluate": True,
            "required_result_fields": [
                "id",
                "trigger",
                "fragment",
                "command",
                "clarify",
                "reason",
            ],
            "output_format": "one JSON object per line",
        },
    }
    _atomic_json_write(output_path, request)
    return {
        "status": "success",
        "output": str(output_path),
        "case_count": request["case_count"],
        "request_sha256": _sha256(output_path),
    }


def _read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        1,
    ):
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            raise ValueError(f"result line {line_number} is not an object")
        yield item


def validate_external_results(
    *,
    request_path: Path,
    results_path: Path,
    evaluator_provider: str,
    evaluator_model: str,
    evaluator_run_id: str,
    output_path: Path,
) -> Dict[str, Any]:
    if not all(
        value.strip()
        for value in (
            evaluator_provider,
            evaluator_model,
            evaluator_run_id,
        )
    ):
        raise ValueError("external evaluator provider/model/run-id are required")

    request = json.loads(request_path.read_text(encoding="utf-8"))
    inputs = request.get("inputs") or {}
    payload = request.get("payload") or {}
    payload_hashes = {
        "skill_sha256": hashlib.sha256(
            str(payload.get("skill_markdown", "")).encode("utf-8")
        ).hexdigest(),
        "cases_sha256": hashlib.sha256(
            str(payload.get("cases_json", "")).encode("utf-8")
        ).hexdigest(),
        "rubric_sha256": hashlib.sha256(
            str(payload.get("rubric_markdown", "")).encode("utf-8")
        ).hexdigest(),
    }
    if any(
        payload_hashes[key] != inputs.get(key)
        for key in payload_hashes
    ):
        raise ValueError("routing request payload does not match input hashes")
    cases = _routing_cases(json.loads(payload["cases_json"]))
    expected = {case["id"]: case for case in cases}
    reviewed = {item["id"]: item for item in _read_jsonl(results_path)}
    if set(reviewed) != set(expected):
        raise ValueError("external results do not cover the exact routing case set")

    positives = [case for case in cases if case["should_trigger"]]
    trigger_correct = sum(
        reviewed[case_id].get("trigger") == case["should_trigger"]
        for case_id, case in expected.items()
    )
    fragment_correct = sum(
        reviewed[case["id"]].get("fragment") == case["fragment"]
        for case in positives
    )
    command_correct = sum(
        reviewed[case["id"]].get("command") == case["command"]
        or reviewed[case["id"]].get("clarify") is True
        for case in positives
    )
    summary = {
        "schema_version": 1,
        "evaluation_type": "independent_semantic_routing",
        "independent_evaluator": True,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "evaluator": {
            "provider": evaluator_provider,
            "model": evaluator_model,
            "run_id": evaluator_run_id,
        },
        "inputs": inputs,
        "request_sha256": _sha256(request_path),
        "results_sha256": _sha256(results_path),
        "artifact": str(results_path),
        "cases": len(cases),
        "trigger_accuracy": trigger_correct / len(cases) if cases else 0,
        "fragment_accuracy": (
            fragment_correct / len(positives) if positives else 0
        ),
        "command_or_clarification_accuracy": (
            command_correct / len(positives) if positives else 0
        ),
    }
    _atomic_json_write(output_path, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--skill", type=Path, default=ROOT / "SKILL.md")
    prepare.add_argument(
        "--cases",
        type=Path,
        default=ROOT / "evals" / "skill-routing-cases.json",
    )
    prepare.add_argument(
        "--rubric",
        type=Path,
        default=ROOT / "evals" / "README.md",
    )
    prepare.add_argument("--output", type=Path, required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--request", type=Path, required=True)
    verify.add_argument("--results", type=Path, required=True)
    verify.add_argument("--provider", required=True)
    verify.add_argument("--model", required=True)
    verify.add_argument("--run-id", required=True)
    verify.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "prepare":
        result = build_evaluation_request(
            skill_path=args.skill,
            cases_path=args.cases,
            rubric_path=args.rubric,
            output_path=args.output,
        )
    else:
        result = validate_external_results(
            request_path=args.request,
            results_path=args.results,
            evaluator_provider=args.provider,
            evaluator_model=args.model,
            evaluator_run_id=args.run_id,
            output_path=args.output,
        )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
