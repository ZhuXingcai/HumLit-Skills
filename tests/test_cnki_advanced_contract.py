"""知网高级检索条件可靠性的离线契约测试。

用假 driver 模拟表单填写与结果页回读，不启动浏览器、不触网。
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core.cnki import search as search_module  # noqa: E402
from core.cnki.query import CnkiCondition  # noqa: E402
from core.cnki.search import (  # noqa: E402
    CnkiRetrievalError,
    _advanced_search,
    _professional_search,
    _read_total_hits,
    _verify_applied_conditions,
)


class FakeElement:
    def __init__(self, text="", value=""):
        self.text = text
        self._value = value
        self.clicked = 0

    def click(self):
        self.clicked += 1

    def get_attribute(self, name):
        return self._value if name == "value" else None

    def is_displayed(self):
        return True


class FakeWait:
    """替代 WebDriverWait：until() 直接返回预置元素。"""

    element = None

    def __init__(self, driver, timeout=None):
        self.driver = driver

    def until(self, _condition):
        return FakeWait.element


class FakeDriver:
    def __init__(self, script_returns=None):
        self.script_returns = list(script_returns or [])
        self.scripts = []
        self.visited = []
        self.current_url = "https://kns.cnki.net/kns8s/search"
        self.title = "CNKI"

    def get(self, url):
        self.visited.append(url)

    def quit(self):
        pass

    def execute_script(self, script, *args):
        self.scripts.append((script, args))
        if self.script_returns:
            return self.script_returns.pop(0)
        return None

    def find_elements(self, by, selector):
        return []


@pytest.fixture(autouse=True)
def _patch_wait(monkeypatch):
    monkeypatch.setattr(search_module, "WebDriverWait", FakeWait)
    monkeypatch.setattr(search_module.time, "sleep", lambda *_: None)
    FakeWait.element = FakeElement(text="共 1,234 条结果")
    yield


def _rows(*statuses):
    """构造 JS 返回的逐行结果。"""
    rows = []
    for index, status in enumerate(statuses):
        rows.append({
            "field": "篇名",
            "value": f"v{index}",
            "status": status,
            "field_ok": status == "filled",
            "logic_ok": True,
            "match_ok": True,
            "value_ok": status == "filled",
        })
    return json.dumps({"status": "done", "rows": rows})


# ── 表单填写与逐条件校验 ──────────────────────────────


def test_all_conditions_applied_returns_ok():
    driver = FakeDriver([_rows("filled", "filled")])
    conds = [
        CnkiCondition(field="篇名", value="人工智能"),
        CnkiCondition(field="关键词", value="教育", logic="并且"),
    ]
    outcome = _advanced_search(driver, conds)
    assert outcome["ok"] is True
    assert outcome["error"] is None
    assert [c["field"] for c in outcome["applied"]] == ["篇名", "关键词"]


def test_partial_fill_is_reported_not_silently_accepted():
    # 第二个条件检索词没写进去：旧实现会判成功，新实现必须失败
    driver = FakeDriver([_rows("filled", "no_input")])
    conds = [
        CnkiCondition(field="篇名", value="人工智能"),
        CnkiCondition(field="摘要", value="教育"),
    ]
    outcome = _advanced_search(driver, conds)
    assert outcome["ok"] is False
    assert outcome["error"]["code"] == "condition_not_applied"
    assert "摘要" in outcome["error"]["message"]


def test_field_not_set_is_reported():
    rows = json.loads(_rows("filled"))
    rows["rows"][0]["field_ok"] = False
    driver = FakeDriver([json.dumps(rows)])
    outcome = _advanced_search(
        driver, [CnkiCondition(field="篇名", value="人工智能")]
    )
    assert outcome["ok"] is False
    assert "字段下拉" in outcome["error"]["message"]


def test_requested_logic_must_be_applied():
    rows = json.loads(_rows("filled", "filled"))
    rows["rows"][1]["logic_ok"] = False
    driver = FakeDriver([json.dumps(rows)])
    conds = [
        CnkiCondition(field="篇名", value="人工智能"),
        CnkiCondition(field="摘要", value="教育", logic="或者"),
    ]
    outcome = _advanced_search(driver, conds)
    assert outcome["ok"] is False
    assert "逻辑关系" in outcome["error"]["message"]


def test_requested_match_must_be_applied():
    rows = json.loads(_rows("filled"))
    rows["rows"][0]["match_ok"] = False
    driver = FakeDriver([json.dumps(rows)])
    outcome = _advanced_search(
        driver, [CnkiCondition(field="篇名", value="人工智能", match="精确")]
    )
    assert outcome["ok"] is False
    assert "匹配方式" in outcome["error"]["message"]


def test_no_rows_reports_form_not_found():
    driver = FakeDriver([json.dumps({"status": "no_rows", "rows": [],
                                     "message": "未找到高级搜索条件行"})])
    outcome = _advanced_search(
        driver, [CnkiCondition(field="篇名", value="人工智能")]
    )
    assert outcome["ok"] is False
    assert outcome["error"]["code"] == "form_not_found"


def test_default_logic_is_not_asserted_when_control_absent():
    """首行逻辑为默认“并且”时不因缺少逻辑下拉而失败。"""
    rows = json.loads(_rows("filled"))
    rows["rows"][0]["logic_ok"] = False
    driver = FakeDriver([json.dumps(rows)])
    outcome = _advanced_search(
        driver, [CnkiCondition(field="篇名", value="人工智能")]
    )
    assert outcome["ok"] is True


# ── 结果页回读校验 ───────────────────────────────────


def test_verify_passes_when_all_values_present():
    FakeWait.element = FakeElement(text="检索条件：篇名=人工智能 AND 摘要=教育")
    result = _verify_applied_conditions(FakeDriver(), ["人工智能", "教育"])
    assert result["verified"] is True
    assert result["missing"] == []


def test_verify_detects_missing_value():
    FakeWait.element = FakeElement(text="检索条件：篇名=人工智能")
    result = _verify_applied_conditions(FakeDriver(), ["人工智能", "教育"])
    assert result["verified"] is False
    assert result["missing"] == ["教育"]


def test_verify_returns_none_when_page_cannot_be_read():
    class BrokenWait:
        def __init__(self, driver, timeout=None):
            pass

        def until(self, _condition):
            raise search_module.TimeoutException("no element")

    search_module.WebDriverWait = BrokenWait
    try:
        result = _verify_applied_conditions(FakeDriver(), ["人工智能"])
    finally:
        search_module.WebDriverWait = FakeWait
    assert result["verified"] is None


# ── 命中数读取 ───────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("共 1,234 条结果", 1234),
        ("共找到 56 条结果", 56),
        ("", None),
        ("没有数字", None),
    ],
)
def test_read_total_hits(text, expected):
    driver = FakeDriver([text])
    assert _read_total_hits(driver) == expected


# ── search_cnki 不得把条件失败伪装成成功 ───────────────


def _patch_search_env(monkeypatch, advanced_outcome):
    monkeypatch.setattr(search_module, "check_cnki_access", lambda: (True, "ok"))
    monkeypatch.setattr(search_module, "_detect_browser", lambda: "edge")
    monkeypatch.setattr(
        search_module, "_create_driver", lambda browser=None: FakeDriver()
    )
    monkeypatch.setattr(search_module, "_load_cookies", lambda driver: None)
    monkeypatch.setattr(search_module, "_save_cookies", lambda driver: None)
    monkeypatch.setattr(search_module, "_handle_captcha", lambda driver: driver)
    monkeypatch.setattr(search_module, "_driver_is_reused", lambda driver: True)
    monkeypatch.setattr(
        search_module, "_advanced_search", lambda driver, conds: advanced_outcome
    )


def test_search_cnki_raises_on_unapplied_condition(monkeypatch):
    _patch_search_env(monkeypatch, {
        "ok": False, "applied": [], "rows": [],
        "error": {"code": "condition_not_applied", "message": "摘要：检索词未成功写入"},
    })
    meta = {}
    results = search_module.search_cnki(
        "",
        conditions=[
            CnkiCondition(field="篇名", value="人工智能"),
            CnkiCondition(field="摘要", value="教育"),
        ],
        meta=meta,
    )
    assert results[0]["status"] == "error"
    assert results[0]["code"] == "CNKI_CONDITION_NOT_APPLIED"
    assert "摘要" in results[0]["message"]
    assert meta["retrieval"]["mode"] == "advanced"


def test_search_cnki_reports_invalid_condition_before_browser(monkeypatch):
    called = {"created": False}

    def _boom(browser=None):
        called["created"] = True
        return FakeDriver()

    monkeypatch.setattr(search_module, "_create_driver", _boom)
    results = search_module.search_cnki(
        "", conditions=[CnkiCondition(field="主题", value="人工智能", match="精确")]
    )
    assert results[0]["code"] == "CNKI_INVALID_EXPRESSION"
    assert called["created"] is False


def test_search_cnki_no_keywords_still_reported(monkeypatch):
    results = search_module.search_cnki("")
    assert results[0]["code"] == "NO_KEYWORDS"


def test_retrieval_error_is_structured():
    exc = CnkiRetrievalError("CNKI_RETRIEVAL_MISMATCH", "不一致")
    assert exc.code == "CNKI_RETRIEVAL_MISMATCH"
    assert isinstance(exc, search_module.CnkiSecurityError)


# ── 专业检索 ─────────────────────────────────────────


def test_professional_search_reports_missing_box():
    driver = FakeDriver()
    outcome = _professional_search(driver, "SU %= 知识管理")
    assert outcome["ok"] is False
    assert outcome["error"]["code"] == "form_not_found"


def test_professional_search_detects_writeback_mismatch(monkeypatch):
    box = FakeElement(text="", value="别的表达式")

    class TabWait:
        def __init__(self, driver, timeout=None):
            pass

        def until(self, _condition):
            return FakeElement()

    monkeypatch.setattr(search_module, "WebDriverWait", TabWait)

    class Driver(FakeDriver):
        def find_elements(self, by, selector):
            return [box] if selector == "textarea" else []

    outcome = _professional_search(Driver(), "SU %= 知识管理")
    assert outcome["ok"] is False
    assert outcome["error"]["code"] == "condition_not_applied"
