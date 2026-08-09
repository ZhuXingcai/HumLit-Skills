import json
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
                       capture_output=True, text=True, encoding="utf-8", input=stdin)
    assert r.returncode == 0, r.stderr
    return r


def test_cite_source_mixed_entries(tmp_path):
    entries = [
        {"source_category": "ancient", "author": "［清］黄宗羲", "title": "明儒学案",
         "juan": "卷十二", "editor": "沈芝盈点校", "place": "北京",
         "publisher": "中华书局", "year": "1985", "page": "256"},
        {"source_category": "archive", "doc_title": "为奏报某事",
         "archive": "中国第一历史档案馆", "fonds": "军机处录副奏折", "file_no": "03-1234-056"},
        {"source_category": "periodical", "article_title": "时评", "periodical": "申报",
         "pub_date": "1895-04-17", "column": "第2版"},
    ]
    f = tmp_path / "entries.json"
    f.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")

    out = json.loads(_run("cite-source", str(f)).stdout)
    assert out["status"] == "success" and out["count"] == 3
    e0 = out["entries"][0]
    assert "《明儒学案》" in e0["footnote"] and "[M]" in e0["gbt7714"]
    e1 = out["entries"][1]
    assert "中国第一历史档案馆" in e1["footnote"] and "[A]" in e1["gbt7714"]
    e2 = out["entries"][2]
    assert "《申报》" in e2["footnote"]


def test_cite_source_stdin_and_start_index():
    entry = {"source_category": "ancient", "title": "明儒学案", "author": "黄宗羲",
             "publisher": "中华书局", "year": "1985"}
    r = _run("cite-source", "--stdin", "--start-index", "5", stdin=json.dumps(entry))
    out = json.loads(r.stdout)
    assert out["entries"][0]["index"] == 5
    assert out["entries"][0]["footnote"].startswith("⑤")


def test_cite_source_template_all_types():
    for t in ["ancient", "archive", "gazetteer", "epigraph", "periodical", "genealogy", "oral"]:
        out = json.loads(_run("cite-source-template", "--type", t).stdout)
        assert out["source_category"] == t
