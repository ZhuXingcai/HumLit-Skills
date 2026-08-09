from __future__ import annotations

import json
import sys
from pathlib import Path

from cli._common import _output


def _read_text(filepath: str, use_stdin: bool):
    """返回 (text, error_dict)。"""
    if use_stdin:
        return sys.stdin.read(), None
    if not filepath:
        return None, {"status": "error", "code": "FILE_NOT_FOUND", "message": "需提供文件或 --stdin"}
    path = Path(filepath)
    if not path.exists():
        return None, {"status": "error", "code": "FILE_NOT_FOUND", "message": f"文件不存在: {filepath}"}
    suffix = path.suffix.lower()
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError:
            return None, {"status": "error", "code": "MISSING_DEPENDENCY", "message": "缺少 python-docx 依赖"}
        try:
            doc = Document(str(path))
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip()), None
        except Exception as e:
            return None, {"status": "error", "code": "DOCX_PARSE_FAILED", "message": f"docx 解析失败: {e}"}
    if suffix in (".md", ".markdown", ".txt"):
        for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312", "gb18030"):
            try:
                return path.read_text(encoding=enc), None
            except (UnicodeDecodeError, LookupError):
                continue
        return None, {"status": "error", "code": "ENCODING_ERROR", "message": "无法识别文件编码"}
    return None, {"status": "error", "code": "UNSUPPORTED_FORMAT", "message": f"不支持的格式: {suffix}"}


def cmd_qual_codebook_template(args):
    """输出编码簿模板。"""
    from core.qual_coding import build_codebook_template
    tpl = build_codebook_template()
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(tpl, ensure_ascii=False, indent=2), encoding="utf-8")
        _output({"status": "success", "message": f"模板已写入: {args.output}", "output": args.output})
    else:
        print(json.dumps(tpl, ensure_ascii=False, indent=2))


def cmd_qual_code(args):
    """按编码簿标注文本 + 频次/共现统计。"""
    from core.qual_coding import validate_codebook, load_codebook, code_text

    cbpath = Path(args.codebook)
    if not cbpath.exists():
        _output({"status": "error", "code": "FILE_NOT_FOUND", "message": f"编码簿不存在: {args.codebook}"})
        return
    try:
        cb = load_codebook(str(cbpath))
    except Exception as e:
        _output({"status": "error", "code": "CODEBOOK_PARSE_FAILED", "message": f"编码簿 JSON 解析失败: {e}"})
        return
    errors = validate_codebook(cb)
    if errors:
        bad_pattern = any("正则非法" in e["message"] for e in errors)
        _output({"status": "error",
                 "code": "BAD_PATTERN" if bad_pattern else "CODEBOOK_INVALID",
                 "errors": errors, "message": f"编码簿有 {len(errors)} 处问题"})
        return

    text, err = _read_text(args.filepath, args.stdin)
    if err:
        _output(err); return

    report = code_text(text or "", cb)
    out = {"status": "success", "codebook": cb.get("name"),
           "file": args.filepath or "<stdin>", **report}

    if args.raw:
        s = report["summary"]
        lines = [f"编码：{cb.get('name')}  {s['codes']} 个编码 / {s['total_hits']} 次命中 / "
                 f"{s['coded_paragraphs']} 段已编码 / {s['uncoded_paragraphs']} 段未编码"]
        for c in report["codes"]:
            lines.append(f"  [{c['code']}] {c['hits']} 次 / {c['paragraphs']} 段")
        if report["cooccurrence"]:
            lines.append("共现 Top：")
            for c in report["cooccurrence"][:10]:
                lines.append(f"  {c['a']} × {c['b']}: {c['count']}")
        print("\n".join(lines))
    else:
        _output(out)


def add_parser(sub):
    # qual-codebook-template
    p_tpl = sub.add_parser("qual-codebook-template", help="生成质性编码簿模板")
    p_tpl.add_argument("--output", help="模板输出路径（默认打印到 stdout）")
    p_tpl.set_defaults(func=cmd_qual_codebook_template)

    # qual-code
    p_code = sub.add_parser("qual-code", help="按编码簿标注文本 + 频次/共现统计")
    p_code.add_argument("filepath", nargs="?", help="访谈/田野文本（.docx/.md/.txt）")
    p_code.add_argument("--codebook", required=True, help="编码簿 JSON 文件")
    p_code.add_argument("--stdin", action="store_true", help="从标准输入读文本")
    p_code.add_argument("--raw", action="store_true", help="输出纯文本而非 JSON")
    p_code.set_defaults(func=cmd_qual_code)
