"""Tests for hooks/_validator.py — deterministic proposal validation."""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hooks"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from _proposals import (
    GateProposal,
    LessonProposal,
    ReflectionProposal,
    StageAdvanceProposal,
)
import _validator as validator

NOW = datetime.datetime.now(datetime.timezone.utc)


def _make_reflection(**kw) -> ReflectionProposal:
    defaults = dict(stage=3, score=5, gaps=[], prose="some text",
                    model="v0.1", prompt_hash="abc", temperature=0.0, created_at=NOW)
    defaults.update(kw)
    return ReflectionProposal(**defaults)


def _make_lesson(**kw) -> LessonProposal:
    defaults = dict(trigger="when X happens", rule="do Y", why="because Z",
                    stage_tags=[3], trust="ephemeral", source_session="s1",
                    source_corrections=[], model="v0.1", prompt_hash="",
                    temperature=0.0, created_at=NOW)
    defaults.update(kw)
    return LessonProposal(**defaults)


class TestReflectionValidation:
    def test_valid_reflection_accepted(self, tmp_path):
        ok, reason = validator.validate(_make_reflection(), tmp_path)
        assert ok
        assert reason == ""

    def test_empty_prose_rejected(self, tmp_path):
        ok, reason = validator.validate(_make_reflection(prose="   "), tmp_path)
        assert not ok
        assert "prose" in reason

    def test_empty_prompt_hash_rejected(self, tmp_path):
        ok, reason = validator.validate(_make_reflection(prompt_hash=""), tmp_path)
        assert not ok
        assert "prompt_hash" in reason


class TestLessonValidation:
    def test_valid_lesson_accepted(self, tmp_path):
        ok, reason = validator.validate(_make_lesson(), tmp_path)
        assert ok

    def test_no_existing_lessons_yaml_accepted(self, tmp_path):
        ok, _ = validator.validate(_make_lesson(), tmp_path)
        assert ok

    def test_duplicate_trigger_rejected(self, tmp_path):
        forge_dir = tmp_path / ".forge"
        forge_dir.mkdir()
        (forge_dir / "lessons.yaml").write_text(
            yaml.dump([{"trigger": "when x happens", "rule": "do something",
                        "trust": "ephemeral"}])
        )
        ok, reason = validator.validate(_make_lesson(trigger="when X happens"), forge_dir)
        assert not ok
        assert "duplicate" in reason.lower()

    def test_conflict_with_trusted_lesson_rejected(self, tmp_path):
        forge_dir = tmp_path / ".forge"
        forge_dir.mkdir()
        (forge_dir / "lessons.yaml").write_text(
            yaml.dump([{
                "trigger": "when editing files",
                "rule": "always read the file first",
                "trust": "trusted",
            }])
        )
        # New lesson with overlapping trigger but negated rule
        lesson = _make_lesson(
            trigger="when editing files in a hurry",
            rule="do not read the file first",
        )
        ok, reason = validator.validate(lesson, forge_dir)
        assert not ok
        assert "conflict" in reason.lower()

    def test_non_conflicting_trusted_lesson_accepted(self, tmp_path):
        forge_dir = tmp_path / ".forge"
        forge_dir.mkdir()
        (forge_dir / "lessons.yaml").write_text(
            yaml.dump([{
                "trigger": "database migrations",
                "rule": "run tests after migration",
                "trust": "trusted",
            }])
        )
        lesson = _make_lesson(trigger="python formatting", rule="always run black")
        ok, _ = validator.validate(lesson, forge_dir)
        assert ok

    def test_corrupt_lessons_yaml_fails_open(self, tmp_path):
        forge_dir = tmp_path / ".forge"
        forge_dir.mkdir()
        (forge_dir / "lessons.yaml").write_text("{{not: valid: yaml: [[")
        ok, _ = validator.validate(_make_lesson(), forge_dir)
        assert ok  # fail open — can't block on unreadable file


class TestGateAndAdvancePassThrough:
    def test_gate_proposal_always_accepted(self, tmp_path):
        p = GateProposal(stage=1, passed=True, blockers=[], advance_to=2, checked_at=NOW)
        ok, _ = validator.validate(p, tmp_path)
        assert ok

    def test_stage_advance_always_accepted(self, tmp_path):
        p = StageAdvanceProposal(
            from_stage=1, to_stage=2,
            triggered_by="done_signal_with_passing_gate",
            created_at=NOW,
        )
        ok, _ = validator.validate(p, tmp_path)
        assert ok
