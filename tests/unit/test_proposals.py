"""Tests for hooks/_proposals.py — Pydantic schema enforcement."""
from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hooks"))

from _proposals import (
    GateProposal,
    LessonProposal,
    ReflectionProposal,
    StageAdvanceProposal,
)

NOW = datetime.datetime.now(datetime.timezone.utc)


class TestReflectionProposal:
    def test_valid_construction(self):
        p = ReflectionProposal(
            stage=3, score=7, gaps=[], prose="some text",
            model="v0.1", prompt_hash="abc123", temperature=0.0, created_at=NOW,
        )
        assert p.stage == 3
        assert p.score == 7

    def test_score_below_1_rejected(self):
        with pytest.raises(ValidationError):
            ReflectionProposal(
                stage=1, score=0, gaps=[], prose="x",
                model="v0.1", prompt_hash="h", temperature=0.0, created_at=NOW,
            )

    def test_score_above_10_rejected(self):
        with pytest.raises(ValidationError):
            ReflectionProposal(
                stage=1, score=11, gaps=[], prose="x",
                model="v0.1", prompt_hash="h", temperature=0.0, created_at=NOW,
            )

    def test_prose_length_cap(self):
        with pytest.raises(ValidationError):
            ReflectionProposal(
                stage=1, score=5, gaps=[], prose="x" * 4001,
                model="v0.1", prompt_hash="h", temperature=0.0, created_at=NOW,
            )

    def test_gaps_list_length_cap(self):
        with pytest.raises(ValidationError):
            ReflectionProposal(
                stage=1, score=5, gaps=["g"] * 11, prose="x",
                model="v0.1", prompt_hash="h", temperature=0.0, created_at=NOW,
            )


class TestLessonProposal:
    def _make(self, **overrides) -> LessonProposal:
        defaults = dict(
            trigger="when editing a file",
            rule="always read before edit",
            why="avoids stale diffs",
            stage_tags=[3],
            trust="ephemeral",
            source_session="s1",
            source_corrections=[],
            model="v0.1",
            prompt_hash="",
            temperature=0.0,
            created_at=NOW,
        )
        defaults.update(overrides)
        return LessonProposal(**defaults)

    def test_valid_construction(self):
        p = self._make()
        assert p.trust == "ephemeral"

    def test_trust_locked_to_ephemeral(self):
        """trust field only accepts 'ephemeral' — no elevation at creation."""
        with pytest.raises((ValidationError, ValueError)):
            self._make(trust="trusted")  # type: ignore[arg-type]

    def test_trigger_length_cap(self):
        with pytest.raises(ValidationError):
            self._make(trigger="x" * 201)

    def test_rule_length_cap(self):
        with pytest.raises(ValidationError):
            self._make(rule="x" * 501)

    def test_why_length_cap(self):
        with pytest.raises(ValidationError):
            self._make(why="x" * 501)


class TestGateProposal:
    def test_valid_construction(self):
        p = GateProposal(stage=1, passed=True, blockers=[], advance_to=2, checked_at=NOW)
        assert p.passed is True

    def test_advance_to_nullable(self):
        p = GateProposal(stage=1, passed=False, blockers=["foo"], advance_to=None, checked_at=NOW)
        assert p.advance_to is None


class TestStageAdvanceProposal:
    def test_valid_construction(self):
        p = StageAdvanceProposal(
            from_stage=1, to_stage=2,
            triggered_by="done_signal_with_passing_gate",
            created_at=NOW,
        )
        assert p.to_stage == 2

    def test_triggered_by_locked(self):
        with pytest.raises((ValidationError, ValueError)):
            StageAdvanceProposal(
                from_stage=1, to_stage=2,
                triggered_by="manual",  # type: ignore[arg-type]
                created_at=NOW,
            )
