"""Tests for scripts/dreamer.py — the Dreamer daemon (T-143, REQ-F-015..021).

Covers:
- apply_confidence_decay: marks dormant, leaves others, idempotent, ignores no-confidence.
- find_duplicates: flags high-Jaccard pairs, does not mutate, respects threshold.
- find_contradictions: flags opposing-polarity similar-trigger pairs, flag-only.
- write_lessons_atomic: round-trips, never raises on bad path.
- run(): decay applied, digest written, idempotent per day, missing lessons graceful.
- run() without capabilities.json → deterministic digest, consolidation_used=False.
- run() with fake claude → consolidation_used=True, session persisted, resumed on 2nd run.
- run() with missing lessons.yaml → graceful no-op, no crash.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import stat
import sys
from pathlib import Path

import yaml

# --- module load (importlib pattern from test_observer.py) ---------------------

_root = Path(__file__).resolve().parent.parent.parent
_mod_path = _root / "scripts" / "dreamer.py"
_spec = importlib.util.spec_from_file_location("dreamer", _mod_path)
_drm = importlib.util.module_from_spec(_spec)
sys.modules["dreamer"] = _drm
_spec.loader.exec_module(_drm)

NOW = dt.datetime(2026, 6, 11, 12, 0, 0, tzinfo=dt.timezone.utc)
DATE = "2026-06-11"


# --- fake claude helpers (mirrors test_observer.py) ---------------------------

def _envelope(session_id: str, result: str) -> str:
    return json.dumps({
        "session_id": session_id,
        "total_cost_usd": 0.005,
        "usage": {"input_tokens": 20, "output_tokens": 10},
        "is_error": False,
        "result": result,
    })


def _fake_claude(tmp_path: Path, body: str) -> str:
    script = tmp_path / "claude"
    script.write_text("#!/bin/sh\n" + body + "\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(script)


def _cap(forge: Path, available: bool = True) -> None:
    forge.mkdir(parents=True, exist_ok=True)
    (forge / "capabilities.json").write_text(json.dumps(
        {"forge_background_available": available, "reason": "test"}))


def _make_lessons_yaml(forge: Path, lessons: list[dict]) -> Path:
    forge.mkdir(parents=True, exist_ok=True)
    path = forge / "lessons.yaml"
    path.write_text(yaml.dump({"schema_version": 1, "lessons": lessons}))
    return path


# ==============================================================================
# apply_confidence_decay
# ==============================================================================

def test_decay_marks_below_threshold_dormant() -> None:
    lessons = [
        {"trigger": "a", "rule": "b", "confidence": 0.2},
        {"trigger": "c", "rule": "d", "confidence": 0.5},
    ]
    updated, n = _drm.apply_confidence_decay(lessons, threshold=0.3)
    assert n == 1
    assert updated[0]["status"] == "dormant"
    assert "status" not in updated[1] or updated[1].get("status") != "dormant"


def test_decay_leaves_above_threshold_untouched() -> None:
    lessons = [{"trigger": "x", "rule": "y", "confidence": 0.9}]
    updated, n = _drm.apply_confidence_decay(lessons, threshold=0.3)
    assert n == 0
    assert updated[0].get("status") != "dormant"


def test_decay_is_idempotent() -> None:
    lessons = [{"trigger": "a", "rule": "b", "confidence": 0.1}]
    pass1, n1 = _drm.apply_confidence_decay(lessons)
    pass2, n2 = _drm.apply_confidence_decay(pass1)
    assert n1 == 1
    assert n2 == 1  # still below threshold — counted again (stable digest count)
    assert pass2[0]["status"] == "dormant"
    # The lesson dict itself is unchanged (already dormant — no re-copy needed)
    assert pass1[0] is pass2[0]


def test_decay_ignores_lessons_without_confidence() -> None:
    lessons = [
        {"trigger": "a", "rule": "b"},  # no confidence key
        {"trigger": "c", "rule": "d", "confidence": None},  # explicit None
    ]
    updated, n = _drm.apply_confidence_decay(lessons)
    assert n == 0
    for l in updated:
        assert l.get("status") != "dormant"


def test_decay_does_not_mutate_input() -> None:
    original = {"trigger": "a", "rule": "b", "confidence": 0.1}
    lessons = [original]
    _drm.apply_confidence_decay(lessons)
    assert "status" not in original  # input not mutated


# ==============================================================================
# find_duplicates
# ==============================================================================

def test_find_duplicates_flags_high_jaccard_pair() -> None:
    # Nearly identical trigger+rule → high Jaccard
    lessons = [
        {"trigger": "when editing a file", "rule": "always read it first"},
        {"trigger": "when editing a file", "rule": "always read it first before changing"},
        {"trigger": "deploy to prod", "rule": "run smoke tests"},
    ]
    pairs = _drm.find_duplicates(lessons, threshold=0.8)
    indices = [(i, j) for i, j, _ in pairs]
    assert (0, 1) in indices


def test_find_duplicates_does_not_flag_dissimilar() -> None:
    lessons = [
        {"trigger": "alpha beta gamma", "rule": "do something"},
        {"trigger": "delta epsilon zeta", "rule": "do something else entirely"},
    ]
    pairs = _drm.find_duplicates(lessons, threshold=0.8)
    assert pairs == []


def test_find_duplicates_does_not_mutate_lessons() -> None:
    lessons = [
        {"trigger": "a b c", "rule": "x y z"},
        {"trigger": "a b c", "rule": "x y z"},
    ]
    original_lessons = [dict(l) for l in lessons]
    _drm.find_duplicates(lessons, threshold=0.5)
    assert lessons == original_lessons


def test_find_duplicates_respects_threshold() -> None:
    lessons = [
        {"trigger": "alpha beta", "rule": "gamma"},
        {"trigger": "alpha beta", "rule": "gamma"},
    ]
    # threshold=1.0 → only exact duplicates (Jaccard=1)
    pairs_strict = _drm.find_duplicates(lessons, threshold=1.0)
    assert len(pairs_strict) == 1
    # threshold=0.0 → all pairs
    pairs_all = _drm.find_duplicates(lessons, threshold=0.0)
    assert len(pairs_all) == 1  # still just the one pair (only 2 lessons)


def test_find_duplicates_indices_i_less_than_j() -> None:
    lessons = [
        {"trigger": "same trigger text", "rule": "same rule text"},
        {"trigger": "same trigger text", "rule": "same rule text"},
        {"trigger": "same trigger text", "rule": "same rule text"},
    ]
    pairs = _drm.find_duplicates(lessons, threshold=0.5)
    for i, j, _ in pairs:
        assert i < j


# ==============================================================================
# find_contradictions
# ==============================================================================

def test_find_contradictions_flags_opposing_polarity() -> None:
    lessons = [
        {"trigger": "before committing code", "rule": "always run the linter"},
        {"trigger": "before committing code", "rule": "never run automated tools blindly"},
    ]
    pairs = _drm.find_contradictions(lessons)
    assert (0, 1) in pairs


def test_find_contradictions_does_not_flag_same_polarity() -> None:
    # Both positive
    lessons = [
        {"trigger": "before committing", "rule": "run the linter"},
        {"trigger": "before committing code", "rule": "run the tests"},
    ]
    pairs = _drm.find_contradictions(lessons)
    assert pairs == []


def test_find_contradictions_does_not_flag_dissimilar_triggers() -> None:
    # High opposing polarity but triggers are completely different → no contradiction
    lessons = [
        {"trigger": "alpha beta gamma", "rule": "always do this"},
        {"trigger": "delta epsilon zeta", "rule": "never do that"},
    ]
    pairs = _drm.find_contradictions(lessons)
    assert pairs == []


def test_find_contradictions_flag_only_no_mutation() -> None:
    lessons = [
        {"trigger": "when editing code", "rule": "read first"},
        {"trigger": "when editing code", "rule": "never edit without reading"},
    ]
    originals = [dict(l) for l in lessons]
    _drm.find_contradictions(lessons)
    assert lessons == originals


def test_find_contradictions_recognises_all_negation_tokens() -> None:
    negation_rules = [
        "never do this",
        "don't do this",
        "do not do this",
        "avoid doing this",
        "no doing this",
    ]
    positive_rule = "always do this"
    trigger = "when something happens every time"
    for neg_rule in negation_rules:
        lessons = [
            {"trigger": trigger, "rule": positive_rule},
            {"trigger": trigger, "rule": neg_rule},
        ]
        pairs = _drm.find_contradictions(lessons)
        assert (0, 1) in pairs, f"Expected contradiction for rule: {neg_rule!r}"


# ==============================================================================
# write_lessons_atomic
# ==============================================================================

def test_write_lessons_atomic_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "lessons.yaml"
    data = {"schema_version": 1, "lessons": [{"trigger": "t", "rule": "r"}]}
    result = _drm.write_lessons_atomic(path, data)
    assert result is True
    loaded = yaml.safe_load(path.read_text())
    assert loaded["schema_version"] == 1
    assert loaded["lessons"][0]["trigger"] == "t"


def test_write_lessons_atomic_never_raises_on_bad_path(tmp_path: Path) -> None:
    # Attempt to write inside a file (not a directory) — should not raise
    bad_parent = tmp_path / "i_am_a_file"
    bad_parent.write_text("not a directory")
    path = bad_parent / "lessons.yaml"
    result = _drm.write_lessons_atomic(path, {"schema_version": 1, "lessons": []})
    assert result is False  # failed gracefully


# ==============================================================================
# run() — core behaviour
# ==============================================================================

def test_run_applies_decay_and_writes_lessons_yaml(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge, available=False)
    _make_lessons_yaml(forge, [
        {"trigger": "a", "rule": "b", "confidence": 0.1},
        {"trigger": "c", "rule": "d", "confidence": 0.9},
    ])
    result = _drm.run(str(tmp_path), now=NOW)
    assert result["decayed"] == 1
    updated = yaml.safe_load((forge / "lessons.yaml").read_text())
    dormant = [l for l in updated["lessons"] if l.get("status") == "dormant"]
    assert len(dormant) == 1


def test_run_writes_daily_digest(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge, available=False)
    _make_lessons_yaml(forge, [{"trigger": "x", "rule": "y"}])
    result = _drm.run(str(tmp_path), now=NOW)
    dpath = Path(result["digest_path"])
    assert dpath.exists()
    content = dpath.read_text()
    assert DATE in content
    assert "Dreamer Daily Digest" in content


def test_run_is_idempotent_same_day(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge, available=False)
    _make_lessons_yaml(forge, [{"trigger": "x", "rule": "y", "confidence": 0.1}])
    _drm.run(str(tmp_path), now=NOW)
    content1 = _drm.daily_digest_path(str(tmp_path), DATE).read_text()

    # Second run same day — digest content should be identical (overwrite, not append)
    _drm.run(str(tmp_path), now=NOW)
    content2 = _drm.daily_digest_path(str(tmp_path), DATE).read_text()
    assert content1 == content2


def test_run_missing_lessons_yaml_graceful_noop(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    # No capabilities, no lessons.yaml
    result = _drm.run(str(tmp_path), now=NOW)
    assert result["decayed"] == 0
    assert result["duplicates"] == []
    assert result["contradictions"] == []
    assert result["consolidation_used"] is False
    # Must not raise
    assert isinstance(result, dict)


# ==============================================================================
# run() — capability gating
# ==============================================================================

def test_run_no_capabilities_json_skips_dispatch_writes_digest(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    # No capabilities.json at all
    _make_lessons_yaml(forge, [{"trigger": "a", "rule": "b"}])
    result = _drm.run(str(tmp_path), now=NOW, claude_bin="/nonexistent")
    assert result["consolidation_used"] is False
    dpath = Path(result["digest_path"])
    assert dpath.exists()
    content = dpath.read_text()
    assert "Dreamer Daily Digest" in content
    # No consolidation section
    assert "## Consolidation" not in content


def test_run_capabilities_false_skips_dispatch(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge, available=False)
    _make_lessons_yaml(forge, [{"trigger": "a", "rule": "b"}])
    result = _drm.run(str(tmp_path), now=NOW, claude_bin="/nonexistent")
    assert result["consolidation_used"] is False


# ==============================================================================
# run() — fake claude dispatch (capability=True path)
# ==============================================================================

def test_run_with_fake_claude_consolidation_used_and_session_persisted(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge, available=True)
    _make_lessons_yaml(forge, [{"trigger": "a", "rule": "b"}])

    consolidation_text = "Lessons look healthy this week. No major issues found."
    env = _envelope("dreamer-1", consolidation_text)
    argv_log = tmp_path / "argv.log"
    claude_bin = _fake_claude(
        tmp_path,
        f'printf "%s\\n" "$*" >> "{argv_log}"\ncat <<\'EOF\'\n{env}\nEOF',
    )
    result = _drm.run(str(tmp_path), now=NOW, claude_bin=claude_bin)
    assert result["consolidation_used"] is True

    # Session persisted
    sess = json.loads((forge / "dreamer-session.json").read_text())
    assert sess["session_id"] == "dreamer-1"

    # Digest includes consolidation
    dpath = Path(result["digest_path"])
    content = dpath.read_text()
    assert "## Consolidation" in content
    assert consolidation_text in content

    # Model is haiku (cost rule)
    argv = argv_log.read_text()
    assert "--model haiku" in argv


def test_run_second_call_resumes_session(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge, available=True)
    _make_lessons_yaml(forge, [{"trigger": "a", "rule": "b"}])

    argv_log = tmp_path / "argv.log"
    env = _envelope("dreamer-1", "Summary text here.")
    claude_bin = _fake_claude(
        tmp_path,
        f'printf "%s\\n" "$*" >> "{argv_log}"\ncat <<\'EOF\'\n{env}\nEOF',
    )

    # First run — no prior session, no --resume
    _drm.run(str(tmp_path), now=NOW, claude_bin=claude_bin)

    # Reset the lessons.yaml for the second run (decay is idempotent anyway)
    _make_lessons_yaml(forge, [{"trigger": "a", "rule": "b"}])

    # Second run — should resume
    later = NOW + dt.timedelta(days=1)
    _drm.run(str(tmp_path), now=later, claude_bin=claude_bin)

    argv_text = argv_log.read_text()
    # Second call must include --resume dreamer-1
    lines = argv_text.strip().splitlines()
    assert len(lines) >= 2, "Expected at least two dispatch calls"
    second_call = lines[1]
    assert "--resume" in second_call
    assert "dreamer-1" in second_call
    assert "--model haiku" in second_call


# ==============================================================================
# run() — return shape
# ==============================================================================

def test_run_returns_correct_shape(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _cap(forge, available=False)
    _make_lessons_yaml(forge, [
        {"trigger": "when editing a file", "rule": "always read it first"},
        {"trigger": "when editing a file", "rule": "always read it first before changing"},
    ])
    result = _drm.run(str(tmp_path), now=NOW)
    assert isinstance(result["decayed"], int)
    assert isinstance(result["duplicates"], list)
    assert isinstance(result["contradictions"], list)
    assert isinstance(result["digest_path"], str)
    assert isinstance(result["consolidation_used"], bool)
    # Duplicate pair should be flagged
    assert len(result["duplicates"]) >= 1


# --- T-223 (REQ-CM-004): static tightening of the free-prose consolidation prompt -----------

def test_consolidation_prompt_tightened_keeps_output_spec():
    # Pure filler dropped; the output spec (one short paragraph, 3-5 sentences, terse, no bullets)
    # is preserved. Deterministic — no toggle.
    p = _drm._CONSOLIDATION_PROMPT
    assert "Forge's Dreamer" in p
    assert "3-5 sentences" in p
    assert "Terse and concrete" in p
    assert "No bullet lists" in p
    # dropped filler:
    assert "You have just completed a lesson consolidation run" not in p
    assert "Provide a single short paragraph" not in p
