from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from cli._common import (
    _is_cnki_paper,
    _load_session,
    _output,
    _save_session,
    _session_project,
)
from core.paths import state_path


def _parse_indices(raw: str, total: int) -> List[int]:
    """解析用户传入的序号字符串，返回 0-based 索引列表。"""
    indices: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            lo_i, hi_i = int(lo.strip()), int(hi.strip())
            indices.extend(range(lo_i - 1, min(hi_i, total)))
        else:
            i = int(part.strip()) - 1
            if 0 <= i < total:
                indices.append(i)
    return sorted(set(indices))


def cmd_detail(args):
    from core.cnki import get_detail
    if not args.url:
        _output({"status": "error", "code": "NO_URL", "message": "请提供知网论文详情页 URL"})
        return
    result = get_detail(args.url)
    _output(result)


def cmd_auth_cnki(args):
    from core.cnki import authenticate_cnki
    result = authenticate_cnki(
        auth_url=args.auth_url,
        verify_url=args.verify_url,
        institution=args.institution,
        wait_seconds=args.wait_seconds,
        captcha_timeout=args.captcha_timeout,
        direct_domains=args.direct_domain,
        debug_snapshot=args.debug_snapshot,
        keep_browser=args.keep_browser,
        force=args.force,
        reuse_session=getattr(args, "reuse_session", False),
    )
    _output(result)


def cmd_read_detail(args):
    """对会话中的论文批量获取摘要/全文（支持本地 PDF 离线提取、硕博 --toc 与 --section 章节切片）"""
    from core.cnki import batch_read_detail
    papers = _load_session(_session_project(args))
    if not papers:
        _output({"status": "error", "code": "NO_SESSION_DATA",
                 "message": "没有可读取的论文，请先执行 search、batch-search、import 或 zotero"})
        return

    do_toc = bool(getattr(args, "toc", False))
    do_section = getattr(args, "section", None)
    max_chars = getattr(args, "max_chars", None)
    do_fulltext = bool(args.fulltext or do_toc or do_section)
    indices_raw = getattr(args, "indices", None)

    if indices_raw:
        pick_idx = _parse_indices(indices_raw, len(papers))
        if not pick_idx:
            _output({"status": "error", "code": "INVALID_INDICES",
                     "message": f"无效序号 '{indices_raw}'，会话共 {len(papers)} 篇（序号 1-{len(papers)}）"})
            return
        selected = [papers[i] for i in pick_idx]
        label = f"第 {indices_raw} 篇"
    else:
        top_n = args.top_n or 5
        selected = papers[:top_n]
        label = f"前 {len(selected)} 篇"

    print(f"[read-detail] 会话共 {len(papers)} 篇，将获取{label}的{'全文' if do_fulltext else '摘要'}",
          file=sys.stderr)

    local_pdf_selected = [
        p for p in selected
        if p.get("local_pdf") and Path(str(p["local_pdf"])).is_file()
    ]
    local_pdf_ids = {id(p) for p in local_pdf_selected}
    cnki_selected = [p for p in selected if id(p) not in local_pdf_ids and _is_cnki_paper(p)]
    non_cnki_selected = [p for p in selected if id(p) not in local_pdf_ids and not _is_cnki_paper(p)]

    enriched: List[Dict[str, Any]] = []
    if local_pdf_selected:
        from cli.docx_cmd import extract_fulltext_from_pdf_file
        for p in local_pdf_selected:
            item = dict(p)
            if do_fulltext:
                try:
                    ft = extract_fulltext_from_pdf_file(Path(str(p["local_pdf"])))
                    item["fulltext"] = ft
                    item["has_fulltext"] = bool(ft)
                    item["fulltext_length"] = len(ft)
                except Exception as exc:
                    item["fulltext_error"] = str(exc)
            enriched.append(item)

    if cnki_selected:
        enriched.extend(
            batch_read_detail(
                papers=cnki_selected,
                top_n=len(cnki_selected),
                fulltext=do_fulltext,
            )
        )
    elif not local_pdf_selected:
        _output({"status": "warning", "code": "NO_SESSION_DATA",
                 "message": "所选论文中无知网论文或本地 PDF 附件。API 源论文请直接使用搜索时返回的摘要",
                 "count": len(non_cnki_selected), "results": non_cnki_selected})
        return
    enriched.extend(non_cnki_selected)

    if indices_raw:
        updated = list(papers)
        enriched_map = {p.get("url", ""): p for p in enriched if p.get("url")}
        for i in pick_idx:
            url = updated[i].get("url", "")
            if url in enriched_map:
                merged = {k: v for k, v in enriched_map[url].items() if k != "fulltext"}
                merged.update({k: updated[i][k] for k in updated[i] if k not in merged})
                updated[i] = merged
        session_papers = updated
    else:
        session_papers = []
        for p in enriched:
            sp = {k: v for k, v in p.items() if k != "fulltext"}
            session_papers.append(sp)
    _save_session(session_papers, project=_session_project(args))

    output_papers = enriched
    results = []
    for p in output_papers:
        entry: Dict[str, Any] = {
            "title": p.get("title", ""),
            "authors": p.get("authors", ""),
            "journal": p.get("journal", ""),
            "date": p.get("date", ""),
            "abstract": p.get("abstract", ""),
            "keywords": p.get("keywords", []),
            "has_fulltext": p.get("has_fulltext", False),
            "fulltext_length": p.get("fulltext_length", 0),
        }
        if p.get("fulltext_cache"):
            entry["fulltext_cache"] = p["fulltext_cache"]

        if do_fulltext and p.get("fulltext"):
            entry["fulltext"] = p["fulltext"]
        elif do_fulltext and p.get("fulltext_cache"):
            try:
                cache_path = Path(p["fulltext_cache"]).resolve()
                allowed_dir = state_path("fulltext").resolve()
                try:
                    cache_path.relative_to(allowed_dir)
                except ValueError:
                    entry["fulltext"] = ""
                else:
                    cache_data = json.loads(
                        cache_path.read_text(encoding="utf-8")
                    )
                    entry["fulltext"] = cache_data.get("fulltext", "")
            except Exception:
                entry["fulltext"] = ""

        if do_fulltext:
            ft_text = entry.get("fulltext", "")
            if ft_text and (do_toc or do_section):
                from core.sections import parse_fulltext_sections, public_toc, slice_fulltext_sections

                secs = parse_fulltext_sections(ft_text)
                entry["toc"] = public_toc(secs)
                if do_toc and not do_section:
                    entry.pop("fulltext", None)
                elif do_section:
                    sliced = slice_fulltext_sections(ft_text, do_section, max_chars=max_chars or 30000)
                    entry["matched_sections"] = sliced.get("matched_sections", [])
                    entry["fulltext"] = sliced.get("text", "")
            elif max_chars and max_chars > 0 and len(ft_text) > max_chars:
                entry["fulltext"] = ft_text[:max_chars]
                entry["truncated"] = True

        results.append(entry)

    _output({"status": "success", "count": len(results), "results": results})


def add_parser(sub):
    # detail
    p_detail = sub.add_parser("detail", help="获取知网论文详情")
    p_detail.add_argument("url", help="知网论文详情页 URL")
    p_detail.set_defaults(func=cmd_detail)

    # auth-cnki
    p_auth = sub.add_parser("auth-cnki", help="打开知网校外认证入口并保存浏览器会话")
    p_auth.add_argument("--auth-url", default="https://fsso.cnki.net/",
                        help="校外认证入口 URL，默认 CNKI FSSO；也可传学校图书馆/VPN/CARSI 入口")
    p_auth.add_argument("--verify-url", default="https://kns.cnki.net/",
                        help="登录后用于确认访问的知网页面，默认 https://kns.cnki.net/")
    p_auth.add_argument("--institution",
                        help="学校/机构名称；传入后尝试在 FSSO 页面自动选择，不传则由用户手动选择")
    p_auth.add_argument("--wait-seconds", type=int, default=180,
                        help="等待用户完成登录/扫码/短信/滑块验证的秒数，默认 180")
    p_auth.add_argument("--captcha-timeout", type=int, default=180,
                        help="等待知网安全验证完成的秒数，设为 0 可跳过等待")
    p_auth.add_argument("--direct-domain", action="append", default=[],
                        help="追加需要直连的学校认证/VPN 域名，可重复传入，如 --direct-domain idp.xxx.edu.cn")
    p_auth.add_argument(
        "--debug-snapshot",
        nargs="?",
        const=str(state_path("cnki-auth-snapshot.html")),
        help="保存认证后页面 HTML 快照；可选指定输出路径",
    )
    p_auth.add_argument("--keep-browser", action="store_true",
                        help="完成后保留浏览器窗口，便于用户继续登录或手动检查")
    p_auth.add_argument("--force", action="store_true",
                        help="重新打开认证入口，并忽略本地会话复用")
    p_auth.add_argument("--reuse-session", action="store_true",
                        help="显式复用本机当前项目已有 CNKI 会话；默认要求手动重新认证")
    p_auth.set_defaults(func=cmd_auth_cnki)

    # read-detail
    p_read = sub.add_parser("read-detail", help="批量获取论文摘要/全文（支持本地 PDF、硕博目录与章节切片）")
    p_read.add_argument("--top-n", type=int, default=5,
                        help="获取前 N 篇论文的详情（默认 5）")
    p_read.add_argument("--indices", type=str, default=None,
                        help="指定论文序号（从1开始），如 '3' '1,3,9' '2-5'。指定后忽略 --top-n")
    p_read.add_argument("--fulltext", action="store_true",
                        help="抓取全文（指定 --toc 或 --section 时自动启用）")
    p_read.add_argument("--toc", action="store_true",
                        help="仅返回全文目录结构与各章节页码/字数（适合硕博长文）")
    p_read.add_argument("--section", type=str, default=None,
                        help="按章节标题关键词或 S序号精准切片精读（如 '研究设计,实证分析'）")
    p_read.add_argument("--max-chars", type=int, default=None,
                        help="单篇返回正文最大字符数上限")
    p_read.add_argument("--project", help="课题文献库名称")
    p_read.set_defaults(func=cmd_read_detail)
