"""Tests for scripts/force-advance.py.

Run with: python -m pytest tests/unit/test_force_advance.py -q
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import yaml

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _state_lib


def _import_force_advance():
    """Import force-advance.py despite the hyphen."""
    path = SCRIPTS / "force-advance.py"
    spec = importlib.util.spec_from_file_location("force_advance", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["force_advance"] = mod
    spec.loader.exec_module(mod)
    return mod


fa = _import_force_advance()


def _init_project(root: Path, current_stage: int = 1) -> None:
    """Minimal project layout: pipeline/state.md + tasks/lessons.md + .forge/."""
    (root / "pipeline").mkdir()
    (root / "tasks").mkdir()
    (root / ".forge").mkdir()
    state_md = root / "pipeline" / "state.md"
    state_md.write_text(
        "---\n"
        "schema_version: 1\n"
        "project_type: api\n"
        "cycle: 1\n"
        f"current_stage: {current_stage}\n"
        "current_task: null\n"
        "current_milestone: null\n"
        "total_tasks: null\n"
        "last_updated: '2026-05-15T00:00:00Z'\n"
        "blockers: []\n"
        "---\n"
        "# Pipeline State\n\n"
        "## Stage History\n\n"
        "| Stage | Started | Completed | Gate | Notes |\n"
        "|-------|---------|-----------|------|-------|\n\n"
        "## Last Reflection\n\n"
        "*(none yet)*\n"
    )
    (root / "tasks" / "lessons.md").write_text(
        "# Lessons Learned\n\n"
        "> Append-only log.\n\n"
        "## Lessons\n\n"
        "*(None yet)*\n"
    )


# ---------- reason validation ----------

class TestReasonValidation:
    def test_empty_reason_rejected(self, tmp_path):
        _init_project(tmp_path)
        rc = fa.main(["--reason", "", "--cwd", str(tmp_path)])
        assert rc == 1

    def test_short_reason_rejected(self, tmp_path):
        _init_project(tmp_path)
        rc = fa.main(["--reason", "too short", "--cwd", str(tmp_path)])
        assert rc == 1

    def test_whitespace_only_reason_rejected(self, tmp_path):
        _init_project(tmp_path)
        rc = fa.main(["--reason", "          ", "--cwd", str(tmp_path)])
        assert rc == 1

    def test_minimum_length_accepted(self, tmp_path):
        # Exactly 10 chars
        _init_project(tmp_path)
        rc = fa.main(["--reason", "ten chars!", "--cwd", str(tmp_path),
                      "--allow-no-blockers"])
        assert rc == 0


# ---------- no-blocker behavior ----------

class TestNoBlockerBehavior:
    def test_exits_2_when_no_blockers(self, tmp_path, monkeypatch):
        _init_project(tmp_path)

        def fake_get_blockers(cwd, plugin_dir, stage):
            return []

        monkeypatch.setattr(fa, "_get_blockers", fake_get_blockers)
        rc = fa.main(["--reason", "ten chars!", "--cwd", str(tmp_path)])
        assert rc == 2

    def test_allow_no_blockers_proceeds(self, tmp_path, monkeypatch):
        _init_project(tmp_path)
        monkeypatch.setattr(fa, "_get_blockers", lambda *a, **k: [])
        rc = fa.main(["--reason", "explicit override for tests",
                      "--cwd", str(tmp_path), "--allow-no-blockers"])
        assert rc == 0


# ---------- lesson writing ----------

class TestLessonRecording:
    def test_lesson_appended_to_yaml(self, tmp_path, monkeypatch):
        _init_project(tmp_path)
        blockers = [{"id": "G1-001", "description": "x", "severity": "blocker", "passed": False}]
        monkeypatch.setattr(fa, "_get_blockers", lambda *a, **k: blockers)
        fa.main(["--reason", "tests need this", "--cwd", str(tmp_path)])

        yml = yaml.safe_load((tmp_path / ".forge" / "lessons.yaml").read_text())
        assert yml["schema_version"] == 1
        assert len(yml["lessons"]) == 1
        lesson = yml["lessons"][0]
        assert lesson["rule"] == "tests need this"
        assert lesson["reason"] == "tests need this"
        assert lesson["stage"] == [1]
        assert "force-advance" in lesson["tags"]
        assert lesson["blockers"] == ["G1-001"]
        assert lesson["source"] == "force-advance"

    def test_lesson_summary_appended_to_md(self, tmp_path, monkeypatch):
        _init_project(tmp_path)
        blockers = [{"id": "G1-001", "description": "x", "severity": "blocker", "passed": False}]
        monkeypatch.setattr(fa, "_get_blockers", lambda *a, **k: blockers)
        fa.main(["--reason", "tests need this", "--cwd", str(tmp_path)])

        md = (tmp_path / "tasks" / "lessons.md").read_text()
        assert "force-advance @ Stage 1" in md
        assert "tests need this" in md
        assert "G1-001" in md
        assert "*(None yet)*" not in md  # placeholder was replaced

    def test_md_appends_when_existing_lessons_present(self, tmp_path, monkeypatch):
        _init_project(tmp_path)
        # Pre-populate lessons.md without the placeholder
        (tmp_path / "tasks" / "lessons.md").write_text(
            "# Lessons Learned\n\n## Lessons\n\n### existing lesson\n\nfoo\n"
        )
        monkeypatch.setattr(fa, "_get_blockers", lambda *a, **k: [])
        fa.main(["--reason", "ten chars!", "--cwd", str(tmp_path),
                 "--allow-no-blockers"])
        md = (tmp_path / "tasks" / "lessons.md").read_text()
        assert "existing lesson" in md  # preserved
        assert "force-advance @ Stage 1" in md  # appended

    def test_md_missing_does_not_crash(self, tmp_path, monkeypatch):
        # pipeline + .forge present but tasks/lessons.md absent
        (tmp_path / "pipeline").mkdir()
        (tmp_path / ".forge").mkdir()
        state_md = tmp_path / "pipeline" / "state.md"
        state_md.write_text(
            "---\n"
            "schema_version: 1\nproject_type: api\ncycle: 1\n"
            "current_stage: 1\ncurrent_task: null\ncurrent_milestone: null\n"
            "total_tasks: null\nlast_updated: '2026-05-15T00:00:00Z'\nblockers: []\n"
            "---\n# State\n\n## Stage History\n\n## Last Reflection\n"
        )
        monkeypatch.setattr(fa, "_get_blockers", lambda *a, **k: [])
        rc = fa.main(["--reason", "ten chars!", "--cwd", str(tmp_path),
                      "--allow-no-blockers"])
        assert rc == 0
        # YAML still got written even though .md was missing
        assert (tmp_path / ".forge" / "lessons.yaml").exists()


# ---------- stage advancement ----------

class TestStageAdvancement:
    def test_increments_by_one(self, tmp_path, monkeypatch):
        _init_project(tmp_path, current_stage=3)
        monkeypatch.setattr(fa, "_get_blockers", lambda *a, **k: [])
        fa.main(["--reason", "ten chars!", "--cwd", str(tmp_path),
                 "--allow-no-blockers"])
        post = _state_lib.read_state(str(tmp_path))
        assert post["current_stage"] == 4

    def test_jumps_to_explicit_stage(self, tmp_path, monkeypatch):
        _init_project(tmp_path, current_stage=2)
        monkeypatch.setattr(fa, "_get_blockers", lambda *a, **k: [])
        fa.main(["--reason", "ten chars!", "--cwd", str(tmp_path),
                 "--allow-no-blockers", "--to", "7"])
        post = _state_lib.read_state(str(tmp_path))
        assert post["current_stage"] == 7


# ---------- history annotation ----------

class TestHistoryRow:
    def test_force_marker_added(self, tmp_path, monkeypatch):
        _init_project(tmp_path, current_stage=1)
        blockers = [{"id": "G1-001", "description": "x",
                     "severity": "blocker", "passed": False},
                    {"id": "G1-002", "description": "y",
                     "severity": "blocker", "passed": False}]
        monkeypatch.setattr(fa, "_get_blockers", lambda *a, **k: blockers)
        fa.main(["--reason", "explicit override", "--cwd", str(tmp_path)])

        _, body = _state_lib._split_frontmatter(
            (tmp_path / "pipeline" / "state.md").read_text()
        )
        assert "FORCE" in body
        assert "G1-001,G1-002" in body
        assert "force-advanced" in body

    def test_long_reason_truncated_in_history(self, tmp_path, monkeypatch):
        _init_project(tmp_path)
        monkeypatch.setattr(fa, "_get_blockers", lambda *a, **k: [])
        long_reason = "x" * 200
        fa.main(["--reason", long_reason, "--cwd", str(tmp_path),
                 "--allow-no-blockers"])
        _, body = _state_lib._split_frontmatter(
            (tmp_path / "pipeline" / "state.md").read_text()
        )
        # Truncated reason includes ellipsis
        assert "…" in body
        # Full reason is NOT in the history row (only first ~60 chars + ellipsis)
        assert long_reason not in body


# ---------- JSON output ----------

class TestJsonOutput:
    def test_json_well_formed(self, tmp_path, capsys, monkeypatch):
        _init_project(tmp_path)
        monkeypatch.setattr(fa, "_get_blockers", lambda *a, **k: [
            {"id": "G1-001", "description": "x", "severity": "blocker", "passed": False}
        ])
        rc = fa.main(["--reason", "json test ok", "--cwd", str(tmp_path), "--json"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["advanced_from"] == 1
        assert data["advanced_to"] == 2
        assert data["blockers_overridden"] == ["G1-001"]
        assert data["lesson_recorded"] is True
        assert data["lesson_tag"] == "force-advance"


# ---------- helpers ----------

class TestLessonBuilder:
    def test_includes_blocker_ids(self):
        lesson = fa._build_lesson(
            5, "explicit override",
            [{"id": "G5-001"}, {"id": "G5-002"}],
        )
        assert lesson["blockers"] == ["G5-001", "G5-002"]
        assert lesson["stage"] == [5]
        assert "force-advance" in lesson["tags"]

    def test_handles_empty_blockers(self):
        lesson = fa._build_lesson(1, "no blockers run", [])
        assert lesson["blockers"] == []
        assert lesson["stage"] == [1]