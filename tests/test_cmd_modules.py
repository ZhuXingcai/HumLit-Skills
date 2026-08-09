import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import argparse  # noqa: E402


def _build(modpath, cmd):
    import importlib
    mod = importlib.import_module(modpath)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    mod.add_parser(sub)
    return parser


def test_search_cmd_registers_parsers():
    parser = _build("cli.search_cmd", "search")
    ns = parser.parse_args(["search", "深度学习"])
    assert ns.command == "search"
    assert callable(ns.func)
    assert ns.query == "深度学习"


def test_download_cmd_registers_parsers():
    parser = _build("cli.download_cmd", "download")
    ns = parser.parse_args(["download", "https://x.cnki.net/abc"])
    assert ns.command == "download"
    assert callable(ns.func)
    ns2 = parser.parse_args(["batch-download", "--from-session"])
    assert ns2.command == "batch-download"
    assert callable(ns2.func)


def test_cnki_cmd_registers_parsers():
    parser = _build("cli.cnki_cmd", "detail")
    ns = parser.parse_args(["detail", "https://x.cnki.net/abc"])
    assert ns.command == "detail"
    assert callable(ns.func)
    ns2 = parser.parse_args(["read-detail", "--indices", "1,3-5"])
    assert ns2.command == "read-detail"
    assert callable(ns2.func)
    ns3 = parser.parse_args(["auth-cnki"])
    assert ns3.command == "auth-cnki"
    assert callable(ns3.func)


def test_review_cmd_registers_parsers():
    parser = _build("cli.review_cmd", "review")
    for cmd in ["review", "write", "validate", "topics", "projects", "library"]:
        pass
    ns = parser.parse_args(["review", "--topic", "知识管理"])
    assert ns.command == "review"
    assert callable(ns.func)
    ns2 = parser.parse_args(["write", "--mode", "outline"])
    assert ns2.command == "write" and callable(ns2.func)
    ns3 = parser.parse_args(["projects"])
    assert ns3.command == "projects" and callable(ns3.func)
    ns4 = parser.parse_args(["library", "--limit", "5"])
    assert ns4.command == "library" and callable(ns4.func)
    ns5 = parser.parse_args(["validate"])
    assert ns5.command == "validate" and callable(ns5.func)
    ns6 = parser.parse_args(["topics"])
    assert ns6.command == "topics" and callable(ns6.func)


def test_citation_cmd_registers_parsers():
    parser = _build("cli.citation_cmd", "cite")
    ns = parser.parse_args(["cite", "--style", "apa"])
    assert ns.command == "cite" and callable(ns.func)
    ns2 = parser.parse_args(["export", "--format", "bibtex"])
    assert ns2.command == "export" and callable(ns2.func)
    ns3 = parser.parse_args(["import", "refs.txt"])
    assert ns3.command == "import" and callable(ns3.func)


def test_docx_cmd_registers_parsers():
    parser = _build("cli.docx_cmd", "write-docx")
    ns = parser.parse_args(["write-docx", "draft.md"])
    assert ns.command == "write-docx" and callable(ns.func)
    ns2 = parser.parse_args(["patch-docx", "a.docx", "--patch", "p.json"])
    assert ns2.command == "patch-docx" and callable(ns2.func)
    ns3 = parser.parse_args(["read-paper", "a.docx"])
    assert ns3.command == "read-paper" and callable(ns3.func)
    ns4 = parser.parse_args(["pdf-meta", "a.pdf"])
    assert ns4.command == "pdf-meta" and callable(ns4.func)


def test_env_cmd_registers_parsers():
    parser = _build("cli.env_cmd", "check")
    ns = parser.parse_args(["check"])
    assert ns.command == "check" and callable(ns.func)
    ns2 = parser.parse_args(["clean-cache", "--all"])
    assert ns2.command == "clean-cache" and callable(ns2.func)
    ns3 = parser.parse_args(["workflows", "--list"])
    assert ns3.command == "workflows" and callable(ns3.func)


def test_format_cmd_registers_parsers():
    parser = _build("cli.format_cmd", "format-profile")
    ns = parser.parse_args(["format-profile", "--template"])
    assert ns.command == "format-profile" and callable(ns.func)
    ns2 = parser.parse_args(["format-check", "thesis.docx", "--profile", "p.json"])
    assert ns2.command == "format-check" and callable(ns2.func)
    assert ns2.profile == "p.json"
    ns3 = parser.parse_args(["format-apply", "thesis.md", "--profile", "p.json"])
    assert ns3.command == "format-apply" and callable(ns3.func)


def test_defense_cmd_registers_parsers():
    parser = _build("cli.defense_cmd", "review-rubric")
    ns = parser.parse_args(["review-rubric", "--template"])
    assert ns.command == "review-rubric" and callable(ns.func)
    ns2 = parser.parse_args(["review-signals", "thesis.docx", "--rubric", "r.json"])
    assert ns2.command == "review-signals" and callable(ns2.func)
    assert ns2.rubric == "r.json"
    ns3 = parser.parse_args(["review-signals", "t.md", "--format-profile", "p.json"])
    assert ns3.format_profile == "p.json"


def test_source_cmd_registers_parsers():
    parser = _build("cli.source_cmd", "cite-source")
    ns = parser.parse_args(["cite-source", "entries.json"])
    assert ns.command == "cite-source" and callable(ns.func)
    assert ns.style == "both"
    ns2 = parser.parse_args(["cite-source-template", "--type", "ancient"])
    assert ns2.command == "cite-source-template" and callable(ns2.func)
    assert ns2.type == "ancient"


def test_polish_cmd_registers_parsers():
    parser = _build("cli.polish_cmd", "polish-signals")
    ns = parser.parse_args(["polish-signals", "draft.md"])
    assert ns.command == "polish-signals" and callable(ns.func)
    ns2 = parser.parse_args(["polish-signals", "--stdin", "--max-sentence", "60"])
    assert ns2.stdin is True and ns2.max_sentence == 60


def test_journal_cmd_registers_parsers():
    parser = _build("cli.journal_cmd", "journal-profile")
    ns = parser.parse_args(["journal-profile", "--template"])
    assert ns.command == "journal-profile" and callable(ns.func)
    ns2 = parser.parse_args(["journal-check", "draft.docx", "--profile", "p.json"])
    assert ns2.command == "journal-check" and callable(ns2.func)
    assert ns2.profile == "p.json"
    ns3 = parser.parse_args(["journal-check", "draft.md"])
    assert ns3.command == "journal-check" and ns3.profile is None


def test_qual_cmd_registers_parsers():
    parser = _build("cli.qual_cmd", "qual-codebook-template")
    ns = parser.parse_args(["qual-codebook-template"])
    assert ns.command == "qual-codebook-template" and callable(ns.func)
    ns2 = parser.parse_args(["qual-code", "interview.md", "--codebook", "cb.json"])
    assert ns2.command == "qual-code" and callable(ns2.func)
    assert ns2.codebook == "cb.json"
    ns3 = parser.parse_args(["qual-code", "--stdin", "--codebook", "cb.json"])
    assert ns3.stdin is True


def test_theory_cmd_registers_parsers():
    parser = _build("cli.theory_cmd", "theory-catalog")
    ns = parser.parse_args(["theory-catalog", "--discipline", "社会学"])
    assert ns.command == "theory-catalog" and callable(ns.func)
    assert ns.discipline == "社会学"
    ns2 = parser.parse_args(["theory-match", "--keywords", "信任,社会资本"])
    assert ns2.command == "theory-match" and callable(ns2.func)
    assert ns2.keywords == "信任,社会资本" and ns2.top == 8
