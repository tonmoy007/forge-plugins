"""Unit tests for scripts/state-manager.py (CLI tested via subprocess)."""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = str(Path(__file__).parent.parent.parent / "scripts" / "state-manager.py")
PYTHON = sys.executable


def _make_state(tmp_path: Path) -> Path:
    """Write a minimal valid pipeline/state.md and return its path."""
    (tmp_path / "pipeline").mkdir()
    state = tmp_path / "pipeline" / "state.md"
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state.write_text(
        f"---\n"
        f"schema_version: 1\n"
        f"project_type: unknown\n"
        f"cycle: 1\n"
        f"current_stage: 0\n"
        f"current_task: null\n"
        f"current_milestone: null\n"
        f"total_tasks: null\n"
        f"last_updated: {now}\n"
        f"blockers: []\n"
        f"---\n"
        f"\n"
        f"# Pipeline State\n"
        f"\n"
        f"## Stage History\n"
        f"| Stage | Started | Completed | Gate | Notes |\n"
        f"|-------|---------|-----------|------|-------|\n"
        f"\n"
        f"## Last Reflection\n"
        f"*(No reflections yet)*\n"
    )
    return state


def run(args: list[str], cwd: str = ".") -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, SCRIPT] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


class TestReadCommand:
    def test_outputs_valid_json(self, tmp_path):
        _make_state(tmp_path)
        r = run(["--cwd", str(tmp_path), "read"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["current_stage"] == 0
        assert data["project_type"] == "unknown"

    def test_field_flag_returns_single_value(self, tmp_path):
        _make_state(tmp_path)
        r = run(["--cwd", str(tmp_path), "read", "--field", "current_stage"])
        assert r.returncode == 0
        assert r.stdout.strip() == "0"

    def test_unknown_field_exits_1(self, tmp_path):
        _make_state(tmp_path)
        r = run(["--cwd", str(tmp_path), "read", "--field", "nonexistent"])
        assert r.returncode == 1

    def test_missing_pipeline_exits_1(self, tmp_path):
        r = run(["--cwd", str(tmp_path), "read"])
        assert r.returncode == 1
        assert "error" in r.stderr.lower()


class TestAdvanceCommand:
    def test_increments_stage_and_returns_json(self, tmp_path):
        _make_state(tmp_path)
        r = run(["--cwd", str(tmp_path), "advance"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["current_stage"] == 1

    def test_to_flag_jumps_to_stage(self, tmp_path):
        _make_state(tmp_path)
        r = run(["--cwd", str(tmp_path), "advance", "--to", "6"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["current_stage"] == 6

    def test_advance_persists_to_disk(self, tmp_path):
        _make_state(tmp_path)
        run(["--cwd", str(tmp_path), "advance"])
        r = run(["--cwd", str(tmp_path), "read", "--field", "current_stage"])
        assert r.stdout.strip() == "1"


class TestSetCommand:
    def test_sets_string_field(self, tmp_path):
        _make_state(tmp_path)
        r = run(["--cwd", str(tmp_path), "set", "--field", "current_task", "--value", "T-007"])
        assert r.returncode == 0
        r2 = run(["--cwd", str(tmp_path), "read", "--field", "current_task"])
        assert r2.stdout.strip() == "T-007"

    def test_sets_int_field(self, tmp_path):
        _make_state(tmp_path)
        r = run(["--cwd", str(tmp_path), "set", "--field", "cycle", "--value", "2"])
        assert r.returncode == 0
        r2 = run(["--cwd", str(tmp_path), "read"])
        data = json.loads(r2.stdout)
        assert data["cycle"] == 2

    def test_unknown_field_exits_1(self, tmp_path):
        _make_state(tmp_path)
        r = run(["--cwd", str(tmp_path), "set", "--field", "bogus", "--value", "x"])
        assert r.returncode == 1


class TestReflectCommand:
    def test_appends_text_to_state_md(self, tmp_path):
        _make_state(tmp_path)
        r = run(["--cwd", str(tmp_path), "reflect", "integration test reflection"])
        assert r.returncode == 0
        text = (tmp_path / "pipeline" / "state.md").read_text()
        assert "integration test reflection" in text

    def test_text_appears_in_last_reflection_section(self, tmp_path):
        _make_state(tmp_path)
        run(["--cwd", str(tmp_path), "reflect", "marker-12345"])
        text = (tmp_path / "pipeline" / "state.md").read_text()
        reflection_idx = text.index("## Last Reflection")
        assert "marker-12345" in text[reflection_idx:]


class TestHistoryAddCommand:
    def test_adds_row_with_stage_result_note(self, tmp_path):
        _make_state(tmp_path)
        r = run([
            "--cwd", str(tmp_path),
            "history-add", "--stage", "1", "--result", "passed", "--note", "smoke test",
        ])
        assert r.returncode == 0
        text = (tmp_path / "pipeline" / "state.md").read_text()
        assert "passed" in text
        assert "smoke test" in text

    def test_row_appears_in_stage_history_section(self, tmp_path):
        _make_state(tmp_path)
        run([
            "--cwd", str(tmp_path),
            "history-add", "--stage", "2", "--result", "failed", "--note", "",
        ])
        text = (tmp_path / "pipeline" / "state.md").read_text()
        history_idx = text.index("## Stage History")
        assert "failed" in text[history_idx:]

    def test_multiple_rows_accumulate(self, tmp_path):
        _make_state(tmp_path)
        run(["--cwd", str(tmp_path), "history-add", "--stage", "1", "--result", "passed", "--note", "a"])
        run(["--cwd", str(tmp_path), "history-add", "--stage", "2", "--result", "passed", "--note", "b"])
        text = (tmp_path / "pipeline" / "state.md").read_text()
        assert text.count("passed") >= 2
