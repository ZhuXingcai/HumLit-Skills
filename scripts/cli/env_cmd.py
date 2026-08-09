from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from cli._common import _output, __version__
from core.paths import state_dir


def _check_browser(subprocess_mod) -> tuple:
    """检测可用浏览器，返回 (ok: bool, detail: str)"""
    import shutil as _shutil
    if sys.platform == "win32":
        import os as _os
        for p in [
            _os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            _os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
            _os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
        ]:
            if _os.path.exists(p):
                try:
                    r = subprocess_mod.run([p, "--version"], capture_output=True, text=True, timeout=5)
                    return True, r.stdout.strip() if r.returncode == 0 else f"Edge ({p})"
                except Exception:
                    return True, f"Edge ({p})"
        _chrome = _shutil.which("chrome") or _shutil.which("google-chrome")
        if _chrome:
            return True, f"Chrome ({_chrome})"
    else:
        if sys.platform == "darwin":
            from core.cnki.driver import MACOS_BROWSER_EXECUTABLES
            for _browser, executable_path in MACOS_BROWSER_EXECUTABLES:
                executable = str(executable_path)
                if not executable_path.exists():
                    continue
                try:
                    result = subprocess_mod.run(
                        [executable, "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    detail = (
                        result.stdout.strip()
                        if result.returncode == 0
                        else f"浏览器 ({executable})"
                    )
                    return True, detail
                except Exception:
                    return True, f"浏览器 ({executable})"
        for cmd in ["microsoft-edge", "microsoft-edge-stable", "google-chrome", "chromium", "chromium-browser"]:
            found = _shutil.which(cmd)
            if found:
                try:
                    r = subprocess_mod.run([found, "--version"], capture_output=True, text=True, timeout=5)
                    return True, r.stdout.strip() if r.returncode == 0 else cmd
                except Exception:
                    return True, cmd
    return False, "未检测到 Edge/Chrome"


def _check_driver() -> tuple:
    """检测浏览器驱动是否可用，返回 (ok: bool, detail: str)。"""
    try:
        from core.cnki.driver import _detect_browser, _find_local_driver
        browser = _detect_browser()
    except Exception as e:
        return False, f"无法检测浏览器类型: {e}"

    manager_available = False
    try:
        from selenium.webdriver.common.selenium_manager import SeleniumManager
        sm_bin = SeleniumManager._get_binary()
        if sm_bin and os.path.isfile(str(sm_bin)):
            manager_available = True
            import subprocess as _sp
            browser_arg = "MicrosoftEdge" if browser == "edge" else "chrome"
            result = _sp.run(
                [str(sm_bin), "--browser", browser_arg, "--offline", "--output", "json"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                try:
                    info = json.loads(result.stdout)
                    driver_path = info.get("result", {}).get("driver_path", "")
                    if driver_path and os.path.isfile(driver_path):
                        return True, f"selenium-manager 找到: {driver_path}"
                except (ValueError, KeyError):
                    pass
    except Exception:
        pass

    local = _find_local_driver(browser)
    if local:
        return True, f"本地驱动: {local}"

    driver_name = "msedgedriver" if browser == "edge" else "chromedriver"
    if manager_available:
        return True, (
            f"Selenium Manager 已就绪；首次知网操作将按需获取匹配的 {driver_name}"
        )
    return False, (
        f"未找到 {driver_name}，且 Selenium Manager 不可用。"
        f"解决：安装锁定的 selenium 依赖，或设置 HUMLIT_DRIVER_PATH"
    )


def _check_cnki() -> tuple:
    """检测知网连通性，返回 (ok: bool, detail: str)。
    SANDBOX_BLOCKED 单独标记，让 check 输出能指导 Agent 提权重试。
    """
    from core.cnki import check_cnki_access
    try:
        accessible, msg = check_cnki_access()
        if accessible:
            return True, "可访问"
        if msg.startswith("SANDBOX_BLOCKED"):
            return False, f"沙盒权限阻止（WinError 10013 等），提权后可能正常"
        return False, msg
    except Exception as e:
        return False, str(e)


def _fix_sandbox_network() -> List[str]:
    """Return manual sandbox actions without changing user or project config."""
    recommendations = []
    is_codex_env = (
        (Path.cwd() / ".codex").exists()
        or (Path.home() / ".codex").exists()
        or os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED")
    )
    if is_codex_env:
        recommendations.append(
            "手动操作：在受信任的客户端设置中授权当前任务联网；"
            "不要由 humlit-skills 改写 ~/.codex/config.toml。"
        )
    if (Path.cwd() / ".claude").exists():
        recommendations.append(
            "手动操作：按团队策略在 Claude Code 中授权 *.cnki.net；"
            "humlit-skills 不自动修改 .claude/settings.json。"
        )
    if not recommendations:
        recommendations.append(
            "手动操作：确认当前运行器允许访问目标学术数据源后重试。"
        )
    return recommendations


def _check_update():
    """只读版本对比：本地版本 vs GitHub 最新 Release/Tag（超时不阻塞）"""
    import re
    _SEMVER_RE = re.compile(r"^\d+\.\d+(\.\d+)?$")

    def _version_key(value: str) -> tuple:
        parts = [int(p) for p in value.split(".")]
        return tuple((parts + [0, 0])[:3])

    repo = "ZhuXingcai/HumLit-Skills"
    urls = [
        f"https://api.github.com/repos/{repo}/releases/latest",
        f"https://api.github.com/repos/{repo}/tags?per_page=1",
    ]

    try:
        latest = None
        for url in urls:
            if latest:
                break
            try:
                data = _fetch_json(url, timeout=5)
                if data is None:
                    continue
                if isinstance(data, list):
                    latest = data[0].get("name", "") if data else ""
                else:
                    latest = data.get("tag_name", "")
            except Exception:
                continue

        if not latest:
            return None

        latest = latest.removeprefix("v")
        if not _SEMVER_RE.match(latest):
            return None

        current = __version__.removeprefix("v")
        if not _SEMVER_RE.match(current):
            return None

        if _version_key(latest) > _version_key(current):
            return {
                "update_available": True,
                "current": current,
                "latest": latest,
                "message": f"新版本 {latest} 可用，在 skill 目录执行 git pull 更新",
            }
        return {"update_available": False, "current": current, "latest": latest}
    except Exception:
        return None


def _fetch_json(url: str, timeout: int = 10):
    """HTTP GET 返回 JSON，httpx 优先，urllib 兜底。失败统一返回 None。"""
    try:
        import httpx
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        return resp.json() if resp.status_code == 200 else None
    except ImportError:
        pass
    except Exception:
        return None
    try:
        from urllib.request import urlopen, Request
        req = Request(url, headers={"User-Agent": "humlit-skills",
                                    "Accept": "application/json"})
        with urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            import json as _json
            return _json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def cmd_clean_cache(args):
    """清理 .humlit/ 缓存目录"""
    from datetime import datetime, timedelta
    from core.config import get as cfg_get

    cache_dir = state_dir()
    if not cache_dir.exists():
        _output({"status": "success", "message": "无缓存目录", "deleted": 0, "freed_bytes": 0})
        return

    ttl_days = cfg_get("cache_ttl_days", 30)
    now = datetime.now()
    stats = {"total": 0, "expired": 0, "deleted": 0, "freed_bytes": 0, "kept": 0}

    for root, _dirs, files in os.walk(str(cache_dir)):
        for fname in files:
            fpath = Path(root) / fname
            stats["total"] += 1
            fsize = fpath.stat().st_size

            _protected = {"session.json", "config.json", "cookies.json"}
            should_delete = args.clean_all and fname not in _protected
            if not should_delete and fname.endswith(".json") and ttl_days > 0 and fname not in _protected:
                try:
                    data = json.loads(fpath.read_text(encoding="utf-8"))
                    ts = data.get("_cached_at", "")
                    if ts:
                        cached_at = datetime.fromisoformat(ts)
                        if now - cached_at > timedelta(days=ttl_days):
                            should_delete = True
                            stats["expired"] += 1
                except Exception:
                    pass

            if should_delete:
                if not args.dry_run:
                    try:
                        fpath.unlink()
                        stats["deleted"] += 1
                        stats["freed_bytes"] += fsize
                    except Exception:
                        pass
                else:
                    stats["deleted"] += 1
                    stats["freed_bytes"] += fsize
            else:
                stats["kept"] += 1

    stats["freed_mb"] = round(stats["freed_bytes"] / 1024 / 1024, 2)
    mode = "dry-run" if args.dry_run else ("全部清理" if args.clean_all else f"TTL>{ttl_days}天")
    _output({"status": "success", "mode": mode, **stats})


def cmd_workflows(args):
    """列出或执行预定义工作流模板"""
    from core.workflows import (
        list_workflows,
        get_workflow,
        render_workflow,
        render_workflow_argv,
        validate_workflow_requirements,
    )

    if args.list:
        # 列出所有工作流
        workflows = list_workflows()
        _output({
            "status": "success",
            "count": len(workflows),
            "workflows": workflows
        })
        return

    if args.execute:
        # 执行指定工作流
        workflow_id = args.execute
        workflow = get_workflow(workflow_id)

        if not workflow:
            _output({
                "status": "error",
                "code": "WORKFLOW_NOT_FOUND",
                "message": f"未找到工作流: {workflow_id}",
                "available_workflows": [wf["id"] for wf in list_workflows()]
            })
            return

        # 解析变量
        variables = {}
        if args.variables:
            try:
                variables = json.loads(args.variables)
            except json.JSONDecodeError as e:
                _output({
                    "status": "error",
                    "code": "INVALID_VARIABLES",
                    "message": f"变量 JSON 格式错误: {e}"
                })
                return

        # 检查必需变量
        missing_vars = [v for v in workflow["variables"] if v not in variables]
        if missing_vars:
            _output({
                "status": "error",
                "code": "MISSING_VARIABLES",
                "message": f"缺少必需变量: {', '.join(missing_vars)}",
                "required_variables": workflow["variables"]
            })
            return

        # 验证前置条件
        # 先运行 check 获取 capabilities
        import subprocess
        check_result = subprocess.run(
            [sys.executable, sys.argv[0], "check"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            check_data = json.loads(check_result.stdout)
            capabilities = check_data.get("capabilities", {})
        except:
            capabilities = {}

        validation = validate_workflow_requirements(workflow_id, capabilities)
        if not validation["satisfied"]:
            _output({
                "status": "error",
                "code": "REQUIREMENTS_NOT_MET",
                "message": "工作流前置条件不满足",
                "missing": validation["missing"],
                "suggestions": validation["suggestions"]
            })
            return

        # 渲染命令
        commands = render_workflow(workflow_id, variables)
        command_argvs = render_workflow_argv(workflow_id, variables)

        if args.dry_run:
            # 仅显示命令，不执行
            _output({
                "status": "success",
                "workflow_id": workflow_id,
                "workflow_name": workflow["name"],
                "commands": commands,
                "estimated_time_seconds": workflow.get("estimated_time_seconds", 10)
            })
            return

        # 执行工作流
        results = []
        for i, (cmd, command_argv) in enumerate(zip(commands, command_argvs)):
            print(f"[workflow] 步骤 {i+1}/{len(commands)}: {cmd}", file=sys.stderr)

            # 执行命令
            result = subprocess.run(
                [sys.executable, sys.argv[0]] + command_argv,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            try:
                step_result = json.loads(result.stdout)
            except:
                step_result = {"status": "error", "message": result.stdout or result.stderr}

            results.append({
                "step": i + 1,
                "command": cmd,
                "result": step_result
            })

            # 如果某步失败，停止执行
            if step_result.get("status") == "error":
                _output({
                    "status": "error",
                    "code": "WORKFLOW_STEP_FAILED",
                    "message": f"工作流在步骤 {i+1} 失败",
                    "failed_step": i + 1,
                    "failed_command": cmd,
                    "results": results
                })
                return

        _output({
            "status": "success",
            "workflow_id": workflow_id,
            "workflow_name": workflow["name"],
            "steps_completed": len(results),
            "results": results
        })
    else:
        # 没有指定操作，显示帮助
        _output({
            "status": "error",
            "code": "NO_ACTION",
            "message": "请指定 --list 或 --execute <workflow_id>"
        })


def cmd_check(args):
    """环境自检：逐项检查运行条件；--fix 仅输出手动修复建议。"""
    import subprocess
    fix_mode = getattr(args, "fix", False)

    checks = []
    recommended_actions = []

    v = sys.version_info
    checks.append({
        "item": "Python",
        "status": "ok" if v >= (3, 9) else "warn" if v >= (3, 8) else "fail",
        "detail": f"{v.major}.{v.minor}.{v.micro}",
    })

    for pkg, import_name in [
        ("selenium", "selenium"), ("httpx", "httpx"),
        ("openpyxl", "openpyxl"),
        ("python-docx", "docx"), ("pypdf", "pypdf"),
    ]:
        try:
            mod = __import__(import_name)
            ver = getattr(mod, "__version__", "?")
            status = "ok"
            detail = ver
            if pkg == "selenium" and ver != "?":
                try:
                    parts = [int(x) for x in ver.split(".")[:2]]
                    if parts < [4, 10]:
                        status = "warn"
                        detail = f"{ver}（需要 >=4.10）"
                except (ValueError, IndexError):
                    pass
            checks.append({"item": pkg, "status": status, "detail": detail})
        except ImportError:
            if pkg == "httpx":
                checks.append({"item": pkg, "status": "warn", "detail": "未安装（urllib 兜底可用）"})
            else:
                checks.append({"item": pkg, "status": "fail", "detail": "未安装"})
                if fix_mode:
                    action = (
                        "手动操作：在项目虚拟环境中运行 "
                        "`python -m pip install -r scripts/requirements.txt`，"
                        "然后重新执行 check。"
                    )
                    if action not in recommended_actions:
                        recommended_actions.append(action)

    encoding = sys.stdout.encoding or "unknown"
    checks.append({
        "item": "终端编码",
        "status": "ok" if "utf" in encoding.lower() else "warn",
        "detail": encoding,
    })

    browser_ok, browser_detail = _check_browser(subprocess)
    checks.append({
        "item": "浏览器",
        "status": "ok" if browser_ok else "warn",
        "detail": browser_detail,
    })

    driver_ok, driver_detail = _check_driver()
    driver_mode = (
        "selenium_manager_on_demand"
        if "按需获取" in driver_detail
        else "cached_or_explicit"
        if driver_ok
        else None
    )
    checks.append({
        "item": "浏览器驱动",
        "status": "ok" if driver_ok else "warn",
        "detail": driver_detail,
    })

    cnki_ok, cnki_detail = _check_cnki()
    checks.append({
        "item": "知网连通性",
        "status": "ok" if cnki_ok else "fail",
        "detail": cnki_detail,
    })

    if fix_mode and not cnki_ok:
        for action in _fix_sandbox_network():
            if action not in recommended_actions:
                recommended_actions.append(action)

    cache_dir = state_dir()
    if cache_dir.exists():
        total = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file())
        checks.append({
            "item": "缓存目录", "status": "ok",
            "detail": f"{cache_dir} ({round(total/1024/1024, 2)} MB)",
        })
    else:
        checks.append({"item": "缓存目录", "status": "ok", "detail": "尚未创建"})

    selenium_item = next((c for c in checks if c["item"] == "selenium"), None)
    selenium_ok = selenium_item is not None and selenium_item["status"] != "fail"
    sandbox_blocked = cnki_detail and "沙盒权限阻止" in cnki_detail
    cnki_feasible = browser_ok and cnki_ok and selenium_ok and driver_ok
    cnki_reasons = []
    if not selenium_ok:
        cnki_reasons.append("selenium 未安装")
    if not browser_ok:
        cnki_reasons.append("未检测到浏览器")
    if not driver_ok:
        cnki_reasons.append("浏览器驱动缺失（需联网下载）")
    if not cnki_ok:
        cnki_reasons.append("知网不可达（沙盒权限阻止）" if sandbox_blocked else "知网不可达")

    is_codex = (
        (Path.cwd() / ".codex").exists()
        or os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED")
        or any(k.startswith("CODEX_") for k in os.environ)
    )
    from core.config import get as cfg_get
    semantic_scholar_key_configured = bool(
        str(cfg_get("semantic_scholar_api_key", "") or "").strip()
    )

    capabilities: Dict[str, Any] = {
        "cnki_feasible": cnki_feasible,
        "sandbox_blocked": sandbox_blocked,
        "driver_ok": driver_ok,
        "driver_mode": driver_mode,
        "api_connectors_available": True,
        "api_sources_runtime_verified": None,
        "docx_tools": any(c["item"] == "python-docx" and c["status"] == "ok" for c in checks),
        "pdf_tools": any(c["item"] == "pypdf" and c["status"] == "ok" for c in checks),

        # 详细数据源能力矩阵
        "sources": {
            "cnki": {
                "available": cnki_feasible,
                "maturity": "conditional_desktop",
                "connector_available": selenium_ok,
                "runtime_verified": None,
                "availability_scope": "local_prerequisites_only",
                "driver_mode": driver_mode,
                "features": ["search", "download", "fulltext", "master_thesis", "doctor_thesis", "core_journals"],
                "limitations": ["requires_vpn", "rate_limited", "chinese_only"],
                "recommended_for": ["中文文献", "学位论文", "核心期刊筛选"]
            },
            "openalex": {
                "available": None,
                "maturity": "conditional_live",
                "connector_available": True,
                "runtime_verified": None,
                "availability_scope": "local_connector_only",
                "features": ["search", "sort_citations", "sort_date", "sort_priority",
                             "filter_journal", "filter_author", "filter_field", "pagination",
                             "retrieval_priority_scoring", "deduplication"],
                "limitations": ["metadata_coverage_varies", "fulltext_not_guaranteed"],
                "recommended_for": ["综合文献", "高被引线索", "跨学科检索", "元数据优先核验"]
            },
            "semantic_scholar": {
                "available": None,
                "maturity": "conditional_live",
                "connector_available": True,
                "runtime_verified": None,
                "availability_scope": "local_connector_only",
                "api_key_configured": semantic_scholar_key_configured,
                "features": ["search", "sort_citations", "sort_date", "citations_network",
                             "filter_author", "filter_field"],
                "limitations": ["narrow_coverage", "occasional_empty_results"],
                "recommended_for": ["计算机科学", "生物医学", "引文分析"]
            },
            "arxiv": {
                "available": None,
                "maturity": "conditional_live",
                "connector_available": True,
                "runtime_verified": None,
                "availability_scope": "local_connector_only",
                "features": ["search", "sort_date", "fulltext_oa", "pagination"],
                "limitations": ["no_citations", "preprints_only", "no_peer_review"],
                "recommended_for": ["最新预印本", "物理/数学/计算机科学"]
            },
            "nssd": {
                "available": None,
                "maturity": "conditional_live",
                "connector_available": True,
                "runtime_verified": None,
                "availability_scope": "local_connector_only",
                "features": ["search", "chinese_social_science"],
                "limitations": ["limited_metadata", "slow_response"],
                "recommended_for": ["中文社科文献"]
            },
            "dblp": {
                "available": None,
                "maturity": "conditional_live",
                "connector_available": True,
                "runtime_verified": None,
                "availability_scope": "local_connector_only",
                "features": ["search", "computer_science", "author_metadata"],
                "limitations": ["no_abstract", "no_citation_count"],
                "recommended_for": ["计算机科学", "会议论文", "作者追踪"]
            },
            "base": {
                "available": False,
                "maturity": "experimental",
                "connector_available": True,
                "runtime_verified": None,
                "availability_scope": "explicit_opt_in_only",
                "opt_in_only": True,
                "features": ["search", "open_access", "repository_coverage"],
                "limitations": ["excluded_from_default_aggregation", "known_live_timeouts",
                                "occasional_access_restrictions", "heterogeneous_metadata"],
                "recommended_for": ["显式试验性的机构知识库补检"]
            }
        },

        # 推荐工作流
        "workflows": {
            "literature_review": {
                "steps": [
                    "search '{topic}' --source openalex --sort citations --year-from 2015 --limit 20",
                    "search '{topic}' --source openalex --sort date --year-from 2023 --limit 10 --append",
                    "review --cluster --gaps"
                ],
                "description": "综述证据脚手架：经典线索 + 最新进展 + 主题聚类",
                "variables": ["topic"]
            },
            "retrieval_priority_screening": {
                "steps": [
                    "search '{topic}' --source openalex --sort priority --year-from {year} --journal-filter '{journal}' --limit 30"
                ],
                "description": "检索优先级筛选：按元数据完整性和影响力线索排序 + 期刊过滤",
                "variables": ["topic", "year", "journal"]
            },
            "topic_research": {
                "steps": [
                    "search '{topic}' --source api --async-search --limit 30 --project {project}",
                    "topics --project {project}",
                    "validate --project {project}"
                ],
                "description": "选题假设：多源搜索 + 当前库覆盖分析 + 词项级证据预检",
                "variables": ["topic", "project"]
            }
        },

        # Agent 决策提示
        "agent_hints": {
            "for_chinese_literature": "优先使用 cnki（需校园网/VPN）或 nssd",
            "for_english_literature": "优先使用 openalex（支持高级过滤和检索优先级排序）",
            "for_latest_research": "使用 arxiv（预印本）或 --sort date",
            "for_priority_screening": "使用 --sort priority 安排核验顺序；不得将分数解释为学术质量",
            "for_biomedical": "可使用 semantic_scholar，并以实际覆盖和 source_statuses 为准",
            "for_citations_network": "使用 citations 命令（基于 Semantic Scholar）",
            "for_thesis": "使用 cnki --doc-type master/doctor",
            "for_core_journals": "使用 cnki --core 北大核心,CSSCI"
        },

        "operations": {
            "cache_enabled": True,
            "concurrent_sources": True,
            "performance_guarantee": None
        }
    }
    if not cnki_feasible:
        capabilities["cnki_blocked_reasons"] = cnki_reasons
        capabilities["suggested_sources"] = ["openalex", "semantic", "arxiv", "nssd"]
        capabilities["sources"]["cnki"]["available"] = False

        if sandbox_blocked or (is_codex and not driver_ok):
            capabilities["needs_escalation"] = True
            capabilities["reason_code"] = "browser_or_driver_requires_host_permission"
            capabilities["agent_action"] = "rerun_same_command_with_escalated_permissions"
            capabilities["retry_command"] = (
                "py -3 -X utf8 scripts/literature.py check --fix"
                if sys.platform == "win32"
                else "python3 scripts/literature.py check --fix"
            )
            capabilities["recommended_env"] = {
                "SE_CACHE_PATH": ".humlit/selenium-cache",
                "HUMLIT_SKIP_NETWORK_CHECK": "1",
            }
            capabilities["fix_note"] = (
                "沙盒限制导致预检/驱动下载失败。"
                "解决：设置 HUMLIT_SKIP_NETWORK_CHECK=1，"
                "然后以提权方式运行知网命令（平台会弹窗让用户授权网络访问）。"
                "提权后 Selenium Manager 自动下载驱动，所有卡点一步清零"
            )
        elif not driver_ok:
            capabilities["fix_note"] = (
                "浏览器驱动缺失。确保有网络连接后运行任意知网命令，"
                "Selenium Manager 会自动下载匹配的驱动。"
                "或手动设置 HUMLIT_DRIVER_PATH 环境变量指向已有驱动"
            )
        elif fix_mode and not cnki_ok and recommended_actions:
            capabilities["fix_note"] = (
                "check 不修改沙箱或依赖环境；请按 recommended_actions "
                "手动授权网络、安装锁定依赖并确认校园网/VPN。"
            )

    update_info = _check_update()

    all_ok = all(c["status"] != "fail" for c in checks)
    output: Dict[str, Any] = {
        "status": "success" if all_ok else "warning",
        "version": __version__,
        "capabilities": capabilities,
        "checks": checks,
    }
    if recommended_actions:
        output["recommended_actions"] = recommended_actions
    if update_info:
        output["update"] = update_info
    _output(output)


def add_parser(sub):
    # clean-cache
    p_clean = sub.add_parser("clean-cache", help="清理过期缓存文件")
    p_clean.add_argument("--all", action="store_true", dest="clean_all",
                         help="删除所有缓存（不仅是过期的）")
    p_clean.add_argument("--dry-run", action="store_true",
                         help="仅统计，不实际删除")
    p_clean.set_defaults(func=cmd_clean_cache)

    # workflows
    p_workflows = sub.add_parser("workflows", help="列出或执行预定义工作流模板")
    p_workflows.add_argument("--list", action="store_true", help="列出所有可用工作流")
    p_workflows.add_argument("--execute", help="执行指定工作流 ID")
    p_workflows.add_argument("--variables", help="工作流变量（JSON 格式），如 '{\"topic\":\"AI\",\"year_from\":\"2020\"}'")
    p_workflows.add_argument("--dry-run", action="store_true", help="仅显示将要执行的命令，不实际执行")
    p_workflows.set_defaults(func=cmd_workflows)

    # check
    p_check = sub.add_parser("check", help="环境自检（Python / 依赖 / 浏览器 / 知网连通性）")
    p_check.add_argument("--fix", action="store_true",
                         help="输出手动修复建议；不安装依赖、不修改沙箱配置")
    p_check.set_defaults(func=cmd_check)
