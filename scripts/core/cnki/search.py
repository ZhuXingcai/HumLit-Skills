"""cnki.search - 知网搜索、筛选、翻页与结果解析"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from .constants import (
    HAS_SELENIUM, CNKI_SEARCH_URL, CNKI_ADV_SEARCH_URL, CNKI_EXPERT_SEARCH_URL,
    REQUEST_INTERVAL, CNKI_SIDEBAR_CORES, _log,
)
from .query import CnkiQueryError, compile_conditions_to_expression
from .driver import (
    _detect_browser, _create_driver, _load_cookies, _save_cookies,
    _handle_captcha, _is_cnki_security_gate, _has_captcha_elements,
    _cnki_page_diagnostics, check_cnki_access,
    _driver_is_reused, CnkiSecurityError, DriverStartupError,
)

if HAS_SELENIUM:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException, NoSuchElementException,
        ElementClickInterceptedException,
    )


def _year_from_date(date_str: str) -> Optional[int]:
    """从日期字符串提取年份，如 '2024-03-15' → 2024。失败返回 None。"""
    try:
        return int(date_str[:4])
    except (ValueError, IndexError, TypeError):
        return None


def _filter_by_year(results: list, year_from: Optional[int], year_to: Optional[int]) -> list:
    """客户端年份过滤，用于 UI 侧边栏筛选失败时的兜底。无日期或解析失败的条目保留。"""
    if not results or (year_from is None and year_to is None):
        return results
    filtered = []
    for r in results:
        if not r.get("date"):
            filtered.append(r)
            continue
        y = _year_from_date(r["date"])
        if y is None:
            filtered.append(r)
            continue
        if year_from is not None and y < year_from:
            continue
        if year_to is not None and y > year_to:
            continue
        filtered.append(r)
    return filtered


# ── 搜索 ─────────────────────────────────────────────

def search_cnki(
    keyword: str,
    core: str = None,
    year_from: int = None,
    year_to: int = None,
    author: str = None,
    journal: str = None,
    doc_type: str = None,
    field: str = None,
    sort: str = "relevance",
    pages: int = 1,
    cite_enrich: int = 0,
    _keep_driver: bool = False,
    conditions: Optional[list] = None,
    professional: Optional[str] = None,
    match: Optional[str] = None,
    cross_language: Optional[bool] = None,
    meta: Optional[Dict[str, Any]] = None,
):
    """
    知网文献搜索。

    Args:
        keyword:       搜索关键词
        core:          核心期刊筛选 (北大核心/CSSCI/AMI/WJCI/CSCD/EI)
        year_from:     起始年份
        year_to:       截止年份
        author:        作者
        journal:       期刊名
        doc_type:      文献类型 (master/doctor/thesis/journal/conference/newspaper)
        field:         搜索字段 (主题/篇名/关键词/摘要/全文/作者/来源)，默认主题
        sort:          排序方式 (relevance/date/citations)
        pages:         抓取页数
        _keep_driver:  内部参数。为 True 时搜索成功后不关闭浏览器，
                       返回 (results, driver) 元组供 batch_download_cnki 复用。

    Returns:
        _keep_driver=False（默认）: list[dict] — 论文信息列表
        _keep_driver=True 且成功:  tuple[list[dict], WebDriver] — (论文列表, 浏览器实例)
        搜索异常时始终返回:        list[dict] — 含 status=error 的单元素列表
    """
    _log(f"[cnki] 开始搜索: keyword={keyword}, core={core}, "
         f"year_from={year_from}, doc_type={doc_type}, field={field}, "
         f"professional={bool(professional)}, conditions={len(conditions or [])}")
    from .query import (
        CnkiQueryError, build_legacy_conditions, normalize_value,
        validate_conditions, validate_professional_expression, validate_value_syntax,
    )

    retrieval: Dict[str, Any] = {
        "source": "cnki",
        "mode": "simple",
        "requested": {},
        "applied": {},
        "verified": None,
        "expression": None,
        "total_hits": None,
    }
    active_conditions: List[Any] = []
    expression: Optional[str] = None

    try:
        if professional:
            expression = validate_professional_expression(professional)
            retrieval["mode"] = "professional"
            retrieval["expression"] = expression
            retrieval["requested"] = {"expression": expression}
        else:
            legacy_advanced = bool(
                author or journal or (field and field != "主题") or match
            )
            if conditions:
                active_conditions = validate_conditions(conditions)
            elif legacy_advanced:
                active_conditions = validate_conditions(build_legacy_conditions(
                    keyword, field=field, author=author, journal=journal, match=match,
                ))
            if active_conditions:
                retrieval["mode"] = "advanced"
                retrieval["requested"] = {
                    "conditions": [c.to_dict() for c in active_conditions]
                }
            else:
                if not str(keyword or "").strip():
                    code = "ADV_SEARCH_FALLBACK" if (author or journal) else "NO_KEYWORDS"
                    message = ("高级搜索未成功且无关键词可回退到简单搜索"
                               if (author or journal) else "未提供搜索关键词")
                    if meta is not None:
                        meta["retrieval"] = retrieval
                    return [{"status": "error", "code": code, "message": message}]
                keyword = normalize_value(keyword)
                validate_value_syntax(keyword)
                retrieval["requested"] = {
                    "keyword": keyword, "field": field or "主题",
                }
        if cross_language is not None:
            retrieval["requested"]["cross_language"] = bool(cross_language)
    except CnkiQueryError as e:
        error = {"status": "error", "code": e.code, "message": e.message}
        if e.condition:
            error["condition"] = e.condition
        if meta is not None:
            meta["retrieval"] = retrieval
        return [error]


    accessible, msg = check_cnki_access()
    _log(f"[cnki] 网络检测: accessible={accessible}, msg={msg}")
    if not accessible:
        if msg.startswith("SANDBOX_BLOCKED"):
            _log("[cnki] 沙盒限制导致预检失败，浏览器可能仍可访问，继续尝试...")
        else:
            return [{"status": "error", "code": "CNKI_UNREACHABLE", "message": msg}]

    driver = None
    should_quit = True
    try:
        browser = _detect_browser()
        _log(f"[cnki] 浏览器: {browser}，正在启动...")
        driver = _create_driver(browser=browser)

        driver.get("https://kns.cnki.net/")
        time.sleep(1)
        _load_cookies(driver)

        if retrieval["mode"] == "professional":
            driver.get(CNKI_EXPERT_SEARCH_URL)
            time.sleep(REQUEST_INTERVAL)
            driver = _handle_captcha(driver)
            if cross_language is not None:
                retrieval["applied"]["cross_language"] = _set_cross_language(
                    driver, cross_language
                )
            outcome = _professional_search(driver, expression)
            if not outcome.get("ok"):
                err = outcome.get("error") or {}
                raise CnkiRetrievalError(
                    "CNKI_CONDITION_NOT_APPLIED",
                    f"专业检索未成功提交: {err.get('message', '未知原因')}",
                )

        elif retrieval["mode"] == "advanced":
            # 高级检索的字段/逻辑/匹配控件是自定义下拉，程序化点击无法可靠展开；
            # 统一编译为专业检索表达式后走专业检索页（实测可写入且可回读）。
            expression = compile_conditions_to_expression(active_conditions)
            _log(f"[cnki] 条件已编译为专业检索表达式: {expression}")
            retrieval["compiled_expression"] = expression
            retrieval["expression"] = expression
            retrieval["applied"]["expression"] = expression
            driver.get(CNKI_EXPERT_SEARCH_URL)
            time.sleep(REQUEST_INTERVAL)
            driver = _handle_captcha(driver)
            if cross_language is not None:
                retrieval["applied"]["cross_language"] = _set_cross_language(
                    driver, cross_language
                )
            outcome = _professional_search(driver, expression)
            if not outcome.get("ok"):
                err = outcome.get("error") or {}
                raise CnkiRetrievalError(
                    "CNKI_CONDITION_NOT_APPLIED",
                    f"检索条件编译后提交失败: {err.get('message', '未知原因')}",
                )
            retrieval["applied"]["conditions"] = [c.to_dict() for c in active_conditions]

        if retrieval["mode"] == "simple":
            _log(f"[cnki] 正在加载搜索页: {CNKI_SEARCH_URL}")
            driver.get(CNKI_SEARCH_URL)
            time.sleep(REQUEST_INTERVAL)
            driver = _handle_captcha(driver)
            if cross_language is not None:
                retrieval["applied"]["cross_language"] = _set_cross_language(
                    driver, cross_language
                )
            _input_search_keyword(driver, keyword)

        def _finalize_retrieval(empty: bool = False):
            """结果页就绪后回读输入框里的表达式与命中数；不一致必须显式报错。"""
            if retrieval["mode"] in ("advanced", "professional") and expression:
                verification = _verify_professional_expression(driver, expression)
                retrieval["verified"] = verification["verified"]
                if verification.get("actual"):
                    retrieval["applied"]["expression_readback"] = verification["actual"]
                if verification["verified"] is False:
                    raise CnkiRetrievalError(
                        "CNKI_RETRIEVAL_MISMATCH",
                        "专业检索输入框回读值与请求表达式不一致: "
                        f"请求 {expression!r}，实际 {verification.get('actual')!r}",
                    )
            retrieval["total_hits"] = _read_total_hits(driver)
            if empty and retrieval["total_hits"] is None:
                # 已确认是真实空结果页时，命中数就是 0，不应留空
                retrieval["total_hits"] = 0

        time.sleep(REQUEST_INTERVAL)
        driver = _handle_captcha(driver)

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "table.result-table-list tbody tr, .result-table-list tbody tr, #gridTable tbody tr"))
            )
            _log("[cnki] 搜索结果已加载")
        except TimeoutException:
            _log("[cnki] [!] 等待结果表格超时，检查页面状态...")
            page_state = _classify_result_page(driver)
            if page_state == "security_gate":
                raise CnkiSecurityError(
                    "CNKI_SECURITY_GATE_UNRESOLVED",
                    "知网搜索结果页仍处于安全验证状态，检索未完成",
                    _cnki_page_diagnostics(driver),
                )
            if page_state != "verified_empty":
                raise CnkiSecurityError(
                    "CNKI_RESULT_PAGE_UNAVAILABLE",
                    "知网结果表格未加载，且页面未提供可信的空结果状态",
                    _cnki_page_diagnostics(driver),
                )
            _log("[cnki] 已确认知网返回真实空结果页面")
            _finalize_retrieval(empty=True)
            if _keep_driver:
                should_quit = False
                return [], driver
            return []

        _finalize_retrieval()

        if doc_type:
            doc_type_ok = _switch_to_doc_type(driver, doc_type)
            if doc_type_ok:
                driver = _handle_captcha(driver)
            else:
                _log(f"[cnki] 文献类型筛选 '{doc_type}' 未生效")

        core_filter_ok = False
        if core:
            core_filter_ok = _set_core_filter(driver, core)
            if not core_filter_ok:
                _log("[cnki] 侧边栏筛选失败，尝试切换到学术期刊数据库...")
                if _switch_to_doc_type(driver, "journal"):
                    driver = _handle_captcha(driver)
                    core_filter_ok = _set_core_filter(driver, core)
            _log(f"[cnki] 核心期刊筛选: {'成功' if core_filter_ok else '未生效（结果可能包含非核心文献）'}")
        if year_from is not None or year_to is not None:
            _set_year_filter(driver, year_from, year_to)
        if sort and sort != "relevance":
            _set_sort(driver, sort)

        time.sleep(1)
        _log(f"[cnki] 筛选后页面: url={driver.current_url[:80]}  title={driver.title}")

        cite_remaining = max(cite_enrich or 0, 0)
        all_results = []
        for page_num in range(pages):
            _log(f"[cnki] 解析第 {page_num + 1}/{pages} 页...")
            if page_num > 0:
                _go_next_page(driver)
                driver = _handle_captcha(driver)

            page_results = _parse_search_results(driver, cite_enrich=cite_remaining)
            cite_remaining = max(0, cite_remaining - len(page_results))
            _log(f"[cnki] 第 {page_num + 1} 页获取 {len(page_results)} 条结果")
            all_results.extend(page_results)

            if not page_results:
                break

        if core and core_filter_ok and all_results:
            core_labels = _parse_core_input(core)
            for r in all_results:
                if r.get("title"):
                    r["is_core"] = True
                    r["core_type"] = ",".join(core_labels)

        all_results = _filter_by_year(all_results, year_from, year_to)

        if _keep_driver:
            should_quit = False
            return all_results, driver
        return all_results

    except (DriverStartupError, CnkiSecurityError) as e:
        result = {"status": "error", "code": e.code, "message": e.message}
        diagnostics = getattr(e, "diagnostics", None)
        if diagnostics:
            result["diagnostics"] = diagnostics
        return [result]
    except Exception as e:
        return [{"status": "error", "code": "CNKI_SEARCH_FAILED",
                 "message": str(e)}]
    finally:
        if meta is not None:
            meta["retrieval"] = retrieval
        if driver is not None:
            try:
                _save_cookies(driver)
                if should_quit and not _driver_is_reused(driver):
                    driver.quit()
            except Exception:
                pass


def _dedupe_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按标题全局去重，保留字段更完整的条目；无标题条目原样保留。"""
    seen: Dict[str, Dict[str, Any]] = {}
    no_title: List[Dict[str, Any]] = []
    for r in results:
        key = r.get("title", "").lower().strip()
        if not key:
            no_title.append(r)
            continue
        if key in seen:
            old = seen[key]
            new_fields = sum(1 for v in r.values() if v)
            old_fields = sum(1 for v in old.values() if v)
            if new_fields > old_fields:
                seen[key] = r
        else:
            seen[key] = r
    return list(seen.values()) + no_title


def batch_search_cnki(
    keywords: List[str],
    core: str = None,
    author: str = None,
    journal: str = None,
    doc_type: str = None,
    field: str = None,
    year_from: int = None,
    year_to: int = None,
    sort: str = "relevance",
    pages: int = 1,
    match: Optional[str] = None,
    cross_language: Optional[bool] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    批量知网搜索：一次启动浏览器、一次验证，循环搜索多组关键词。

    Args:
        keywords:  关键词列表
        core:      核心期刊筛选
        author:    作者（对每组关键词生效）
        journal:   期刊名（对每组关键词生效）
        doc_type:  文献类型筛选
        field:     搜索字段
        year_from: 起始年份
        year_to:   截止年份
        sort:      排序方式
        pages:     每组关键词抓取页数

    Returns:
        {"status": "success", "results": [...], "errors": [...]}
    """
    if not keywords:
        return {"status": "error", "code": "NO_KEYWORDS", "message": "未提供关键词"}

    _log(f"[cnki-batch] 开始批量搜索: {len(keywords)} 组关键词")
    accessible, msg = check_cnki_access()
    if not accessible:
        if msg.startswith("SANDBOX_BLOCKED"):
            _log("[cnki-batch] 沙盒限制导致预检失败，浏览器可能仍可访问，继续尝试...")
        else:
            return {"status": "error", "code": "CNKI_UNREACHABLE", "message": msg}

    driver = None
    all_results = []
    errors = []
    empty_keywords = []
    core_filter_results: Dict[str, bool] = {}
    retrieval_items: List[Dict[str, Any]] = []
    from .query import (
        CnkiQueryError, build_legacy_conditions, normalize_value,
        validate_conditions, validate_value_syntax,
    )

    try:
        browser = _detect_browser()
        _log(f"[cnki-batch] 浏览器: {browser}，正在启动...")
        driver = _create_driver(browser=browser)

        driver.get("https://kns.cnki.net/")
        time.sleep(1)
        _load_cookies(driver)

        driver.get(CNKI_SEARCH_URL)
        time.sleep(REQUEST_INTERVAL)
        driver = _handle_captcha(driver)
        _save_cookies(driver)
        _log("[cnki-batch] 浏览器就绪，开始逐组搜索...")

        use_advanced = bool(author or journal or (field and field != "主题") or match)

        for idx, keyword in enumerate(keywords):
            _log(f"\n[cnki-batch] === 搜索 {idx + 1}/{len(keywords)}: {keyword} ===")
            item: Dict[str, Any] = {
                "keyword": keyword,
                "mode": "advanced" if use_advanced else "simple",
                "requested": {}, "applied": {}, "verified": None, "total_hits": None,
            }
            retrieval_items.append(item)
            expected_values: List[str] = []

            try:
                target_url = (
                    CNKI_EXPERT_SEARCH_URL if use_advanced else CNKI_SEARCH_URL
                )
                if idx > 0:
                    driver.get(target_url)
                    time.sleep(REQUEST_INTERVAL)
                    driver = _handle_captcha(driver)
                elif use_advanced:
                    driver.get(CNKI_EXPERT_SEARCH_URL)
                    time.sleep(REQUEST_INTERVAL)
                    driver = _handle_captcha(driver)

                if cross_language is not None:
                    item["applied"]["cross_language"] = _set_cross_language(
                        driver, cross_language
                    )

                if use_advanced:
                    kw_conditions = validate_conditions(build_legacy_conditions(
                        keyword, field=field, author=author, journal=journal, match=match,
                    ))
                    expression = compile_conditions_to_expression(kw_conditions)
                    expected_values = [expression]
                    item["requested"] = {
                        "conditions": [c.to_dict() for c in kw_conditions],
                        "expression": expression,
                    }
                    item["compiled_expression"] = expression
                    item["applied"]["expression"] = expression
                    outcome = _professional_search(driver, expression)
                    if outcome.get("ok"):
                        item["applied"]["conditions"] = [
                            c.to_dict() for c in kw_conditions
                        ]
                    else:
                        err = outcome.get("error") or {}
                        raise CnkiRetrievalError(
                            "CNKI_CONDITION_NOT_APPLIED",
                            err.get("message", "检索条件编译后提交失败"),
                        )
                else:
                    keyword = normalize_value(keyword)
                    validate_value_syntax(keyword)
                    item["requested"] = {"keyword": keyword, "field": field or "主题"}
                    _input_search_keyword(driver, keyword)
                time.sleep(REQUEST_INTERVAL)
                driver = _handle_captcha(driver)

                verified_empty = False
                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "table.result-table-list tbody tr, .result-table-list tbody tr, #gridTable tbody tr"))
                    )
                except TimeoutException:
                    _log(f"[cnki-batch] 等待结果超时，检查页面状态: {keyword}")
                    page_state = _classify_result_page(driver)
                    if page_state == "security_gate":
                        raise CnkiSecurityError(
                            "CNKI_SECURITY_GATE_UNRESOLVED",
                            f"知网搜索 '{keyword}' 仍处于安全验证状态，检索未完成",
                            _cnki_page_diagnostics(driver),
                        )
                    if page_state != "verified_empty":
                        raise CnkiSecurityError(
                            "CNKI_RESULT_PAGE_UNAVAILABLE",
                            f"知网搜索 '{keyword}' 的结果表格未加载，页面状态不可确认",
                            _cnki_page_diagnostics(driver),
                        )
                    verified_empty = True
                    empty_keywords.append(keyword)
                    _log(f"[cnki-batch] {keyword}: 已确认真实空结果页面")

                if item["mode"] == "advanced" and expected_values:
                    verification = _verify_professional_expression(
                        driver, expected_values[0]
                    )
                    item["verified"] = verification["verified"]
                    if verification.get("actual"):
                        item["applied"]["expression_readback"] = verification["actual"]
                    if verification["verified"] is False:
                        raise CnkiRetrievalError(
                            "CNKI_RETRIEVAL_MISMATCH",
                            f"知网搜索 '{keyword}' 的专业检索表达式回读不一致: "
                            f"请求 {expected_values[0]!r}，实际 {verification.get('actual')!r}",
                        )
                item["total_hits"] = _read_total_hits(driver)

                if verified_empty:
                    continue

                if doc_type and idx == 0:
                    if _switch_to_doc_type(driver, doc_type):
                        driver = _handle_captcha(driver)

                kw_core_ok = False
                if core:
                    kw_core_ok = _set_core_filter(driver, core)
                    if not kw_core_ok:
                        _log(f"[cnki-batch] {keyword}: 侧边栏筛选失败，尝试切换学术期刊数据库...")
                        if _switch_to_doc_type(driver, "journal"):
                            driver = _handle_captcha(driver)
                            kw_core_ok = _set_core_filter(driver, core)
                    core_filter_results[keyword] = kw_core_ok

                if year_from is not None or year_to is not None:
                    _set_year_filter(driver, year_from, year_to)

                if sort and sort != "relevance":
                    _set_sort(driver, sort)

                time.sleep(1)

                kw_results = []
                for page_num in range(pages):
                    if page_num > 0:
                        _go_next_page(driver)
                        driver = _handle_captcha(driver)

                    page_results = _parse_search_results(driver)
                    _log(f"[cnki-batch] {keyword} 第 {page_num + 1} 页: {len(page_results)} 条")
                    kw_results.extend(page_results)
                    if not page_results:
                        break

                if core and kw_core_ok and kw_results:
                    core_labels = _parse_core_input(core)
                    for r in kw_results:
                        if r.get("title"):
                            r["is_core"] = True
                            r["core_type"] = ",".join(core_labels)

                all_results.extend(kw_results)
                _log(f"[cnki-batch] {keyword}: 获取 {len(kw_results)} 条")

            except CnkiSecurityError as e:
                err_msg = f"搜索 '{keyword}' 失败: {e.message}"
                _log(f"[cnki-batch] {err_msg}")
                error = {"keyword": keyword, "code": e.code, "error": e.message}
                if e.diagnostics:
                    error["diagnostics"] = e.diagnostics
                errors.append(error)
                continue
            except CnkiQueryError as e:
                _log(f"[cnki-batch] {keyword}: 检索式不合法: {e.message}")
                errors.append({"keyword": keyword, "code": e.code, "error": e.message})
                continue
            except Exception as e:
                err_msg = f"搜索 '{keyword}' 失败: {e}"
                _log(f"[cnki-batch] {err_msg}")
                errors.append({"keyword": keyword, "code": "CNKI_SEARCH_FAILED", "error": str(e)})
                continue

        deduped = _dedupe_results(all_results)
        deduped = _filter_by_year(deduped, year_from, year_to)

        _log(f"\n[cnki-batch] 完成: 总计 {len(all_results)} 条, 去重/过滤后 {len(deduped)} 条, 错误 {len(errors)} 组")

        result: Dict[str, Any] = {
            "status": "partial" if errors else ("empty" if not deduped else "success"),
            "count": len(deduped),
            "results": deduped,
        }
        if empty_keywords:
            result["empty_keywords"] = empty_keywords
        if errors:
            result["errors"] = errors
        if core and core_filter_results:
            failed_kws = [kw for kw, ok in core_filter_results.items() if not ok]
            if failed_kws:
                result["filter_warning"] = (
                    f"侧边栏筛选 '{core}' 未生效（结果可能包含非核心文献）: "
                    f"{', '.join(failed_kws)}"
                )
        return result

    except CnkiSecurityError as e:
        result = {"status": "error", "code": e.code, "message": e.message}
        if e.diagnostics:
            result["diagnostics"] = e.diagnostics
        return result
    except Exception as e:
        return {"status": "error", "code": "CNKI_BATCH_FAILED",
                "message": str(e)}
    finally:
        if meta is not None:
            meta["retrieval"] = {
                "source": "cnki", "mode": "batch", "queries": retrieval_items,
            }
        if driver is not None:
            try:
                _save_cookies(driver)
                if not _driver_is_reused(driver):
                    driver.quit()
            except Exception:
                pass


# ── 输入与筛选 ────────────────────────────────────────

def _classify_result_page(driver) -> str:
    """Classify CNKI result page without confusing retry/security pages with empty."""
    if _is_cnki_security_gate(driver) or _has_captcha_elements(driver):
        return "security_gate"
    try:
        tables = driver.find_elements(
            By.CSS_SELECTOR, "table.result-table-list, .result-table-list, #gridTable"
        )
        rows = driver.find_elements(
            By.CSS_SELECTOR,
            "table.result-table-list tbody tr, .result-table-list tbody tr, #gridTable tbody tr",
        )
        if tables and rows:
            return "results"
        body_text = driver.execute_script(
            "return (document.body && document.body.innerText || '').substring(0, 5000);"
        ) or ""
    except Exception:
        return "unknown"

    empty_markers = ("暂无数据", "暂无相关数据", "未检索到相关结果", "没有找到相关结果")
    # 实测（2026-10）：知网真实空结果页的文案是
    # 「抱歉，暂无数据，请稍后重试。」——它自带“请稍后重试”字样，
    # 因此该短语不能作为否决“空结果”的依据，否则 0 命中的合法检索会被误报为页面不可用。
    # 限流/异常页仍通过“系统繁忙/访问异常”以及前面的安全验证判定拦截。
    retry_markers = ("系统繁忙", "访问异常")
    if any(marker in body_text for marker in empty_markers):
        if not any(marker in body_text for marker in retry_markers):
            return "verified_empty"
    return "unknown"

def _input_search_keyword(driver, keyword: str):
    """在知网搜索页面输入关键词并提交"""
    selectors = [
        (By.CSS_SELECTOR, "#txt_search"),
        (By.CSS_SELECTOR, "input.search-input"),
        (By.ID, "txt_SearchText"),
        (By.CSS_SELECTOR, "input[name='txt_1_value1']"),
    ]
    search_input = None
    for by, selector in selectors:
        try:
            search_input = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((by, selector))
            )
            break
        except TimeoutException:
            continue

    if not search_input:
        raise RuntimeError("无法找到知网搜索输入框")

    search_input.clear()
    search_input.send_keys(keyword)
    time.sleep(0.5)

    btn_selectors = [
        "input.search-btn",
        ".search-btn",
        "input.btnSearch",
        "button.search-btn",
    ]
    for sel in btn_selectors:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, sel)
            driver.execute_script("arguments[0].click();", btn)
            return
        except (NoSuchElementException, ElementClickInterceptedException):
            continue

    search_input.send_keys(Keys.RETURN)


class CnkiRetrievalError(CnkiSecurityError):
    """检索条件未按请求应用，或结果页回读与请求不一致。

    继承 CnkiSecurityError 以复用 search/batch 既有的结构化错误出口。
    """


def _visible_professional_box(driver):
    """返回专业检索页当前可见的表达式输入框；找不到返回 None。"""
    try:
        return driver.execute_script(r"""
            var prefer = document.querySelectorAll('textarea.majorSearch, textarea.textarea-major');
            for (var i = 0; i < prefer.length; i++) {
                if (prefer[i].offsetParent !== null) return prefer[i];
            }
            var all = document.querySelectorAll('textarea');
            for (var j = 0; j < all.length; j++) {
                if (all[j].offsetParent !== null) return all[j];
            }
            return null;
        """)
    except Exception:
        return None


def _professional_search(driver, expression: str) -> Dict[str, Any]:
    """在专业检索页写入表达式并提交。

    调用方负责先导航到 CNKI_EXPERT_SEARCH_URL：高级检索页上的“专业检索”标签是
    指向该独立 URL 的 target=_blank 链接，点击不会切换当前页面（实测 2026-10）。
    """
    _log(f"[cnki-pro] 专业检索表达式: {expression}")
    try:
        box = _visible_professional_box(driver)
        if box is None:
            return {"ok": False,
                    "error": {"code": "form_not_found",
                              "message": "未找到专业检索输入框"}}
        driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
            box, expression,
        )
        written = (box.get_attribute("value") or "").strip()
        if written != expression.strip():
            return {"ok": False,
                    "error": {"code": "condition_not_applied",
                              "message": f"表达式写入后回读不一致（实际 {written!r}），未提交"}}
        clicked = driver.execute_script(r"""
            var bs = document.querySelectorAll(
                'input.btn-search, .search-btn, input[type=button], button');
            for (var i = 0; i < bs.length; i++) {
                var el = bs[i];
                if (el.offsetParent === null) continue;
                var label = (el.value || el.textContent || '').trim();
                if (label.indexOf('检索') !== -1) { el.click(); return true; }
            }
            return false;
        """)
        if not clicked:
            return {"ok": False,
                    "error": {"code": "form_not_found",
                              "message": "未找到专业检索的检索按钮"}}
        _log("[cnki-pro] 已提交专业检索")
        return {"ok": True, "written": written, "error": None}
    except Exception as e:
        _log(f"[cnki-pro] 专业检索失败: {e}")
        return {"ok": False,
                "error": {"code": "form_not_found", "message": str(e)}}


def _set_cross_language(driver, enabled: bool) -> Optional[bool]:
    """设置检索控制区的中英文扩展。返回实际生效值；找不到控件返回 None。"""
    try:
        script = r"""
        var want = arguments[0];
        var labels = document.querySelectorAll('label, span, div');
        for (var i = 0; i < labels.length; i++) {
            var el = labels[i];
            var text = (el.textContent || '').trim();
            if (text.length > 40 || text.indexOf('中英文扩展') === -1) continue;
            var box = el.querySelector('input[type="checkbox"]');
            if (!box && el.previousElementSibling &&
                el.previousElementSibling.type === 'checkbox') {
                box = el.previousElementSibling;
            }
            if (!box) {
                var parent = el.parentElement;
                if (parent) box = parent.querySelector('input[type="checkbox"]');
            }
            if (!box) continue;
            var before = box.checked;
            if (before !== want) box.click();
            return JSON.stringify({found: true, before: before, after: box.checked});
        }
        return JSON.stringify({found: false});
        """
        raw = driver.execute_script(script, bool(enabled))
        info = json.loads(raw) if raw else {}
        if not info.get("found"):
            _log("[cnki] 未找到中英文扩展控件，保持知网默认")
            return None
        _log(f"[cnki] 中英文扩展: {info.get('before')} -> {info.get('after')}")
        return bool(info.get("after"))
    except Exception as e:
        _log(f"[cnki] 设置中英文扩展失败: {e}")
        return None


def _read_professional_expression(driver) -> Optional[str]:
    """回读专业检索输入框当前值（结果页仍保留已提交的表达式）。读不到返回 None。"""
    box = _visible_professional_box(driver)
    if box is None:
        return None
    try:
        value = (box.get_attribute("value") or "").strip()
    except Exception:
        return None
    return value or None


def _read_total_hits(driver) -> Optional[int]:
    """读取命中数。只在明确的结果计数容器内解析，不在整页正文里猜数字。"""
    try:
        raw = driver.execute_script(r"""
            var selectors = ['.pagerTitleCell', '.result-count', '.total-count',
                             '.search-result-count', '.result-num', '.count-num'];
            for (var i = 0; i < selectors.length; i++) {
                var els = document.querySelectorAll(selectors[i]);
                for (var j = 0; j < els.length; j++) {
                    var t = (els[j].textContent || '').trim();
                    if (t && t.length < 200) return t;
                }
            }
            return '';
        """)
        text = (raw or "").strip()
        if not text:
            return None
        match = re.search(r"([0-9][0-9,]*)\s*条", text)
        if not match:
            match = re.search(r"共\s*([0-9][0-9,]*)", text)
        if not match:
            return None
        return int(match.group(1).replace(",", ""))
    except Exception:
        return None


def _verify_professional_expression(driver, expected: str) -> Dict[str, Any]:
    """把回读值与请求表达式比对：True/False，读不到为 None。"""
    actual = _read_professional_expression(driver)
    if actual is None:
        return {"verified": None, "actual": None}
    compact = lambda text: re.sub(r"\s+", "", text or "")
    return {"verified": compact(actual) == compact(expected), "actual": actual}


def _set_year_filter(driver, year_from: int = None, year_to: int = None):
    """通过侧边栏「年度」分组中的 checkbox 筛选年份。"""
    if year_from is None and year_to is None:
        return

    current_year = time.localtime().tm_year
    y_from = year_from or 1900
    y_to = year_to or current_year

    try:
        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "dt.tit"))
            )
        except TimeoutException:
            _log("[cnki] 侧边栏未加载，将依赖客户端过滤")
            return

        expand_js = """
        var dts = document.querySelectorAll('dt.tit');
        for (var i = 0; i < dts.length; i++) {
            if ((dts[i].textContent || '').indexOf('年度') >= 0) {
                var dl = dts[i].closest('dl');
                if (dl && dl.classList.contains('off')) {
                    dts[i].click();
                    return 'expanded';
                }
                return 'already_open';
            }
        }
        return 'not_found';
        """
        expand_result = driver.execute_script(expand_js)
        _log(f"[cnki] 年度面板展开: {expand_result}")

        if expand_result == "not_found":
            _log("[cnki] 侧边栏未找到「年度」分组，将依赖客户端过滤")
            return

        if expand_result == "expanded":
            time.sleep(2)

        click_js = """
        var yFrom = arguments[0], yTo = arguments[1];
        var dts = document.querySelectorAll('dt.tit');
        var targetDl = null;
        for (var i = 0; i < dts.length; i++) {
            if ((dts[i].textContent || '').indexOf('年度') >= 0) {
                targetDl = dts[i].closest('dl');
                break;
            }
        }
        if (!targetDl) return JSON.stringify({stage:'no_dl'});

        var items = targetDl.querySelectorAll('dd li');
        var clicked = [], values = [];
        for (var j = 0; j < items.length; j++) {
            var cb = items[j].querySelector('input[type=checkbox]');
            var a = items[j].querySelector('a');
            var txt = a ? a.textContent.trim() : items[j].textContent.trim();
            values.push(txt);
            var yearNum = parseInt(txt, 10);
            if (!isNaN(yearNum) && yearNum >= yFrom && yearNum <= yTo && cb) {
                cb.click();
                clicked.push(yearNum);
            }
        }
        return JSON.stringify({stage: clicked.length > 0 ? 'clicked' : 'no_match',
                               total: items.length, values: values.slice(0,10), clicked: clicked});
        """
        result_json = driver.execute_script(click_js, y_from, y_to)
        _log(f"[cnki] 年份筛选结果: {result_json}")

        if result_json:
            info = json.loads(result_json)
            if info.get("clicked"):
                _log(f"[cnki] 已勾选年份: {info['clicked']}")
                time.sleep(2)
                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "table.result-table-list, .result-table-list"))
                    )
                except TimeoutException:
                    _log("[cnki] 年份筛选后等待结果超时，继续...")
                time.sleep(1)
            else:
                _log(f"[cnki] 年份范围 {y_from}-{y_to} 未匹配到选项 (可用: {info.get('values', [])})")
    except Exception as e:
        _log(f"[cnki] 年份筛选失败: {e}，将依赖客户端过滤")


_DOCTYPE_TAB_MAP = {
    "journal": ("学术期刊", "期刊"),
    "master": ("硕士",),
    "doctor": ("博士",),
    "thesis": ("学位", "学位论文"),
    "conference": ("会议",),
    "newspaper": ("报纸",),
}


def _switch_to_doc_type(driver, doc_type: str) -> bool:
    """点击知网搜索结果顶部的文献类型标签。

    doc_type 可选: journal / master / doctor / thesis / conference / newspaper
    """
    keywords = _DOCTYPE_TAB_MAP.get(doc_type)
    if not keywords:
        _log(f"[cnki] 未知文献类型: {doc_type}，可选: {list(_DOCTYPE_TAB_MAP.keys())}")
        return False

    switch_js = r"""
    var keywords = arguments[0];
    var tabs = document.querySelectorAll('.doctype-menus a[name="classify"], .doctype-menus a');
    var available = [];
    for (var i = 0; i < tabs.length; i++) {
        var t = (tabs[i].textContent || '').trim();
        available.push(t);
        for (var k = 0; k < keywords.length; k++) {
            if (t.indexOf(keywords[k]) >= 0) {
                tabs[i].click();
                return JSON.stringify({status: 'clicked', text: t,
                    classid: tabs[i].getAttribute('classid')});
            }
        }
    }
    return JSON.stringify({status: 'not_found', available: available});
    """
    try:
        raw = driver.execute_script(switch_js, list(keywords))
        info = json.loads(raw) if raw else {}
        _log(f"[cnki] 切换文献类型 '{doc_type}': {json.dumps(info, ensure_ascii=False)}")
        if info.get("status") == "clicked":
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "table.result-table-list, .result-table-list"))
                )
            except TimeoutException:
                _log("[cnki] 切换文献类型后等待结果超时，继续...")
            time.sleep(1)
            return True
        else:
            _log(f"[cnki] 未找到文献类型标签 '{doc_type}'，可用: {info.get('available', [])}")
    except Exception as e:
        _log(f"[cnki] 切换文献类型失败: {e}")
    return False


def _parse_core_input(core: str) -> list[str]:
    """将逗号分隔的字符串拆分为选项列表，去重保序。

    Agent 负责将用户意图翻译为知网侧边栏的实际选项名（北大核心/CSSCI/AMI/WJCI/CSCD/EI），
    脚本只做机械拆分和点击，不做语义解析。
    """
    items = [s.strip() for s in core.split(",") if s.strip()]
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _set_core_filter(driver, core: str) -> bool:
    """设置核心期刊筛选——支持逗号分隔多选。

    通过 dl[groupid='LYBSM'] 定位侧边栏来源类别面板，逐个点击需要的选项。
    知网侧边栏为复选框，点击后页面刷新但面板保留，可继续点击下一个。
    """
    core_names = _parse_core_input(core)
    if not core_names:
        _log(f"[cnki] 核心期刊参数为空: {core}")
        return False

    unknown = [n for n in core_names if n not in CNKI_SIDEBAR_CORES]
    if unknown:
        _log(f"[cnki] 警告: 以下选项可能不在知网侧边栏中: {unknown}，"
             f"知网已知选项: {CNKI_SIDEBAR_CORES}（仍会尝试点击）")

    _log(f"[cnki] 核心期刊筛选目标: {core_names}")

    click_one_js = r"""
    var coreName = arguments[0];

    var lybsm = document.querySelector('dl[groupid="LYBSM"]');
    if (lybsm) {
        if (lybsm.classList.contains('off')) {
            var dt = lybsm.querySelector('dt');
            if (dt) dt.click();
        }
        var links = lybsm.querySelectorAll('a');
        for (var i = 0; i < links.length; i++) {
            var title = (links[i].getAttribute('title') || '').trim();
            var text = (links[i].textContent || '').trim();
            if (title === coreName || text === coreName || text.indexOf(coreName) >= 0) {
                var cb = links[i].querySelector('input[type="checkbox"]');
                if (cb && cb.checked) {
                    return JSON.stringify({status:'already_checked', text: text});
                }
                links[i].scrollIntoView({block: 'center'});
                links[i].click();
                return JSON.stringify({status:'clicked', text: text});
            }
        }
        var avail = [];
        for (var j = 0; j < links.length; j++) {
            avail.push((links[j].getAttribute('title') || links[j].textContent || '').trim());
        }
        return JSON.stringify({status:'type_not_found', available: avail});
    }

    var dls = document.querySelectorAll('dl[groupid]');
    var gids = [];
    for (var k = 0; k < dls.length; k++) gids.push(dls[k].getAttribute('groupid'));
    return JSON.stringify({status:'no_lybsm', dl_groupids: gids});
    """

    clicked_any = False

    for name in core_names:
        success = False
        for attempt in range(4):
            if attempt > 0:
                wait = 2 + attempt * 3
                time.sleep(wait)
            try:
                raw = driver.execute_script(click_one_js, name)
                info = json.loads(raw) if raw else {}
                status = info.get("status", "error")

                if status == "clicked":
                    _log(f"[cnki] 已勾选: {name}")
                    try:
                        WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR,
                                 "table.result-table-list, .result-table-list"))
                        )
                    except TimeoutException:
                        pass
                    clicked_any = True
                    success = True
                    break
                elif status == "already_checked":
                    _log(f"[cnki] 已选中（跳过）: {name}")
                    success = True
                    break
                elif status == "no_lybsm":
                    _log("[cnki] 来源类别面板不存在")
                    break
                elif status == "type_not_found":
                    avail = info.get("available", [])
                    if avail:
                        _log(f"[cnki] LYBSM 中无 {name}，可用: {avail}")
                        break
                    _log(f"[cnki] LYBSM 面板链接未加载，等待重试 ({attempt+1}/4)...")
                    continue
            except Exception as e:
                _log(f"[cnki] 核心筛选脚本执行失败: {e}")
                break

        if not success:
            _log(f"[cnki] 核心期刊筛选未成功: {name}")

    if clicked_any:
        _log(f"[cnki] 核心期刊筛选完成")
    return clicked_any


def _set_sort(driver, sort: str):
    """设置排序方式（kns8s 排序栏 #orderList li）"""
    sort_id_map = {
        "date": "PT",
        "citations": "CF",
        "downloads": "DFR",
        "relevance": "FFD",
        "comprehensive": "ZH",
    }
    sort_text_map = {
        "date": "发表时间",
        "citations": "被引",
        "downloads": "下载",
        "relevance": "相关度",
        "comprehensive": "综合",
    }
    sort_id = sort_id_map.get(sort)
    sort_text = sort_text_map.get(sort)
    if not sort_id:
        return

    try:
        li = driver.find_element(By.CSS_SELECTOR, f"#orderList li#{sort_id}")
        if "cur" in (li.get_attribute("class") or ""):
            _log(f"[cnki] 排序已经是 {sort_text}，无需切换")
            return
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", li)
        time.sleep(0.3)
        li.click()
        _log(f"[cnki] 已点击排序: {sort_text} (#{sort_id})")
        time.sleep(1.5)
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "table.result-table-list, .result-table-list"))
            )
        except TimeoutException:
            _log("[cnki] 排序后等待结果超时，继续...")
        return
    except NoSuchElementException:
        pass

    try:
        li = driver.find_element(
            By.XPATH, f"//ul[@id='orderList']/li[contains(text(),'{sort_text}')]"
        )
        li.click()
        _log(f"[cnki] 已通过 XPath 点击排序: {sort_text}")
        time.sleep(1.5)
    except NoSuchElementException:
        _log(f"[cnki] 未找到排序选项: {sort_text}")


def _go_next_page(driver):
    """翻到下一页"""
    try:
        next_btn = driver.find_element(By.CSS_SELECTOR, "a.next, #PageNext, a[id='PageNext']")
        next_btn.click()
        time.sleep(2)
    except (NoSuchElementException, ElementClickInterceptedException):
        pass


def _extract_pages_from_gbt7714(ref: str) -> str:
    ref = ref.strip()
    if not ref:
        return ""
    patterns = (
        r'[,，]\s*(\d+(?:[-–—]\d+)?)\s*\[(?:19|20)\d{2}',
        r'\)\s*[:：]\s*(\d+(?:[-–—]\d+)?)',
        r'(?:19|20)\d{2}[^.。]*[:：]\s*(\d+(?:[-–—]\d+)?)',
        r'[,，]\s*(\d+[-–—]\d+)(?=\.|。|$)',
    )
    for pattern in patterns:
        matches = re.findall(pattern, ref)
        if matches:
            return matches[-1].replace('–', '-').replace('—', '-')
    return ""


# ── 结果解析 ──────────────────────────────────────────

def _parse_search_results(driver, cite_enrich: int = 0) -> list[dict]:
    """解析当前页的搜索结果"""
    results = []

    row_selectors = [
        "table.result-table-list tbody tr",
        ".result-table-list tbody tr",
        "#gridTable tbody tr",
    ]

    rows = []
    for selector in row_selectors:
        rows = driver.find_elements(By.CSS_SELECTOR, selector)
        if rows:
            break

    for idx, row in enumerate(rows):
        try:
            result = _parse_single_row(row)
            if result and result.get("title"):
                if idx < cite_enrich:
                    try:
                        _enrich_row_from_quote_popup(driver, row, result)
                    except Exception as e:
                        _log(f"[cnki] 引用补全跳过: {e}")
                results.append(result)
        except Exception as e:
            _log(f"[cnki] 单行解析失败: {e}")
            continue

    return results

def _enrich_row_from_quote_popup(driver, row, result: Dict[str, Any]) -> None:
    try:
        quote_btn = row.find_element(By.CSS_SELECTOR, "a.icon-quote")
    except NoSuchElementException:
        return

    try:
        driver.execute_script("arguments[0].click();", quote_btn)
        WebDriverWait(driver, 8).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".quote-pop"))
        )
        gbt_text = driver.execute_script(r"""
            var rows = document.querySelectorAll('.quote-pop tr');
            for (var i = 0; i < rows.length; i++) {
                var left = rows[i].querySelector('.quote-l');
                var right = rows[i].querySelector('.quote-r');
                if (left && right && left.textContent.indexOf('GB/T') >= 0) {
                    return right.textContent.trim();
                }
            }
            var first = document.querySelector('.quote-pop .quote-r');
            return first ? first.textContent.trim() : '';
        """) or ""
        if gbt_text:
            result["gbt7714_raw"] = gbt_text
            pages = _extract_pages_from_gbt7714(gbt_text)
            if pages and not result.get("pages"):
                result["pages"] = pages
    except Exception as e:
        _log(f"[cnki] 引用弹窗解析失败: {e}")
    finally:
        try:
            close_btn = driver.find_element(By.CSS_SELECTOR, ".quote-pop .layui-layer-close")
            driver.execute_script("arguments[0].click();", close_btn)
            time.sleep(0.2)
        except Exception:
            try:
                driver.execute_script("document.querySelectorAll('.quote-pop').forEach(function(e){e.remove();});")
            except Exception:
                pass


def _parse_single_row(row) -> dict:
    """解析单行搜索结果"""
    result = {
        "title": "",
        "authors": "",
        "journal": "",
        "date": "",
        "cited_by": 0,
        "url": "",
        "is_core": False,
        "core_type": "",
        "source": "CNKI",
    }

    try:
        title_el = row.find_element(By.CSS_SELECTOR, "td.name a, .fz14")
        result["title"] = title_el.text.strip()
        result["url"] = title_el.get_attribute("href") or ""
    except NoSuchElementException:
        return result

    try:
        author_el = row.find_element(By.CSS_SELECTOR, "td.author, .author")
        result["authors"] = author_el.text.strip()
    except NoSuchElementException:
        pass

    try:
        source_el = row.find_element(By.CSS_SELECTOR, "td.source, .source")
        result["journal"] = source_el.text.strip()
    except NoSuchElementException:
        pass

    try:
        date_el = row.find_element(By.CSS_SELECTOR, "td.date, .date")
        result["date"] = date_el.text.strip()
        year_m = re.search(r'(?:19|20)\d{2}', result["date"])
        if year_m:
            result["year"] = int(year_m.group(0))
    except NoSuchElementException:
        pass

    try:
        cite_el = row.find_element(By.CSS_SELECTOR, "td.quote, .quote, td.count")
        cite_text = cite_el.text.strip()
        if cite_text.isdigit():
            result["cited_by"] = int(cite_text)
    except (NoSuchElementException, ValueError):
        pass

    # 行内核心期刊标记（弱信号：CNKI 搜索结果页未必显示这些标签，
    # 但保留检测以便将来 CNKI 改版时自动生效）
    try:
        badge_els = row.find_elements(By.CSS_SELECTOR,
            "span[class*='icon'], em[class*='icon'], i[class*='icon'], .badge, .tag")
        detected_cores = set()
        for badge in badge_els:
            cls = (badge.get_attribute("class") or "").lower()
            txt = (badge.text or "").strip()
            if "cssci" in cls or txt == "CSSCI" or "南大核心" in txt:
                detected_cores.add("CSSCI")
            elif "pku" in cls or "北大核心" in cls or txt in ("北大核心", "核心"):
                detected_cores.add("北大核心")
            elif "cscd" in cls or txt == "CSCD":
                detected_cores.add("CSCD")
            elif "sci" in cls or txt == "SCI":
                detected_cores.add("SCI")
            elif "ei" in cls or txt == "EI":
                detected_cores.add("EI")
            elif "科技核心" in cls or "统计源" in cls or txt in ("科技核心", "统计源"):
                detected_cores.add("科技核心")
        if detected_cores:
            result["is_core"] = True
            result["core_type"] = ";".join(sorted(detected_cores))
    except Exception:
        pass

    return result
