from __future__ import annotations

import json
from pathlib import Path

from cli._common import _output


def cmd_format_profile(args):
    """profile 工具：--template 产出模板；--validate 校验已填 profile。"""
    from core.thesis_format import profile as P

    if args.validate:
        path = Path(args.validate)
        if not path.exists():
            _output({"status": "error", "code": "FILE_NOT_FOUND", "message": f"文件不存在: {args.validate}"})
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            _output({"status": "error", "code": "PROFILE_PARSE_FAILED", "message": f"JSON 解析失败: {e}"})
            return
        errors = P.validate_profile(data)
        if errors:
            _output({"status": "error", "code": "PROFILE_INVALID", "errors": errors,
                     "message": f"profile 有 {len(errors)} 处问题"})
        else:
            _output({"status": "success", "message": "profile 合法", "name": data.get("name")})
        return

    # 默认/--template：输出模板
    tpl = P.build_template()
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(tpl, ensure_ascii=False, indent=2), encoding="utf-8")
        _output({"status": "success", "message": f"模板已写入: {args.output}", "output": args.output})
    else:
        print(json.dumps(tpl, ensure_ascii=False, indent=2))


def _load_model(filepath: str):
    """按扩展名解析为 DocModel；返回 (model, error_dict)。"""
    from core.thesis_format import inspect as I
    path = Path(filepath)
    if not path.exists():
        return None, {"status": "error", "code": "FILE_NOT_FOUND", "message": f"文件不存在: {filepath}"}
    suffix = path.suffix.lower()
    if suffix == ".docx":
        try:
            return I.inspect_docx(str(path)), None
        except ImportError:
            return None, {"status": "error", "code": "MISSING_DEPENDENCY", "message": "缺少 python-docx 依赖"}
        except Exception as e:
            return None, {"status": "error", "code": "DOCX_PARSE_FAILED", "message": f"docx 解析失败: {e}"}
    if suffix in (".md", ".markdown", ".txt"):
        text = None
        for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312", "gb18030"):
            try:
                text = path.read_text(encoding=enc); break
            except (UnicodeDecodeError, LookupError):
                continue
        if text is None:
            return None, {"status": "error", "code": "ENCODING_ERROR", "message": "无法识别文件编码"}
        return I.inspect_markdown(text), None
    return None, {"status": "error", "code": "UNSUPPORTED_FORMAT", "message": f"不支持的格式: {suffix}"}


def _resolve_profile(profile_path: str):
    """加载并校验 profile；返回 (profile, error_dict)。"""
    from core.thesis_format import profile as P
    path = Path(profile_path)
    if not path.exists():
        return None, {"status": "error", "code": "FILE_NOT_FOUND", "message": f"profile 不存在: {profile_path}"}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return None, {"status": "error", "code": "PROFILE_PARSE_FAILED", "message": f"profile JSON 解析失败: {e}"}
    errors = P.validate_profile(raw)
    if errors:
        return None, {"status": "error", "code": "PROFILE_INVALID", "errors": errors,
                      "message": f"profile 有 {len(errors)} 处问题"}
    return P.load_profile(str(path)), None


def cmd_format_check(args):
    """格式 linter：对照 profile 输出问题清单。"""
    from core.thesis_format import check as C

    profile, err = _resolve_profile(args.profile)
    if err:
        _output(err); return
    model, err = _load_model(args.filepath)
    if err:
        _output(err); return

    report = C.check_format(model, profile)
    _output({"status": "success", "profile": profile.get("name"),
             "file": args.filepath, **report})


def cmd_format_apply(args):
    """套用 profile：.docx 原地重排 / .md 生成合规 .docx。"""
    from core.thesis_format import apply as A

    profile, err = _resolve_profile(args.profile)
    if err:
        _output(err); return

    path = Path(args.filepath)
    if not path.exists():
        _output({"status": "error", "code": "FILE_NOT_FOUND", "message": f"文件不存在: {args.filepath}"})
        return

    suffix = path.suffix.lower()
    out = args.output or str(path.with_name(path.stem + "_formatted.docx"))

    if suffix == ".docx":
        _output(A.apply_to_docx(str(path), profile, out))
    elif suffix in (".md", ".markdown", ".txt"):
        text = None
        for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312", "gb18030"):
            try:
                text = path.read_text(encoding=enc); break
            except (UnicodeDecodeError, LookupError):
                continue
        if text is None:
            _output({"status": "error", "code": "ENCODING_ERROR", "message": "无法识别文件编码"})
            return
        _output(A.apply_from_markdown(text, profile, out))
    else:
        _output({"status": "error", "code": "UNSUPPORTED_FORMAT", "message": f"不支持的格式: {suffix}"})


def add_parser(sub):
    # format-profile
    p_prof = sub.add_parser("format-profile", help="生成 profile 模板 / 校验 profile")
    p_prof.add_argument("--template", action="store_true", help="输出 profile 模板（默认动作）")
    p_prof.add_argument("--validate", help="校验指定 profile JSON 文件")
    p_prof.add_argument("--output", help="模板输出路径（默认打印到 stdout）")
    p_prof.set_defaults(func=cmd_format_profile)

    # format-check
    p_chk = sub.add_parser("format-check", help="检测论文是否符合 profile 格式规范")
    p_chk.add_argument("filepath", help="论文文件（.docx/.md）")
    p_chk.add_argument("--profile", required=True, help="格式规范 profile JSON")
    p_chk.add_argument("--raw", action="store_true", help="输出纯 JSON")
    p_chk.set_defaults(func=cmd_format_check)

    # format-apply
    p_app = sub.add_parser("format-apply", help="按 profile 套用格式产出合规 .docx")
    p_app.add_argument("filepath", help="论文文件（.docx 原地重排 / .md 生成）")
    p_app.add_argument("--profile", required=True, help="格式规范 profile JSON")
    p_app.add_argument("--output", help="输出 .docx 路径（默认 原名_formatted.docx）")
    p_app.add_argument("--only", help="仅套用指定维度，逗号分隔（预留）")
    p_app.set_defaults(func=cmd_format_apply)
