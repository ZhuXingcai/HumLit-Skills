from __future__ import annotations

import argparse
import io
import json
import sqlite3
import sys
from contextlib import redirect_stdout
from pathlib import Path
from docx import Document

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cli import citation_cmd, cnki_cmd, docx_cmd, journal_cmd, research_cmd  # noqa: E402
from core import formatter, venues  # noqa: E402
from core.zotero import read_zotero_sqlite  # noqa: E402


def _create_mock_zotero_db(root: Path) -> Path:
    db = root / "zotero.sqlite"
    storage = root / "storage" / "ATTKEY01"
    storage.mkdir(parents=True)
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE collections (collectionID INTEGER PRIMARY KEY, collectionName TEXT);
        CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
        CREATE TABLE items (itemID INTEGER PRIMARY KEY, itemTypeID INTEGER, key TEXT, dateModified TEXT);
        CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY);
        CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
        CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
        CREATE TABLE creators (creatorID INTEGER PRIMARY KEY, firstName TEXT, lastName TEXT, fieldMode INTEGER);
        CREATE TABLE itemCreators (itemID INTEGER, creatorID INTEGER, orderIndex INTEGER);
        CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE itemTags (itemID INTEGER, tagID INTEGER);
        CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER);
        CREATE TABLE itemAttachments (itemID INTEGER, parentItemID INTEGER, contentType TEXT, path TEXT);

        INSERT INTO collections VALUES (1, '数字人文');
        INSERT INTO itemTypes VALUES (1, 'journalArticle'), (2, 'attachment');
        INSERT INTO items VALUES (10, 1, 'PAPER01', '2026-01-01'), (11, 2, 'ATTKEY01', '2026-01-01');
        INSERT INTO fields VALUES (1, 'title'), (2, 'date'), (3, 'publicationTitle'), (4, 'DOI');
        INSERT INTO itemDataValues VALUES
            (1, '数字人文视野下的古籍文献整理'),
            (2, '2025'),
            (3, '中国社会科学'),
            (4, '10.1000/dh.2025.01');
        INSERT INTO itemData VALUES (10, 1, 1), (10, 2, 2), (10, 3, 3), (10, 4, 4);
        INSERT INTO creators VALUES (1, '', '张三', 1);
        INSERT INTO itemCreators VALUES (10, 1, 0);
        INSERT INTO tags VALUES (1, '古籍');
        INSERT INTO itemTags VALUES (10, 1);
        INSERT INTO collectionItems VALUES (1, 10);
        INSERT INTO itemAttachments VALUES (11, 10, 'application/pdf', 'storage:dh.pdf');
        """
    )
    conn.commit()
    conn.close()
    (storage / "dh.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    return root


def test_zotero_readonly_snapshot_reads_items_and_pdf_attachment(tmp_path: Path):
    zdir = _create_mock_zotero_db(tmp_path / "Zotero")
    res = read_zotero_sqlite(zdir, collection="数字人文", limit=10)
    assert res["status"] == "success"
    assert res["count"] == 1
    item = res["results"][0]
    assert item["title"] == "数字人文视野下的古籍文献整理"
    assert item["journal"] == "中国社会科学"
    assert item["local_pdf"].endswith("dh.pdf")


def test_read_paper_numbered_toc_and_section_slicing(tmp_path: Path):
    md = tmp_path / "thesis.md"
    md.write_text(
        "第一章 绪论\n\n这是绪论段落，讨论研究背景与核心问题。\n\n"
        "第二章 研究设计\n\n这是研究设计段落，说明样本来源与方法论。\n\n"
        "第三章 实证分析\n\n这是实证分析段落，报告主要检验结果。\n",
        encoding="utf-8",
    )
    toc_res = docx_cmd.read_paper_payload(str(md), toc=True)
    assert toc_res["status"] == "success"
    assert len(toc_res["toc"]) >= 3

    sec_res = docx_cmd.read_paper_payload(str(md), section="研究设计")
    assert sec_res["status"] == "success"
    assert "研究设计段落" in sec_res["text"]
    assert "实证分析段落" not in sec_res["text"]

    num_res = docx_cmd.read_paper_payload(str(md), numbered=True)
    assert "[P1]" in num_res["text"]


def test_offline_venues_annotation_and_journal_check_signals(tmp_path: Path):
    ssci = venues.annotate_venue_quality({"journal": "Nature"})
    assert "SCI" in ssci.get("venue_tags", [])

    warn = venues.annotate_venue_quality({"journal": "Computers and Electrical Engineering"})
    assert warn.get("is_warning") is True

    draft = tmp_path / "paper.md"
    draft.write_text("# 标题\n\n摘要：这是一段摘要。\n\n关键词：数字人文；文献学\n\n正文内容若干。\n", encoding="utf-8")
    buf = io.StringIO()
    with redirect_stdout(buf):
        journal_cmd.cmd_journal_check(
            argparse.Namespace(
                filepath=str(draft),
                profile=None,
                journal_name="Nature",
                raw=False,
            )
        )
    out = json.loads(buf.getvalue())
    assert out["status"] == "success"
    assert "SCI" in out["venue_index_signals"]["venue_tags"]


def test_cite_author_year_chinese_econ_and_markdown_rewrite(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    papers = [
        {"title": "数字经济与高质量发展", "authors": "赵涛; 张智", "journal": "管理世界", "year": 2020, "issue": "10", "pages": "65-76"},
        {"title": "Digital Humanities Methods", "authors": "John Smith", "journal": "Digital Scholarship", "year": 2023, "volume": "38", "issue": "2", "pages": "100-115"},
    ]
    from cli._common import _save_session
    _save_session(papers, project="cite_test")

    ay = formatter.generate_reference_list(papers, "gbt7714-author-year")
    assert "赵涛" in ay and "2020" in ay
    econ = formatter.generate_reference_list(papers, "chinese-econ")
    assert "《管理世界》" in econ

    draft = tmp_path / "draft.md"
    draft.write_text("前人研究指出[2]，国内研究也发现[1]。\n", encoding="utf-8")
    final_md = tmp_path / "final.md"
    refs_bib = tmp_path / "refs.bib"

    buf = io.StringIO()
    with redirect_stdout(buf):
        citation_cmd.cmd_cite(
            argparse.Namespace(
                style="gbt7714",
                indices=None,
                from_file=str(draft),
                rewrite_output=str(final_md),
                bibtex_output=str(refs_bib),
                keep_numbers=False,
                in_text=True,
                no_enrich=True,
                raw=False,
                project="cite_test",
            )
        )
    out = json.loads(buf.getvalue())
    assert out["status"] == "success"
    assert out["count"] == 2
    assert final_md.is_file() and "[1]" in final_md.read_text(encoding="utf-8")
    assert refs_bib.is_file() and "@article{" in refs_bib.read_text(encoding="utf-8")
    assert "in_text" in out


def test_data_table_and_rebuttal_commands(tmp_path: Path):
    csv_path = tmp_path / "panel.csv"
    csv_path.write_text("x,y\n1,2.1\n2,3.9\n3,6.2\n4,7.8\n5,10.1\n", encoding="utf-8")
    buf_dt = io.StringIO()
    with redirect_stdout(buf_dt):
        research_cmd.cmd_data_table(
            argparse.Namespace(
                filepath=str(csv_path),
                type="corr",
                columns=None,
                digits=3,
                lang="zh",
                caption="表1 相关系数矩阵",
                format="markdown",
                output=None,
                raw=False,
            )
        )
    dt_out = json.loads(buf_dt.getvalue())
    assert dt_out["status"] == "success"
    assert "表1 相关系数矩阵" in dt_out["markdown"]

    manuscript = tmp_path / "ms.docx"
    doc = Document()
    doc.add_paragraph("引言部分讨论研究背景。")
    doc.add_paragraph("研究方法部分说明样本选择与变量定义。")
    doc.save(str(manuscript))

    comments = tmp_path / "reviewers.txt"
    comments.write_text("Reviewer #1:\n1. Please clarify the sample selection in the methodology section.\n", encoding="utf-8")
    patch_json = tmp_path / "patch.json"
    buf_reb = io.StringIO()
    with redirect_stdout(buf_reb):
        research_cmd.cmd_rebuttal(
            argparse.Namespace(
                filepath=str(comments),
                manuscript=str(manuscript),
                title="Test Paper",
                lang="en",
                format="markdown",
                output=None,
                init_patch=str(patch_json),
                raw=False,
            )
        )
    reb_out = json.loads(buf_reb.getvalue())
    assert reb_out["status"] == "success"
    assert patch_json.is_file()
