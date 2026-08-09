import argparse
import builtins
import io
import json
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cli import download_cmd, env_cmd  # noqa: E402
from core import cnki  # noqa: E402
from core.cnki.download import _parse_bibtex_export  # noqa: E402


def test_bibtex_parser_handles_nested_braces_quotes_and_macros():
    content = """
@string{journal_name = "Journal of Structured Data"}
@article{nested2026,
  title = {A {Nested} Title with \\{Escaped\\} Braces},
  author = "Doe, Jane and Zhang, San",
  journal = journal_name,
  year = {2026},
  pages = "10--20",
  doi = {10.1000/nested}
}
"""

    result = _parse_bibtex_export(content)

    assert result == [
        {
            "source": "CNKI-export",
            "title": "A {Nested} Title with {Escaped} Braces",
            "authors": "Doe, Jane and Zhang, San",
            "journal": "Journal of Structured Data",
            "year": 2026,
            "pages": "10-20",
            "doi": "10.1000/nested",
        }
    ]


def test_check_fix_does_not_modify_user_level_codex_config(
    monkeypatch, tmp_path
):
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    config = home / ".codex" / "config.toml"
    config.parent.mkdir(parents=True)
    original = 'approval_policy = "never"\n'
    config.write_text(original, encoding="utf-8")
    monkeypatch.chdir(project)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("CODEX_SANDBOX_NETWORK_DISABLED", "1")

    recommendations = env_cmd._fix_sandbox_network()

    assert config.read_text(encoding="utf-8") == original
    assert recommendations
    assert all("manual" in item.lower() or "手动" in item for item in recommendations)


def test_check_fix_does_not_run_pip_install(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(env_cmd, "_check_browser", lambda _: (False, "missing"))
    monkeypatch.setattr(env_cmd, "_check_driver", lambda: (False, "missing"))
    monkeypatch.setattr(env_cmd, "_check_cnki", lambda: (False, "blocked"))
    monkeypatch.setattr(env_cmd, "_check_update", lambda: None)
    monkeypatch.setattr(env_cmd, "_fix_sandbox_network", lambda: ["manual action"])

    original_import = builtins.__import__

    def missing_selenium(name, *args, **kwargs):
        if name == "selenium":
            raise ImportError("simulated missing selenium")
        return original_import(name, *args, **kwargs)

    calls = []

    def record_subprocess(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(builtins, "__import__", missing_selenium)
    monkeypatch.setattr(subprocess, "run", record_subprocess)

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        env_cmd.cmd_check(argparse.Namespace(fix=True))
    result = json.loads(stdout.getvalue())

    assert calls == []
    assert "recommended_actions" in result
    assert "fixes_applied" not in result


def test_macos_browser_detection_is_shared_by_check_and_driver(
    monkeypatch, tmp_path
):
    from core import config
    from core.cnki import driver

    chrome = tmp_path / "Google Chrome"
    chrome.write_text("", encoding="utf-8")
    monkeypatch.setattr(env_cmd.sys, "platform", "darwin")
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setattr(
        driver,
        "MACOS_BROWSER_EXECUTABLES",
        (("chrome", chrome),),
    )
    monkeypatch.setattr(config, "get", lambda *_args, **_kwargs: "auto")
    runner = SimpleNamespace(
        run=lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="Google Chrome 130",
        )
    )

    assert driver._detect_browser() == "chrome"
    assert env_cmd._check_browser(runner) == (True, "Google Chrome 130")


def test_macos_browser_detection_falls_back_to_path(monkeypatch):
    from core import config
    from core.cnki import driver

    chrome = "/opt/homebrew/bin/google-chrome"
    monkeypatch.setattr(env_cmd.sys, "platform", "darwin")
    monkeypatch.setattr(
        shutil,
        "which",
        lambda command: chrome if command == "google-chrome" else None,
    )
    monkeypatch.setattr(driver, "MACOS_BROWSER_EXECUTABLES", ())
    monkeypatch.setattr(config, "get", lambda *_args, **_kwargs: "auto")
    runner = SimpleNamespace(
        run=lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="Google Chrome 130\n",
        )
    )

    assert driver._detect_browser() == "chrome"
    assert env_cmd._check_browser(runner) == (True, "Google Chrome 130")


def test_cnki_url_validation_rejects_hostname_confusion(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        cnki,
        "download_cnki",
        lambda *args, **kwargs: (
            calls.append((args, kwargs))
            or {"status": "success", "path": "unexpected"}
        ),
    )
    args = argparse.Namespace(
        doi=None,
        target="https://cnki.net.evil.example/paper",
        dir=str(tmp_path),
        file_format="pdf",
        link_only=False,
    )

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        download_cmd.cmd_download(args)
    result = json.loads(stdout.getvalue())

    assert result["code"] == "UNSUPPORTED_URL"
    assert calls == []


class StreamingResponse:
    headers = {"content-type": "application/pdf"}
    url = "https://example.org/paper.pdf"

    def __init__(self, chunks):
        self._chunks = chunks

    @property
    def content(self):
        raise AssertionError("download must not buffer response.content")

    def raise_for_status(self):
        return None

    def iter_bytes(self):
        yield from self._chunks

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class StreamingClient:
    chunks = [b"%PDF-1.7\n", b"payload"]

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def stream(self, *args, **kwargs):
        return StreamingResponse(self.chunks)

    def get(self, *args, **kwargs):
        return StreamingResponse(self.chunks)


def test_oa_download_streams_chunks_without_buffering(monkeypatch, tmp_path):
    import httpx

    StreamingClient.chunks = [b"%PDF-1.7\n", b"payload"]
    monkeypatch.setattr(httpx, "Client", StreamingClient)

    output = tmp_path / "paper.pdf"
    result = download_cmd._download_oa_pdf(
        "https://example.org/paper.pdf",
        output,
        max_bytes=1024,
    )

    assert result["status"] == "success"
    assert output.read_bytes() == b"%PDF-1.7\npayload"


def test_oa_download_rejects_oversized_response_without_artifact(
    monkeypatch, tmp_path
):
    import httpx

    StreamingClient.chunks = [b"%PDF-", b"x" * 20]
    monkeypatch.setattr(httpx, "Client", StreamingClient)

    output = tmp_path / "paper.pdf"
    result = download_cmd._download_oa_pdf(
        "https://example.org/paper.pdf",
        output,
        max_bytes=10,
    )

    assert result["status"] == "error"
    assert result["code"] == "OA_PDF_TOO_LARGE"
    assert not output.exists()
    assert not list(tmp_path.glob("*.part"))


def test_doi_filenames_include_collision_resistant_identity():
    first = download_cmd._doi_filename("10.1/a:b")
    second = download_cmd._doi_filename("10.1/a/b")

    assert first != second
    assert first.endswith(".pdf")
    assert second.endswith(".pdf")


def test_existing_verified_pdf_is_kept_without_network_request(
    monkeypatch, tmp_path
):
    import httpx

    class NetworkMustNotRun:
        def __init__(self, *args, **kwargs):
            raise AssertionError("existing verified PDF should be reused")

    monkeypatch.setattr(httpx, "Client", NetworkMustNotRun)
    output = tmp_path / "paper.pdf"
    original = b"%PDF-1.7\nexisting"
    output.write_bytes(original)

    result = download_cmd._download_oa_pdf(
        "https://example.org/paper.pdf",
        output,
    )

    assert result["status"] == "success"
    assert result["cached"] is True
    assert output.read_bytes() == original
