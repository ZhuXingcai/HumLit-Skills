import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from smoke_test import classify_live_status, summarize_checks  # noqa: E402
from verify_skill_architecture import (  # noqa: E402
    _text_sha256,
    validate_repository,
)


def test_repository_skill_architecture_is_consistent():
    report = validate_repository(ROOT)

    assert report.errors == ()
    assert report.stats["tasks"] == 13
    assert report.stats["commands"] == 39
    assert report.stats["capabilities"] == 17
    assert report.stats["routing_cases"] == 48
    assert report.stats["positive_cases"] == 24
    assert report.stats["negative_cases"] == 12
    assert report.stats["ambiguous_cases"] == 12


def test_evidence_hash_ignores_platform_line_endings(tmp_path):
    lf_path = tmp_path / "lf.md"
    crlf_path = tmp_path / "crlf.md"
    lf_path.write_bytes(b"first\nsecond\n")
    crlf_path.write_bytes(b"first\r\nsecond\r\n")

    assert _text_sha256(lf_path) == _text_sha256(crlf_path)


def test_semantic_rate_limit_without_key_is_conditional():
    payload = {
        "status": "error",
        "code": "API_RATE_LIMIT",
        "message": "rate limited",
    }

    assert classify_live_status(
        "semantic",
        payload,
        api_key_configured=False,
    ) == "conditional"


def test_semantic_rate_limit_with_key_is_error():
    payload = {
        "status": "error",
        "code": "API_RATE_LIMIT",
        "message": "rate limited",
    }

    assert classify_live_status(
        "semantic",
        payload,
        api_key_configured=True,
    ) == "error"


def test_schema_error_is_never_conditional():
    payload = {
        "status": "error",
        "code": "SOURCE_SCHEMA_ERROR",
        "message": "schema changed",
    }

    assert classify_live_status(
        "semantic",
        payload,
        api_key_configured=False,
    ) == "error"


def test_conditional_summary_does_not_fail_process():
    payload, exit_code = summarize_checks(
        "live",
        [
            {
                "id": "live_semantic",
                "status": "conditional",
                "details": {"code": "API_RATE_LIMIT"},
            }
        ],
    )

    assert exit_code == 0
    assert payload["status"] == "conditional"
    assert payload["passed"] == 0
    assert payload["conditional"] == 1
    assert payload["failed"] == 0


def test_error_summary_fails_process():
    payload, exit_code = summarize_checks(
        "live",
        [
            {
                "id": "live_semantic",
                "status": "error",
                "error": "SOURCE_SCHEMA_ERROR",
            }
        ],
    )

    assert exit_code == 1
    assert payload["status"] == "error"
    assert payload["conditional"] == 0
    assert payload["failed"] == 1
