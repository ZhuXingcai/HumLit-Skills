import argparse
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cli import download_cmd  # noqa: E402


class FakeResponse:
    def __init__(self, content, *, content_type="application/pdf", url="https://example.org/paper.pdf"):
        self.content = content
        self.headers = {"content-type": content_type}
        self.url = url

    def raise_for_status(self):
        return None


class FakeClient:
    response = FakeResponse(b"%PDF-1.7\nsmoke")

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get(self, *args, **kwargs):
        return self.response


def test_verified_oa_pdf_is_atomically_saved(monkeypatch, tmp_path):
    import httpx

    FakeClient.response = FakeResponse(b"%PDF-1.7\nsmoke")
    monkeypatch.setattr(httpx, "Client", FakeClient)
    output = tmp_path / "pdf" / "paper.pdf"

    result = download_cmd._download_oa_pdf("https://example.org/paper.pdf", output)

    assert result["status"] == "success"
    assert output.read_bytes().startswith(b"%PDF-")
    assert not list(output.parent.glob("*.part"))


def test_non_pdf_response_is_rejected_without_partial_artifact(monkeypatch, tmp_path):
    import httpx

    FakeClient.response = FakeResponse(
        b"<html>login</html>",
        content_type="text/html",
        url="https://example.org/login",
    )
    monkeypatch.setattr(httpx, "Client", FakeClient)
    output = tmp_path / "pdf" / "paper.pdf"

    result = download_cmd._download_oa_pdf("https://example.org/paper.pdf", output)

    assert result["status"] == "error"
    assert result["code"] == "OA_DOWNLOAD_FAILED"
    assert not output.exists()
    assert not list(output.parent.glob("*.part"))


def test_doi_download_falls_back_to_openalex_and_reports_saved_file(monkeypatch, tmp_path):
    monkeypatch.setattr(download_cmd, "resolve_unpaywall", lambda doi: None)
    monkeypatch.setattr(
        download_cmd,
        "resolve_openalex_oa",
        lambda doi: {
            "oa_url": "https://example.org/paper.pdf",
            "source": "OpenAlex",
            "title": "Open paper",
        },
    )

    def fake_download(url, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF-1.7\nsmoke")
        return {
            "status": "success",
            "path": str(output_path),
            "bytes": output_path.stat().st_size,
            "url": url,
            "content_type": "application/pdf",
        }

    monkeypatch.setattr(download_cmd, "_download_oa_pdf", fake_download)
    args = argparse.Namespace(
        doi="10.1000/test",
        target=None,
        dir=str(tmp_path),
        file_format="pdf",
        link_only=False,
    )
    output = io.StringIO()
    with redirect_stdout(output):
        download_cmd.cmd_download(args)
    payload = json.loads(output.getvalue())

    assert payload["status"] == "success"
    assert payload["method"] == "openalex_oa"
    assert Path(payload["path"]).is_file()
