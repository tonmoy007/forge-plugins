"""Tests for hooks/_executor.py — atomic writes + event log."""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hooks"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import _event_log as event_log
import _executor as executor
from _proposals import LessonProposal, ReflectionProposal, StageAdvanceProposal

NOW = datetime.datetime.now(datetime.timezone.utc)


def _make_state(tmp_path: Path, stage: int = 3) -> None:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    ts = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "pipeline" / "state.md").write_text(
        f"---\nschema_version: 1\nproject_type: fullstack\ncycle: 1\n"
        f"current_stage: {stage}\ncurrent_task: null\ncurrent_milestone: null\n"
        f"total_tasks: null\nlast_updated: {ts}\nblockers: []\n---\n\n"
        "# Pipeline State\n\n## Stage History\n\n## Last Reflection\n"
    )
    (tmp_path / "tasks").mkdir(exist_ok=True)


def _make_reflection_proposal(stage: int = 3) -> ReflectionProposal:
    return ReflectionProposal(
        stage=stage, score=5, gaps=[], prose="**Timestamp**: now\n**Stage**: 3",
        model="v0.1", prompt_hash="abc123", temperature=0.0, created_at=NOW,
    )


def _make_lesson_proposal() -> LessonProposal:
    return LessonProposal(
        trigger="when editing files", rule="read before edit", why="stale diffs",
        stage_tags=[3], trust="ephemeral", source_session="s1",
        source_corrections=[], model="v0.1", prompt_hash="", temperature=0.0,
        created_at=NOW,
    )


class TestExecuteReflection:
    def test_prose_written_to_state_md(self, tmp_path):
        _make_state(tmp_path)
        forge_dir = tmp_path / ".forge"
        p = _make_reflection_proposal()
        ok = executor.execute_reflection(tmp_path, p, forge_dir, "s1")
        assert ok
        state_text = (tmp_path / "pipeline" / "state.md").read_text()
        assert "**Timestamp**" in state_text

    def test_event_logged(self, tmp_path):
        _make_state(tmp_path)
        forge_dir = tmp_path / ".forge"
        executor.execute_reflection(tmp_path, _make_reflection_proposal(), forge_dir, "s1")
        assert (forge_dir / "events.jsonl").exists()
        event = json.loads((forge_dir / "events.jsonl").read_text().strip())
        assert event["type"] == "ReflectionRecorded"

    def test_event_chain_verifies(self, tmp_path):
        _make_state(tmp_path)
        forge_dir = tmp_path / ".forge"
        executor.execute_reflection(tmp_path, _make_reflection_proposal(), forge_dir, "s1")
        executor.execute_reflection(tmp_path, _make_reflection_proposal(), forge_dir, "s1")
        ok, reason = event_log.verify(forge_dir)
        assert ok, reason


class TestExecuteLessons:
    def test_lesson_written_to_lessons_md(self, tmp_path):
        _make_state(tmp_path)
        forge_dir = tmp_path / ".forge"
        count = executor.execute_lessons(tmp_path, [_make_lesson_proposal()], forge_dir, "s1")
        assert count == 1
        md = (tmp_path / "tasks" / "lessons.md").read_text()
        assert "when editing files" in md
        assert "read before edit" in md

    def test_lesson_written_to_lessons_yaml(self, tmp_path):
        _make_state(tmp_path)
        forge_dir = tmp_path / ".forge"
        executor.execute_lessons(tmp_path, [_make_lesson_proposal()], forge_dir, "s1")
        lessons = yaml.safe_load((forge_dir / "lessons.yaml").read_text())
        assert isinstance(lessons, list)
        assert lessons[0]["trigger"] == "when editing files"
        assert lessons[0]["trust"] == "ephemeral"

    def test_lessons_md_and_yaml_stay_in_sync(self, tmp_path):
        _make_state(tmp_path)
        forge_dir = tmp_path / ".forge"
        proposals = [_make_lesson_proposal() for _ in range(3)]
        executor.execute_lessons(tmp_path, proposals, forge_dir, "s1")
        yaml_count = len(yaml.safe_load((forge_dir / "lessons.yaml").read_text()))
        md_count = (tmp_path / "tasks" / "lessons.md").read_text().count("**Rule**:")
        assert yaml_count == md_count == 3

    def test_empty_proposals_returns_zero(self, tmp_path):
        _make_state(tmp_path)
        forge_dir = tmp_path / ".forge"
        count = executor.execute_lessons(tmp_path, [], forge_dir, "s1")
        assert count == 0

    def test_event_logged_for_each_lesson(self, tmp_path):
        _make_state(tmp_path)
        forge_dir = tmp_path / ".forge"
        executor.execute_lessons(tmp_path, [_make_lesson_proposal()], forge_dir, "s1")
        events = [
            json.loads(ln)
            for ln in (forge_dir / "events.jsonl").read_text().splitlines()
            if ln.strip()
        ]
        assert any(e["type"] == "LessonRecorded" for e in events)


class TestExecuteStageAdvance:
    def test_stage_incremented(self, tmp_path):
        _make_state(tmp_path, stage=3)
        forge_dir = tmp_path / ".forge"
        p = StageAdvanceProposal(
            from_stage=3, to_stage=4,
            triggered_by="done_signal_with_passing_gate",
            created_at=NOW,
        )
        ok = executor.execute_stage_advance(tmp_path, p, forge_dir, "s1")
        assert ok
        import _state_lib as lib
        state = lib.read_state(str(tmp_path))
        assert state["current_stage"] == 4

    def test_event_logged(self, tmp_path):
        _make_state(tmp_path, stage=3)
        forge_dir = tmp_path / ".forge"
        p = StageAdvanceProposal(
            from_stage=3, to_stage=4,
            triggered_by="done_signal_with_passing_gate",
            created_at=NOW,
        )
        executor.execute_stage_advance(tmp_path, p, forge_dir, "s1")
        events = [
            json.loads(ln)
            for ln in (forge_dir / "events.jsonl").read_text().splitlines()
            if ln.strip()
        ]
        assert any(e["type"] == "StageAdvanced" for e in events)


class TestAtomicAppend:
    def test_atomic_append_creates_file(self, tmp_path):
        path = tmp_path / "test.md"
        executor._atomic_append(path, "hello\n")
        assert path.read_text() == "hello\n"

    def test_atomic_append_accumulates(self, tmp_path):
        path = tmp_path / "test.md"
        executor._atomic_append(path, "first\n")
        executor._atomic_append(path, "second\n")
        assert path.read_text() == "first\nsecond\n"

    def test_no_tmp_file_left_behind(self, tmp_path):
        path = tmp_path / "test.md"
        executor._atomic_append(path, "data\n")
        assert not path.with_suffix(".tmp").exists()
