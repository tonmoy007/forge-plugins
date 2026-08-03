"""T-239 / AC-BUILDPIPE-001a+b: the Pro-tier pipeline is wired correctly, and the
original forge-build skill + builder agent are left completely untouched.

AC-BUILDPIPE-001a: forge-build-pro/SKILL.md -> agents/builder-pro.md -> the three
                   sub-agents, referenced in order (context-loader, code-generator,
                   quality-gate-runner).
AC-BUILDPIPE-001b: skills/forge-build/SKILL.md and agents/builder.md are unchanged
                   from the pre-T-235 baseline (commit 6a22fa1, the last commit before
                   this feature's planning commit bd39791) -- verified by diffing
                   against that commit, not just by absence of new-file mentions.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS = ROOT / "agents"
SKILLS = ROOT / "skills"

# The last commit before this feature's planning commit (bd39791) touched anything --
# an ancestor of HEAD on this branch, so it stays reachable regardless of later commits.
PRE_FEATURE_SHA = "6a22fa1"

SUB_AGENTS_IN_ORDER = ["context-loader", "code-generator", "quality-gate-runner"]


def _git_show(sha: str, relpath: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{sha}:{relpath}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_builder_pro_agent_references_all_three_sub_agents_in_order() -> None:
    text = (AGENTS / "builder-pro.md").read_text()
    positions = [text.index(f"{slug}.md") for slug in SUB_AGENTS_IN_ORDER]
    assert positions == sorted(positions), (
        "builder-pro.md must reference context-loader.md, code-generator.md, "
        "quality-gate-runner.md in that order"
    )


def test_forge_build_pro_skill_references_builder_pro() -> None:
    text = (SKILLS / "forge-build-pro" / "SKILL.md").read_text()
    assert "agents/builder-pro.md" in text


@pytest.mark.parametrize("slug", SUB_AGENTS_IN_ORDER)
def test_sub_agent_files_exist(slug: str) -> None:
    assert (AGENTS / f"{slug}.md").exists()


def test_forge_build_skill_unchanged_from_pre_feature_baseline() -> None:
    baseline = _git_show(PRE_FEATURE_SHA, "skills/forge-build/SKILL.md")
    current = (SKILLS / "forge-build" / "SKILL.md").read_text()
    assert current == baseline, (
        "skills/forge-build/SKILL.md must stay byte-identical to the pre-T-235 "
        "baseline -- the Pro pipeline lives only in forge-build-pro"
    )


def test_builder_agent_unchanged_from_pre_feature_baseline() -> None:
    baseline = _git_show(PRE_FEATURE_SHA, "agents/builder.md")
    current = (AGENTS / "builder.md").read_text()
    assert current == baseline, (
        "agents/builder.md must stay byte-identical to the pre-T-235 baseline -- "
        "builder-pro.md is a separate, coexisting agent, not a modification of this one"
    )


def test_forge_build_skill_does_not_mention_sub_agents() -> None:
    text = (SKILLS / "forge-build" / "SKILL.md").read_text()
    for slug in SUB_AGENTS_IN_ORDER + ["builder-pro"]:
        assert slug not in text, f"forge-build/SKILL.md must not reference {slug}"
