import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cli.registry import COMMANDS, modules_for  # noqa: E402

EXPECTED_COMMANDS = {
    "search", "batch-search", "trends", "citations",
    "download", "batch-download",
    "detail", "auth-cnki", "read-detail",
    "review", "write", "validate", "topics", "projects", "library",
    "cite", "export", "import",
    "write-docx", "patch-docx", "read-paper", "pdf-meta",
    "check", "clean-cache", "workflows",
    "format-profile", "format-check", "format-apply",
    "review-rubric", "review-signals",
    "cite-source", "cite-source-template",
    "polish-signals",
    "journal-profile", "journal-check",
    "qual-codebook-template", "qual-code",
    "theory-catalog", "theory-match",
}


def test_all_commands_registered():
    assert set(COMMANDS.keys()) == EXPECTED_COMMANDS
    assert len(COMMANDS) == 39


def test_modules_for_dedupes():
    mods = modules_for(["search", "batch-search", "trends"])
    assert mods == ["cli.search_cmd"]


def test_registry_values_are_strings_not_modules():
    # 注册表只存路径字符串，保证不预导入
    assert all(isinstance(v, str) for v in COMMANDS.values())
