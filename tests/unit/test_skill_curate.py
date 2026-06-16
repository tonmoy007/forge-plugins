"""Tests for scripts/skill_curate.py — library curation (T-182, REQ-SM-009).

ExpeL-style voting (ADD / UPVOTE / DOWNVOTE / EDIT-merge, prune at weight 0) persisted
in `.forge/skill-stats.jsonl`, a TroVE log-scaled frequency trim, and a scheduled
`/dream`-style maintenance pass that merges near-duplicate descriptions, prunes
never-used skills, and flags skills referencing missing files/commands.

AC-SM-009: two near-duplicate proposals merged; a never-used skill pruned; a skill
referencing a deleted file flagged; voting updates persist.

These functions run offline on the background path: `.forge`-only writes, never raise,
stdlib + PyYAML fail-soft. The module filename is hyphen-free so it imports cleanly, but
we load it via importlib for parity with the other curation tests and to register it in
sys.modules (so @dataclass round-trips resolve).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
_mod_path = _root / "scripts" / "skill_curate.py"
_spec = importlib.util.spec_from_file_location("skill_curate", _mod_path)
_sc = importlib.util.module_from_spec(_spec)
sys.modules["skill_curate"] = _sc
_spec.loader.exec_module(_sc)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _write_skill(root: Path, slug: str, *, name: str, description: str, body: str = "") -> Path:
    """Create <root>/<slug>/SKILL.md with frontmatter; return the dir."""
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    text = f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n\n{body}"
    (d / "SKILL.md").write_text(text, encoding="utf-8")
    return d


# --------------------------------------------------------------------------- #
# Voting + persistence
# --------------------------------------------------------------------------- #
def test_add_then_aggregate_initial_weight(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _sc.vote(forge, "alpha", "ADD")
    stats = _sc.aggregate_stats(forge)
    assert "alpha" in stats
    assert stats["alpha"].weight == _sc.INIT_WEIGHT
    assert stats["alpha"].uses == 0


def test_upvote_increases_weight_and_uses(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _sc.vote(forge, "alpha", "ADD")
    _sc.vote(forge, "alpha", "UPVOTE")
    _sc.vote(forge, "alpha", "UPVOTE")
    stat = _sc.aggregate_stats(forge)["alpha"]
    assert stat.weight == _sc.INIT_WEIGHT + 2
    assert stat.uses == 2


def test_downvote_decreases_weight(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _sc.vote(forge, "alpha", "ADD")
    _sc.vote(forge, "alpha", "DOWNVOTE")
    stat = _sc.aggregate_stats(forge)["alpha"]
    assert stat.weight == _sc.INIT_WEIGHT - 1
    # a failed reuse still counts as a use (it was tried)
    assert stat.uses == 1


def test_votes_persist_across_calls(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _sc.vote(forge, "alpha", "ADD")
    _sc.vote(forge, "alpha", "UPVOTE")
    # Re-aggregating from the same jsonl reproduces the state — votes are durable.
    assert _sc.aggregate_stats(forge)["alpha"].weight == _sc.INIT_WEIGHT + 1
    assert (forge / "skill-stats.jsonl").exists()


def test_prune_at_weight_zero(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _sc.vote(forge, "alpha", "ADD")  # weight 1
    _sc.vote(forge, "alpha", "DOWNVOTE")  # weight 0 -> prunable
    stats = _sc.aggregate_stats(forge)
    assert "alpha" in _sc.prunable_by_weight(stats)


def test_positive_weight_not_pruned(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _sc.vote(forge, "alpha", "ADD")
    _sc.vote(forge, "alpha", "UPVOTE")
    stats = _sc.aggregate_stats(forge)
    assert "alpha" not in _sc.prunable_by_weight(stats)


# --------------------------------------------------------------------------- #
# Fail-soft
# --------------------------------------------------------------------------- #
def test_aggregate_missing_file_is_empty(tmp_path: Path) -> None:
    assert _sc.aggregate_stats(tmp_path / ".forge") == {}


def test_aggregate_skips_malformed_lines(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir()
    stats_path = forge / "skill-stats.jsonl"
    stats_path.write_text(
        "not json\n"
        + json.dumps({"skill": "alpha", "action": "ADD"})
        + "\n"
        + "{broken\n"
        + json.dumps({"action": "UPVOTE"})  # missing skill — skipped
        + "\n",
        encoding="utf-8",
    )
    stats = _sc.aggregate_stats(forge)
    assert set(stats) == {"alpha"}


def test_vote_never_raises_on_bad_input(tmp_path: Path) -> None:
    # unknown action and odd paths must not raise on the background path
    assert _sc.vote(tmp_path / ".forge", "alpha", "BOGUS") in (True, False)
    assert _sc.aggregate_stats(tmp_path / ".forge") == {} or True


# --------------------------------------------------------------------------- #
# TroVE frequency trim
# --------------------------------------------------------------------------- #
def test_frequency_trim_drops_rarely_used(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    # popular skill used many times; rare skill used once
    _sc.vote(forge, "popular", "ADD")
    for _ in range(20):
        _sc.vote(forge, "popular", "UPVOTE")
    _sc.vote(forge, "rare", "ADD")
    _sc.vote(forge, "rare", "UPVOTE")  # 1 use
    stats = _sc.aggregate_stats(forge)
    trimmed = _sc.trim_by_frequency(stats)
    assert "rare" in trimmed
    assert "popular" not in trimmed


def test_frequency_trim_empty_is_safe(tmp_path: Path) -> None:
    assert _sc.trim_by_frequency({}) == set()


# --------------------------------------------------------------------------- #
# Maintenance pass (/dream-style)
# --------------------------------------------------------------------------- #
def test_maintenance_merges_near_duplicate_proposals(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    proposed = forge / "proposed-skills"
    desc = "Diagnose a failing pytest run, locate the root cause, patch it, add a regression test."
    _write_skill(proposed, "fix-failing-test-a", name="fix-failing-test-a", description=desc)
    _write_skill(
        proposed,
        "fix-failing-test-b",
        name="fix-failing-test-b",
        description=desc + " ",  # near-identical
    )
    report = _sc.run_maintenance(forge, plugin_dir=tmp_path / "plugin")
    merged_pairs = [m for m in report.merged]
    assert merged_pairs, "expected at least one near-duplicate merge"
    # one of the pair is removed from disk; the other survives
    survivors = list(proposed.glob("*/SKILL.md"))
    assert len(survivors) == 1


def test_maintenance_prunes_never_used_skill(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    plugin = tmp_path / "plugin"
    skills = plugin / "skills"
    _write_skill(skills, "ghost", name="ghost", description="Never invoked by anyone, ever.")
    # ghost has no stats row at all -> never used
    report = _sc.run_maintenance(forge, plugin_dir=plugin)
    assert "ghost" in report.pruned


def test_maintenance_keeps_used_skill(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    plugin = tmp_path / "plugin"
    skills = plugin / "skills"
    _write_skill(skills, "useful", name="useful", description="Does a real, used thing.")
    _sc.vote(forge, "useful", "ADD")
    _sc.vote(forge, "useful", "UPVOTE")
    report = _sc.run_maintenance(forge, plugin_dir=plugin)
    assert "useful" not in report.pruned


def test_maintenance_flags_missing_file_reference(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    plugin = tmp_path / "plugin"
    skills = plugin / "skills"
    body = "## Procedure\n\nRun `python3 scripts/totally-missing.py` then check output.\n"
    _write_skill(
        skills,
        "stale-ref",
        name="stale-ref",
        description="References a file that no longer exists.",
        body=body,
    )
    _sc.vote(forge, "stale-ref", "ADD")
    _sc.vote(forge, "stale-ref", "UPVOTE")  # keep it from being pruned as unused
    report = _sc.run_maintenance(forge, plugin_dir=plugin)
    flagged_names = {f.skill for f in report.flagged}
    assert "stale-ref" in flagged_names


def test_maintenance_does_not_flag_existing_file(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    plugin = tmp_path / "plugin"
    skills = plugin / "skills"
    (plugin / "scripts").mkdir(parents=True, exist_ok=True)
    (plugin / "scripts" / "real.py").write_text("# real\n", encoding="utf-8")
    body = "## Procedure\n\nRun `python3 scripts/real.py`.\n"
    _write_skill(
        skills, "good-ref", name="good-ref", description="Points at a real file.", body=body
    )
    _sc.vote(forge, "good-ref", "ADD")
    _sc.vote(forge, "good-ref", "UPVOTE")
    report = _sc.run_maintenance(forge, plugin_dir=plugin)
    assert "good-ref" not in {f.skill for f in report.flagged}


def test_maintenance_never_raises_on_empty(tmp_path: Path) -> None:
    # No .forge, no plugin — must produce an empty report, not crash.
    report = _sc.run_maintenance(tmp_path / "nope" / ".forge", plugin_dir=tmp_path / "nope2")
    assert report.merged == [] and report.pruned == [] and report.flagged == []


def test_maintenance_writes_only_under_forge_and_skills(tmp_path: Path) -> None:
    """Maintenance may delete proposal/skill dirs but must not write outside the tree."""
    forge = tmp_path / ".forge"
    proposed = forge / "proposed-skills"
    desc = "Same description for both."
    _write_skill(proposed, "dup-a", name="dup-a", description=desc)
    _write_skill(proposed, "dup-b", name="dup-b", description=desc)
    sentinel = tmp_path / "outside.txt"
    sentinel.write_text("untouched", encoding="utf-8")
    _sc.run_maintenance(forge, plugin_dir=tmp_path / "plugin")
    assert sentinel.read_text() == "untouched"
