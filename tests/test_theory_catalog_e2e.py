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
    return r


def test_theory_catalog_lists_all():
    r = _run("theory-catalog")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["status"] == "success" and out["count"] >= 20
    assert "disciplines" in out


def test_theory_catalog_filter_discipline():
    out = json.loads(_run("theory-catalog", "--discipline", "传播学").stdout)
    assert out["count"] >= 1
    assert all(t["discipline"] == "传播学" for t in out["theories"])


def test_theory_match_ranks_candidates():
    out = json.loads(_run("theory-match", "--keywords", "社会资本,信任,弱关系").stdout)
    assert out["status"] == "success" and out["count"] >= 1
    scores = [m["score"] for m in out["matches"]]
    assert scores == sorted(scores, reverse=True)
    names = [m["name"] for m in out["matches"]]
    assert "社会资本理论" in names


def test_theory_match_no_keywords_errors():
    r = _run("theory-match", "--keywords", "  ")
    out = json.loads(r.stdout)
    assert out["status"] == "error" and out["code"] == "NO_KEYWORDS"


def test_theory_match_custom_library(tmp_path):
    lib = tmp_path / "lib.json"
    lib.write_text(json.dumps({"theories": [
        {"id": "my", "name": "数字劳动理论", "proposer": "某",
         "discipline": "社会学", "concepts": ["数字劳动"], "keywords": ["数字劳动", "平台"],
         "summary": "平台经济下的劳动形态。", "key_refs": ["X"]}
    ]}, ensure_ascii=False), encoding="utf-8")
    out = json.loads(_run("theory-match", "--keywords", "数字劳动,平台",
                          "--library", str(lib)).stdout)
    names = [m["name"] for m in out["matches"]]
    assert "数字劳动理论" in names


def test_theory_match_chinese_comma():
    out = json.loads(_run("theory-match", "--keywords", "议程设置，框架").stdout)
    assert out["count"] >= 1
