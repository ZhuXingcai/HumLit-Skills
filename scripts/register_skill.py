#!/usr/bin/env python3
"""Register one HumLit Skills checkout with supported agent clients."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


CLIENT_SKILL_DIRS = {
    "codex": Path(".codex/skills"),
    "claude": Path(".claude/skills"),
    "trae": Path(".trae-cn/skills"),
    "cursor": Path(".cursor/skills"),
    "gemini": Path(".gemini/skills"),
}


def register_skill(source: Path, home: Path, clients: Iterable[str]) -> dict:
    source = source.expanduser().resolve()
    home = home.expanduser().resolve()
    if not (source / "SKILL.md").is_file():
        return {
            "status": "error",
            "code": "INVALID_SKILL_SOURCE",
            "message": f"SKILL.md not found under {source}",
            "results": [],
        }

    results = []
    has_error = False
    for client in dict.fromkeys(clients):
        relative_root = CLIENT_SKILL_DIRS.get(client)
        if relative_root is None:
            has_error = True
            results.append({
                "client": client,
                "status": "error",
                "code": "UNKNOWN_CLIENT",
            })
            continue

        target = home / relative_root / "humlit-skills"
        if target.exists() or target.is_symlink():
            try:
                same_source = target.resolve() == source
            except OSError:
                same_source = False
            if same_source:
                results.append({
                    "client": client,
                    "status": "already_registered",
                    "path": str(target),
                })
            else:
                has_error = True
                results.append({
                    "client": client,
                    "status": "error",
                    "code": "TARGET_EXISTS",
                    "path": str(target),
                    "message": "目标位置已存在其他文件，未覆盖",
                })
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.symlink_to(source, target_is_directory=True)
        except OSError as exc:
            has_error = True
            results.append({
                "client": client,
                "status": "error",
                "code": "LINK_CREATE_FAILED",
                "path": str(target),
                "message": str(exc),
            })
            continue

        results.append({
            "client": client,
            "status": "registered",
            "path": str(target),
        })

    registered = sum(
        item["status"] in {"registered", "already_registered"}
        for item in results
    )
    return {
        "status": "partial" if has_error and registered else "error" if has_error else "success",
        "source": str(source),
        "registered": registered,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Register HumLit Skills with one or more agent clients.",
    )
    parser.add_argument(
        "--source",
        default=str(Path(__file__).resolve().parents[1]),
        help="HumLit Skills repository path",
    )
    parser.add_argument(
        "--home",
        default=str(Path.home()),
        help="Home directory used to resolve client skill folders",
    )
    parser.add_argument(
        "--client",
        action="append",
        choices=sorted(CLIENT_SKILL_DIRS),
        required=True,
        help="Client to register; repeat for multiple clients",
    )
    args = parser.parse_args()
    result = register_skill(Path(args.source), Path(args.home), args.client)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
