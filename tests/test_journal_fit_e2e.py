import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
ENTRY = SCRIPTS / "literature.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _run(*args):
    r = subprocess.run([sys.executable, str(ENTRY), *args],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r


def test_journal_profile_template():
    out = json.loads(_run("journal-profile", "--template").stdout)
    assert out["schema_version"]
    assert "_README" in out and "length" in out


def test_journal_check_default_profile_flags_short(tmp_path):
    f = tmp_path / "draft.md"
    f.write_text("摘要：太短。\n\n关键词：仅一个\n\n# 引言\n正文很短。", encoding="utf-8")
    out = json.loads(_run("journal-check", str(f)).stdout)
    assert out["status"] == "success"
    assert out["metrics"]["length"]["ok"] is False
    assert out["anonymity"]["required"] is True


def test_journal_check_detects_fund_leak(tmp_path):
    f = tmp_path / "draft.md"
    f.write_text(
        "摘要：这是一段足够长的中文摘要用于测试投稿适配引擎的匿名泄露检测能力。\n\n"
        "关键词：投稿；适配；匿名\n\n"
        "# 引言\n本文系国家社会科学基金重大项目（17ZDA158）阶段性成果。" + "内容。" * 50,
        encoding="utf-8")
    out = json.loads(_run("journal-check", str(f)).stdout)
    leaks = out["anonymity"]["leaks"]
    assert any(l["type"] == "fund_leak" and l["severity"] == "error" for l in leaks)


def test_journal_check_custom_profile(tmp_path):
    prof = tmp_path / "p.json"
    prof.write_text(json.dumps({
        "schema_version": "1.0", "name": "测试刊",
        "length": {"min_chars": 1, "max_chars": 999999},
        "abstract": {"min_chars": 1, "max_chars": 999, "require_en": False},
        "keywords": {"min": 1, "max": 10},
        "references": {"min": 0}, "anonymous": False,
    }, ensure_ascii=False), encoding="utf-8")
    f = tmp_path / "draft.md"
    f.write_text("摘要：内容。\n\n关键词：甲；乙\n\n# 引言\n正文内容足够。", encoding="utf-8")
    out = json.loads(_run("journal-check", str(f), "--profile", str(prof)).stdout)
    assert out["profile"] == "测试刊"
    assert out["metrics"]["length"]["ok"] is True
    assert out["anonymity"]["required"] is False
