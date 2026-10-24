#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trellis hook launcher for WorkBuddy.

Problem
-------
Trellis hooks locate the project by walking *up* from the session cwd looking
for a ``.trellis/`` directory.  WorkBuddy sessions start at the workspace root
(``<workspace-root>``) while the actual Trellis project is nested at
``<workspace-root>/HumLit-Skills``, so the upstream hooks silently
no-op.

What this does
--------------
1. Reads the hook payload from stdin.
2. Resolves the Trellis project root:
   a. walk up from the payload ``cwd`` looking for ``.trellis/``;
   b. otherwise fall back to the project that owns this script
      (``<project>/.workbuddy/hooks/_launcher.py``);
   c. otherwise exit 0 silently.
3. Rewrites ``cwd`` in the payload, exports ``CODEBUDDY_PROJECT_DIR``, and
   re-runs the real hook with the patched payload.

Any failure exits 0 so a broken hook can never block the session.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Force UTF-8 on Windows, otherwise Chinese task names / prd snippets break.
if sys.platform.startswith("win"):
    for _name in ("stdin", "stdout", "stderr"):
        _stream = getattr(sys, _name, None)
        if _stream is not None and hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _find_trellis_root(start: Path) -> Path | None:
    """Walk up from *start* looking for a .trellis directory."""
    try:
        cur = start.resolve()
    except OSError:
        return None
    while True:
        if (cur / ".trellis").is_dir():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


def _own_project_root() -> Path | None:
    """<project>/.workbuddy/hooks/_launcher.py -> <project>"""
    try:
        candidate = Path(__file__).resolve().parents[2]
    except (OSError, IndexError):
        return None
    return candidate if (candidate / ".trellis").is_dir() else None


def _resolve_project(payload: dict) -> Path | None:
    cwd = payload.get("cwd") or os.getcwd()
    root = _find_trellis_root(Path(cwd))
    if root is not None:
        return root
    return _own_project_root()


def main() -> int:
    if os.environ.get("TRELLIS_HOOKS") == "0" or os.environ.get("TRELLIS_DISABLE_HOOKS") == "1":
        return 0

    if len(sys.argv) < 2:
        return 0

    target = (Path(__file__).resolve().parent / sys.argv[1]).resolve()
    if not target.is_file():
        return 0

    raw = sys.stdin.buffer.read()
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace")) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    project = _resolve_project(payload)
    if project is None:
        return 0

    payload["cwd"] = str(project)
    patched = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    env = os.environ.copy()

    # The upstream hooks resolve the project root from env vars BEFORE looking
    # at the payload cwd, and WorkBuddy injects CLAUDE_PROJECT_DIR /
    # CODEBUDDY_PROJECT_DIR pointing at the workspace root.  Drop every
    # platform variant, then set only the CodeBuddy one so the hooks both find
    # the right project and detect the correct platform.
    for _var in (
        "CLAUDE_PROJECT_DIR",
        "QODER_PROJECT_DIR",
        "FACTORY_PROJECT_DIR",
        "CURSOR_PROJECT_DIR",
        "GEMINI_PROJECT_DIR",
        "KIRO_PROJECT_DIR",
        "COPILOT_PROJECT_DIR",
    ):
        env.pop(_var, None)
    env["CODEBUDDY_PROJECT_DIR"] = str(project)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    try:
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", str(target)],
            input=patched,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=str(project),
            env=env,
            timeout=25,
        )
    except Exception:
        return 0

    if proc.stdout:
        try:
            sys.stdout.buffer.write(proc.stdout)
            sys.stdout.buffer.flush()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
