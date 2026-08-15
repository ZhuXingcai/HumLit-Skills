#!/usr/bin/env python3
"""End-to-end smoke tests for advertised HumLit Skills capabilities."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Union


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "scripts" / "literature.py"


class SmokeFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class SmokeOutcome:
    status: str
    details: Dict[str, Any]


def _run_cli(
    workdir: Path,
    *args: str,
    timeout: int = 60,
    allow_error_payload: bool = False,
) -> Dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(ENTRY), *args],
        cwd=workdir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.returncode != 0:
        raise SmokeFailure(
            f"{' '.join(args)} exited {result.returncode}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SmokeFailure(
            f"{' '.join(args)} polluted stdout: {result.stdout[:300]!r}"
        ) from exc
    if (
        payload.get("status") not in {"success", "partial", "warning"}
        and not allow_error_payload
    ):
        raise SmokeFailure(
            f"{' '.join(args)} returned {payload.get('status')}: "
            f"{payload.get('code', '')} {payload.get('message', '')}".strip()
        )
    return payload


def _record(
    check_id: str,
    run: Callable[[], Union[Dict[str, Any], SmokeOutcome]],
) -> Dict[str, Any]:
    try:
        result = run()
        if isinstance(result, SmokeOutcome):
            return {
                "id": check_id,
                "status": result.status,
                "details": result.details,
            }
        return {"id": check_id, "status": "success", "details": result}
    except Exception as exc:
        return {
            "id": check_id,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _research_library(workdir: Path) -> Dict[str, Any]:
    bib = workdir / "library.bib"
    bib.write_text(
        """
@article{demo1,
  title={数字人文视域下的地方志知识组织},
  author={张三 and 李四},
  journal={数字人文研究},
  year={2024},
  volume={2},
  number={1},
  pages={10--20}
}
@article{demo2,
  title={数字人文与档案知识图谱研究},
  author={王五},
  journal={档案学通讯},
  year={2023},
  volume={5},
  number={2},
  pages={30--42}
}
""".strip(),
        encoding="utf-8",
    )
    project_args = ("--project", "smoke")
    imported = _run_cli(workdir, "import", str(bib), *project_args)
    library = _run_cli(workdir, "library", *project_args)
    citations = _run_cli(workdir, "cite", "--style", "gbt7714", *project_args)
    exported = _run_cli(workdir, "export", "--format", "json", *project_args)
    trends = _run_cli(workdir, "trends", *project_args)
    review = _run_cli(
        workdir,
        "review",
        "--topic",
        "数字人文",
        "--cluster",
        "--gaps",
        *project_args,
    )
    writing = _run_cli(
        workdir,
        "write",
        "--topic",
        "数字人文",
        "--mode",
        "outline",
        "--validate",
        *project_args,
    )
    validation = _run_cli(
        workdir,
        "validate",
        "--topic",
        "数字人文",
        *project_args,
    )
    topics = _run_cli(
        workdir,
        "topics",
        "--topic",
        "数字人文",
        *project_args,
    )
    projects = _run_cli(workdir, "projects")

    if imported.get("count") != 2 or library.get("count") != 2:
        raise SmokeFailure("import -> library did not preserve both records")
    if citations.get("count") != 2 or not citations.get("references"):
        raise SmokeFailure("cite did not format the imported records")
    if not exported.get("content") or trends.get("total") != 2:
        raise SmokeFailure("export or trends did not consume the saved session")
    if not review.get("evidence") or "markdown" not in writing:
        raise SmokeFailure("review/write did not produce a traceable scaffold")
    if "support_counts" not in validation or not topics.get("topics"):
        raise SmokeFailure("validate/topics did not complete")
    if not any(item.get("name") == "smoke" for item in projects.get("projects", [])):
        raise SmokeFailure("project library was not discoverable")
    return {
        "records": library["count"],
        "review_evidence": len(review["evidence"]),
        "topic_hypotheses": topics["count"],
    }


def _document_io(workdir: Path) -> Dict[str, Any]:
    markdown = workdir / "paper.md"
    markdown.write_text(
        "# 数字人文研究\n\n本文讨论地方志知识组织。\n\n## 参考文献\n\n[1] 张三. 测试文献[J]. 学报, 2024.",
        encoding="utf-8",
    )
    docx_path = workdir / "paper.docx"
    created = _run_cli(
        workdir,
        "write-docx",
        str(markdown),
        "--output",
        str(docx_path),
    )
    read_back = _run_cli(workdir, "read-paper", str(docx_path))

    patch = workdir / "patch.json"
    patch.write_text(
        json.dumps(
            {
                "patches": [
                    {
                        "find": "本文讨论地方志知识组织。",
                        "replace": "本文讨论数字人文语境中的地方志知识组织。",
                    }
                ],
                "footnotes": [],
                "append_references": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    patched_path = workdir / "paper_patched.docx"
    patched = _run_cli(
        workdir,
        "patch-docx",
        str(docx_path),
        "--patch",
        str(patch),
        "--output",
        str(patched_path),
    )
    patched_text = _run_cli(workdir, "read-paper", str(patched_path))

    try:
        from pypdf import PdfWriter
    except ImportError as exc:
        raise SmokeFailure("pypdf is missing from the locked runtime") from exc
    pdf_path = workdir / "metadata.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Title": "Smoke Metadata", "/Author": "HumLit Skills"})
    with pdf_path.open("wb") as handle:
        writer.write(handle)
    pdf_meta = _run_cli(workdir, "pdf-meta", str(pdf_path))

    if not docx_path.exists() or created.get("status") != "success":
        raise SmokeFailure("write-docx did not create an artifact")
    if "地方志知识组织" not in read_back.get("text", ""):
        raise SmokeFailure("read-paper did not recover docx text")
    if patched.get("replaced") != 1 or "数字人文语境" not in patched_text.get("text", ""):
        raise SmokeFailure("patch-docx change was not observable after re-reading")
    if pdf_meta.get("title") != "Smoke Metadata":
        raise SmokeFailure("pdf-meta did not read embedded metadata")
    return {
        "docx_bytes": docx_path.stat().st_size,
        "patches_applied": patched["replaced"],
        "pdf_title": pdf_meta["title"],
    }


def _format_and_review(workdir: Path) -> Dict[str, Any]:
    draft = workdir / "thesis.md"
    draft.write_text(
        "摘要\n本文讨论数字人文方法。\n\n关键词：数字人文；地方志\n\n"
        "第一章 引言\n本文系国家社会科学基金项目（17ZDA158）成果。\n\n"
        "参考文献\n[1] 张三. 测试文献[J]. 学报, 2024.",
        encoding="utf-8",
    )
    profile = workdir / "format-profile.json"
    rubric = workdir / "review-rubric.json"
    formatted = workdir / "formatted.docx"

    _run_cli(workdir, "format-profile", "--template", "--output", str(profile))
    checked = _run_cli(
        workdir,
        "format-check",
        str(draft),
        "--profile",
        str(profile),
    )
    applied = _run_cli(
        workdir,
        "format-apply",
        str(draft),
        "--profile",
        str(profile),
        "--output",
        str(formatted),
    )
    _run_cli(workdir, "review-rubric", "--template", "--output", str(rubric))
    signals = _run_cli(
        workdir,
        "review-signals",
        str(draft),
        "--rubric",
        str(rubric),
    )

    if not formatted.exists() or applied.get("status") != "success":
        raise SmokeFailure("format-apply did not create a docx")
    judgment_items = sum(
        len(item.get("needs_human_judgment", []))
        for item in signals.get("signals", {}).values()
    )
    if "summary" not in checked or judgment_items < 1:
        raise SmokeFailure("format/review signals missed their output contract")
    return {
        "format_issues": len(checked.get("issues", [])),
        "unknown_dimensions": checked["summary"].get("unknown_dimensions", []),
        "human_judgment_items": judgment_items,
    }


def _humanities_tools(workdir: Path) -> Dict[str, Any]:
    draft = workdir / "humanities.md"
    draft.write_text(
        "摘要\n其实我觉得这个问题挺重要。\n\n关键词：社会资本；信任\n\n"
        "第一章 引言\n本文系国家社会科学基金项目（17ZDA158）成果，"
        "笔者所在的示例大学开展了相关访谈。\n\n参考文献\n[1] 张三. 测试[J]. 学报, 2024.",
        encoding="utf-8",
    )
    source = workdir / "source.json"
    source.write_text(
        json.dumps(
            {
                "source_category": "ancient",
                "author": "黄宗羲",
                "title": "明儒学案",
                "publisher": "中华书局",
                "year": "1985",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    codebook = workdir / "codebook.json"
    codebook.write_text(
        json.dumps(
            {
                "name": "smoke",
                "codes": [
                    {"code": "信任", "keywords": ["信任"], "patterns": []},
                    {"code": "机构", "keywords": ["大学"], "patterns": []},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    source_template_path = workdir / "source-template.json"
    _run_cli(
        workdir,
        "cite-source-template",
        "--type",
        "ancient",
        "--output",
        str(source_template_path),
    )
    source_template = json.loads(source_template_path.read_text(encoding="utf-8"))
    source_citation = _run_cli(workdir, "cite-source", str(source))
    polish = _run_cli(workdir, "polish-signals", str(draft))
    journal_profile_path = workdir / "journal-profile.json"
    _run_cli(
        workdir,
        "journal-profile",
        "--template",
        "--output",
        str(journal_profile_path),
    )
    journal_profile = json.loads(journal_profile_path.read_text(encoding="utf-8"))
    journal = _run_cli(workdir, "journal-check", str(draft))
    codebook_template_path = workdir / "codebook-template.json"
    _run_cli(
        workdir,
        "qual-codebook-template",
        "--output",
        str(codebook_template_path),
    )
    codebook_template = json.loads(codebook_template_path.read_text(encoding="utf-8"))
    coding = _run_cli(
        workdir,
        "qual-code",
        str(draft),
        "--codebook",
        str(codebook),
    )
    catalog = _run_cli(workdir, "theory-catalog", "--query", "社会资本")
    theory = _run_cli(
        workdir,
        "theory-match",
        "--keywords",
        "社会资本,信任,弱关系",
    )

    if source_template.get("source_category") != "ancient":
        raise SmokeFailure("source template returned the wrong category")
    if source_citation.get("count") != 1:
        raise SmokeFailure("historical citation did not format the record")
    if polish.get("summary", {}).get("issues", 0) < 1:
        raise SmokeFailure("polish diagnostics missed the seeded signal")
    if "journal_system" not in journal_profile or not journal.get("anonymity", {}).get("leaks"):
        raise SmokeFailure("journal profile/preflight did not complete")
    if "codes" not in codebook_template or coding.get("summary", {}).get("total_hits", 0) < 1:
        raise SmokeFailure("deterministic coding did not match the codebook")
    if catalog.get("count", 0) < 1 or theory.get("count", 0) < 1:
        raise SmokeFailure("theory catalog/match returned no candidates")
    return {
        "polish_signals": polish["summary"]["issues"],
        "anonymity_leaks": len(journal["anonymity"]["leaks"]),
        "coding_matches": coding["summary"]["total_hits"],
        "theory_candidates": theory["count"],
    }


def _workflow_routing(workdir: Path) -> Dict[str, Any]:
    listed = _run_cli(workdir, "workflows", "--list")
    dry_run = _run_cli(
        workdir,
        "workflows",
        "--execute",
        "topic_research",
        "--variables",
        json.dumps({"topic": "数字人文", "project": "smoke"}, ensure_ascii=False),
        "--dry-run",
    )
    cache = _run_cli(workdir, "clean-cache", "--dry-run")
    commands = dry_run.get("commands", [])
    if listed.get("count", 0) < 1 or len(commands) != 3:
        raise SmokeFailure("workflow list/render did not complete")
    if "--source api" not in commands[0] or "--async-search" not in commands[0]:
        raise SmokeFailure("topic_research does not use the maintained public aggregate")
    return {
        "workflows": listed["count"],
        "rendered_steps": len(commands),
        "cache_mode": cache.get("mode", "none"),
    }


OFFLINE_CHECKS = {
    "research_library": _research_library,
    "document_io": _document_io,
    "format_and_review": _format_and_review,
    "humanities_tools": _humanities_tools,
    "workflow_routing": _workflow_routing,
}


LIVE_SOURCES = {
    "openalex": ("digital humanities", "openalex"),
    "semantic": ("digital humanities", "semantic"),
    "arxiv": ("large language model", "arxiv"),
    "nssd": ("数字人文", "nssd"),
    "dblp": ("large language model", "dblp"),
}


def classify_live_status(
    source_id: str,
    payload: Dict[str, Any],
    *,
    api_key_configured: bool,
) -> str:
    if payload.get("status") in {"success", "partial", "warning"}:
        return "success"
    if (
        source_id == "semantic"
        and payload.get("code") == "API_RATE_LIMIT"
        and not api_key_configured
    ):
        return "conditional"
    return "error"


def _live_search(
    workdir: Path,
    source_id: str,
) -> Union[Dict[str, Any], SmokeOutcome]:
    query, cli_source = LIVE_SOURCES[source_id]
    payload = _run_cli(
        workdir,
        "search",
        query,
        "--source",
        cli_source,
        "--limit",
        "1",
        timeout=90,
        allow_error_payload=True,
    )
    probe_status = classify_live_status(
        source_id,
        payload,
        api_key_configured=bool(
            os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "").strip()
        ),
    )
    if probe_status == "conditional":
        return SmokeOutcome(
            status="conditional",
            details={
                "code": payload.get("code"),
                "message": payload.get("message"),
                "source": "semantic_scholar",
                "api_key_configured": False,
            },
        )
    if probe_status == "error":
        raise SmokeFailure(
            f"search {query} --source {cli_source} returned "
            f"{payload.get('status')}: {payload.get('code', '')} "
            f"{payload.get('message', '')}".strip()
        )
    if payload.get("count", 0) < 1 or not payload.get("results", [{}])[0].get("title"):
        raise SmokeFailure(f"{source_id} returned no titled record")
    expected_status_key = "semantic_scholar" if source_id == "semantic" else source_id
    source_status = payload.get("source_statuses", {}).get(expected_status_key, {})
    if source_status.get("status") != "success":
        raise SmokeFailure(f"{source_id} source status is {source_status}")
    return {
        "count": payload["count"],
        "title": payload["results"][0]["title"],
    }


def _live_oa_download(workdir: Path) -> Dict[str, Any]:
    payload = _run_cli(
        workdir,
        "download",
        "--doi",
        "10.1038/sdata.2016.18",
        "--dir",
        str(workdir / "papers"),
        timeout=90,
    )
    path = Path(payload.get("path", ""))
    if (
        not path.is_file()
        or not path.read_bytes().startswith(b"%PDF-")
        or payload.get("bytes", 0) < 1000
    ):
        raise SmokeFailure("OA DOI download did not create a verified PDF")
    return {
        "method": payload.get("method"),
        "path": str(path),
        "bytes": payload["bytes"],
    }


def _live_citations(workdir: Path) -> Dict[str, Any]:
    payload = _run_cli(
        workdir,
        "citations",
        "10.1038/sdata.2016.18",
        "--direction",
        "both",
        "--limit",
        "1",
        timeout=90,
    )
    if not payload.get("paper"):
        raise SmokeFailure("citation resolver returned no root paper")
    return {
        "citing": len(payload.get("citing", [])),
        "references": len(payload.get("references", [])),
    }


def run_offline() -> List[Dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="humlit-skills-smoke-") as temp_dir:
        workdir = Path(temp_dir)
        return [
            _record(check_id, lambda run=run: run(workdir))
            for check_id, run in OFFLINE_CHECKS.items()
        ]


def run_live(selected: List[str]) -> List[Dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="humlit-skills-live-") as temp_dir:
        workdir = Path(temp_dir)
        checks = []
        for source_id in selected:
            if source_id in LIVE_SOURCES:
                checks.append(
                    _record(
                        f"live_{source_id}",
                        lambda source_id=source_id: _live_search(workdir, source_id),
                    )
                )
            elif source_id == "oa-download":
                checks.append(
                    _record("live_oa_download", lambda: _live_oa_download(workdir))
                )
            elif source_id == "citations":
                checks.append(_record("live_citations", lambda: _live_citations(workdir)))
            else:
                checks.append({
                    "id": f"live_{source_id}",
                    "status": "error",
                    "error": f"unknown live source: {source_id}",
                })
        return checks


def summarize_checks(
    mode: str,
    checks: List[Dict[str, Any]],
) -> tuple:
    failed = sum(item["status"] == "error" for item in checks)
    conditional = sum(item["status"] == "conditional" for item in checks)
    passed = sum(item["status"] == "success" for item in checks)
    status = "error" if failed else "conditional" if conditional else "success"
    return {
        "status": status,
        "mode": mode,
        "checks": checks,
        "passed": passed,
        "conditional": conditional,
        "failed": failed,
    }, 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["offline", "live", "all"], default="offline")
    parser.add_argument(
        "--sources",
        default="openalex,semantic,arxiv,nssd,dblp,oa-download,citations",
        help="Comma-separated live probes",
    )
    args = parser.parse_args()

    checks: List[Dict[str, Any]] = []
    if args.mode in {"offline", "all"}:
        checks.extend(run_offline())
    if args.mode in {"live", "all"}:
        selected = [item.strip() for item in args.sources.split(",") if item.strip()]
        checks.extend(run_live(selected))

    payload, exit_code = summarize_checks(args.mode, checks)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
