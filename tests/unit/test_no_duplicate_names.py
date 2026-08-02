"""Regression test: every `name:` frontmatter field must be unique.

Guards against the bug class where a Pro-tier skill/agent file was copy-pasted
from its Classic counterpart and kept the Classic `name:` frontmatter value.
Claude Code discovers skills/agents by directory-scanning `skills/*/SKILL.md`
and `agents/*.md` and indexing them by their frontmatter `name:` field — a
duplicate `name:` makes the second file with that name unreachable (it is
shadowed by whichever file the scanner indexes first). Six such collisions
(`forge-srs`, `forge-product`, `forge-arch`, `requirements-analyst`,
`product-designer`, `system-architect` each declared by both a Classic and a
Pro file) shipped across three commits before anything checked for it.

Uniqueness is checked separately within skills and within agents — the two
namespaces are scanned independently by Claude Code, so a skill and an agent
sharing a `name:` is not a collision.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = ROOT / "skills"
AGENTS_DIR = ROOT / "agents"

# Matches the `name:` key inside a YAML frontmatter block. Deliberately a
# lightweight regex (not a full YAML parse) to keep this test stdlib-only,
# consistent with the frontmatter scan in scripts/mine-skills.py.
_NAME_RE = re.compile(r"^name:\s*(\S+)\s*$", re.MULTILINE)


def _frontmatter_name(path: Path) -> str | None:
    """Return the `name:` value from a file's leading `---` frontmatter block."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    match = _NAME_RE.search(parts[1])
    return match.group(1).strip() if match else None


def _collect_names(paths: list[Path]) -> dict[str, list[Path]]:
    """Map each declared `name:` to the list of files that declare it."""
    names: dict[str, list[Path]] = defaultdict(list)
    for path in paths:
        name = _frontmatter_name(path)
        if name is not None:
            names[name].append(path)
    return names


def _assert_no_duplicates(names: dict[str, list[Path]], kind: str) -> None:
    duplicates = {name: paths for name, paths in names.items() if len(paths) > 1}
    if duplicates:
        lines = [
            f"  name: {name!r} declared by "
            + ", ".join(str(p.relative_to(ROOT)) for p in paths)
            for name, paths in sorted(duplicates.items())
        ]
        raise AssertionError(
            f"Duplicate {kind} `name:` frontmatter collisions found "
            f"(Claude Code indexes by name — the later file becomes "
            f"unreachable):\n" + "\n".join(lines)
        )


def test_no_duplicate_skill_names() -> None:
    skill_files = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    assert skill_files, f"expected to find SKILL.md files under {SKILLS_DIR}"
    _assert_no_duplicates(_collect_names(skill_files), "skill")


def test_no_duplicate_agent_names() -> None:
    agent_files = sorted(AGENTS_DIR.glob("*.md"))
    assert agent_files, f"expected to find agent files under {AGENTS_DIR}"
    _assert_no_duplicates(_collect_names(agent_files), "agent")


def test_every_skill_declares_a_name() -> None:
    missing = [
        str(p.relative_to(ROOT))
        for p in sorted(SKILLS_DIR.glob("*/SKILL.md"))
        if _frontmatter_name(p) is None
    ]
    assert not missing, f"skills missing `name:` frontmatter: {missing}"


def test_every_agent_declares_a_name() -> None:
    missing = [
        str(p.relative_to(ROOT))
        for p in sorted(AGENTS_DIR.glob("*.md"))
        if _frontmatter_name(p) is None
    ]
    assert not missing, f"agents missing `name:` frontmatter: {missing}"
