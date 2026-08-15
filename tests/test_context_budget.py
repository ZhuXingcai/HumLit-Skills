import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from generate_skill_index import load_manifest  # noqa: E402
from verify_skill_architecture import (  # noqa: E402
    context_statistics,
    validate_context_budget,
)


def test_runtime_context_stays_within_budget():
    manifest = load_manifest(ROOT / "manifest.yaml")
    stats = context_statistics(ROOT, manifest)

    assert stats["skill_lines"] <= 80
    assert stats["always_load_lines"] <= 90
    assert stats["pre_task_lines"] <= 170
    assert stats["skill_chars"] <= 6000
    assert stats["always_load_chars"] <= 4500
    assert stats["pre_task_chars"] <= 10000


def test_context_budget_reports_each_exceeded_limit(tmp_path):
    skill = tmp_path / "SKILL.md"
    core = tmp_path / "core.md"
    skill.write_text("\n".join(["skill"] * 81) + "\n", encoding="utf-8")
    core.write_text("\n".join(["core"] * 91) + "\n", encoding="utf-8")

    errors = validate_context_budget(
        skill_path=skill,
        always_load_paths=(core,),
        skill_limit=80,
        always_load_limit=90,
        pre_task_limit=170,
    )

    assert len(errors) == 3
    assert any("SKILL.md" in error for error in errors)
    assert any("always-load" in error for error in errors)
    assert any("pre-task" in error for error in errors)


def test_reference_leaf_files_stay_bounded():
    oversized = []
    for path in sorted((ROOT / "references").rglob("*.md")):
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > 180:
            oversized.append((str(path.relative_to(ROOT)), lines))

    assert oversized == []
