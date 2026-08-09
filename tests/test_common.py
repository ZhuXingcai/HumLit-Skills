import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cli import _common  # noqa: E402


def test_safe_project_name_sanitizes():
    assert _common._safe_project_name("  我的 课题/x  ") == "我的 课题_x"


def test_citation_style_choices_complete():
    assert _common.CITATION_STYLE_CHOICES == ["gbt7714", "gb", "apa", "mla", "chicago", "footnote"]


def test_emit_outputs_json(capsys):
    _common.emit({"status": "success", "n": 1})
    out = capsys.readouterr().out
    assert '"status": "success"' in out
    assert '"n": 1' in out


def test_session_write_is_versioned_and_atomic(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    papers = [{"title": "A", "doi": "10.1/a"}]

    _common._save_session(papers)

    raw = json.loads((tmp_path / ".humlit" / "session.json").read_text(encoding="utf-8"))
    assert raw["schema_version"] == 1
    assert raw["papers"] == papers
    assert not (tmp_path / ".humlit" / "session.json.tmp").exists()
    assert _common._load_session() == papers


def test_corrupt_session_is_backed_up_and_reported(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    session = tmp_path / ".humlit" / "session.json"
    session.parent.mkdir()
    session.write_text("{bad", encoding="utf-8")

    with pytest.raises(_common.SessionDataError) as exc:
        _common._load_session()

    assert exc.value.code == "SESSION_CORRUPT"
    assert exc.value.backup_path is not None
    assert Path(exc.value.backup_path).read_text(encoding="utf-8") == "{bad"


def test_append_merges_duplicate_records_by_doi(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _common._save_session([{"title": "A", "doi": "10.1/A", "abstract": ""}])

    _common._save_session(
        [{"title": "A revised", "doi": "https://doi.org/10.1/a", "abstract": "full"}],
        append=True,
    )

    papers = _common._load_session()
    assert len(papers) == 1
    assert papers[0]["title"] == "A revised"
    assert papers[0]["abstract"] == "full"
