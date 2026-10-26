"""知网检索执行路径的离线契约测试。

真机结论（2026-10）：高级检索页的字段/逻辑/匹配是自定义下拉（无原生 select），
程序化点击无法可靠展开；专业检索是独立页面（/kns8s/AdvSearch?type=expert），
输入框可写入且提交后保留值。因此结构化条件统一编译为专业检索表达式执行。
本文件测试该路径的契约，不触网、不启动浏览器。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core.cnki import search as search_module  # noqa: E402
from core.cnki.query import CnkiCondition  # noqa: E402
from core.cnki.search import (  # noqa: E402
    CnkiRetrievalError,
    _professional_search,
    _read_total_hits,
    _verify_professional_expression,
)


class FakeBox:
    """模拟专业检索输入框；ignore_writes=True 模拟写入不生效。"""

    def __init__(self, value: str = "", ignore_writes: bool = False):
        self._value = value
        self.ignore_writes = ignore_writes

    def get_attribute(self, name):
        return self._value if name == "value" else None

    def write(self, value: str):
        if not self.ignore_writes:
            self._value = value


class FakeDriver:
    def __init__(self, box=None, submit_ok=True):
        self.box = box
        self.submit_ok = submit_ok
        self.visited = []
        self.submitted = False

    def get(self, url):
        self.visited.append(url)

    def quit(self):
        pass

    def execute_script(self, script, *args):
        if "textarea.majorSearch" in script:
            return self.box
        if "input.btn-search" in script and "indexOf('检索')" in script:
            self.submitted = True
            return self.submit_ok
        if "arguments[0].value = arguments[1]" in script:
            if self.box is not None:
                self.box.write(args[1])
            return None
        return None


# ── 专业检索提交 ─────────────────────────────────────


def test_professional_search_writes_and_submits():
    box = FakeBox()
    driver = FakeDriver(box=box)
    outcome = _professional_search(driver, "SU %= 知识管理")
    assert outcome["ok"] is True
    assert outcome["written"] == "SU %= 知识管理"
    assert driver.submitted is True
    assert box.get_attribute("value") == "SU %= 知识管理"


def test_professional_search_reports_missing_box():
    outcome = _professional_search(FakeDriver(box=None), "SU %= 知识管理")
    assert outcome["ok"] is False
    assert outcome["error"]["code"] == "form_not_found"


def test_professional_search_detects_writeback_mismatch():
    box = FakeBox(value="", ignore_writes=True)
    outcome = _professional_search(FakeDriver(box=box), "SU %= 知识管理")
    assert outcome["ok"] is False
    assert outcome["error"]["code"] == "condition_not_applied"
    assert "回读不一致" in outcome["error"]["message"]


def test_professional_search_reports_missing_button():
    outcome = _professional_search(
        FakeDriver(box=FakeBox(), submit_ok=False), "SU %= 知识管理"
    )
    assert outcome["ok"] is False
    assert outcome["error"]["code"] == "form_not_found"
    assert "检索按钮" in outcome["error"]["message"]


# ── 结果页回读校验 ───────────────────────────────────


def test_verify_passes_on_identical_expression():
    box = FakeBox(value="SU %= 知识管理")
    result = _verify_professional_expression(FakeDriver(box=box), "SU %= 知识管理")
    assert result["verified"] is True


def test_verify_ignores_whitespace_differences():
    box = FakeBox(value="SU   %=   知识管理")
    result = _verify_professional_expression(FakeDriver(box=box), "SU %= 知识管理")
    assert result["verified"] is True


def test_verify_detects_different_expression():
    box = FakeBox(value="SU %= 信息管理")
    result = _verify_professional_expression(FakeDriver(box=box), "SU %= 知识管理")
    assert result["verified"] is False
    assert result["actual"] == "SU %= 信息管理"


def test_verify_returns_none_when_box_missing():
    result = _verify_professional_expression(FakeDriver(box=None), "SU %= 知识管理")
    assert result["verified"] is None


# ── 命中数读取 ───────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("共找到\n            50,940\n            条结果", 50940),
        ("共 1,234 条结果", 1234),
        ("", None),
        ("没有数字", None),
    ],
)
def test_read_total_hits(text, expected):
    driver = FakeDriver(box=FakeBox())
    driver.execute_script = lambda script, *args: text
    assert _read_total_hits(driver) == expected


# ── search_cnki 端到端契约（假 driver） ───────────────


class _ImmediateWait:
    def __init__(self, driver, timeout=None):
        pass

    def until(self, _condition):
        return True


def _patch_env(monkeypatch, professional_outcome, driver=None):
    driver = driver or FakeDriver(box=FakeBox())
    monkeypatch.setattr(search_module, "check_cnki_access", lambda: (True, "ok"))
    monkeypatch.setattr(search_module, "_detect_browser", lambda: "edge")
    monkeypatch.setattr(search_module, "_create_driver", lambda browser=None: driver)
    monkeypatch.setattr(search_module, "_load_cookies", lambda d: None)
    monkeypatch.setattr(search_module, "_save_cookies", lambda d: None)
    monkeypatch.setattr(search_module, "_handle_captcha", lambda d: d)
    monkeypatch.setattr(search_module, "_driver_is_reused", lambda d: True)
    monkeypatch.setattr(search_module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(search_module, "_professional_search",
                        lambda d, expr: professional_outcome)
    monkeypatch.setattr(search_module, "WebDriverWait", _ImmediateWait)
    monkeypatch.setattr(search_module, "_classify_result_page", lambda d: "results")
    monkeypatch.setattr(search_module, "_parse_search_results",
                        lambda d, cite_enrich=0: [])
    monkeypatch.setattr(search_module, "_go_next_page", lambda d: None)
    monkeypatch.setattr(search_module, "_filter_by_year", lambda rows, a, b: rows)
    monkeypatch.setattr(search_module, "_read_total_hits", lambda d: 42)
    monkeypatch.setattr(search_module, "_verify_professional_expression",
                        lambda d, expr: {"verified": True, "actual": expr})
    return driver


def test_conditions_are_compiled_to_expression(monkeypatch):
    _patch_env(monkeypatch, {"ok": True, "written": "x", "error": None})
    meta = {}
    search_module.search_cnki(
        "",
        conditions=[
            CnkiCondition(field="篇名", value="生成式AI"),
            CnkiCondition(field="关键词", value="广告", match="模糊"),
            CnkiCondition(field="摘要", value="品牌信任", logic="或者"),
            CnkiCondition(field="文献来源", value="新闻与传播研究", logic="并且"),
        ],
        meta=meta,
    )
    retrieval = meta["retrieval"]
    assert retrieval["mode"] == "advanced"
    compiled = retrieval["compiled_expression"]
    assert compiled == (
        "TI % 生成式AI AND (KY % 广告 OR AB % 品牌信任) AND JN % 新闻与传播研究"
    )
    assert retrieval["applied"]["expression"] == compiled
    assert retrieval["verified"] is True
    assert retrieval["total_hits"] == 42


def test_failed_compiled_submission_is_not_silently_accepted(monkeypatch):
    _patch_env(monkeypatch, {
        "ok": False,
        "error": {"code": "condition_not_applied", "message": "表达式写入后回读不一致"},
    })
    meta = {}
    results = search_module.search_cnki(
        "", conditions=[CnkiCondition(field="篇名", value="生成式AI")], meta=meta,
    )
    assert results[0]["status"] == "error"
    assert results[0]["code"] == "CNKI_CONDITION_NOT_APPLIED"
    assert meta["retrieval"]["mode"] == "advanced"


def test_invalid_condition_fails_before_browser(monkeypatch):
    called = {"created": False}

    def _boom(browser=None):
        called["created"] = True
        return FakeDriver(box=FakeBox())

    monkeypatch.setattr(search_module, "_create_driver", _boom)
    results = search_module.search_cnki(
        "", conditions=[CnkiCondition(field="主题", value="人工智能", match="精确")]
    )
    assert results[0]["code"] == "CNKI_INVALID_EXPRESSION"
    assert called["created"] is False


def test_no_keywords_still_reported():
    results = search_module.search_cnki("")
    assert results[0]["code"] == "NO_KEYWORDS"


def test_retrieval_error_is_structured():
    exc = CnkiRetrievalError("CNKI_RETRIEVAL_MISMATCH", "不一致")
    assert exc.code == "CNKI_RETRIEVAL_MISMATCH"
    assert isinstance(exc, search_module.CnkiSecurityError)


def test_professional_mode_uses_expert_url(monkeypatch):
    driver = _patch_env(
        monkeypatch,
        {"ok": False, "error": {"code": "form_not_found",
                                "message": "未找到专业检索输入框"}},
    )
    search_module.search_cnki("", professional="SU %= 知识管理")
    assert any("type=expert" in url for url in driver.visited)
