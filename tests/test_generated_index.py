import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from generate_skill_index import (  # noqa: E402
    GeneratedIndexError,
    ManifestError,
    load_manifest,
    render_generated_routes,
    synchronize_skill,
)


def _write_manifest(path: Path) -> None:
    path.write_text(
        """
name: humlit-skills
version: 1.0.2
always_load:
  - static/core/python-discovery.md
routing: {
  "search": {
    "triggers": ["搜索文献"],
    "exclusions": ["通用网页搜索"],
    "fragment": "static/fragments/task/search.md",
    "commands": ["search"],
    "capabilities": ["public_api_search"],
    "references": ["references/search/source-selection.md"]
  }
}
on_demand:
  error-codes: references/error-codes.md
""".lstrip(),
        encoding="utf-8",
    )


def test_render_generated_routes_is_deterministic(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"
    _write_manifest(manifest_path)

    manifest = load_manifest(manifest_path)
    first = render_generated_routes(manifest)
    second = render_generated_routes(manifest)

    assert first == second
    assert "search" in first
    assert "`search`" in first
    assert "`static/fragments/task/search.md`" in first
    assert "搜索文献" in first


def test_synchronize_skill_updates_then_check_is_idempotent(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"
    skill_path = tmp_path / "SKILL.md"
    _write_manifest(manifest_path)
    skill_path.write_text(
        "# Skill\n\n"
        "<!-- BEGIN GENERATED ROUTES -->\n"
        "stale\n"
        "<!-- END GENERATED ROUTES -->\n",
        encoding="utf-8",
    )

    assert synchronize_skill(manifest_path, skill_path) is True
    assert synchronize_skill(manifest_path, skill_path) is False
    assert synchronize_skill(manifest_path, skill_path, check=True) is False


def test_synchronize_skill_check_rejects_drift(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"
    skill_path = tmp_path / "SKILL.md"
    _write_manifest(manifest_path)
    skill_path.write_text(
        "# Skill\n\n"
        "<!-- BEGIN GENERATED ROUTES -->\n"
        "stale\n"
        "<!-- END GENERATED ROUTES -->\n",
        encoding="utf-8",
    )

    with pytest.raises(GeneratedIndexError, match="out of date"):
        synchronize_skill(manifest_path, skill_path, check=True)


def test_load_manifest_rejects_incomplete_route(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"
    _write_manifest(manifest_path)
    text = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(
        text.replace('"commands": ["search"],', '"commands": [],'),
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="commands"):
        load_manifest(manifest_path)
