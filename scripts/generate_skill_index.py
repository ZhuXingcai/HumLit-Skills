#!/usr/bin/env python3
"""Generate the SKILL.md routing table from manifest.yaml."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


ROOT = Path(__file__).resolve().parents[1]
BEGIN_MARKER = "<!-- BEGIN GENERATED ROUTES -->"
END_MARKER = "<!-- END GENERATED ROUTES -->"
ROUTE_FIELDS = (
    "triggers",
    "exclusions",
    "fragment",
    "commands",
    "capabilities",
    "references",
)


class ManifestError(ValueError):
    """The controlled manifest subset is missing or malformed."""


class GeneratedIndexError(RuntimeError):
    """The generated SKILL index is missing or out of date."""


@dataclass(frozen=True)
class TaskRoute:
    task_id: str
    triggers: Tuple[str, ...]
    exclusions: Tuple[str, ...]
    fragment: str
    commands: Tuple[str, ...]
    capabilities: Tuple[str, ...]
    references: Tuple[str, ...]


@dataclass(frozen=True)
class ManifestIndex:
    name: str
    version: str
    always_load: Tuple[str, ...]
    routes: Tuple[TaskRoute, ...]
    on_demand: Tuple[Tuple[str, str], ...]


def _scalar(text: str, key: str) -> str:
    match = re.search(
        rf"^{re.escape(key)}:\s*([^\n#]+?)\s*$",
        text,
        re.MULTILINE,
    )
    if not match:
        raise ManifestError(f"manifest is missing {key}")
    return match.group(1).strip()


def _indented_list(text: str, key: str) -> Tuple[str, ...]:
    match = re.search(
        rf"^{re.escape(key)}:\s*\n(?P<body>(?:[ \t]+-[^\n]*\n?)*)",
        text,
        re.MULTILINE,
    )
    if not match:
        raise ManifestError(f"manifest is missing {key}")
    values = tuple(
        line.split("-", 1)[1].strip()
        for line in match.group("body").splitlines()
        if line.lstrip().startswith("-")
    )
    if not values:
        raise ManifestError(f"manifest {key} must not be empty")
    return values


def _json_mapping(text: str, key: str) -> Dict[str, Any]:
    match = re.search(
        rf"^{re.escape(key)}:\s*(?P<value>\{{)",
        text,
        re.MULTILINE,
    )
    if not match:
        raise ManifestError(
            f"manifest {key} must be a JSON-compatible YAML flow mapping"
        )
    try:
        value, _ = json.JSONDecoder().raw_decode(text[match.start("value"):])
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest {key} is invalid: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestError(f"manifest {key} must be an object")
    return value


def _indented_mapping(text: str, key: str) -> Tuple[Tuple[str, str], ...]:
    match = re.search(
        rf"^{re.escape(key)}:\s*\n"
        r"(?P<body>(?:[ \t]+[A-Za-z0-9_-]+:\s*[^\n]+\n?)*)",
        text,
        re.MULTILINE,
    )
    if not match:
        raise ManifestError(f"manifest is missing {key}")
    items = []
    for line in match.group("body").splitlines():
        name, value = line.strip().split(":", 1)
        items.append((name.strip(), value.strip()))
    return tuple(items)


def _string_tuple(
    task_id: str,
    data: Dict[str, Any],
    field: str,
    *,
    allow_empty: bool = False,
) -> Tuple[str, ...]:
    value = data.get(field)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip()
        for item in value
    ):
        raise ManifestError(f"route {task_id} {field} must be a string list")
    if not value and not allow_empty:
        raise ManifestError(f"route {task_id} {field} must not be empty")
    return tuple(item.strip() for item in value)


def _route(task_id: str, raw: Any) -> TaskRoute:
    if not isinstance(raw, dict):
        raise ManifestError(f"route {task_id} must be an object")
    missing = [field for field in ROUTE_FIELDS if field not in raw]
    if missing:
        raise ManifestError(f"route {task_id} missing fields: {missing}")
    fragment = raw["fragment"]
    if not isinstance(fragment, str) or not fragment.strip():
        raise ManifestError(f"route {task_id} fragment must be a string")
    return TaskRoute(
        task_id=task_id,
        triggers=_string_tuple(task_id, raw, "triggers"),
        exclusions=_string_tuple(task_id, raw, "exclusions"),
        fragment=fragment.strip(),
        commands=_string_tuple(task_id, raw, "commands"),
        capabilities=_string_tuple(task_id, raw, "capabilities"),
        references=_string_tuple(
            task_id,
            raw,
            "references",
            allow_empty=True,
        ),
    )


def load_manifest(path: Path) -> ManifestIndex:
    text = path.read_text(encoding="utf-8")
    routing = _json_mapping(text, "routing")
    routes = tuple(_route(task_id, raw) for task_id, raw in routing.items())
    if not routes:
        raise ManifestError("manifest routing must not be empty")
    return ManifestIndex(
        name=_scalar(text, "name"),
        version=_scalar(text, "version"),
        always_load=_indented_list(text, "always_load"),
        routes=routes,
        on_demand=_indented_mapping(text, "on_demand"),
    )


def _cell(values: Iterable[str]) -> str:
    return "<br>".join(value.replace("|", r"\|") for value in values)


def render_generated_routes(manifest: ManifestIndex) -> str:
    lines = [
        "## 意图路由（由 manifest.yaml 生成）",
        "",
        "| 任务 | 触发信号 | 排除信号 | 命令 | 按需读取 |",
        "|------|----------|----------|------|----------|",
    ]
    for route in manifest.routes:
        commands = _cell(f"`{command}`" for command in route.commands)
        lines.append(
            f"| `{route.task_id}` | {_cell(route.triggers)} | "
            f"{_cell(route.exclusions)} | {commands} | "
            f"`{route.fragment}` |"
        )
    return "\n".join(lines)


def _atomic_write(path: Path, text: str) -> None:
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        Path(temporary).unlink(missing_ok=True)
        raise


def synchronize_skill(
    manifest_path: Path,
    skill_path: Path,
    *,
    check: bool = False,
) -> bool:
    manifest = load_manifest(manifest_path)
    current = skill_path.read_text(encoding="utf-8")
    if current.count(BEGIN_MARKER) != 1 or current.count(END_MARKER) != 1:
        raise GeneratedIndexError("SKILL.md generated route markers are missing")
    start = current.index(BEGIN_MARKER)
    end = current.index(END_MARKER, start) + len(END_MARKER)
    generated = (
        f"{BEGIN_MARKER}\n"
        f"{render_generated_routes(manifest)}\n"
        f"{END_MARKER}"
    )
    expected = current[:start] + generated + current[end:]
    if expected == current:
        return False
    if check:
        raise GeneratedIndexError(
            "SKILL.md generated routing index is out of date"
        )
    _atomic_write(skill_path, expected)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "manifest.yaml")
    parser.add_argument("--skill", type=Path, default=ROOT / "SKILL.md")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        changed = synchronize_skill(
            args.manifest,
            args.skill,
            check=args.check,
        )
    except (ManifestError, GeneratedIndexError) as exc:
        print(str(exc))
        return 1
    print("updated" if changed else "up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
