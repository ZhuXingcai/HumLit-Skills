from __future__ import annotations

import json
from pathlib import Path

from cli._common import _output


def _resolve_theories(library_path: str):
    """加载内置库并按需合并自定义库；返回 (theories, error_dict)。"""
    from core import theory_catalog as TC
    theories = TC.THEORIES
    if library_path:
        path = Path(library_path)
        if not path.exists():
            return None, {"status": "error", "code": "FILE_NOT_FOUND", "message": f"自定义库不存在: {library_path}"}
        try:
            extra = TC.load_library(str(path))
        except TC.LibraryValidationError as e:
            return None, {
                "status": "error",
                "code": "LIBRARY_INVALID",
                "errors": e.errors,
                "message": f"自定义理论库有 {len(e.errors)} 处问题",
            }
        except Exception as e:
            return None, {"status": "error", "code": "LIBRARY_PARSE_FAILED", "message": f"自定义库解析失败: {e}"}
        errors = TC.validate_library(extra)
        if errors:
            return None, {
                "status": "error",
                "code": "LIBRARY_INVALID",
                "errors": errors,
                "message": f"自定义理论库有 {len(errors)} 处问题",
            }
        theories = TC.merge_libraries(theories, extra)
    return theories, None


def cmd_theory_catalog(args):
    """浏览/检索理论库。"""
    from core import theory_catalog as TC
    theories, err = _resolve_theories(args.library)
    if err:
        _output(err); return
    result = TC.list_theories(theories, discipline=args.discipline, query=args.query)
    if args.raw:
        lines = [f"理论库：{len(result)} 条"
                 + (f"（学科={args.discipline}）" if args.discipline else "")
                 + (f"（query={args.query}）" if args.query else "")]
        for t in result:
            lines.append(f"  [{t.get('discipline')}] {t.get('name')}（{t.get('proposer')}）：{t.get('summary')}")
        print("\n".join(lines))
    else:
        _output({"status": "success", "count": len(result),
                 "disciplines": TC.DISCIPLINES, "theories": result})


def cmd_theory_match(args):
    """据关键词匹配候选理论。"""
    from core import theory_catalog as TC
    if not args.keywords or not args.keywords.strip():
        _output({"status": "error", "code": "NO_KEYWORDS", "message": "需用 --keywords 提供关键词（逗号分隔）"})
        return
    theories, err = _resolve_theories(args.library)
    if err:
        _output(err); return
    if args.discipline:
        theories = TC.list_theories(theories, discipline=args.discipline)
    keywords = [k.strip() for k in args.keywords.replace("，", ",").split(",") if k.strip()]
    matches = TC.match_theories(theories, keywords, top=args.top)
    if args.raw:
        lines = [f"关键词匹配：{keywords} → {len(matches)} 条候选"]
        for m in matches:
            lines.append(f"  [{m['score']}分] {m['name']}（{m['discipline']}）命中 {m['matched']}：{m['summary']}")
        print("\n".join(lines))
    else:
        _output({"status": "success", "keywords": keywords, "count": len(matches), "matches": matches})


def add_parser(sub):
    # theory-catalog
    p_cat = sub.add_parser("theory-catalog", help="浏览/检索人文社科理论库")
    p_cat.add_argument("--discipline", help="按学科过滤（社会学/政治学/传播学等）")
    p_cat.add_argument("--query", help="按关键词过滤理论名/简介/概念")
    p_cat.add_argument("--library", help="叠加自定义理论库 JSON")
    p_cat.add_argument("--raw", action="store_true", help="输出纯文本而非 JSON")
    p_cat.set_defaults(func=cmd_theory_catalog)

    # theory-match
    p_match = sub.add_parser("theory-match", help="据研究关键词匹配候选理论框架")
    p_match.add_argument("--keywords", required=True, help="研究关键词，逗号分隔，如 '信任,社会资本,弱关系'")
    p_match.add_argument("--top", type=int, default=8, help="返回候选数（默认 8）")
    p_match.add_argument("--discipline", help="限定学科")
    p_match.add_argument("--library", help="叠加自定义理论库 JSON")
    p_match.add_argument("--raw", action="store_true", help="输出纯文本而非 JSON")
    p_match.set_defaults(func=cmd_theory_match)
