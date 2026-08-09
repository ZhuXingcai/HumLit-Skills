import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
ENTRY = SCRIPTS / "literature.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _run(*args, stdin=None):
    r = subprocess.run([sys.executable, str(ENTRY), *args],
                       capture_output=True, text=True, encoding="utf-8", input=stdin,
                       env={**os.environ, "PYTHONIOENCODING": "cp1252"})
    assert r.returncode == 0, r.stderr
    return r


def test_polish_signals_stdin():
    text = "其实这个问题的话挺复杂的。我觉得研究表明,这个结论是成立的。"
    out = json.loads(_run("polish-signals", "--stdin", stdin=text).stdout)
    assert out["status"] == "success"
    types = out["summary"]["by_type"]
    assert types.get("colloquial", 0) >= 1
    assert types.get("subjective", 0) >= 1
    assert types.get("punct_mix", 0) >= 1


def test_polish_signals_file_and_maxsentence(tmp_path):
    f = tmp_path / "draft.md"
    f.write_text("本文" + "围绕这一核心议题展开深入讨论" * 6 + "。", encoding="utf-8")
    out = json.loads(_run("polish-signals", str(f), "--max-sentence", "40").stdout)
    assert any(i["type"] == "long_sentence" for i in out["issues"])
