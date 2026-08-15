#!/usr/bin/env python3
"""Validate HumLit Skills routing, content, and attachment boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cli.registry import COMMANDS  # noqa: E402
from generate_skill_index import (  # noqa: E402
    GeneratedIndexError,
    ManifestIndex,
    load_manifest,
    synchronize_skill,
)


@dataclass(frozen=True)
class ValidationReport:
    errors: Tuple[str, ...]
    stats: Mapping[str, int]

    @property
    def ok(self) -> bool:
        return not self.errors


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_context_budget(
    *,
    skill_path: Path,
    always_load_paths: Sequence[Path],
    skill_limit: int = 80,
    always_load_limit: int = 90,
    pre_task_limit: int = 170,
    skill_char_limit: int = 6000,
    always_load_char_limit: int = 4500,
    pre_task_char_limit: int = 10000,
) -> Tuple[str, ...]:
    skill_lines = _line_count(skill_path)
    always_load_lines = sum(_line_count(path) for path in always_load_paths)
    skill_chars = len(skill_path.read_text(encoding="utf-8"))
    always_load_chars = sum(
        len(path.read_text(encoding="utf-8"))
        for path in always_load_paths
    )
    errors = []
    if skill_lines > skill_limit:
        errors.append(
            f"SKILL.md has {skill_lines} lines; limit is {skill_limit}"
        )
    if always_load_lines > always_load_limit:
        errors.append(
            f"always-load content has {always_load_lines} lines; "
            f"limit is {always_load_limit}"
        )
    pre_task_lines = skill_lines + always_load_lines
    if pre_task_lines > pre_task_limit:
        errors.append(
            f"pre-task content has {pre_task_lines} lines; "
            f"limit is {pre_task_limit}"
        )
    if skill_chars > skill_char_limit:
        errors.append(
            f"SKILL.md has {skill_chars} characters; "
            f"limit is {skill_char_limit}"
        )
    if always_load_chars > always_load_char_limit:
        errors.append(
            f"always-load content has {always_load_chars} characters; "
            f"limit is {always_load_char_limit}"
        )
    pre_task_chars = skill_chars + always_load_chars
    if pre_task_chars > pre_task_char_limit:
        errors.append(
            f"pre-task content has {pre_task_chars} characters; "
            f"limit is {pre_task_char_limit}"
        )
    return tuple(errors)


def context_statistics(
    root: Path,
    manifest: ManifestIndex,
) -> Dict[str, int]:
    skill_lines = _line_count(root / "SKILL.md")
    always_load_lines = sum(
        _line_count(root / relative)
        for relative in manifest.always_load
    )
    skill_chars = len((root / "SKILL.md").read_text(encoding="utf-8"))
    always_load_chars = sum(
        len((root / relative).read_text(encoding="utf-8"))
        for relative in manifest.always_load
    )
    return {
        "skill_lines": skill_lines,
        "always_load_lines": always_load_lines,
        "pre_task_lines": skill_lines + always_load_lines,
        "skill_chars": skill_chars,
        "always_load_chars": always_load_chars,
        "pre_task_chars": skill_chars + always_load_chars,
    }


def _all_cases(path: Path) -> List[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported routing case schema")
    return list(data.get("cases", [])) + list(
        data.get("extended_cases", [])
    )


def _case_kind(case: dict) -> str:
    explicit = case.get("kind")
    if explicit:
        return str(explicit)
    return "positive" if case.get("should_trigger") else "negative"


def _markdown_files(root: Path) -> Iterable[Path]:
    yield root / "SKILL.md"
    yield root / "README.md"
    yield root / "evals" / "README.md"
    yield from sorted((root / "static").rglob("*.md"))
    yield from sorted((root / "references").rglob("*.md"))


def _broken_markdown_links(root: Path) -> List[str]:
    errors = []
    pattern = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
    for path in _markdown_files(root):
        text = path.read_text(encoding="utf-8")
        for raw_target in pattern.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if (
                not target
                or target.startswith(("#", "http://", "https://", "mailto:"))
            ):
                continue
            relative = target.split("#", 1)[0]
            resolved = (path.parent / relative).resolve()
            if not resolved.exists():
                errors.append(
                    f"{_relative_path(path, root)} links to missing {target}"
                )
    return errors


def _capabilities(root: Path) -> Dict[str, set]:
    data = json.loads(
        (root / "evals" / "capability-contract.json").read_text(
            encoding="utf-8"
        )
    )
    return {
        item["id"]: set(item["commands"])
        for item in data.get("capabilities", [])
    }


def _validate_routes(
    root: Path,
    manifest: ManifestIndex,
    capability_commands: Mapping[str, set],
) -> List[str]:
    errors = []
    seen_tasks = set()
    routed_commands = set()
    routed_fragments = set()
    for route in manifest.routes:
        if route.task_id in seen_tasks:
            errors.append(f"duplicate task route: {route.task_id}")
        seen_tasks.add(route.task_id)
        fragment = root / route.fragment
        if not fragment.is_file():
            errors.append(f"missing fragment: {route.fragment}")
        routed_fragments.add(route.fragment)
        unknown_commands = set(route.commands) - set(COMMANDS)
        if unknown_commands:
            errors.append(
                f"route {route.task_id} has unknown commands: "
                f"{sorted(unknown_commands)}"
            )
        routed_commands.update(route.commands)
        unknown_capabilities = (
            set(route.capabilities) - set(capability_commands)
        )
        if unknown_capabilities:
            errors.append(
                f"route {route.task_id} has unknown capabilities: "
                f"{sorted(unknown_capabilities)}"
            )
        selected_commands = set().union(
            *(
                capability_commands[capability]
                for capability in route.capabilities
                if capability in capability_commands
            )
        )
        missing_contract = set(route.commands) - selected_commands
        if missing_contract:
            errors.append(
                f"route {route.task_id} commands lack selected capability "
                f"coverage: {sorted(missing_contract)}"
            )
        for reference in route.references:
            if not (root / reference).is_file():
                errors.append(
                    f"route {route.task_id} references missing {reference}"
                )

    expected_fragments = {
        _relative_path(path, root)
        for path in (root / "static" / "fragments" / "task").glob("*.md")
    }
    missing_fragments = expected_fragments - routed_fragments
    if missing_fragments:
        errors.append(
            "fragment routing mismatch: "
            f"missing={sorted(missing_fragments)}"
        )
    if routed_commands != set(COMMANDS):
        errors.append(
            "command routing mismatch: "
            f"missing={sorted(set(COMMANDS) - routed_commands)}"
        )
    return errors


def _validate_content_index(
    root: Path,
    manifest: ManifestIndex,
) -> List[str]:
    indexed = set(manifest.always_load)
    indexed.update(value for _, value in manifest.on_demand)
    for route in manifest.routes:
        indexed.add(route.fragment)
        indexed.update(route.references)

    content_files = {
        _relative_path(path, root)
        for directory in ("static", "references")
        for path in (root / directory).rglob("*.md")
    }
    missing = sorted(content_files - indexed)
    errors = []
    if missing:
        errors.append(f"unindexed content files: {missing}")
    for relative in sorted(indexed):
        if relative.startswith(("static/", "references/")) and not (
            root / relative
        ).is_file():
            errors.append(f"indexed content is missing: {relative}")
    oversized = [
        (_relative_path(path, root), _line_count(path))
        for path in sorted((root / "references").rglob("*.md"))
        if _line_count(path) > 180
    ]
    if oversized:
        errors.append(f"oversized reference files: {oversized}")
    return errors


def _validate_fragment_sections(root: Path) -> List[str]:
    required = (
        "## 触发条件",
        "## 排除条件",
        "## 前置条件",
        "## 决策流程",
        "## 命令",
        "## 输出合同",
        "## 停止与降级",
        "## 附件",
    )
    errors = []
    for path in sorted((root / "static" / "fragments" / "task").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        positions = [text.find(heading) for heading in required]
        missing = [
            heading for heading, position in zip(required, positions)
            if position < 0
        ]
        if missing:
            errors.append(
                f"{_relative_path(path, root)} "
                f"missing standard sections: {missing}"
            )
        elif positions != sorted(positions):
            errors.append(
                f"{_relative_path(path, root)} "
                "standard sections are out of order"
            )
    return errors


def _validate_cases(
    root: Path,
    manifest: ManifestIndex,
) -> Tuple[List[str], Dict[str, int]]:
    cases = _all_cases(root / "evals" / "skill-routing-cases.json")
    routes = {route.task_id: route for route in manifest.routes}
    errors = []
    ids = [case.get("id") for case in cases]
    if len(ids) != len(set(ids)):
        errors.append("routing case ids must be unique")
    counts = {"positive": 0, "negative": 0, "ambiguous": 0}
    for case in cases:
        kind = _case_kind(case)
        if kind not in counts:
            errors.append(
                f"routing case {case.get('id')} has unknown kind {kind}"
            )
            continue
        counts[kind] += 1
        if not case.get("should_trigger"):
            continue
        task_id = case.get("task")
        route = routes.get(task_id)
        if route is None:
            errors.append(
                f"routing case {case.get('id')} has unknown task {task_id}"
            )
            continue
        if case.get("fragment") != route.fragment:
            errors.append(
                f"routing case {case.get('id')} fragment mismatches manifest"
            )
        if case.get("command") not in route.commands:
            errors.append(
                f"routing case {case.get('id')} command mismatches manifest"
            )
    expected = {"positive": 24, "negative": 12, "ambiguous": 12}
    if counts != expected:
        errors.append(f"routing case distribution is {counts}, expected {expected}")
    return errors, counts


def _validate_independent_evaluation(root: Path) -> List[str]:
    path = root / "evals" / "results" / "architecture-independent-summary.json"
    if not path.is_file():
        return ["independent routing evaluation summary is missing"]
    summary = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    if summary.get("independent_evaluator") is not True:
        errors.append("routing evaluation is not independent")
    if summary.get("cases") != 48:
        errors.append("independent routing evaluation must cover 48 cases")
    for field, minimum in (
        ("trigger_accuracy", 1.0),
        ("fragment_accuracy", 1.0),
        ("command_or_clarification_accuracy", 0.9),
    ):
        if summary.get(field, 0) < minimum:
            errors.append(
                f"independent routing {field} is below {minimum}"
            )
    inputs = summary.get("inputs") or {}
    current = {
        "skill_sha256": _text_sha256(root / "SKILL.md"),
        "cases_sha256": _text_sha256(
            root / "evals" / "skill-routing-cases.json"
        ),
        "rubric_sha256": _text_sha256(root / "evals" / "README.md"),
    }
    for key, digest in current.items():
        if inputs.get(key) != digest:
            errors.append(f"independent routing input is stale: {key}")
    result_path = root / str(summary.get("artifact", ""))
    if not result_path.is_file():
        errors.append("independent routing result artifact is missing")
    elif summary.get("results_sha256") != _text_sha256(result_path):
        errors.append("independent routing result hash mismatch")
    return errors


def validate_repository(root: Path = ROOT) -> ValidationReport:
    errors: List[str] = []
    manifest = load_manifest(root / "manifest.yaml")
    capability_commands = _capabilities(root)
    errors.extend(_validate_routes(root, manifest, capability_commands))
    errors.extend(_validate_content_index(root, manifest))
    errors.extend(_validate_fragment_sections(root))
    errors.extend(_broken_markdown_links(root))
    always_load_paths = tuple(root / path for path in manifest.always_load)
    errors.extend(
        validate_context_budget(
            skill_path=root / "SKILL.md",
            always_load_paths=always_load_paths,
        )
    )
    try:
        synchronize_skill(
            root / "manifest.yaml",
            root / "SKILL.md",
            check=True,
        )
    except GeneratedIndexError as exc:
        errors.append(str(exc))

    case_errors, case_counts = _validate_cases(root, manifest)
    errors.extend(case_errors)
    errors.extend(_validate_independent_evaluation(root))
    context = context_statistics(root, manifest)
    stats = {
        "tasks": len(manifest.routes),
        "commands": len(COMMANDS),
        "capabilities": len(capability_commands),
        "routing_cases": sum(case_counts.values()),
        "positive_cases": case_counts["positive"],
        "negative_cases": case_counts["negative"],
        "ambiguous_cases": case_counts["ambiguous"],
        **context,
    }
    return ValidationReport(errors=tuple(errors), stats=stats)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    report = validate_repository(args.root.resolve())
    print(json.dumps({
        "status": "success" if report.ok else "error",
        "errors": list(report.errors),
        "stats": dict(report.stats),
    }, ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
