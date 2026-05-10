"""Unit tests for scripts/_state_lib.py"""
from __future__ import annotations

import datetime
import importlib.util
import sys
from pathlib import Path

import pytest

# _state_lib is a valid Python name — use importlib for consistent path handling
def _load_lib():
    spec = importlib.util.spec_from_file_location(
        "_state_lib",
        Path(__file__).parent.parent.parent / "scripts" / "_state_lib.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

lib = _load_lib()


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


class TestValidateFrontmatter:
    def test_valid_full_state_passes(self):
        data = {
            "schema_version": 1,
            "project_type": "unknown",
            "cycle": 1,
            "current_stage": 0,
            "current_task": None,
            "current_milestone": None,
            "total_tasks": None,
            "last_updated": "2026-05-10T00:00:00Z",
            "blockers": [],
        }
        ok, errors = lib.validate_frontmatter(data)
        assert ok
        assert errors == []

    def test_missing_field_returns_error(self):
        ok, errors = lib.validate_frontmatter({"schema_version": 1})
        assert not ok
        assert any("project_type" in e for e in errors)

    def test_wrong_type_returns_error(self):
        data = {
            "schema_version": "one",  # must be int
            "project_type": "unknown",
            "cycle": 1,
            "current_stage": 0,
            "current_task": None,
            "current_milestone": None,
            "total_tasks": None,
            "last_updated": "2026-05-10T00:00:00Z",
            "blockers": [],
        }
        ok, errors = lib.validate_frontmatter(data)
        assert not ok
        assert any("schema_version" in e for e in errors)

    def test_nullable_fields_accept_none(self):
        data = {
            "schema_version": 1,
            "project_type": "ml-pipeline",
            "cycle": 1,
            "current_stage": 3,
            "current_task": None,
            "current_milestone": None,
            "total_tasks": None,
            "last_updated": "2026-05-10T00:00:00Z",
            "blockers": [],
        }
        ok, errors = lib.validate_frontmatter(data)
        assert ok, errors

    def test_nullable_fields_accept_values(self):
        data = {
            "schema_version": 1,
            "project_type": "ml-pipeline",
            "cycle": 1,
            "current_stage": 3,
            "current_task": "T-007",
            "current_milestone": "M2",
            "total_tasks": 23,
            "last_updated": "2026-05-10T00:00:00Z",
            "blockers": ["missing SRS"],
        }
        ok, errors = lib.validate_frontmatter(data)
        assert ok, errors


class TestReadState:
    def test_returns_dict_with_all_fields(self, tmp_path):
        _make_state(tmp_path)
        state = lib.read_state(str(tmp_path))
        assert state["schema_version"] == 1
        assert state["current_stage"] == 0
        assert state["project_type"] == "unknown"
        assert state["blockers"] == []

    def test_missing_pipeline_exits_1(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            lib.read_state(str(tmp_path))
        assert exc.value.code == 1


class TestWriteState:
    def test_updates_project_type(self, tmp_path):
        _make_state(tmp_path)
        state = lib.read_state(str(tmp_path))
        state["project_type"] = "ml-pipeline"
        lib.write_state(str(tmp_path), state)
        assert lib.read_state(str(tmp_path))["project_type"] == "ml-pipeline"

    def test_preserves_markdown_body(self, tmp_path):
        _make_state(tmp_path)
        state = lib.read_state(str(tmp_path))
        lib.write_state(str(tmp_path), state)
        text = (tmp_path / "pipeline" / "state.md").read_text()
        assert "## Stage History" in text
        assert "## Last Reflection" in text

    def test_rejects_invalid_frontmatter_exits_1(self, tmp_path):
        _make_state(tmp_path)
        with pytest.raises(SystemExit) as exc:
            lib.write_state(str(tmp_path), {"schema_version": "bad"})
        assert exc.value.code == 1

    def test_atomic_write_leaves_no_tmp_files(self, tmp_path):
        _make_state(tmp_path)
        state = lib.read_state(str(tmp_path))
        lib.write_state(str(tmp_path), state)
        assert list((tmp_path / "pipeline").glob("*.tmp")) == []


class TestAdvanceStage:
    def test_increments_by_one(self, tmp_path):
        _make_state(tmp_path)
        lib.advance_stage(str(tmp_path))
        assert lib.read_state(str(tmp_path))["current_stage"] == 1

    def test_increments_again(self, tmp_path):
        _make_state(tmp_path)
        lib.advance_stage(str(tmp_path))
        lib.advance_stage(str(tmp_path))
        assert lib.read_state(str(tmp_path))["current_stage"] == 2

    def test_jump_to_target(self, tmp_path):
        _make_state(tmp_path)
        lib.advance_stage(str(tmp_path), to=6)
        assert lib.read_state(str(tmp_path))["current_stage"] == 6

    def test_updates_last_updated(self, tmp_path):
        _make_state(tmp_path)
        lib.advance_stage(str(tmp_path))
        updated = lib.read_state(str(tmp_path))["last_updated"]
        assert isinstance(updated, str)
        assert "T" in updated  # ISO 8601 format

    def test_returns_new_state_dict(self, tmp_path):
        _make_state(tmp_path)
        result = lib.advance_stage(str(tmp_path))
        assert result["current_stage"] == 1

    def test_backward_advance_emits_warning(self, tmp_path, capsys):
        _make_state(tmp_path)
        lib.advance_stage(str(tmp_path), to=5)
        lib.advance_stage(str(tmp_path), to=2)  # backward
        captured = capsys.readouterr()
        assert "backward" in captured.err


class TestAppendToSection:
    def test_appends_to_last_reflection(self, tmp_path):
        _make_state(tmp_path)
        lib.append_to_section(str(tmp_path), "Last Reflection", "test reflection line")
        text = (tmp_path / "pipeline" / "state.md").read_text()
        assert "test reflection line" in text

    def test_appends_row_to_stage_history(self, tmp_path):
        _make_state(tmp_path)
        row = "| 1 | 2026-05-10 | | passed | ok |"
        lib.append_to_section(str(tmp_path), "Stage History", row)
        text = (tmp_path / "pipeline" / "state.md").read_text()
        assert row in text

    def test_creates_missing_section(self, tmp_path):
        _make_state(tmp_path)
        lib.append_to_section(str(tmp_path), "Custom Section", "custom content")
        text = (tmp_path / "pipeline" / "state.md").read_text()
        assert "## Custom Section" in text
        assert "custom content" in text

    def test_preserves_other_sections(self, tmp_path):
        _make_state(tmp_path)
        lib.append_to_section(str(tmp_path), "Stage History", "| 1 | 2026-05-10 | | passed | |")
        text = (tmp_path / "pipeline" / "state.md").read_text()
        assert "## Last Reflection" in text
        assert "*(No reflections yet)*" in text
