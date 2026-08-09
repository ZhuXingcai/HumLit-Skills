import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "scripts" / "literature.py"


def _run(*args, stdin=None):
    r = subprocess.run([sys.executable, str(ENTRY), *args], input=stdin, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r


def test_real_world_plain_markdown_pipeline(tmp_path):
    draft = tmp_path / "draft.md"
    draft.write_text(
        """摘要
本文研究地方志资源的数字化组织方法。

关键词：数字人文；方志；知识组织

一、引言
本文系国家社会科学基金项目（17ZDA158）成果。笔者所在的某大学开展了相关研究。其实这个问题很重要。

参考文献
[1] 张三. 数字人文导论[M]. 北京: 中华书局, 2020.
""",
        encoding="utf-8",
    )
    profile = tmp_path / "format.json"
    json.loads(_run("format-profile", "--template", "--output", str(profile)).stdout)

    fmt = json.loads(_run("format-check", str(draft), "--profile", str(profile)).stdout)
    assert fmt["status"] == "success"
    assert "page" in fmt["summary"]["unknown_dimensions"]
    assert len(fmt["issues"]) >= 1

    journal = json.loads(_run("journal-check", str(draft)).stdout)
    leak_types = {x["type"] for x in journal["anonymity"]["leaks"]}
    assert {"fund_leak", "self_institution"}.issubset(leak_types)

    polish = json.loads(_run("polish-signals", str(draft)).stdout)
    assert polish["summary"]["issues"] >= 1


def test_stdout_json_purity_for_representative_commands(tmp_path):
    src = tmp_path / "source.json"
    src.write_text(json.dumps({"source_category": "ancient", "title": "明儒学案"}, ensure_ascii=False), encoding="utf-8")
    cb = tmp_path / "cb.json"
    cb.write_text(json.dumps({"codes": [{"code": "信任", "keywords": ["信任"]}]}, ensure_ascii=False), encoding="utf-8")
    txt = tmp_path / "t.md"
    txt.write_text("我信任医生。", encoding="utf-8")

    commands = [
        ("cite-source", str(src)),
        ("qual-code", str(txt), "--codebook", str(cb)),
        ("theory-match", "--keywords", "信任,社会资本"),
    ]
    for cmd in commands:
        out = _run(*cmd).stdout
        parsed = json.loads(out)
        assert parsed["status"] == "success"
