#!/usr/bin/env python3
"""Register one HumLit Skills checkout with supported agent clients."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable


CLIENT_SKILL_DIRS = {
    "codex": Path(".codex/skills"),
    "claude": Path(".claude/skills"),
    "trae": Path(".trae-cn/skills"),
    "cursor": Path(".cursor/skills"),
    "gemini": Path(".gemini/skills"),
}


def _same_source(target: Path, source: Path) -> bool:
    try:
        return target.resolve() == source
    except OSError:
        return False


def _junction_reparse_data(source: Path) -> bytes:
    import struct
    source_text = str(source)
    if source_text.startswith("\\\\"):
        substitute = "\\??\\UNC\\" + source_text.lstrip("\\")
    else:
        substitute = "\\??\\" + source_text
    substitute_bytes = substitute.encode("utf-16-le")
    print_bytes = source_text.encode("utf-16-le")
    path_buffer = substitute_bytes + b"\0\0" + print_bytes + b"\0\0"
    return struct.pack(
        "<LHHHHHH", 0xA0000003, 8 + len(path_buffer), 0,
        0, len(substitute_bytes), len(substitute_bytes) + 2, len(print_bytes),
    ) + path_buffer


def _create_windows_junction(target: Path, source: Path) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.DeviceIoControl.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, wintypes.LPDWORD, wintypes.LPVOID,
    )
    kernel32.DeviceIoControl.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL

    target.mkdir()
    handle = kernel32.CreateFileW(
        str(target), 0x40000000, 0x00000007, None, 3,
        0x00200000 | 0x02000000, None,
    )
    if handle == wintypes.HANDLE(-1).value:
        target.rmdir()
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        returned = wintypes.DWORD()
        payload = _junction_reparse_data(source)
        buffer = ctypes.create_string_buffer(payload)
        if not kernel32.DeviceIoControl(
            handle, 0x000900A4, buffer, len(payload),
            None, 0, ctypes.byref(returned), None,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
    except Exception:
        kernel32.CloseHandle(handle)
        try:
            target.rmdir()
        except OSError:
            pass
        raise
    kernel32.CloseHandle(handle)


def _create_directory_link(target: Path, source: Path) -> None:
    try:
        target.symlink_to(source, target_is_directory=True)
    except OSError as symlink_error:
        if os.name != "nt":
            raise
        try:
            _create_windows_junction(target, source)
        except OSError as junction_error:
            raise OSError(
                f"symlink failed: {symlink_error}; "
                f"junction failed: {junction_error}"
            ) from junction_error


def _register_client(source: Path, home: Path, client: str) -> dict:
    relative_root = CLIENT_SKILL_DIRS.get(client)
    if relative_root is None:
        return {"client": client, "status": "error", "code": "UNKNOWN_CLIENT"}

    target = home / relative_root / "humlit-skills"
    if os.path.lexists(target):
        if _same_source(target, source):
            return {
                "client": client,
                "status": "already_registered",
                "path": str(target),
            }
        return {
            "client": client,
            "status": "error",
            "code": "TARGET_EXISTS",
            "path": str(target),
            "message": "目标位置已存在其他文件，未覆盖",
        }

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        _create_directory_link(target, source)
    except OSError as exc:
        return {
            "client": client,
            "status": "error",
            "code": "LINK_CREATE_FAILED",
            "path": str(target),
            "message": str(exc),
        }
    return {"client": client, "status": "registered", "path": str(target)}


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

    results = [_register_client(source, home, client) for client in dict.fromkeys(clients)]
    has_error = any(item["status"] == "error" for item in results)
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
