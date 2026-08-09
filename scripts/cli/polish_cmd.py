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


def cmd_polish_signals(args):
    """中文学术表达诊断信号（脚本只诊断，Agent 润色）。"""
    from core.zh_polish import diagnose

    text, err = _read_text(args.filepath, args.stdin)
    if err:
        _output(err); return

    report = diagnose(text or "", max_sentence=args.max_sentence)
    out = {"status": "success", "file": args.filepath or "<stdin>", **report}

    if args.raw:
        lines = [f"诊断：{report['summary']['issues']} 处问题 / "
                 f"{report['summary']['sentences']} 句 / {report['summary']['paragraphs']} 段"]
        for i in report["issues"]:
            lines.append(f"[{i['locator']}] {i['type']}: {i['detail']} —— {i['excerpt']}")
        print("\n".join(lines))
    else:
        _output(out)


def add_parser(sub):
    p = sub.add_parser("polish-signals", help="中文学术表达诊断（超长句/口语化/主观/标点等）")
    p.add_argument("filepath", nargs="?", help="文稿文件（.md/.txt/.docx）")
    p.add_argument("--stdin", action="store_true", help="从标准输入读文本")
    p.add_argument("--max-sentence", dest="max_sentence", type=int, default=80,
                   help="超长句阈值（中文字数，默认 80）")
    p.add_argument("--raw", action="store_true", help="输出纯文本而非 JSON")
    p.set_defaults(func=cmd_polish_signals)
