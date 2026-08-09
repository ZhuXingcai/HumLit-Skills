from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "scripts" / "literature.py"
REQUIRE_INSTALLED = os.environ.get("HUMLIT_ADVERSARIAL_REQUIRE_INSTALLED") == "1"
WINDOWS_RESERVED_NAMES = {
    "aux",
    "clock$",
    "con",
    "nul",
    "prn",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


def _console() -> list[str]:
    executable = shutil.which("humlit")
    if executable:
        return [executable]
    if REQUIRE_INSTALLED:
        pytest.fail("installed console command is missing: humlit")
    return [sys.executable, str(ENTRY)]


def _hostile_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.update(
        {
            "PYTHONIOENCODING": "cp1252",
            "PYTHONUTF8": "0",
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "ALL_PROXY": "http://127.0.0.1:9",
            "NO_PROXY": "",
        }
    )
    return env


def _run_cli(
    *args: str,
    cwd: Path,
    stdin: str | None = None,
) -> tuple[subprocess.CompletedProcess[bytes], str, str]:
    result = subprocess.run(
        [*_console(), *args],
        cwd=cwd,
        env=_hostile_env(),
        input=stdin.encode("utf-8") if stdin is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    return (
        result,
        result.stdout.decode("utf-8", errors="strict"),
        result.stderr.decode("utf-8", errors="strict"),
    )


def _json_stdout(stdout: str) -> dict:
    assert not stdout.startswith("\ufeff")
    assert stdout.count("{") >= 1
    return json.loads(stdout)


def test_installed_entrypoint_works_outside_checkout(tmp_path):
    cwd = tmp_path / "outside checkout 研究 [v1]"
    cwd.mkdir()
    removed_entrypoint = "scholar" + "-kit"

    result, stdout, stderr = _run_cli("--version", cwd=cwd)
    assert result.returncode == 0, stderr
    assert stdout.strip() == "humlit 1.0.2"
    assert stderr == ""
    assert shutil.which(removed_entrypoint) is None


def test_utf8_pipe_and_hostile_path_keep_stdout_as_single_json(tmp_path):
    cwd = tmp_path / "研究 data & $ [x] (测试)"
    cwd.mkdir()
    codebook = cwd / "访谈 编码簿 [v1].json"
    codebook.write_text(
        json.dumps(
            {
                "name": "对抗编码簿",
                "codes": [
                    {"code": "信任", "keywords": ["信任"]},
                    {"code": "就医", "keywords": ["就医"]},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result, stdout, stderr = _run_cli(
        "qual-code",
        "--stdin",
        "--codebook",
        str(codebook),
        cwd=cwd,
        stdin="我信任医生，所以及时就医。\n\n普通段落。",
    )

    assert result.returncode == 0, stderr
    payload = _json_stdout(stdout)
    assert payload["status"] == "success"
    assert payload["summary"]["total_hits"] == 2
    assert payload["cooccurrence"][0]["count"] == 1
    assert "Traceback" not in stderr


def test_deep_unicode_output_path_is_created_without_shell_parsing(tmp_path):
    cwd = tmp_path / "cwd with spaces"
    cwd.mkdir()
    output_dir = cwd
    for index in range(12):
        output_dir /= f"层 {index:02d}"
    output = output_dir / "格式 模板 [最终].json"

    result, stdout, stderr = _run_cli(
        "format-profile",
        "--template",
        "--output",
        str(output),
        cwd=cwd,
    )

    assert result.returncode == 0, stderr
    payload = _json_stdout(stdout)
    assert payload["status"] == "success"
    assert output.is_file()
    assert json.loads(output.read_text(encoding="utf-8"))["schema_version"]


@pytest.mark.parametrize(
    ("args", "stdin", "expected_code"),
    [
        (("cite-source", "--stdin"), "{not-json", "ENTRY_PARSE_FAILED"),
        (
            ("qual-code", "--stdin", "--codebook", "missing.json"),
            "文本",
            "FILE_NOT_FOUND",
        ),
        (("theory-match", "--keywords", "  "), None, "NO_KEYWORDS"),
    ],
)
def test_malformed_inputs_return_json_without_tracebacks(
    tmp_path, args, stdin, expected_code
):
    result, stdout, stderr = _run_cli(*args, cwd=tmp_path, stdin=stdin)

    assert result.returncode == 0, stderr
    payload = _json_stdout(stdout)
    assert payload["status"] == "error"
    assert payload["code"] == expected_code
    assert "Traceback" not in stdout
    assert "Traceback" not in stderr


def test_corrupt_session_is_backed_up_without_polluting_stdout(tmp_path):
    state = tmp_path / ".humlit"
    state.mkdir()
    (state / "session.json").write_text("{broken", encoding="utf-8")

    result, stdout, stderr = _run_cli("library", cwd=tmp_path)

    assert result.returncode == 0, stderr
    payload = _json_stdout(stdout)
    assert payload["status"] == "error"
    assert payload["code"] == "SESSION_CORRUPT"
    assert len(list(state.glob("session.json.corrupt-*.bak"))) == 1
    assert "Traceback" not in stderr


def test_concurrent_first_run_is_deterministic(tmp_path):
    processes = [
        subprocess.Popen(
            [*_console(), "projects"],
            cwd=tmp_path,
            env=_hostile_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(8)
    ]
    outputs = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=30)
        outputs.append(
            (
                process.returncode,
                stdout.decode("utf-8", errors="strict"),
                stderr.decode("utf-8", errors="strict"),
            )
        )

    for returncode, stdout, stderr in outputs:
        assert returncode == 0, stderr
        payload = _json_stdout(stdout)
        assert payload["status"] == "success"
        assert payload["count"] == 0
        assert payload["projects"] == []
        assert "Traceback" not in stderr

    assert not list(tmp_path.rglob("*.tmp"))


def test_tracked_paths_are_safe_on_case_insensitive_filesystems():
    raw = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
    )
    paths = [path for path in raw.decode("utf-8").split("\0") if path]
    casefolded: dict[str, str] = {}

    for path in paths:
        folded = path.casefold()
        assert folded not in casefolded, (
            f"case-insensitive path collision: {casefolded.get(folded)} and {path}"
        )
        casefolded[folded] = path
        assert len(path) < 220, f"path is unsafe for common Windows checkout roots: {path}"
        for part in Path(path).parts:
            assert part == part.rstrip(" ."), f"Windows strips trailing dot/space: {path}"
            assert part.split(".", 1)[0].casefold() not in WINDOWS_RESERVED_NAMES, (
                f"Windows reserved path component: {path}"
            )
