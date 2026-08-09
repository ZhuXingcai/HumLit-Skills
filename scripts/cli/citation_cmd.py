from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.search import resolve_crossref
from core.formatter import export_papers, generate_reference_list
from cli._common import (
    CITATION_STYLE_CHOICES,
    _output, _load_session, _save_session, _session_project, _is_cnki_paper,
)


def cmd_export(args):
    papers = _load_session(_session_project(args))
    if not papers:
        _output({"status": "error", "code": "NO_SESSION_DATA", "message": "没有可导出的数据，请先执行 search、batch-search 或 import"})
        return

    result = export_papers(papers, args.export_format, args.output)
    if isinstance(result, dict) and result.get("status") == "error":
        _output(result)
        return
    if args.raw:
        print(result)
    else:
        _output({"status": "success", "project": _session_project(args), "format": args.export_format,
                 "output_file": args.output, "content": result})


def cmd_cite(args):
    papers = _load_session(_session_project(args))
    if not papers:
        _output({"status": "error", "code": "NO_SESSION_DATA", "message": "没有可格式化的数据，请先执行 search、batch-search 或 import"})
        return

    # 对缺少卷期页码的知网论文，自动走 detail 补全
    cnki_need_enrich = [
        (i, p) for i, p in enumerate(papers)
        if _is_cnki_paper(p) and p.get("url") and not p.get("pages") and "cnki.net" in p.get("url", "")
    ]
    if cnki_need_enrich:
        print(f"[cite] 正在补全 {len(cnki_need_enrich)} 篇知网论文的卷期页码...",
              file=__import__('sys').stderr)
        from core.cnki import get_detail
        for idx, p in cnki_need_enrich:
            detail = get_detail(p["url"])
            if detail and detail.get("status") != "error":
                for k in ("volume", "issue", "pages", "doi", "year", "journal"):
                    if detail.get(k) and not p.get(k):
                        p[k] = detail[k]
            time.sleep(1)

    enriched = []
    for i, p in enumerate(papers):
        if p.get("doi") and not p.get("volume"):
            if i > 0:
                time.sleep(1)
            crossref_data = resolve_crossref(p["doi"])
            if crossref_data:
                p.update({k: v for k, v in crossref_data.items() if v and not p.get(k)})
        enriched.append(p)

    ref_list = generate_reference_list(enriched, args.style or "gbt7714")
    if args.raw:
        print(ref_list)
    else:
        _output({"status": "success", "project": _session_project(args), "style": args.style or "gbt7714",
                 "count": len(enriched), "references": ref_list})


def cmd_import(args):
    from core.cnki import parse_cnki_export
    results = parse_cnki_export(args.filepath)
    if results and not (len(results) == 1 and results[0].get("status") == "error"):
        _save_session(results, project=_session_project(args))
        _output({"status": "success", "count": len(results), "results": results})
    else:
        _output(results[0] if results else {"status": "error", "code": "IMPORT_PARSE_FAILED", "message": "解析失败"})


def add_parser(sub):
    # export
    p_export = sub.add_parser("export", help="导出上次搜索结果")
    p_export.add_argument("--format", dest="export_format", required=True,
                          choices=["bibtex", "ris", "markdown", "json", "excel",
                                   "gbt7714", "footnote", "apa", "mla", "chicago"])
    p_export.add_argument("--output", help="输出文件路径")
    p_export.add_argument("--raw", action="store_true", help="输出纯文本而非 JSON")
    p_export.add_argument("--project", help="课题文献库名称")
    p_export.set_defaults(func=cmd_export)

    # cite
    p_cite = sub.add_parser("cite", help="生成引用格式")
    p_cite.add_argument("--style", default="gbt7714",
                        choices=CITATION_STYLE_CHOICES)
    p_cite.add_argument("--raw", action="store_true", help="输出纯文本而非 JSON")
    p_cite.add_argument("--project", help="课题文献库名称")
    p_cite.set_defaults(func=cmd_cite)

    # import
    p_import = sub.add_parser("import", help="导入知网导出的题录文件")
    p_import.add_argument("filepath", help="题录文件路径")
    p_import.add_argument("--project", help="课题文献库名称")
    p_import.set_defaults(func=cmd_import)
