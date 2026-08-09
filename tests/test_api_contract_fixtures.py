import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = Path(__file__).parent / "fixtures"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from core import search  # noqa: E402
from core.cnki import search as cnki_search  # noqa: E402
from selenium.common.exceptions import NoSuchElementException  # noqa: E402


class _DomElement:
    def __init__(self, node):
        self.node = node

    @property
    def text(self):
        return self.node.get_text(" ", strip=True)

    def get_attribute(self, name):
        value = self.node.get(name)
        if isinstance(value, list):
            return " ".join(value)
        return value

    def find_element(self, by, selector):
        node = self.node.select_one(selector)
        if node is None:
            raise NoSuchElementException(selector)
        return _DomElement(node)

    def find_elements(self, by, selector):
        return [_DomElement(node) for node in self.node.select(selector)]


def _json_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_openalex_contract_fixture(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(search, "_http_get", lambda *args, **kwargs: _json_fixture("openalex_response.json"))

    papers = search.search_openalex("digital humanities")

    assert papers[0]["doi"] == "10.1000/openalex"
    assert papers[0]["authors"] == "Zhang San"
    assert papers[0]["keywords"] == ["Digital humanities"]


def test_semantic_scholar_contract_fixture(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    captured = {}

    def fixture_response(*args, **kwargs):
        captured.update(kwargs)
        return _json_fixture("semantic_scholar_response.json")

    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "test-key")
    from core import config
    config.reset()
    monkeypatch.setattr(
        search,
        "_http_get",
        fixture_response,
    )

    papers = search.search_semantic_scholar("social capital")

    config.reset()
    assert papers[0]["doi"] == "10.1000/s2"
    assert papers[0]["journal"] == "Social Research"
    assert papers[0]["keywords"] == ["Sociology"]
    assert captured["headers"] == {"x-api-key": "test-key"}


def test_arxiv_contract_fixture(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    xml = (FIXTURES / "arxiv_response.xml").read_text(encoding="utf-8")
    monkeypatch.setattr(search, "_http_get", lambda *args, **kwargs: xml)

    papers = search.search_arxiv("archives")

    assert papers[0]["arxiv_id"] == "2401.00001v1"
    assert papers[0]["year"] == 2024
    assert papers[0]["oa_url"].endswith("2401.00001v1")


def test_nssd_contract_fixture(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        search,
        "_http_post_form",
        lambda *args, **kwargs: _json_fixture("nssd_response.json"),
    )

    papers = search.search_nssd("乡村治理")

    assert papers[0]["title"] == "数字人文视域下的地方志知识组织"
    assert papers[0]["year"] == 2024
    assert papers[0]["doi"] == "10.1000/nssd"
    assert papers[0]["oa_url"] == "https://ftprp.ncpssd.cn/example.pdf"
    assert papers[0]["pages"] == "10-20"


def test_dblp_contract_fixture(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(search, "_http_get", lambda *args, **kwargs: _json_fixture("dblp_response.json"))

    papers = search.search_dblp("historical archives")

    assert papers[0]["doi"] == "10.1000/dblp"
    assert papers[0]["doc_type"] == "Conference Papers"
    assert papers[0]["is_oa"] is True


def test_base_contract_fixture(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(search, "_http_get", lambda *args, **kwargs: _json_fixture("base_response.json"))

    papers = search.search_base("public history")

    assert papers[0]["title"] == "Open Archives and Public History"
    assert papers[0]["doi"] == "10.1000/base"
    assert papers[0]["keywords"] == ["archives", "public history"]


def test_cnki_result_row_dom_contract_fixture():
    from bs4 import BeautifulSoup

    html = (FIXTURES / "cnki_result_row.html").read_text(encoding="utf-8")
    row = _DomElement(BeautifulSoup(html, "html.parser").select_one("tr"))

    paper = cnki_search._parse_single_row(row)

    assert paper["title"] == "数字人文视域下的地方志研究"
    assert paper["authors"] == "周九; 吴十"
    assert paper["year"] == 2024
    assert paper["cited_by"] == 17
    assert paper["core_type"] == "CSSCI"
