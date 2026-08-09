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


def test_qual_codebook_template():
    out = json.loads(_run("qual-codebook-template").stdout)
    assert "_README" in out and isinstance(out["codes"], list)


def test_qual_code_interview(tmp_path):
    cb = tmp_path / "cb.json"
    cb.write_text(json.dumps({
        "name": "访谈编码簿v1",
        "codes": [
            {"code": "信任", "keywords": ["信任", "相信"]},
            {"code": "就医决策", "keywords": ["就医", "看病", "挂号"]},
        ],
    }, ensure_ascii=False), encoding="utf-8")
    interview = tmp_path / "i01.md"
    interview.write_text(
        "我比较信任社区的医生，所以有点小病就去看病。\n\n"
        "网上的东西我不太相信，还是去医院挂号靠谱。\n\n"
        "周末一般在家休息。",
        encoding="utf-8")
    out = json.loads(_run("qual-code", str(interview), "--codebook", str(cb)).stdout)
    assert out["status"] == "success"
    codes = {c["code"]: c for c in out["codes"]}
    assert codes["信任"]["hits"] == 2
    assert codes["就医决策"]["hits"] >= 2
    assert out["summary"]["uncoded_paragraphs"] == 1


def test_qual_code_cooccurrence_and_stdin(tmp_path):
    cb = tmp_path / "cb.json"
    cb.write_text(json.dumps({
        "codes": [
            {"code": "信任", "keywords": ["信任"]},
            {"code": "就医", "keywords": ["就医"]},
        ],
    }, ensure_ascii=False), encoding="utf-8")
    text = "我信任医生所以及时就医。\n\n今天天气很好。"
    out = json.loads(_run("qual-code", "--stdin", "--codebook", str(cb), stdin=text).stdout)
    assert out["cooccurrence"] and out["cooccurrence"][0]["count"] == 1


def test_qual_code_bad_pattern(tmp_path):
    cb = tmp_path / "cb.json"
    cb.write_text(json.dumps({"codes": [{"code": "x", "patterns": ["("]}]},
                             ensure_ascii=False), encoding="utf-8")
    f = tmp_path / "t.md"
    f.write_text("内容。", encoding="utf-8")
    r = subprocess.run([sys.executable, str(ENTRY), "qual-code", str(f), "--codebook", str(cb)],
                       capture_output=True, text=True, encoding="utf-8")
    out = json.loads(r.stdout)
    assert out["status"] == "error" and out["code"] == "BAD_PATTERN"
