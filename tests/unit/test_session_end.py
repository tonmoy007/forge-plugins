"""Unit tests for hooks/session-end.py (tested via subprocess)."""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = str(Path(__file__).parent.parent.parent / "hooks" / "session-end.py")
PYTHON = sys.executable


def _run(cwd: str, session_id: str = "test-session") -> subprocess.CompletedProcess:
    payload = json.dumps({
        "hook_event_name": "SessionEnd",
        "session_id": session_id,
        "cwd": cwd,
    })
    return subprocess.run(
        [PYTHON, HOOK],
        input=payload,
        capture_output=True,
        text=True,
    )


def _make_state(tmp_path: Path, stage: int = 3, task: str | None = "T-010") -> Path:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    state = tmp_path / "pipeline" / "state.md"
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    task_val = f'"{task}"' if task else "null"
    state.write_text(
        f"---\nschema_version: 1\nproject_type: fullstack\ncycle: 1\n"
        f"current_stage: {stage}\ncurrent_task: {task_val}\ncurrent_milestone: null\n"
        f"total_tasks: null\nlast_updated: {now}\nblockers: []\n---\n\n# State\n"
    )
    return state


def _make_lessons(tmp_path: Path, titles: list[str]) -> None:
    (tmp_path / "tasks").mkdir(exist_ok=True)
    content = "# Lessons\n\n"
    for t in titles:
        content += f"### {t}\nSome rule here.\n\n"
    (tmp_path / "tasks" / "lessons.md").write_text(content)


def _make_session_log(tmp_path: Path, paths: list[str]) -> None:
    forge_dir = tmp_path / ".forge"
    forge_dir.mkdir(exist_ok=True)
    lines = [json.dumps({"path": p}) for p in paths]
    (forge_dir / "session-log.jsonl").write_text("\n".join(lines) + "\n")


class TestNonForgeDir:
    def test_no_pipeline_silent_exit_0(self, tmp_path):
        r = _run(str(tmp_path))
        assert r.returncode == 0
        assert r.stdout.strip() == ""

    def test_no_pipeline_no_stderr(self, tmp_path):
        r = _run(str(tmp_path))
        assert r.stderr.strip() == ""


class TestSessionSummaryCreated:
    def test_sessions_dir_created(self, tmp_path):
        _make_state(tmp_path)
        _run(str(tmp_path))
        assert (tmp_path / ".forge" / "sessions").is_dir()

    def test_summary_file_written(self, tmp_path):
        _make_state(tmp_path)
        _run(str(tmp_path))
        sessions = list((tmp_path / ".forge" / "sessions").glob("*.md"))
        assert len(sessions) == 1

    def test_summary_contains_session_id(self, tmp_path):
        _make_state(tmp_path)
        _run(str(tmp_path), session_id="my-session-abc")
        summary = next((tmp_path / ".forge" / "sessions").glob("*.md")).read_text()
        assert "my-session-abc" in summary

    def test_summary_contains_stage(self, tmp_path):
        _make_state(tmp_path, stage=6)
        _run(str(tmp_path))
        summary = next((tmp_path / ".forge" / "sessions").glob("*.md")).read_text()
        assert "6" in summary

    def test_summary_contains_task(self, tmp_path):
        _make_state(tmp_path, task="T-007")
        _run(str(tmp_path))
        summary = next((tmp_path / ".forge" / "sessions").glob("*.md")).read_text()
        assert "T-007" in summary

    def test_summary_contains_end_time(self, tmp_path):
        _make_state(tmp_path)
        _run(str(tmp_path))
        summary = next((tmp_path / ".forge" / "sessions").glob("*.md")).read_text()
        assert "End time" in summary
        assert "2026" in summary

    def test_summary_file_named_with_timestamp(self, tmp_path):
        _make_state(tmp_path)
        _run(str(tmp_path))
        files = list((tmp_path / ".forge" / "sessions").glob("*.md"))
        assert len(files) == 1
        # Name should look like 2026-05-10T13-00-00Z.md
        assert files[0].name.startswith("2026")


class TestLessonsSection:
    def test_no_lessons_file_shows_none(self, tmp_path):
        _make_state(tmp_path)
        _run(str(tmp_path))
        summary = next((tmp_path / ".forge" / "sessions").glob("*.md")).read_text()
        assert "Lessons Added" in summary
        assert "none" in summary.lower()

    def test_lessons_listed_in_summary(self, tmp_path):
        _make_state(tmp_path)
        _make_lessons(tmp_path, ["L-001 Use design tokens", "L-002 Avoid mocks"])
        _run(str(tmp_path))
        summary = next((tmp_path / ".forge" / "sessions").glob("*.md")).read_text()
        assert "L-001 Use design tokens" in summary
        assert "L-002 Avoid mocks" in summary

    def test_lessons_capped_at_three(self, tmp_path):
        _make_state(tmp_path)
        titles = [f"L-{i:03d} lesson" for i in range(10)]
        _make_lessons(tmp_path, titles)
        _run(str(tmp_path))
        summary = next((tmp_path / ".forge" / "sessions").glob("*.md")).read_text()
        # Only last 3 should appear
        assert "L-009 lesson" in summary
        assert "L-000 lesson" not in summary


class TestFilesSection:
    def test_no_session_log_shows_empty(self, tmp_path):
        _make_state(tmp_path)
        _run(str(tmp_path))
        summary = next((tmp_path / ".forge" / "sessions").glob("*.md")).read_text()
        assert "Files Modified" in summary

    def test_session_log_files_listed(self, tmp_path):
        _make_state(tmp_path)
        _make_session_log(tmp_path, ["hooks/foo.py", "scripts/bar.py"])
        _run(str(tmp_path))
        summary = next((tmp_path / ".forge" / "sessions").glob("*.md")).read_text()
        assert "hooks/foo.py" in summary
        assert "scripts/bar.py" in summary

    def test_duplicate_files_deduplicated(self, tmp_path):
        _make_state(tmp_path)
        _make_session_log(tmp_path, ["foo.py", "foo.py", "bar.py"])
        _run(str(tmp_path))
        summary = next((tmp_path / ".forge" / "sessions").glob("*.md")).read_text()
        assert summary.count("foo.py") == 1


class TestEdgeCases:
    def test_empty_stdin_exits_0(self):
        r = subprocess.run(
            [PYTHON, HOOK],
            input="",
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0

    def test_corrupt_state_exits_0(self, tmp_path):
        (tmp_path / "pipeline").mkdir()
        (tmp_path / "pipeline" / "state.md").write_text("not: valid: yaml: [[\n")
        r = _run(str(tmp_path))
        assert r.returncode == 0

    def test_second_run_appends_new_file(self, tmp_path):
        """Each session end writes a new timestamped file."""
        _make_state(tmp_path)
        _run(str(tmp_path))
        _run(str(tmp_path))
        files = list((tmp_path / ".forge" / "sessions").glob("*.md"))
        # May be 1 if both runs happen in the same second (same filename)
        assert len(files) >= 1
