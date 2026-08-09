from __future__ import annotations

import json
from pathlib import Path

from cli._common import _output


def cmd_journal_profile(args):
    """profile 工具：--template 产出模板；--validate 校验已填 profile。"""
    from core import journal_fit as JF

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
        errors = JF.validate_profile(data)
        if errors:
            _output({"status": "error", "code": "PROFILE_INVALID", "errors": errors,
                     "message": f"profile 有 {len(errors)} 处问题"})
        else:
            _output({"status": "success", "message": "profile 合法", "name": data.get("name")})
        return

    tpl = JF.build_template()
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(tpl, ensure_ascii=False, indent=2), encoding="utf-8")
        _output({"status": "success", "message": f"模板已写入: {args.output}", "output": args.output})
    else:
        print(json.dumps(tpl, ensure_ascii=False, indent=2))


def _read_text_and_model(filepath: str):
    """按扩展名解析为 (full_text, DocModel)；返回 (text, model, error_dict)。"""
    from core.thesis_format import inspect as I
    path = Path(filepath)
    if not path.exists():
        return None, None, {"status": "error", "code": "FILE_NOT_FOUND", "message": f"文件不存在: {filepath}"}
    suffix = path.suffix.lower()
    if suffix == ".docx":
        try:
            model = I.inspect_docx(str(path))
        except ImportError:
            return None, None, {"status": "error", "code": "MISSING_DEPENDENCY", "message": "缺少 python-docx 依赖"}
        except Exception as e:
            return None, None, {"status": "error", "code": "DOCX_PARSE_FAILED", "message": f"docx 解析失败: {e}"}
        try:
            from docx import Document
            doc = Document(str(path))
            text = "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            text = ""
        return text, model, None
    if suffix in (".md", ".markdown", ".txt"):
        text = None
        for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312", "gb18030"):
            try:
                text = path.read_text(encoding=enc); break
            except (UnicodeDecodeError, LookupError):
                continue
        if text is None:
            return None, None, {"status": "error", "code": "ENCODING_ERROR", "message": "无法识别文件编码"}
        return text, I.inspect_markdown(text), None
    return None, None, {"status": "error", "code": "UNSUPPORTED_FORMAT", "message": f"不支持的格式: {suffix}"}


def cmd_journal_check(args):
    """对照期刊 profile 检查篇幅/摘要/关键词/参考文献 + 匿名泄露扫描。"""
    from core import journal_fit as JF

    if args.profile:
        ppath = Path(args.profile)
        if not ppath.exists():
            _output({"status": "error", "code": "FILE_NOT_FOUND", "message": f"profile 不存在: {args.profile}"})
            return
        try:
            raw = json.loads(ppath.read_text(encoding="utf-8"))
        except Exception as e:
            _output({"status": "error", "code": "PROFILE_PARSE_FAILED", "message": f"profile JSON 解析失败: {e}"})
            return
        errors = JF.validate_profile(raw)
        if errors:
            _output({"status": "error", "code": "PROFILE_INVALID", "errors": errors,
                     "message": f"profile 有 {len(errors)} 处问题"})
            return
        profile = JF.load_profile(str(ppath))
    else:
        profile = JF.DEFAULT_PROFILE

    text, model, err = _read_text_and_model(args.filepath)
    if err:
        _output(err); return

    report = JF.check_journal_fit(text or "", model, profile)
    out = {"status": "success", "profile": profile.get("name"), "file": args.filepath, **report}

    if args.raw:
        m = report["metrics"]
        lines = [f"投稿适配：{profile.get('name')}",
                 f"  正文字数 {m['length']['value']}  {'OK' if m['length']['ok'] else '不达标'}",
                 f"  摘要字数 {m['abstract']['value']}  含英文摘要={m['abstract']['has_en']}  {'OK' if m['abstract']['ok'] else '不达标'}",
                 f"  关键词 {m['keywords']['value']} 个  {'OK' if m['keywords']['ok'] else '不达标'}",
                 f"  参考文献 {m['references']['value']} 条  {'OK' if m['references']['ok'] else '不达标'}"]
        if report["issues"]:
            lines.append("适配问题：")
            for i in report["issues"]:
                lines.append(f"  - {i['type']}: {i['detail']}")
        anon = report["anonymity"]
        if anon["leaks"]:
            lines.append(f"匿名泄露（{'一票否决' if anon['required'] else '非匿名稿可保留'}）：")
            for lk in anon["leaks"]:
                lines.append(f"  - [{lk['severity']}] {lk['type']}: {lk['detail']} —— {lk['excerpt']}")
        print("\n".join(lines))
    else:
        _output(out)


def add_parser(sub):
    # journal-profile
    p_prof = sub.add_parser("journal-profile", help="生成期刊投稿要求模板 / 校验 profile")
    p_prof.add_argument("--template", action="store_true", help="输出 profile 模板（默认动作）")
    p_prof.add_argument("--validate", help="校验指定 profile JSON 文件")
    p_prof.add_argument("--output", help="模板输出路径（默认打印到 stdout）")
    p_prof.set_defaults(func=cmd_journal_profile)

    # journal-check
    p_chk = sub.add_parser("journal-check", help="投稿前适配自查（篇幅/摘要/关键词 + 匿名泄露）")
    p_chk.add_argument("filepath", help="稿件文件（.docx/.md/.txt）")
    p_chk.add_argument("--profile", help="期刊投稿要求 profile JSON（缺省用内置默认）")
    p_chk.add_argument("--raw", action="store_true", help="输出纯文本而非 JSON")
    p_chk.set_defaults(func=cmd_journal_check)
