import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from register_skill import register_skill  # noqa: E402


def test_registers_one_checkout_for_multiple_clients(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: humlit-skills\n---\n", encoding="utf-8")
    home = tmp_path / "home"

    result = register_skill(source, home, ["codex", "claude", "trae"])

    assert result["status"] == "success"
    assert result["registered"] == 3
    for relative in (".codex/skills", ".claude/skills", ".trae-cn/skills"):
        target = home / relative / "humlit-skills"
        assert target.is_symlink()
        assert target.resolve() == source.resolve()


def test_registration_is_idempotent(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: humlit-skills\n---\n", encoding="utf-8")
    home = tmp_path / "home"

    register_skill(source, home, ["trae"])
    result = register_skill(source, home, ["trae"])

    assert result["status"] == "success"
    assert result["results"][0]["status"] == "already_registered"


def test_does_not_overwrite_existing_target(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: humlit-skills\n---\n", encoding="utf-8")
    target = tmp_path / "home" / ".trae-cn" / "skills" / "humlit-skills"
    target.mkdir(parents=True)
    marker = target / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    result = register_skill(source, tmp_path / "home", ["trae"])

    assert result["status"] == "error"
    assert result["results"][0]["code"] == "TARGET_EXISTS"
    assert marker.read_text(encoding="utf-8") == "keep"
