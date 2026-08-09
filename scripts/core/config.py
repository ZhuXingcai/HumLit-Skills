"""config.py - HumLit Skills 统一配置加载

优先级: 环境变量 > .humlit/config.json > 内置默认值
"""
from __future__ import annotations

import json
import os
from typing import Any

from core.paths import state_path

_DEFAULTS = {
    "request_interval": 3,
    "cache_ttl_days": 30,
    "mailto": "",
    "semantic_scholar_api_key": "",
    "save_dir": "./papers",
    "browser": "auto",
    "batch_window_size": 10,
}

_ENV_MAP = {
    "request_interval": "HUMLIT_REQUEST_INTERVAL",
    "cache_ttl_days": "HUMLIT_CACHE_TTL_DAYS",
    "mailto": "HUMLIT_MAILTO",
    "semantic_scholar_api_key": "SEMANTIC_SCHOLAR_API_KEY",
    "save_dir": "HUMLIT_SAVE_DIR",
    "browser": "HUMLIT_BROWSER",
    "batch_window_size": "HUMLIT_BATCH_WINDOW_SIZE",
}

_INT_KEYS = {"request_interval", "cache_ttl_days", "batch_window_size"}

_loaded: dict[str, Any] | None = None


def get_env(
    name: str,
    default: str | None = None,
) -> str | None:
    """Read one environment variable without aliases."""
    return os.environ.get(name, default)


def _config_path():
    return state_path("config.json")


def _load_file() -> dict[str, Any]:
    p = _config_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            import sys
            print(f"[humlit-skills] config.json 解析失败，已使用默认值: {e}",
                  file=sys.stderr)
    return {}


def load() -> dict[str, Any]:
    global _loaded
    if _loaded is not None:
        return _loaded

    file_cfg = _load_file()
    result = {}

    for key, default in _DEFAULTS.items():
        env_name = _ENV_MAP.get(key, "")
        env_val = get_env(env_name) if env_name else None

        if env_val is not None:
            if key in _INT_KEYS:
                try:
                    result[key] = int(env_val)
                except (TypeError, ValueError):
                    result[key] = default
            else:
                result[key] = env_val
        elif key in file_cfg:
            val = file_cfg[key]
            if key in _INT_KEYS:
                try:
                    val = int(val)
                except (TypeError, ValueError):
                    val = default
            result[key] = val
        else:
            result[key] = default

    _loaded = result
    return result


def get(key: str, fallback: Any = None) -> Any:
    cfg = load()
    return cfg.get(key, fallback)


def reset():
    """强制重新加载（测试用）"""
    global _loaded
    _loaded = None
