"""T-250 / AC-BUILDSKILL-001a+b: the Builder Pro pipeline is wired correctly under
the corrected (Revision 2) architecture, and the original forge-build skill +
builder agent are left completely untouched.

AC-BUILDSKILL-001a: forge-build-pro/SKILL.md -> scripts/build_executor.py AND
                     agents/builder-pro.md -> references/build/01..05.md, in order.
AC-BUILDSKILL-001b: skills/forge-build/SKILL.md and agents/builder.md are unchanged
                     from the pre-T-235 baseline -- verified by diffing against a
                     literal fixture snapshot, not just by absence of new-file
                     mentions.

Compares against a committed fixture snapshot rather than `git show <old-sha>:path`:
CI's default `actions/checkout` is shallow (fetch-depth 1, see .github/workflows/
tests.yml), so an ancestor commit's objects are not guaranteed to be fetched even
though the sha is a real ancestor of HEAD -- `git show` then fails with exit 128
("bad object"), not a content mismatch. A fixture comparison has no history-depth
dependency and works identically locally and in CI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS = ROOT / "agents"
SKILLS = ROOT / "skills"
REFERENCES = ROOT / "references"
SCRIPTS = ROOT / "scripts"
BASELINE_FIXTURES = ROOT / "tests" / "fixtures" / "pre_pro_tier_baseline"

BUILD_REFERENCES_IN_ORDER = [
    "01-foundation.md",
    "02-context-resolution.md",
    "03-execution-verification.md",
    "04-traceability-validation.md",
    "05-workflow-governance.md",
]


def test_builder_pro_agent_references_all_five_build_references_in_order() -> None:
    text = (AGENTS / "builder-pro.md").read_text()
    positions = [text.index(name) for name in BUILD_REFERENCES_IN_ORDER]
    assert positions == sorted(positions), (
        "builder-pro.md must reference references/build/01..05.md in order"
    )


def test_builder_pro_agent_does_not_reference_deleted_revision_1_sub_agents() -> None:
    text = (AGENTS / "builder-pro.md").read_text()
    for slug in ("context-loader", "code-generator", "quality-gate-runner"):
        assert slug not in text, (
            f"builder-pro.md must not reference the deleted Revision-1 sub-agent {slug}.md"
        )


@pytest.mark.parametrize("relpath", [f"references/build/{n}" for n in BUILD_REFERENCES_IN_ORDER])
def test_build_reference_files_exist(relpath: str) -> None:
    assert (ROOT / relpath).exists()


def test_forge_build_pro_skill_references_build_executor_script() -> None:
    text = (SKILLS / "forge-build-pro" / "SKILL.md").read_text()
    assert "scripts/build_executor.py" in text


def test_forge_build_pro_skill_references_builder_pro_agent() -> None:
    text = (SKILLS / "forge-build-pro" / "SKILL.md").read_text()
    assert "agents/builder-pro.md" in text


def test_build_executor_script_exists() -> None:
    assert (SCRIPTS / "build_executor.py").exists()


def test_forge_build_skill_unchanged_from_pre_feature_baseline() -> None:
    baseline = (BASELINE_FIXTURES / "forge-build-SKILL.md").read_text()
    current = (SKILLS / "forge-build" / "SKILL.md").read_text()
    assert current == baseline, (
        "skills/forge-build/SKILL.md must stay byte-identical to the pre-T-235 "
        "baseline -- the Pro pipeline lives only in forge-build-pro"
    )


def test_builder_agent_unchanged_from_pre_feature_baseline() -> None:
    baseline = (BASELINE_FIXTURES / "builder.md").read_text()
    current = (AGENTS / "builder.md").read_text()
    assert current == baseline, (
        "agents/builder.md must stay byte-identical to the pre-T-235 baseline -- "
        "builder-pro.md is a separate, coexisting agent, not a modification of this one"
    )


def test_forge_build_skill_does_not_mention_pro_tier_internals() -> None:
    text = (SKILLS / "forge-build" / "SKILL.md").read_text()
    for slug in ("builder-pro", "build_executor", "context-loader", "code-generator", "quality-gate-runner"):
        assert slug not in text, f"forge-build/SKILL.md must not reference {slug}"
