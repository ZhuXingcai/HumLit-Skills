import argparse
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cli import review_cmd  # noqa: E402
from cli._common import _write_docx_from_markdown  # noqa: E402
from cli.docx_cmd import cmd_read_paper  # noqa: E402


def test_cross_domain_review_uses_corpus_terms_instead_of_communication_labels():
    paper = {
        "title": "CRISPR gene editing in plant cells",
        "abstract": "We evaluate off-target effects in a gene-editing model.",
        "keywords": ["CRISPR", "gene editing", "plant cells"],
        "journal": "Plant Biotechnology",
    }

    label = review_cmd._cluster_label_for_paper(paper, "CRISPR gene editing")
    gaps = review_cmd._review_gaps([paper], "CRISPR gene editing")

    forbidden = {
        "国家形象建构与官方叙事",
        "国际传播能力与对外传播",
        "平台机制与社交媒体",
        "文化符号与中国故事",
        "受众认知与传播效果",
        "跨平台比较不足",
        "受众实证研究不足",
        "非西方或比较视角不足",
    }
    assert label not in forbidden
    assert label.lower() in {"crispr", "gene editing", "plant cells"}
    assert not forbidden.intersection({gap["title"] for gap in gaps})
    assert all(gap["claim_scope"] == "corpus_coverage_signal" for gap in gaps)


def test_cross_domain_topic_methods_do_not_inject_communication_methods():
    methods = review_cmd._topic_methods(
        "CRISPR gene editing",
        "full-text evidence is sparse",
    )

    assert "平台比较" not in methods
    assert "计算传播分析" not in methods
    assert "符号分析" not in methods


def test_read_paper_recovers_footnotes_and_reports_observed_parts(tmp_path):
    docx_path = tmp_path / "paper.docx"
    created = _write_docx_from_markdown(
        "正文中的论断[^1]\n\n[^1]: 可追溯的脚注证据。",
        docx_path,
    )
    assert created["status"] == "success"
    assert created["footnotes"] == 1

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        cmd_read_paper(
            argparse.Namespace(
                filepath=str(docx_path),
                output=None,
                raw=False,
            )
        )
    result = json.loads(stdout.getvalue())

    assert result["status"] == "success"
    assert "可追溯的脚注证据" in result["text"]
    assert "footnotes" in result["observability"]["observed_parts"]
    assert "embedded_objects" in result["observability"]["unobserved_parts"]
