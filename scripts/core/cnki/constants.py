"""cnki.constants - 共享常量与工具函数"""
from __future__ import annotations

import os
import sys

try:
    import selenium  # noqa: F401
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False

CNKI_SEARCH_URL = "https://kns.cnki.net/kns8s/search"
CNKI_ADV_SEARCH_URL = "https://kns.cnki.net/kns8s/AdvSearch"
# 专业检索是独立页面（高级检索页的“专业检索”标签指向该 URL，且 target=_blank），
# 直接导航比点击标签更可靠。实测路径，2026-10。
CNKI_EXPERT_SEARCH_URL = "https://kns.cnki.net/kns8s/AdvSearch?type=expert"


def _get_request_interval() -> int:
    try:
        from core.config import get as cfg_get
        return cfg_get("request_interval", 3)
    except ImportError:
        return int(os.environ.get("HUMLIT_REQUEST_INTERVAL", "3"))


REQUEST_INTERVAL = _get_request_interval()

CNKI_SIDEBAR_CORES = ["北大核心", "CSSCI", "AMI", "WJCI", "CSCD", "EI"]


def _log(msg: str):
    import sys as _sys
    try:
        print(msg, file=_sys.stderr, flush=True)
    except UnicodeEncodeError:
        safe = msg.encode("ascii", errors="backslashreplace").decode("ascii")
        print(safe, file=_sys.stderr, flush=True)
