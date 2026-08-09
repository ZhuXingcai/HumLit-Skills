import asyncio
import contextlib
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core import search_async  # noqa: E402
from core.search import SearchSourceError  # noqa: E402


def test_http_async_errors_go_to_stderr_not_stdout():
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        with pytest.raises(SearchSourceError) as exc:
            asyncio.run(search_async._http_get_async("http://127.0.0.1:1/nope", timeout=1))

    assert exc.value.code == "SOURCE_UNAVAILABLE"
    assert stdout.getvalue() == ""
    assert "[async]" in stderr.getvalue()


def test_search_all_async_source_exception_goes_to_stderr(monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("simulated source failure")

    async def empty(*args, **kwargs):
        return []

    monkeypatch.setattr(search_async, "search_openalex_async", boom)
    monkeypatch.setattr(search_async, "search_semantic_scholar_async", empty)
    monkeypatch.setattr(search_async, "search_arxiv_async", empty)
    monkeypatch.setattr(search_async, "search_nssd_async", empty)
    monkeypatch.setattr(search_async, "search_dblp_async", empty)
    monkeypatch.setattr(search_async, "search_base_async", empty, raising=False)

    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        result = asyncio.run(search_async.search_all_async("topic", limit=1))

    assert result["results"] == []
    assert stdout.getvalue() == ""
    assert "simulated source failure" in stderr.getvalue()
