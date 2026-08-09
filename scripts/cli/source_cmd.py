from __future__ import annotations

import json
import sys
from pathlib import Path

from cli._common import _output


def cmd_cite_source_template(args):
    """输出指定史料类型的字段模板。"""
    from core.source_citation import build_source_template, SOURCE_CATEGORIES
    if args.type not in SOURCE_CATEGORIES:
        _output({"status": "error", "code": "INVALID_SOURCE_CATEGORY",
                 "message": f"未知史料类型: {args.type}", "valid": list(SOURCE_CATEGORIES)})
        return
    tpl = build_source_template(args.type)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(tpl, ensure_ascii=False, indent=2), encoding="utf-8")
        _output({"status": "success", "message": f"模板已写入: {args.output}", "output": args.output})
    else:
        print(json.dumps(tpl, ensure_ascii=False, indent=2))


def cmd_cite_source(args):
    """史料条目 JSON → 脚注体 + GB/T 7714。"""
    from core.source_citation import format_source_entry

    if args.stdin:
        raw = sys.stdin.read()
    else:
        if not args.filepath:
            _output({"status": "error", "code": "FILE_NOT_FOUND", "message": "需提供条目 JSON 文件或 --stdin"})
            return
        path = Path(args.filepath)
        if not path.exists():
            _output({"status": "error", "code": "FILE_NOT_FOUND", "message": f"文件不存在: {args.filepath}"})
            return
        raw = path.read_text(encoding="utf-8")

    try:
        data = json.loads(raw)
    except Exception as e:
        _output({"status": "error", "code": "ENTRY_PARSE_FAILED", "message": f"JSON 解析失败: {e}"})
        return

    entries = data if isinstance(data, list) else [data]
    if not entries:
        _output({"status": "error", "code": "EMPTY_ENTRIES", "message": "条目为空"})
        return

    start = args.start_index or 1
    results = [format_source_entry(e, start + i, style=args.style) for i, e in enumerate(entries)]

    if args.raw:
        lines = []
        if args.style in ("footnote", "both"):
            lines += [r["footnote"] for r in results if r.get("footnote")]
        if args.style in ("gbt7714", "both"):
            if lines:
                lines.append("")
                lines.append("参考文献：")
            lines += [r["gbt7714"] for r in results if r.get("gbt7714")]
        print("\n".join(lines))
    else:
        _output({"status": "success", "count": len(results), "style": args.style, "entries": results})


def add_parser(sub):
    # cite-source-template
    p_tpl = sub.add_parser("cite-source-template", help="输出史料字段模板（按类型）")
    p_tpl.add_argument("--type", required=True,
                       help="史料类型: ancient/archive/gazetteer/epigraph/periodical/genealogy/oral")
    p_tpl.add_argument("--output", help="模板输出路径（默认打印）")
    p_tpl.set_defaults(func=cmd_cite_source_template)

    # cite-source
    p_src = sub.add_parser("cite-source", help="史料条目 JSON → 脚注体 + GB/T 7714")
    p_src.add_argument("filepath", nargs="?", help="史料条目 JSON 文件（单条或数组）")
    p_src.add_argument("--stdin", action="store_true", help="从标准输入读 JSON")
    p_src.add_argument("--style", choices=["footnote", "gbt7714", "both"], default="both",
                       help="输出体例（默认 both）")
    p_src.add_argument("--start-index", dest="start_index", type=int, default=1, help="起始序号")
    p_src.add_argument("--raw", action="store_true", help="输出纯文本而非 JSON")
    p_src.set_defaults(func=cmd_cite_source)
