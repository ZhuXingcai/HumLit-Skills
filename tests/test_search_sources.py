import asyncio
import argparse
import contextlib
import io
import json
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core import search  # noqa: E402
from core import search_async  # noqa: E402
from cli import search_cmd  # noqa: E402


def test_semantic_alias_uses_semantic_scholar_fallback_chain(monkeypatch):
    monkeypatch.setattr(search, "search_semantic_scholar", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        search,
        "search_openalex",
        lambda *args, **kwargs: [{"title": "fallback result", "source": "OpenAlex"}],
    )

    result = search.search_with_fallback("graph neural networks", "semantic", limit=1)

    assert result["fallback"] is True
    assert result["source"] == "openalex"
    assert result["original_source"] == "semantic"
    assert result["results"][0]["source"] == "OpenAlex"


def test_fallback_chain_preserves_verified_empty_state(monkeypatch):
    monkeypatch.setattr(search, "search_openalex", lambda *args, **kwargs: [])
    monkeypatch.setattr(search, "search_semantic_scholar", lambda *args, **kwargs: [])
    monkeypatch.setattr(search, "search_arxiv", lambda *args, **kwargs: [])

    result = search.search_with_fallback("no matches", "openalex", limit=1)

    assert result["results"] == []
    assert "error" not in result
    assert result["status"] == "empty"
    assert all(
        item["status"] == "empty"
        for item in result["source_statuses"].values()
    )


@pytest.mark.parametrize(
    ("source_name", "function_name", "paper_source"),
    [
        ("nssd", "search_nssd", "NSSD"),
        ("dblp", "search_dblp", "DBLP"),
        ("base", "search_base", "BASE"),
    ],
)
def test_fallback_dispatch_uses_source_specific_signatures(
    monkeypatch, source_name, function_name, paper_source
):
    def primary(query, limit=10, year_from=None, year_to=None):
        return [{"title": f"{paper_source} paper", "source": paper_source}]

    monkeypatch.setattr(search, function_name, primary)

    result = search.search_with_fallback(
        "topic",
        source_name,
        limit=1,
        sort="date",
        field="title",
        page=2,
    )

    assert result == {
        "source": source_name,
        "results": [{"title": f"{paper_source} paper", "source": paper_source}],
        "fallback": False,
        "source_statuses": {
            source_name: {"status": "success", "count": 1},
        },
    }


def test_search_all_includes_only_stable_public_sources(monkeypatch):
    def source_result(source_name):
        return [{"title": f"{source_name} title", "source": source_name, "cited_by": 0}]

    monkeypatch.setattr(search.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(search, "search_openalex", lambda *args, **kwargs: source_result("OpenAlex"))
    monkeypatch.setattr(search, "search_semantic_scholar", lambda *args, **kwargs: source_result("Semantic Scholar"))
    monkeypatch.setattr(search, "search_arxiv", lambda *args, **kwargs: source_result("arXiv"))
    monkeypatch.setattr(search, "search_nssd", lambda *args, **kwargs: source_result("NSSD"))
    monkeypatch.setattr(search, "search_dblp", lambda *args, **kwargs: source_result("DBLP"))
    monkeypatch.setattr(search, "search_base", lambda *args, **kwargs: source_result("BASE"))

    results = search.search_all("topic", limit=3)

    assert {paper["source"] for paper in results} == {
        "OpenAlex",
        "Semantic Scholar",
        "arXiv",
        "NSSD",
        "DBLP",
    }


def test_async_search_all_uses_only_stable_sources_by_default(monkeypatch):
    def async_source(source_name):
        async def _run(*args, **kwargs):
            return [{"title": f"{source_name} title", "source": source_name}]

        return _run

    monkeypatch.setattr(search_async, "search_openalex_async", async_source("OpenAlex"))
    monkeypatch.setattr(search_async, "search_semantic_scholar_async", async_source("Semantic Scholar"))
    monkeypatch.setattr(search_async, "search_arxiv_async", async_source("arXiv"))
    monkeypatch.setattr(search_async, "search_nssd_async", async_source("NSSD"))
    monkeypatch.setattr(search_async, "search_dblp_async", async_source("DBLP"))
    monkeypatch.setattr(search_async, "search_base_async", async_source("BASE"), raising=False)

    result = asyncio.run(search_async.search_all_async("topic", limit=1))

    assert "base" not in result["source_statuses"]
    assert not any(paper["source"] == "BASE" for paper in result["results"])
    assert set(result["source_statuses"]) == {
        "openalex",
        "semantic_scholar",
        "arxiv",
        "nssd",
        "dblp",
    }


def test_single_source_failure_is_not_reported_as_no_results(monkeypatch, tmp_path):
    def unavailable(*args, **kwargs):
        raise search.SearchSourceError(
            "openalex",
            "SOURCE_UNAVAILABLE",
            "simulated connection failure",
        )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(search_cmd, "search_openalex", unavailable)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    search_cmd.add_parser(sub)
    args = parser.parse_args(["search", "topic", "--source", "openalex"])

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        args.func(args)

    result = json.loads(stdout.getvalue())
    assert result["status"] == "error"
    assert result["code"] == "SOURCE_UNAVAILABLE"
    assert result["source_statuses"]["openalex"]["status"] == "error"


def test_async_search_forwards_filters_and_page(monkeypatch):
    calls = {}

    def recorder(source_name):
        async def _run(*args, **kwargs):
            calls[source_name] = {"args": args, "kwargs": kwargs}
            return []

        return _run

    monkeypatch.setattr(search_async, "search_openalex_async", recorder("openalex"))
    monkeypatch.setattr(
        search_async,
        "search_semantic_scholar_async",
        recorder("semantic_scholar"),
    )
    monkeypatch.setattr(search_async, "search_arxiv_async", recorder("arxiv"))
    monkeypatch.setattr(search_async, "search_nssd_async", recorder("nssd"))
    monkeypatch.setattr(search_async, "search_dblp_async", recorder("dblp"))
    monkeypatch.setattr(search_async, "search_base_async", recorder("base"))

    asyncio.run(
        search_async.search_all_async(
            "topic",
            limit=5,
            field="title",
            journal="Nature",
            author="Wang",
            field_of_study="Sociology",
            page=3,
        )
    )

    assert calls["openalex"]["kwargs"] == {
        "field": "title",
        "journal": "Nature",
        "author": "Wang",
        "field_of_study": "Sociology",
        "page": 3,
    }
    assert calls["semantic_scholar"]["kwargs"] == calls["openalex"]["kwargs"]
    assert calls["arxiv"]["kwargs"] == {"page": 3}


def test_async_cli_does_not_repeat_sources_synchronously(monkeypatch, tmp_path):
    def sync_call_is_a_bug(*args, **kwargs):
        raise AssertionError("async CLI repeated a source synchronously")

    for name in (
        "search_openalex",
        "search_semantic_scholar",
        "search_arxiv",
        "search_nssd",
        "search_dblp",
        "search_base",
    ):
        monkeypatch.setattr(search_cmd, name, sync_call_is_a_bug)
    monkeypatch.setattr(search_cmd, "_cnki_cache_get", lambda args: [])
    monkeypatch.setattr(
        search_async,
        "search_all_sync",
        lambda **kwargs: {
            "results": [],
            "sources_used": [],
            "source_statuses": {
                name: {"status": "empty", "count": 0}
                for name in (
                    "openalex",
                    "semantic_scholar",
                    "arxiv",
                    "nssd",
                    "dblp",
                    "base",
                )
            },
            "elapsed_ms": 1,
            "count": 0,
        },
    )
    monkeypatch.chdir(tmp_path)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    search_cmd.add_parser(sub)
    args = parser.parse_args(["search", "topic", "--source", "all", "--async-search"])

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        args.func(args)

    result = json.loads(stdout.getvalue())
    assert result["code"] == "NO_RESULTS"


def test_api_aggregate_skips_cnki_and_experimental_base(monkeypatch, tmp_path):
    calls = []

    def stable(source_name):
        def _run(*args, **kwargs):
            calls.append(source_name)
            return [{"title": source_name, "source": source_name}]

        return _run

    monkeypatch.setattr(search_cmd, "search_openalex", stable("openalex"))
    monkeypatch.setattr(
        search_cmd,
        "search_semantic_scholar",
        stable("semantic_scholar"),
    )
    monkeypatch.setattr(search_cmd, "search_arxiv", stable("arxiv"))
    monkeypatch.setattr(search_cmd, "search_nssd", stable("nssd"))
    monkeypatch.setattr(search_cmd, "search_dblp", stable("dblp"))
    monkeypatch.setattr(
        search_cmd,
        "search_base",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("experimental BASE must be explicit")
        ),
    )
    monkeypatch.chdir(tmp_path)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    search_cmd.add_parser(sub)
    args = parser.parse_args(["search", "topic", "--source", "api"])

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        args.func(args)

    result = json.loads(stdout.getvalue())
    assert result["status"] == "success"
    assert calls == ["openalex", "semantic_scholar", "arxiv", "nssd", "dblp"]


def test_retrieval_priority_score_stays_within_documented_range():
    paper = {
        "abstract": "x" * 600,
        "doi": "10.1/example",
        "cited_by": 100,
        "keywords": ["topic"],
        "is_oa": True,
        "source": "OpenAlex",
        "year": 2025,
    }

    score = search.calculate_retrieval_priority_score(paper)

    assert 0 <= score <= 100


def test_rate_limit_fails_fast_without_hidden_backoff(monkeypatch):
    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, *args, **kwargs):
            request = search.httpx.Request("GET", "https://example.test")
            response = search.httpx.Response(
                429,
                request=request,
                headers={"retry-after": "120"},
            )
            raise search.httpx.HTTPStatusError(
                "rate limited",
                request=request,
                response=response,
            )

    monkeypatch.setattr(search, "_get_client", lambda: Client())
    slept = []
    monkeypatch.setattr(search.time, "sleep", lambda seconds: slept.append(seconds))

    started = time.monotonic()
    with pytest.raises(search.SearchSourceError) as raised:
        search._http_get(
            "https://example.test",
            source="semantic_scholar",
            raise_on_error=True,
        )

    assert raised.value.code == "API_RATE_LIMIT"
    assert raised.value.status_code == 429
    assert slept == []
    assert time.monotonic() - started < 1
