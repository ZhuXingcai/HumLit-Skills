import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core import config, paths  # noqa: E402
import literature  # noqa: E402


def test_state_directory_is_project_local(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    assert paths.state_dir() == tmp_path / ".humlit"
    assert paths.state_path("projects", "sample") == (
        tmp_path / ".humlit" / "projects" / "sample"
    )


def test_humlit_environment_variable_overrides_config(
    monkeypatch, tmp_path
):
    state = tmp_path / ".humlit"
    state.mkdir()
    (state / "config.json").write_text(
        '{"save_dir":"./config-papers"}',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HUMLIT_SAVE_DIR", "./env-papers")
    config.reset()

    assert config.get("save_dir") == "./env-papers"


def test_humlit_console_identity(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["humlit", "--version"])

    with pytest.raises(SystemExit) as exc:
        literature.main()

    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert captured.out.strip() == "humlit 1.0.2"
    assert captured.err == ""
