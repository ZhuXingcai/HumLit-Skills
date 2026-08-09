"""Runtime paths for HumLit Skills."""

from __future__ import annotations

from pathlib import Path
from typing import Union


PathPart = Union[str, Path]
STATE_DIR_NAME = ".humlit"


def state_dir(base: Path | None = None) -> Path:
    """Return the project-local HumLit state directory."""
    base = (base or Path.cwd()).resolve()
    return base / STATE_DIR_NAME


def state_path(*parts: PathPart, base: Path | None = None) -> Path:
    """Resolve a path below the active state directory."""
    path = state_dir(base)
    for part in parts:
        path /= part
    return path
