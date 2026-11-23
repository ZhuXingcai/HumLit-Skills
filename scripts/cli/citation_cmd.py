from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.formatter import (
    export_papers,
    generate_in_text_citations,
    generate_reference_list,
    to_bibtex_with_keys,
)
from core.search import resolve_crossref
from cli._common import (
    CITATION_STYLE_CHOICES,
    _is_cnki_paper,
    _load_session,
    _output,
    _save_session,
    _session_project,
)


def _parse_indices(raw: str, total: int) -> List[int]:
    """解析 1-based 序号列表，保留传入顺序并去重（如 '3,1,5-7'）。"""
    out: List[int] = []
    seen = set()
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo_s, hi_s = part.split("-", 1)
            lo_i, hi_i = int(lo_s.strip()), int(hi_s.strip())
            for i in range(lo_i - 1, min(hi_i, total)):
                if 0 <= i < total and i not in seen:
                    seen.add(i)
                    out.append(i)
        else:
            i = int(part) - 1
            if 0 <= i < total and i not in seen:
                seen.add(i)
                out.append(i)
    return out


def _strip_trailing_bibliography(doc_text: str) -> str:
    m = re.search(
        r"(?m)^\s*(?:#{1,3}\s*)?(?:参考文献|References|Bibliography|Works\s+Cited)\s*$",
        doc_text,
        re.IGNORECASE,
    )
    return doc_text[: m.start()] if m else doc_text


def _expand_bracket_tokens(spec: str, max_index: int) -> Optional[List[int]]:
    nums: List[int] = []
    for part in re.split(r"[,，、]\s*", spec.strip()):
        part = part.strip()
        if not part:
            return None
        rm = re.fullmatch(r"(\d+)\s*[-–—~]\s*(\d+)", part)
        if rm:
            a, b = int(rm.group(1)), int(rm.group(2))
            if a < 1 or b < a or b > max_index or (b - a) > 50:
                return None
            nums.extend(range(a, b + 1))
        elif re.fullmatch(r"\d+", part):
            v = int(part)
            if v < 1 or v > max_index:
                return None
            nums.append(v)
        else:
            return None
    return nums if nums else None


def _format_sequential_bracket(nums: List[int]) -> str:
    ordered = sorted(set(nums))
    if not ordered:
        return "[]"
    ranges: List[str] = []
    start = prev = ordered[0]
    for n in ordered[1:]:
        if n == prev + 1:
            prev = n
        else:
            ranges.append(f"{start}-{prev}" if prev - start >= 2 else (f"{start},{prev}" if prev > start else str(start)))
            start = prev = n
    ranges.append(f"{start}-{prev}" if prev - start >= 2 else (f"{start},{prev}" if prev > start else str(start)))
    return "[" + ",".join(ranges) + "]"


def _extract_pick_indices_from_doc(doc_text: str, total_papers: int) -> List[int]:
    body = _strip_trailing_bibliography(doc_text)
    found: List[int] = []
    seen = set()
    for m in re.finditer(r"\[(\d+(?:\s*(?:[,，、]|[-–—~])\s*\d+)*)\]", body):
        nums = _expand_bracket_tokens(m.group(1), total_papers)
        if not nums:
            continue
        for n in nums:
            idx0 = n - 1
            if idx0 not in seen:
                seen.add(idx0)
                found.append(idx0)
    return found


def _read_any_doc_text(fp: Path) -> str:
    suf = fp.suffix.lower()
    if suf == ".docx":
        from docx import Document
        doc = Document(str(fp))
        return "\n".join(p.text for p in doc.paragraphs)
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            return fp.read_text(encoding=enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return fp.read_text(encoding="utf-8", errors="replace")


def _apply_original_numbers(ref_list: str, orig_numbers: List[int]) -> str:
    lines = ref_list.splitlines()
    out: List[str] = []
    for i, line in enumerate(lines):
        if i < len(orig_numbers):
            out.append(re.sub(r"^\[\d+\]", f"[{orig_numbers[i]}]", line, count=1))
        else:
            out.append(line)
    return "\n".join(out)


def _rewrite_doc_with_sequential_refs(doc_text: str, mapping_1based: Dict[int, int], ref_list: str) -> str:
    body = _strip_trailing_bibliography(doc_text).rstrip()

    def _repl(m):
        nums = _expand_bracket_tokens(m.group(1), max(mapping_1based) if mapping_1based else 0)
        if not nums or not all(n in mapping_1based for n in nums):
            return m.group(0)
        return _format_sequential_bracket([mapping_1based[n] for n in nums])

    rewritten_body = re.sub(r"\[(\d+(?:\s*(?:[,，、]|[-–—~])\s*\d+)*)\]", _repl, body)
    return f"{rewritten_body}\n\n## 参考文献\n\n{ref_list}\n"


def _rewrite_tex_with_citekeys(doc_text: str, mapping_1based: Dict[int, str]) -> str:
    body = _strip_trailing_bibliography(doc_text)

    def _repl(m):
        nums = _expand_bracket_tokens(m.group(1), max(mapping_1based) if mapping_1based else 0)
        if not nums or not all(n in mapping_1based for n in nums):
            return m.group(0)
        keys = list(dict.fromkeys(mapping_1based[n] for n in nums))
        return "\\cite{" + ",".join(keys) + "}"

    return re.sub(r"\[(\d+(?:\s*(?:[,，、]|[-–—~])\s*\d+)*)\]", _repl, body)


def cmd_export(args):
    papers = _load_session(_session_project(args))
    if not papers:
        _output({"status": "error", "code": "NO_SESSION_DATA", "message": "没有可导出的数据，请先执行 search、batch-search、import 或 zotero"})
        return

    indices_raw = getattr(args, "indices", None)
    if indices_raw:
        pick = _parse_indices(indices_raw, len(papers))
        if not pick:
            _output({"status": "error", "code": "INVALID_INDICES", "message": f"无效序号 '{indices_raw}'"})
            return
        papers = [papers[i] for i in pick]

    result = export_papers(papers, args.export_format, args.output)
    if isinstance(result, dict) and result.get("status") == "error":
        _output(result)
        return
    if args.raw:
        print(result)
    else:
        _output({"status": "success", "project": _session_project(args), "format": args.export_format,
                 "count": len(papers), "output_file": args.output, "content": result})


def cmd_cite(args):
    papers = _load_session(_session_project(args))
    if not papers:
        _output({"status": "error", "code": "NO_SESSION_DATA", "message": "没有可格式化的数据，请先执行 search、batch-search、import 或 zotero"})
        return

    style = args.style or "gbt7714"
    from_file = getattr(args, "from_file", None)
    indices_raw = getattr(args, "indices", None)
    keep_numbers = bool(getattr(args, "keep_numbers", False))
    no_enrich = bool(getattr(args, "no_enrich", False))
    want_in_text = bool(getattr(args, "in_text", False))
    rewrite_output = getattr(args, "rewrite_output", None)
    bibtex_output = getattr(args, "bibtex_output", None)

    doc_text = ""
    pick_idx: Optional[List[int]] = None
    if from_file:
        fp = Path(from_file)
        if not fp.exists():
            _output({"status": "error", "code": "FILE_NOT_FOUND", "message": f"文件不存在: {from_file}"})
            return
        doc_text = _read_any_doc_text(fp)
        pick_idx = _extract_pick_indices_from_doc(doc_text, len(papers))
        if not pick_idx:
            _output({"status": "warning", "code": "NO_CITATIONS_IN_FILE", "message": f"未在 {from_file} 中找到有效的 [序号] 引用"})
            return
    elif indices_raw:
        pick_idx = _parse_indices(indices_raw, len(papers))
        if not pick_idx:
            _output({"status": "error", "code": "INVALID_INDICES", "message": f"无效序号 '{indices_raw}'"})
            return

    selected = [papers[i] for i in pick_idx] if pick_idx is not None else list(papers)
    orig_numbers = [i + 1 for i in pick_idx] if pick_idx is not None else list(range(1, len(selected) + 1))

    if not no_enrich:
        cnki_need_enrich = [
            (i, p) for i, p in enumerate(selected)
            if _is_cnki_paper(p) and p.get("url") and not p.get("pages") and "cnki.net" in p.get("url", "")
        ]
        if cnki_need_enrich:
            print(f"[cite] 正在补全 {len(cnki_need_enrich)} 篇知网论文的卷期页码...", file=sys.stderr)
            from core.cnki import get_detail
            for _idx, p in cnki_need_enrich:
                detail = get_detail(p["url"])
                if detail and detail.get("status") != "error":
                    for k in ("volume", "issue", "pages", "doi", "year", "journal"):
                        if detail.get(k) and not p.get(k):
                            p[k] = detail[k]
                time.sleep(1)

        for i, p in enumerate(selected):
            if p.get("doi") and not p.get("volume"):
                if i > 0:
                    time.sleep(1)
                crossref_data = resolve_crossref(p["doi"])
                if crossref_data:
                    p.update({k: v for k, v in crossref_data.items() if v and not p.get(k)})

    ref_list = generate_reference_list(selected, style)
    if keep_numbers and style in ("gbt7714", "gb") and pick_idx is not None:
        ref_list = _apply_original_numbers(ref_list, orig_numbers)

    bib_text = ""
    bib_keys: List[str] = []
    if bibtex_output or (rewrite_output and str(rewrite_output).lower().endswith(".tex")):
        bib_text, bib_keys = to_bibtex_with_keys(selected)
        if bibtex_output:
            bp = Path(bibtex_output)
            bp.parent.mkdir(parents=True, exist_ok=True)
            bp.write_text(bib_text, encoding="utf-8")

    rewritten_path = None
    if rewrite_output and from_file and doc_text:
        rp = Path(rewrite_output)
        rp.parent.mkdir(parents=True, exist_ok=True)
        if rp.suffix.lower() == ".tex" or Path(from_file).suffix.lower() == ".tex":
            mapping_tex = {orig_numbers[i]: bib_keys[i] for i in range(len(selected))}
            rp.write_text(_rewrite_tex_with_citekeys(doc_text, mapping_tex), encoding="utf-8")
        else:
            mapping_seq = {orig_numbers[i]: i + 1 for i in range(len(selected))}
            rp.write_text(_rewrite_doc_with_sequential_refs(doc_text, mapping_seq, ref_list), encoding="utf-8")
        rewritten_path = str(rp)

    if args.raw:
        print(ref_list)
        return

    out: Dict[str, Any] = {
        "status": "success",
        "project": _session_project(args),
        "style": style,
        "count": len(selected),
        "references": ref_list,
    }
    if want_in_text:
        out["in_text"] = generate_in_text_citations(selected, style)
    if rewritten_path:
        out["rewrite_output"] = rewritten_path
    if bibtex_output:
        out["bibtex_output"] = str(bibtex_output)
        out["citekeys"] = bib_keys
    _output(out)


def cmd_import(args):
    from core.cnki import parse_cnki_export
    results = parse_cnki_export(args.filepath)
    if results and not (len(results) == 1 and results[0].get("status") == "error"):
        _save_session(results, append=getattr(args, "append", False), project=_session_project(args))
        _output({"status": "success", "count": len(results), "results": results})
    else:
        _output(results[0] if results else {"status": "error", "code": "IMPORT_PARSE_FAILED", "message": "解析失败"})


def cmd_zotero(args):
    """本机 Zotero 文献库只读快照直连（零第三方依赖、绝不写回、不锁运行中的 Zotero）。"""
    from core.zotero import query_local_zotero

    res = query_local_zotero(
        query=getattr(args, "query", "") or "",
        collection=getattr(args, "collection", "") or "",
        data_dir=getattr(args, "data_dir", None),
        limit=getattr(args, "limit", 30) or 30,
        list_collections=bool(getattr(args, "list_collections", False)),
    )
    if res.get("status") == "success" and getattr(args, "save", False) and res.get("results"):
        _save_session(
            res["results"],
            append=bool(getattr(args, "append", False)),
            project=_session_project(args),
        )
        res["saved_to_session"] = True
        res["project"] = _session_project(args)
    _output(res)


def add_parser(sub):
    # export
    p_export = sub.add_parser("export", help="导出上次搜索结果")
    p_export.add_argument("--format", dest="export_format", required=True,
                          choices=["bibtex", "ris", "markdown", "json", "excel"] + CITATION_STYLE_CHOICES)
    p_export.add_argument("--indices", help="仅导出指定序号文献（如 '1,3,5-8'）")
    p_export.add_argument("--output", help="输出文件路径")
    p_export.add_argument("--raw", action="store_true", help="输出纯文本而非 JSON")
    p_export.add_argument("--project", help="课题文献库名称")
    p_export.set_defaults(func=cmd_export)

    # cite
    p_cite = sub.add_parser("cite", help="生成引用格式（支持 GB/T 7714 顺序/著者-出版年制、经管顶刊体例与角标重排）")
    p_cite.add_argument("--style", default="gbt7714", choices=CITATION_STYLE_CHOICES)
    p_cite.add_argument("--indices", help="仅格式化指定序号文献（如 '9,2,5' 或 '1-5'）")
    p_cite.add_argument("--from-file", help="从 .md/.tex/.docx 正文按首次出现顺序提取 [序号] 文献子集")
    p_cite.add_argument("--rewrite-output", help="配合 --from-file 重排 Markdown [1]..[N] 或重写 LaTeX \\cite{key}")
    p_cite.add_argument("--bibtex-output", help="同步导出所选文献子集的纯 ASCII Citekey BibTeX 文件")
    p_cite.add_argument("--keep-numbers", action="store_true", help="保留原文献库序号而非从 [1] 重排")
    p_cite.add_argument("--in-text", action="store_true", help="同时生成文内引文（叙述式与括号式）")
    p_cite.add_argument("--no-enrich", action="store_true", help="跳过自动联网补全缺页码")
    p_cite.add_argument("--raw", action="store_true", help="输出纯文本而非 JSON")
    p_cite.add_argument("--project", help="课题文献库名称")
    p_cite.set_defaults(func=cmd_cite)

    # import
    p_import = sub.add_parser("import", help="导入知网导出的题录文件")
    p_import.add_argument("filepath", help="题录文件路径")
    p_import.add_argument("--append", action="store_true", help="追加到当前会话/课题库")
    p_import.add_argument("--project", help="课题文献库名称")
    p_import.set_defaults(func=cmd_import)

    # zotero (read-only snapshot)
    p_zotero = sub.add_parser("zotero", help="只读检索或导入本机 Zotero 文献库（SQLite 快照不锁库、绝不写回）")
    p_zotero.add_argument("query", nargs="?", default="", help="过滤关键词（标题/作者/期刊/摘要/标签）")
    p_zotero.add_argument("--collection", help="仅读取指定名称的 Zotero 分类集合")
    p_zotero.add_argument("--data-dir", help="自定义 Zotero 数据目录（默认探测 ~/Zotero）")
    p_zotero.add_argument("--limit", type=int, default=30, help="最多读取条数（默认 30）")
    p_zotero.add_argument("--list-collections", action="store_true", help="仅列出本机 Zotero 分类集合")
    p_zotero.add_argument("--save", action="store_true", help="将结果存入当前会话或 --project 课题库")
    p_zotero.add_argument("--append", action="store_true", help="配合 --save 追加到现有课题库")
    p_zotero.add_argument("--project", help="课题文献库名称")
    p_zotero.set_defaults(func=cmd_zotero)
