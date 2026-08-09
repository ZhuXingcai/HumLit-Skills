import argparse
import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cli import search_cmd  # noqa: E402
from core import search  # noqa: E402


def _search_args():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    search_cmd.add_parser(sub)
    return parser.parse_args(
        ["search", "topic", "--source", "api", "--limit", "3"]
    )


def test_default_multi_source_limit_round_robins_successful_sources(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)

    def source_results(source_name):
        return [
            {
                "title": f"{source_name} result {index}",
                "source": source_name,
                "cited_by": 0,
            }
            for index in range(3)
        ]

    monkeypatch.setattr(
        search_cmd,
        "search_openalex",
        lambda *args, **kwargs: source_results("OpenAlex"),
    )
    monkeypatch.setattr(
        search_cmd,
        "search_semantic_scholar",
        lambda *args, **kwargs: source_results("Semantic Scholar"),
    )
    monkeypatch.setattr(
        search_cmd,
        "search_arxiv",
        lambda *args, **kwargs: source_results("arXiv"),
    )
    monkeypatch.setattr(
        search_cmd,
        "search_nssd",
        lambda *args, **kwargs: source_results("NSSD"),
    )
    monkeypatch.setattr(
        search_cmd,
        "search_dblp",
        lambda *args, **kwargs: source_results("DBLP"),
    )

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        search_cmd.cmd_search(_search_args())
    result = json.loads(stdout.getvalue())

    assert result["status"] == "success"
    assert len({paper["source"] for paper in result["results"]}) == 3


def test_cache_uses_stored_source_and_query_for_ttl(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / ".humlit"
    cache_dir.mkdir()
    (cache_dir / "sample.json").write_text(
        json.dumps(
            {
                "_cached_at": datetime.now().isoformat(),
                "_source": "nssd",
                "_query": "数字人文",
                "results": [{"title": "cached"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    observed = {}

    def ttl(source, query):
        observed.update(source=source, query=query)
        return 24

    monkeypatch.setattr(search, "_get_smart_ttl", ttl)

    assert search._cache_get("sample") == [{"title": "cached"}]
    assert observed == {"source": "nssd", "query": "数字人文"}


def test_cache_write_uses_atomic_replace(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls = []
    original_replace = os.replace

    def recording_replace(source_path, destination_path):
        calls.append((Path(source_path), Path(destination_path)))
        original_replace(source_path, destination_path)

    monkeypatch.setattr(search.os, "replace", recording_replace)

    search._cache_set(
        "atomic",
        [{"title": "cached"}],
        source="openalex",
        query="topic",
    )

    assert len(calls) == 1
    assert calls[0][1].name == "atomic.json"
    assert json.loads(calls[0][1].read_text(encoding="utf-8"))["results"]
    assert not list((tmp_path / ".humlit").glob("*.tmp"))


def test_corrupt_cache_is_backed_up_and_reported_on_stderr(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / ".humlit"
    cache_dir.mkdir()
    (cache_dir / "broken.json").write_text("{not-json", encoding="utf-8")

    stderr = io.StringIO()
    with redirect_stderr(stderr):
        result = search._cache_get("broken")

    assert result is None
    assert list(cache_dir.glob("broken.json.corrupt-*"))
    assert "corrupt" in stderr.getvalue().lower()
