import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core.cnki import driver as cnki_driver  # noqa: E402
from core.cnki import search_cnki  # noqa: E402
from smoke_test import run_live  # noqa: E402


RUN_LIVE = os.environ.get("HUMLIT_RUN_LIVE_TESTS") == "1"
RUN_CNKI = os.environ.get("HUMLIT_RUN_CNKI_TESTS") == "1"
RUN_CNKI_DESKTOP = os.environ.get("HUMLIT_RUN_CNKI_DESKTOP_TESTS") == "1"


@pytest.mark.live
@pytest.mark.skipif(
    not RUN_LIVE,
    reason="set HUMLIT_RUN_LIVE_TESTS=1 to call public scholarly services",
)
@pytest.mark.parametrize(
    "source",
    [
        "openalex",
        "semantic",
        "arxiv",
        "nssd",
        "dblp",
        "oa-download",
        "citations",
    ],
)
def test_live_capability_returns_verified_artifact(source):
    check = run_live([source])[0]

    if (
        source == "semantic"
        and check["status"] == "error"
        and "API_RATE_LIMIT" in check.get("error", "")
    ):
        pytest.xfail("Semantic Scholar anonymous API rate limit")

    assert check["status"] == "success", check
    assert check.get("details"), check


@pytest.mark.cnki
@pytest.mark.skipif(
    not RUN_CNKI,
    reason="set HUMLIT_RUN_CNKI_TESTS=1 to probe CNKI network access",
)
def test_cnki_network_is_reachable():
    accessible, message = cnki_driver.check_cnki_access()

    assert accessible, message
    assert message


@pytest.mark.cnki
@pytest.mark.skipif(
    not RUN_CNKI_DESKTOP,
    reason=(
        "set HUMLIT_RUN_CNKI_DESKTOP_TESTS=1 to launch a real CNKI browser search"
    ),
)
def test_cnki_desktop_search_returns_titled_record():
    results = search_cnki("数字人文", pages=1)

    assert results
    assert results[0].get("status") != "error", results[0]
    assert any(item.get("title") for item in results)
