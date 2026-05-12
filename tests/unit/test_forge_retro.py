"""Structural tests for skills/forge-retro/SKILL.md.

The retro skill is markdown for an agent to follow — there is no Python to
unit-test. These tests assert the contract:
  - Valid YAML frontmatter with name, description, allowed-tools
  - Each of the four T-029 done-when categories is explicitly addressed
  - Required workflow scaffolding is present (Pre-flight, Steps, Verification)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILL_PATH = Path(__file__).parent.parent.parent / "skills" / "forge-retro" / "SKILL.md"


@pytest.fixture(scope="module")
def skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def frontmatter(skill_text: str) -> dict[str, str]:
    """Parse the YAML-ish frontmatter into a simple key→raw-value dict."""
    assert skill_text.startswith("---\n"), "missing opening frontmatter delimiter"
    end = skill_text.find("\n---\n", 4)
    assert end > 0, "missing closing frontmatter delimiter"
    block = skill_text[4:end]
    out: dict[str, str] = {}
    current_key: str | None = None
    for line in block.splitlines():
        m = re.match(r"^([a-z_-]+):\s*(.*)$", line)
        if m:
            current_key = m.group(1)
            out[current_key] = m.group(2).strip()
        elif current_key and line.startswith("  "):
            # YAML continuation of a multi-line value
            out[current_key] = (out[current_key] + " " + line.strip()).strip()
    return out


# ---------------------------------------------------------------------------
# Frontmatter contract
# ---------------------------------------------------------------------------


def test_skill_file_exists():
    assert SKILL_PATH.exists()


def test_frontmatter_has_name(frontmatter):
    assert frontmatter.get("name") == "forge-retro"


def test_frontmatter_has_description(frontmatter):
    desc = frontmatter.get("description", "")
    assert len(desc) > 30, "description should explain when to invoke the skill"


def test_frontmatter_has_allowed_tools(frontmatter):
    tools = frontmatter.get("allowed-tools", "")
    # The skill reads files, writes the retro, and runs scripts via Bash
    assert "Read" in tools
    assert "Write" in tools
    assert "Bash" in tools


# ---------------------------------------------------------------------------
# Required scaffolding sections
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("section", [
    "## When to Use",
    "## Pre-flight",
    "## Steps",
    "## Verification",
])
def test_scaffolding_section_present(skill_text: str, section: str):
    assert section in skill_text


# ---------------------------------------------------------------------------
# Done-when criteria: retro covers each of the four categories
# ---------------------------------------------------------------------------


def test_done_when_what_went_well(skill_text: str):
    """T-029 done-when: retro covers what went well."""
    assert "What Went Well" in skill_text
    assert "Identify what went well" in skill_text


def test_done_when_what_didnt_go_well(skill_text: str):
    """T-029 done-when: retro covers what didn't."""
    assert "What Didn't Go Well" in skill_text
    assert "Identify what didn't go well" in skill_text


def test_done_when_lessons_captured(skill_text: str):
    """T-029 done-when: retro covers lessons captured."""
    assert "Lessons Captured" in skill_text
    assert "tasks/lessons.md" in skill_text


def test_done_when_skills_proposed(skill_text: str):
    """T-029 done-when: retro covers skills proposed."""
    assert "Skill Proposals" in skill_text
    # Must integrate with the T-028 approval flow
    assert "skill-approval.py" in skill_text


# ---------------------------------------------------------------------------
# Stage 12 trigger + output location
# ---------------------------------------------------------------------------


def test_skill_triggers_after_stage_12(skill_text: str):
    assert "Stage 12" in skill_text or "stage 12" in skill_text
    assert "current_stage < 12" in skill_text  # pre-flight warns if not at stage 12


def test_retro_output_path_documented(skill_text: str):
    assert "pipeline/12-release/retro.md" in skill_text


def test_calls_mine_skills_to_refresh_proposals(skill_text: str):
    assert "mine-skills.py" in skill_text


def test_directory_name_matches_skill_name():
    """plugin.json globs skills/* — the directory name is what the user types."""
    assert SKILL_PATH.parent.name == "forge-retro"
