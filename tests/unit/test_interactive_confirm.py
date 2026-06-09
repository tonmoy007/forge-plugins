"""T-127 / REQ-INTERACTIVE-CONFIRM-001: staged confirmation in spec & plan.

AC-CONFIRM-001a: BOTH skills/forge-spec/SKILL.md AND skills/forge-plan/SKILL.md
present an outline/TOC AND an explicit confirmation pause that PRECEDES the
full-artifact generation (the step that writes the technical-spec / task-DAG).
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS = ROOT / "skills"
AGENTS = ROOT / "agents"

# (skill SKILL.md, the marker text of the full-artifact write step)
SKILL_CASES = [
    (SKILLS / "forge-spec" / "SKILL.md", "pipeline/04-spec/technical-spec.md"),
    (SKILLS / "forge-plan" / "SKILL.md", "pipeline/05-plan/task-dag.md"),
]

AGENT_FILES = [AGENTS / "spec-writer.md", AGENTS / "planner.md"]


@pytest.mark.parametrize("skill_path,_write_marker", SKILL_CASES)
def test_skill_has_outline_and_confirm_pause(skill_path: Path, _write_marker: str) -> None:
    text = skill_path.read_text()
    assert "REQ-INTERACTIVE-CONFIRM-001" in text, f"{skill_path.name} missing REQ tag"
    lower = text.lower()
    assert "outline" in lower, f"{skill_path.name} missing an outline/TOC step"
    # An explicit pause-for-confirmation directive.
    assert "confirm" in lower and "pause" in lower, (
        f"{skill_path.name} missing an explicit confirmation pause"
    )


@pytest.mark.parametrize("skill_path,write_marker", SKILL_CASES)
def test_confirm_precedes_full_write(skill_path: Path, write_marker: str) -> None:
    text = skill_path.read_text()
    outline_idx = text.lower().find("outline")
    confirm_idx = text.lower().find("pause")
    write_idx = text.find(write_marker)
    assert outline_idx != -1 and confirm_idx != -1 and write_idx != -1
    # Ordering: outline first, then the confirmation pause, then the full write.
    assert outline_idx < write_idx, f"{skill_path.name}: outline must precede full write"
    assert confirm_idx < write_idx, (
        f"{skill_path.name}: confirmation pause must precede full-artifact write"
    )


@pytest.mark.parametrize("agent_path", AGENT_FILES)
def test_agent_reflects_outline_then_confirm(agent_path: Path) -> None:
    lower = agent_path.read_text().lower()
    assert "outline" in lower, f"{agent_path.name} missing outline-then-confirm behavior"
    assert "confirm" in lower and "pause" in lower, (
        f"{agent_path.name} missing confirmation pause"
    )
