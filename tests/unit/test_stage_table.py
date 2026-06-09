"""Tests for scripts/_stage_table.py — the canonical stage-order source of truth.

Covers T-101 (REQ-NEXTHINT-001, REQ-GATE-ENTRY-001, REQ-PATHS-001, REQ-PIPEBOUNDS-001):
the table validates, has no duplicate stage directories, and the loader returns the
correct next-stage + prerequisite for all 12 transitions.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _stage_table as st  # noqa: E402

# Canonical directory names — the EF-005 collision is resolved to exactly these.
CANONICAL_DIRS = {
    1: "01-srs",
    2: "02-product-ux",
    3: "03-architecture",
    4: "04-spec",
    5: "05-plan",
    6: "06-implementation",
    7: "07-evaluation",
    8: "08-deploy",
    9: "09-monitor",
    10: "10-feedback",
    11: "11-resolve",
    12: "12-release",
}

EXPECTED_SKILL = {
    1: "/forge:srs",
    2: "/forge:product",
    3: "/forge:arch",
    4: "/forge:spec",
    5: "/forge:plan",
    6: "/forge:build",
    7: "/forge:eval",
    8: "/forge:deploy",
    9: "/forge:monitor",
    10: "/forge:feedback",
    11: "/forge:resolve",
    12: "/forge:release",
}


# ---------- structural validity ----------

def test_table_validates_clean():
    assert st.validate() == []


def test_twelve_contiguous_stages():
    nums = [s["stage"] for s in st.stages()]
    assert nums == list(range(1, 13))


def test_no_duplicate_directories():
    dirs = [s["dir"] for s in st.stages()]
    assert len(dirs) == len(set(dirs))


@pytest.mark.parametrize("n,expected", CANONICAL_DIRS.items())
def test_canonical_dir(n, expected):
    assert st.canonical_dir(n) == expected


def test_stage_4_is_04_spec_not_technical_spec():
    # EF-005 / OQ-1: canonical is 04-spec, never 04-technical-spec.
    assert st.canonical_dir(4) == "04-spec"
    assert st.primary_artifact(4) == "pipeline/04-spec/technical-spec.md"


@pytest.mark.parametrize("n,skill", EXPECTED_SKILL.items())
def test_skill_per_stage(n, skill):
    assert st.stage(n)["skill"] == skill


# ---------- next-step chain (REQ-NEXTHINT-001) ----------

def test_next_stage_chain():
    for n in range(1, 12):
        assert st.next_stage(n) == n + 1
    assert st.next_stage(12) is None


def test_next_skill_matches_next_stage_skill():
    for n in range(1, 12):
        assert st.next_skill(n) == EXPECTED_SKILL[n + 1]


def test_next_hint_after_srs_names_product_not_architecture():
    # The EF-004 bug: after SRS the hint wrongly pointed at architecture.
    hint = st.next_hint(1)
    assert "/forge:product" in hint
    assert "/forge:arch" not in hint


def test_every_transition_has_a_hint():
    for n in range(1, 13):
        assert st.next_hint(n)  # non-empty


# ---------- prerequisites (REQ-GATE-ENTRY-001) ----------

def test_stage_1_has_no_prerequisite():
    assert st.prerequisite(1) is None
    assert st.prerequisite_skill(1) is None


def test_prerequisite_is_prior_primary_artifact():
    for n in range(2, 13):
        assert st.prerequisite(n) == st.primary_artifact(n - 1)


def test_arch_prerequisite_is_prd():
    # REQ-GATE-ENTRY-001 worked example: /forge:arch needs prd.md.
    assert st.prerequisite(3) == "pipeline/02-product-ux/prd.md"
    assert st.prerequisite_skill(3) == "/forge:product"


# ---------- bounds + cycles (REQ-PIPEBOUNDS-001) ----------

def test_bounds():
    assert st.min_stage() == 0
    assert st.max_stage() == 12
    assert st.bounds()["on_overflow"] == "cycle-wrap"


def test_cycle_types_present():
    c = st.cycles()
    assert c["full"] == {"entry": 1, "exit": 12}
    assert c["hotfix"] == {"entry": 6, "exit": 9}
    assert set(c) == {"full", "iteration", "hotfix", "tech-debt"}


# ---------- edge cases ----------

def test_unknown_stage_returns_none():
    assert st.stage(0) is None
    assert st.stage(13) is None
    assert st.stage(99) is None
    assert st.canonical_dir(99) is None
    assert st.next_hint(99) is None
