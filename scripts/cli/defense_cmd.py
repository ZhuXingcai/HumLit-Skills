from __future__ import annotations

import json
from pathlib import Path

from cli._common import _output


def cmd_review_rubric(args):
    """rubric 工具：--template 产出模板；--validate 校验。"""
    from core.blind_review import rubric as R

    if args.validate:
        path = Path(args.validate)
        if not path.exists():
            _output({"status": "error", "code": "FILE_NOT_FOUND", "message": f"文件不存在: {args.validate}"})
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            _output({"status": "error", "code": "RUBRIC_PARSE_FAILED", "message": f"JSON 解析失败: {e}"})
            return
        errors = R.validate_rubric(data)
        if errors:
            _output({"status": "error", "code": "RUBRIC_INVALID", "errors": errors,
                     "message": f"rubric 有 {len(errors)} 处问题"})
        else:
            _output({"status": "success", "message": "rubric 合法", "name": data.get("name")})
        return

    tpl = R.build_rubric_template()
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


def cmd_review_signals(args):
    """计算送审就绪度信号。"""
    from core.blind_review import rubric as R
    from core.blind_review import signals as S

    if args.rubric:
        rpath = Path(args.rubric)
        if not rpath.exists():
            _output({"status": "error", "code": "FILE_NOT_FOUND", "message": f"rubric 不存在: {args.rubric}"})
            return
        try:
            raw = json.loads(rpath.read_text(encoding="utf-8"))
        except Exception as e:
            _output({"status": "error", "code": "RUBRIC_PARSE_FAILED", "message": f"rubric JSON 解析失败: {e}"})
            return
        errors = R.validate_rubric(raw)
        if errors:
            _output({"status": "error", "code": "RUBRIC_INVALID", "errors": errors,
                     "message": f"rubric 有 {len(errors)} 处问题"})
            return
        rubric = R.load_rubric(str(rpath))
    else:
        rubric = R.DEFAULT_RUBRIC

    text, model, err = _read_text_and_model(args.filepath)
    if err:
        _output(err); return

    format_report = None
    if args.format_profile:
        from core.thesis_format import profile as P
        from core.thesis_format import check as C
        ppath = Path(args.format_profile)
        if not ppath.exists():
            _output({"status": "error", "code": "FILE_NOT_FOUND", "message": f"format-profile 不存在: {args.format_profile}"})
            return
        try:
            prof = P.load_profile(str(ppath))
        except Exception as e:
            _output({"status": "error", "code": "PROFILE_PARSE_FAILED", "message": f"profile 解析失败: {e}"})
            return
        format_report = C.check_format(model, prof)

    report = S.compute_signals(model, rubric, full_text=text or "", format_report=format_report)
    out = {"status": "success", "file": args.filepath, **report}
    if args.raw:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        _output(out)


def add_parser(sub):
    # review-rubric
    p_rub = sub.add_parser("review-rubric", help="生成盲审 rubric 模板 / 校验 rubric")
    p_rub.add_argument("--template", action="store_true", help="输出 rubric 模板（默认动作）")
    p_rub.add_argument("--validate", help="校验指定 rubric JSON 文件")
    p_rub.add_argument("--output", help="模板输出路径（默认打印到 stdout）")
    p_rub.set_defaults(func=cmd_review_rubric)

    # review-signals
    p_sig = sub.add_parser("review-signals", help="计算论文送审就绪度信号（供 Agent 盲审）")
    p_sig.add_argument("filepath", help="论文文件（.docx/.md）")
    p_sig.add_argument("--rubric", help="自定义评审 rubric JSON（默认教育部 4 维）")
    p_sig.add_argument("--format-profile", dest="format_profile", help="格式 profile，内嵌 format-check 结果")
    p_sig.add_argument("--raw", action="store_true", help="输出纯 JSON")
    p_sig.set_defaults(func=cmd_review_signals)
