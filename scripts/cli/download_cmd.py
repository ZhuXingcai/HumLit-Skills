from __future__ import annotations

import hashlib
import re
import os
import tempfile
from typing import Any, Dict, List
from pathlib import Path
from urllib.parse import urlparse

from core.search import resolve_crossref, resolve_openalex_oa, resolve_unpaywall
from cli._common import (
    CITATION_STYLE_CHOICES,
    _output, _load_session, _session_project,
    _merge_fallback_download, attach_download_report,
)


MAX_OA_PDF_BYTES = 100 * 1024 * 1024


class _OAPdfTooLarge(ValueError):
    pass


def _is_cnki_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    hostname = (parsed.hostname or "").lower().rstrip(".")
    return (
        parsed.scheme.lower() in {"http", "https"}
        and (hostname == "cnki.net" or hostname.endswith(".cnki.net"))
    )


def _download_oa_pdf(
    url: str,
    output_path: Path,
    *,
    max_bytes: int = MAX_OA_PDF_BYTES,
) -> Dict[str, Any]:
    """Stream and atomically save a size-bounded, verified PDF."""
    if output_path.exists():
        try:
            with output_path.open("rb") as existing:
                signature = existing.read(5)
        except OSError as exc:
            return {
                "status": "error",
                "code": "OA_OUTPUT_EXISTS",
                "message": f"无法检查既有文件: {exc}",
                "url": url,
            }
        if signature == b"%PDF-":
            return {
                "status": "success",
                "path": str(output_path),
                "bytes": output_path.stat().st_size,
                "url": url,
                "content_type": "application/pdf",
                "cached": True,
            }
        return {
            "status": "error",
            "code": "OA_OUTPUT_EXISTS",
            "message": "目标路径已存在且不是可验证 PDF，拒绝覆盖",
            "url": url,
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f"{output_path.name}.",
        suffix=".part",
        dir=str(output_path.parent),
    )
    os.close(fd)
    temp_path = Path(temp_name)
    headers = {"User-Agent": "Mozilla/5.0 HumLit/1.0"}
    total = 0
    content_type = ""
    final_url = url

    def write_chunks(chunks):
        nonlocal total
        with temp_path.open("wb") as handle:
            for chunk in chunks:
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise _OAPdfTooLarge(
                        f"OA PDF 超过大小上限 {max_bytes} bytes"
                    )
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())

    try:
        try:
            import httpx

            with httpx.Client(timeout=60, follow_redirects=True) as client:
                if hasattr(client, "stream"):
                    response_context = client.stream(
                        "GET",
                        url,
                        headers=headers,
                    )
                    with response_context as response:
                        response.raise_for_status()
                        content_type = response.headers.get("content-type", "")
                        final_url = str(response.url)
                        content_length = response.headers.get("content-length")
                        if content_length and int(content_length) > max_bytes:
                            raise _OAPdfTooLarge(
                                f"OA PDF 超过大小上限 {max_bytes} bytes"
                            )
                        write_chunks(response.iter_bytes())
                else:
                    response = client.get(url, headers=headers)
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    final_url = str(response.url)
                    write_chunks([response.content])
        except ImportError:
            import urllib.request

            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                content_type = response.headers.get("content-type", "")
                final_url = response.geturl()
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    raise _OAPdfTooLarge(
                        f"OA PDF 超过大小上限 {max_bytes} bytes"
                    )

                def urllib_chunks():
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        yield chunk

                write_chunks(urllib_chunks())

        with temp_path.open("rb") as downloaded:
            signature = downloaded.read(5)
        if signature != b"%PDF-":
            raise ValueError(f"响应不是 PDF（content-type={content_type or 'unknown'}）")
        os.replace(temp_path, output_path)
        return {
            "status": "success",
            "path": str(output_path),
            "bytes": total,
            "url": final_url,
            "content_type": content_type,
            "cached": False,
        }
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        return {
            "status": "error",
            "code": (
                "OA_PDF_TOO_LARGE"
                if isinstance(exc, _OAPdfTooLarge)
                else "OA_DOWNLOAD_FAILED"
            ),
            "message": str(exc),
            "url": url,
        }


def _doi_filename(doi: str) -> str:
    normalized = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized).strip("._")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    stem = (safe or "open_access_paper")[:96]
    return f"{stem}-{digest}.pdf"


def cmd_download(args):
    from core.config import get as cfg_get

    target = args.target
    save_dir = args.dir if args.dir != "./papers" else cfg_get("save_dir", "./papers")

    if args.doi:
        unpaywall = resolve_unpaywall(args.doi)
        oa = unpaywall if unpaywall and unpaywall.get("oa_url") else resolve_openalex_oa(args.doi)
        if oa and oa.get("oa_url"):
            if getattr(args, "link_only", False):
                _output({
                    "status": "success",
                    "method": f"{oa.get('source', 'oa').lower()}_link",
                    "url": oa["oa_url"],
                    "message": f"找到 OA 链接: {oa['oa_url']}",
                })
                return
            output_path = Path(save_dir) / "pdf" / _doi_filename(args.doi)
            downloaded = _download_oa_pdf(oa["oa_url"], output_path)
            if downloaded.get("status") == "success":
                downloaded.update({
                    "method": f"{oa.get('source', 'oa').lower()}_oa",
                    "doi": args.doi,
                    "title": oa.get("title", ""),
                })
                _output(downloaded)
                return
            _output({
                **downloaded,
                "doi": args.doi,
                "title": oa.get("title", ""),
            })
            return

        crossref = resolve_crossref(args.doi)
        meta = {
            "title": (crossref or {}).get("title", ""),
            "authors": (crossref or {}).get("authors", ""),
            "journal": (crossref or {}).get("journal", ""),
            "doi": args.doi,
        }
        if target and _is_cnki_url(target):
            from core.cnki import download_cnki

            result = download_cnki(target, save_dir=save_dir, file_format=args.file_format or "pdf")
            _output(result)
            return
        _output({
            "status": "error",
            "code": "OA_NOT_FOUND",
            "message": "Unpaywall 未找到 OA 版本，无知网 URL 可回退",
            "metadata": meta,
        })
        return

    if target and _is_cnki_url(target):
        from core.cnki import download_cnki

        result = download_cnki(target, save_dir=save_dir, file_format=args.file_format or "pdf")
        _output(result)
    elif target:
        _output({
            "status": "error",
            "code": "UNSUPPORTED_URL",
            "message": "目前仅支持知网 URL 直接下载",
        })
    else:
        _output({"status": "error", "code": "NO_DOWNLOAD_TARGET",
                 "message": "请提供下载目标（URL 或 --doi）"})


def cmd_batch_download(args):
    """批量下载：浏览器只启动一次，多标签页并行下载"""
    from core.config import get as cfg_get
    from core.cnki import batch_download_cnki
    urls = list(args.urls) if args.urls else []
    session_data: List[Dict[str, Any]] = []

    if args.from_session:
        session_data = _load_session(_session_project(args))
        if not session_data:
            _output({"status": "error", "code": "NO_SESSION",
                     "message": "没有搜索记录，请先执行 search 或 batch-search"})
            return
        top_n = args.top_n or len(session_data)
        session_urls = [p.get("url") for p in session_data[:top_n]
                        if isinstance(p, dict) and p.get("url")]
        urls.extend(session_urls)

    if not urls:
        _output({"status": "error", "code": "NO_URLS",
                 "message": "未提供下载 URL（可用 --from-session 从上次搜索结果读取）"})
        return
    invalid_urls = [url for url in urls if not _is_cnki_url(str(url))]
    if invalid_urls:
        _output({
            "status": "error",
            "code": "UNSUPPORTED_URL",
            "message": "批量下载仅接受合法的 CNKI http/https URL",
            "invalid_urls": invalid_urls[:10],
        })
        return

    save_dir = args.dir if args.dir != "./papers" else cfg_get("save_dir", "./papers")
    result = batch_download_cnki(
        urls=urls,
        save_dir=save_dir,
        file_format=args.file_format or "pdf",
    )
    fallback_format = getattr(args, "fallback_format", None)
    if fallback_format:
        failed_urls = [
            err.get("url") for err in (result.get("errors") or [])
            if isinstance(err, dict)
            and err.get("url")
            and err.get("code") == "DOWNLOAD_BTN_NOT_FOUND"
        ]
        if failed_urls:
            fallback_result = batch_download_cnki(
                urls=failed_urls,
                save_dir=save_dir,
                file_format=fallback_format,
            )
            result = _merge_fallback_download(result, fallback_result)
    if not getattr(args, "no_report", False):
        result = attach_download_report(
            result,
            save_dir=save_dir,
            session_papers=session_data,
            requested_urls=urls,
            citation_style=getattr(args, "citation_style", "gbt7714") or "gbt7714",
            file_format=args.file_format or "pdf",
            report_output=getattr(args, "report_output", None),
        )
    _output(result)


def add_parser(sub):
    # download
    p_download = sub.add_parser("download", help="下载知网论文，或按 DOI 验证并保存 OA PDF")
    p_download.add_argument("target", nargs="?", help="知网论文 URL")
    p_download.add_argument("--doi", help="通过 DOI 解析并下载合法 OA PDF")
    p_download.add_argument("--dir", default="./papers", help="保存目录")
    p_download.add_argument("--file-format", choices=["pdf", "caj"], default="pdf")
    p_download.add_argument("--link-only", action="store_true",
                            help="DOI 模式仅返回 OA 链接，不下载文件")
    p_download.set_defaults(func=cmd_download)

    # batch-download
    p_bdl = sub.add_parser("batch-download", help="批量下载知网论文（一次启动浏览器）")
    p_bdl.add_argument("urls", nargs="*", help="知网论文 URL 列表（可选，也可用 --from-session）")
    p_bdl.add_argument("--from-session", action="store_true",
                       help="从上次搜索结果（session.json）读取 URL")
    p_bdl.add_argument("--top-n", type=int, help="配合 --from-session，只下载前 N 篇")
    p_bdl.add_argument("--dir", default="./papers", help="保存目录")
    p_bdl.add_argument("--file-format", choices=["pdf", "caj"], default="pdf")
    p_bdl.add_argument("--fallback-format", choices=["caj"], default=None,
                       help="主格式失败时的兜底格式；例如 PDF 按钮不存在时尝试 CAJ")
    p_bdl.add_argument("--citation-style", choices=CITATION_STYLE_CHOICES,
                       default="gbt7714", help="下载清单引用格式")
    p_bdl.add_argument("--report-output", help="下载清单输出路径（默认写入下载目录）")
    p_bdl.add_argument("--no-report", action="store_true", help="不生成下载清单")
    p_bdl.add_argument("--project", help="课题文献库名称；配合 --from-session 使用")
    p_bdl.set_defaults(func=cmd_batch_download)
