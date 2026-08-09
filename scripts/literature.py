"""
literature.py - HumLit Skills 统一 CLI 入口 (v1.0.0)
用法:
  python literature.py search "关键词" [--project 课题名] [--source cnki|openalex|semantic|arxiv|nssd|dblp|api|all] [--doc-type master] [--field 摘要] [--author] [--journal] [--download] ...
  python literature.py batch-search "词1" "词2" ... [--project 课题名] [--query-file kw.txt] [--core CSSCI] [--doc-type master] [--field 摘要] [--author] [--journal] [--append]
  python literature.py read-detail [--project 课题名] [--top-n 5] [--fulltext]
  python literature.py read-paper <论文.docx> [--output paper.txt]
  python literature.py download <url_or_doi> [--dir ./papers] [--doi DOI]
  python literature.py batch-download --from-session [--top-n 20] [--dir ./papers]
  python literature.py batch-download url1 url2 ... [--dir ./papers]
  python literature.py detail <cnki_url>
  python literature.py export --format bibtex|ris|markdown|json|excel|gbt7714|footnote|apa|mla|chicago [--output file]
  python literature.py cite --style gbt7714|gb|footnote|apa|mla|chicago
  python literature.py import <filepath>
  python literature.py write-docx <draft.md> [--output 论文.docx]
  python literature.py patch-docx <原论文.docx> --patch patch.json [--output 修改后.docx]
  python literature.py citations <DOI|URL> [--direction citing|cited|both] [--limit 20]
  python literature.py trends                  # 研究趋势（基于会话数据）
  python literature.py review [--project 课题名] [--topic 综述主题] [--auto-detail] [--output review.md]
  python literature.py write [--project 课题名] [--topic 主题] [--mode outline|draft|section] [--section 章节名] [--format markdown|docx] [--with-citations] [--validate]
  python literature.py validate [--project 课题名] [--topic 主题] [--file draft.md]
  python literature.py topics [--project 课题名] [--topic 主题]
  python literature.py check                   # 环境自检
  python literature.py clean-cache [--all] [--dry-run]  # 缓存清理

子命令实现见 cli/*_cmd.py；逻辑层见 core/。
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        encoding = getattr(stream, "encoding", None)
        reconfigure = getattr(stream, "reconfigure", None)
        if encoding and encoding.lower() != "utf-8" and callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


_configure_utf8_stdio()

_script_dir = str(Path(__file__).parent)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from cli._common import SessionDataError, __version__, _output  # noqa: E402
from cli.registry import COMMANDS  # noqa: E402


def _detect_command(argv) -> str | None:
    """取第一个不以 '-' 开头的 token 作为候选命令。

    目前唯一的全局选项是 --version（action，无取值），无需跳过选项值。
    """
    for tok in argv:
        if not tok.startswith("-"):
            return tok
    return None


def main(*, prog: str = "humlit"):
    parser = argparse.ArgumentParser(
        prog=prog,
        description="HumLit Skills - 学术文献检索工具",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    argv = sys.argv[1:]
    cmd = _detect_command(argv)

    if cmd and cmd in COMMANDS:
        # 惰性加载：只导入该命令所属模块，纯 API 命令不触碰 cnki/selenium
        importlib.import_module(COMMANDS[cmd]).add_parser(sub)
        args = parser.parse_args()
        try:
            args.func(args)
        except SessionDataError as exc:
            _output(exc.as_dict())
        return

    # 无命令 / --help / 未知命令：注册全部命令以输出完整帮助或标准报错
    for modpath in dict.fromkeys(COMMANDS.values()):
        importlib.import_module(modpath).add_parser(sub)
    args = parser.parse_args()
    if not getattr(args, "command", None):
        parser.print_help()
        return
    try:
        args.func(args)
    except SessionDataError as exc:
        _output(exc.as_dict())


if __name__ == "__main__":
    main()
