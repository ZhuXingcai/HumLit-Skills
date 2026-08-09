from __future__ import annotations

COMMANDS: dict[str, str] = {
    "search": "cli.search_cmd",      "batch-search": "cli.search_cmd",
    "trends": "cli.search_cmd",      "citations": "cli.search_cmd",
    "download": "cli.download_cmd",  "batch-download": "cli.download_cmd",
    "detail": "cli.cnki_cmd",        "auth-cnki": "cli.cnki_cmd",
    "read-detail": "cli.cnki_cmd",
    "review": "cli.review_cmd",      "write": "cli.review_cmd",
    "validate": "cli.review_cmd",    "topics": "cli.review_cmd",
    "projects": "cli.review_cmd",    "library": "cli.review_cmd",
    "cite": "cli.citation_cmd",      "export": "cli.citation_cmd",
    "import": "cli.citation_cmd",
    "write-docx": "cli.docx_cmd",    "patch-docx": "cli.docx_cmd",
    "read-paper": "cli.docx_cmd",    "pdf-meta": "cli.docx_cmd",
    "check": "cli.env_cmd",          "clean-cache": "cli.env_cmd",
    "workflows": "cli.env_cmd",
    "format-profile": "cli.format_cmd", "format-check": "cli.format_cmd",
    "format-apply": "cli.format_cmd",
    "review-rubric": "cli.defense_cmd", "review-signals": "cli.defense_cmd",
    "cite-source": "cli.source_cmd", "cite-source-template": "cli.source_cmd",
    "polish-signals": "cli.polish_cmd",
    "journal-profile": "cli.journal_cmd", "journal-check": "cli.journal_cmd",
    "qual-codebook-template": "cli.qual_cmd", "qual-code": "cli.qual_cmd",
    "theory-catalog": "cli.theory_cmd", "theory-match": "cli.theory_cmd",
}


def modules_for(commands) -> list[str]:
    """去重保序：一组命令名 → 需导入的模块路径列表。"""
    return list(dict.fromkeys(COMMANDS[c] for c in commands if c in COMMANDS))
