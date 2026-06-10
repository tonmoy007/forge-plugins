"""Unit tests for hooks/session-start.py (tested via subprocess)."""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = str(Path(__file__).parent.parent.parent / "hooks" / "session-start.py")
PLUGIN_DIR = str(Path(__file__).parent.parent.parent)
PYTHON = sys.executable


def _run(cwd: str, env: dict | None = None) -> subprocess.CompletedProcess:
    payload = json.dumps({"cwd": cwd, "hook_event_name": "SessionStart"})
    # Default to the kill switch so tests never spawn a real `claude` refresh
    # (T-138). A test that exercises the capability path passes its own env.
    run_env = env if env is not None else {**os.environ, "FORGE_NO_BACKGROUND": "1"}
    return subprocess.run(
        [PYTHON, HOOK],
        input=payload,
        capture_output=True,
        text=True,
        env=run_env,
    )


def _make_state(
    tmp_path: Path,
    *,
    stage: int = 0,
    project_type: str = "unknown",
    task: str | None = None,
    blockers: list | None = None,
) -> Path:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    state = tmp_path / "pipeline" / "state.md"
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state.write_text(
        f"---\n"
        f"schema_version: 1\n"
        f"project_type: {project_type}\n"
        f"cycle: 1\n"
        f"current_stage: {stage}\n"
        f"current_task: {task!r}\n"
        f"current_milestone: null\n"
        f"total_tasks: null\n"
        f"last_updated: {now}\n"
        f"blockers: {json.dumps(blockers or [])}\n"
        f"---\n\n# Pipeline State\n\n## Stage History\n\n## Last Reflection\n"
    )
    return state


def _make_lessons(tmp_path: Path, lessons: list[dict]) -> None:
    forge_dir = tmp_path / ".forge"
    forge_dir.mkdir(exist_ok=True)
    data = {"schema_version": 1, "lessons": lessons}
    import yaml
    (forge_dir / "lessons.yaml").write_text(yaml.dump(data))


class TestNonForgeDir:
    def test_no_pipeline_silent_exit_0(self, tmp_path):
        r = _run(str(tmp_path))
        assert r.returncode == 0
        assert r.stdout.strip() == ""

    def test_no_pipeline_no_stderr(self, tmp_path):
        r = _run(str(tmp_path))
        assert r.stderr.strip() == ""


class TestFreshState:
    def test_stage_0_outputs_forge_lines(self, tmp_path):
        _make_state(tmp_path, stage=0)
        r = _run(str(tmp_path))
        assert r.returncode == 0
        assert "[Forge]" in r.stdout

    def test_stage_0_shows_not_started(self, tmp_path):
        _make_state(tmp_path, stage=0)
        r = _run(str(tmp_path))
        assert "Stage 0" in r.stdout
        assert "not started" in r.stdout

    def test_stage_0_suggests_srs(self, tmp_path):
        _make_state(tmp_path, stage=0)
        r = _run(str(tmp_path))
        assert "srs" in r.stdout.lower()


class TestContextContent:
    def test_shows_project_type(self, tmp_path):
        _make_state(tmp_path, stage=3, project_type="ml-pipeline")
        r = _run(str(tmp_path))
        assert "ml-pipeline" in r.stdout

    def test_shows_current_task(self, tmp_path):
        _make_state(tmp_path, stage=6, task="T-007")
        r = _run(str(tmp_path))
        assert "T-007" in r.stdout

    def test_shows_blockers(self, tmp_path):
        _make_state(tmp_path, stage=6, blockers=["GPU out of memory"])
        r = _run(str(tmp_path))
        assert "GPU out of memory" in r.stdout

    def test_no_blockers_not_shown(self, tmp_path):
        _make_state(tmp_path, stage=3, blockers=[])
        r = _run(str(tmp_path))
        assert "Blockers" not in r.stdout

    def test_gate_criteria_line_present(self, tmp_path):
        _make_state(tmp_path, stage=1)
        r = _run(str(tmp_path))
        assert "gate criteria" in r.stdout.lower()


class TestLessonsFiltering:
    def test_no_lessons_shows_zero(self, tmp_path):
        _make_state(tmp_path, stage=6, project_type="fullstack")
        _make_lessons(tmp_path, [])
        r = _run(str(tmp_path), env={**os.environ, "HOME": str(tmp_path)})
        assert "Active lessons (0)" in r.stdout

    def test_matching_lesson_included(self, tmp_path):
        _make_state(tmp_path, stage=6, project_type="fullstack")
        _make_lessons(tmp_path, [{
            "id": "L-001",
            "stage": [6],
            "project_types": ["fullstack"],
            "trigger": "use design tokens not raw values",
            "rule": "always use --color- variables",
            "why": "audit fails",
            "frequency": 3,
            "last_used": "2026-05-01",
            "tags": ["design"],
        }])
        r = _run(str(tmp_path), env={**os.environ, "HOME": str(tmp_path)})
        assert "Active lessons (1)" in r.stdout
        assert "design token" in r.stdout.lower()

    def test_non_matching_stage_excluded(self, tmp_path):
        _make_state(tmp_path, stage=3, project_type="fullstack")
        _make_lessons(tmp_path, [{
            "id": "L-001",
            "stage": [6],  # only relevant at stage 6
            "project_types": [],
            "trigger": "stage-6-only lesson",
            "rule": "skip this",
            "why": "irrelevant",
            "frequency": 5,
            "last_used": "2026-05-01",
            "tags": [],
        }])
        r = _run(str(tmp_path))
        assert "stage-6-only" not in r.stdout

    def test_fifty_lessons_capped_at_five(self, tmp_path):
        _make_state(tmp_path, stage=6, project_type="fullstack")
        lessons = [
            {
                "id": f"L-{i:03d}",
                "stage": [],
                "project_types": [],
                "trigger": f"lesson trigger {i}",
                "rule": f"rule {i}",
                "why": "why",
                "frequency": i,
                "last_used": "2026-05-01",
                "tags": [],
            }
            for i in range(50)
        ]
        _make_lessons(tmp_path, lessons)
        r = _run(str(tmp_path), env={**os.environ, "HOME": str(tmp_path)})
        # Should show at most 5 project lessons
        import re
        m = re.search(r"Active lessons \((\d+)\)", r.stdout)
        assert m is not None
        assert int(m.group(1)) <= 5

    def test_ml_project_shows_gpu_lesson_not_docs_lesson(self, tmp_path):
        # done-when criterion for T-020: stage 6 ML project sees GPU lessons,
        # not documentation-only lessons
        _make_state(tmp_path, stage=6, project_type="ml-pipeline")
        _make_lessons(tmp_path, [
            {
                "id": "L-gpu",
                "stage": [6],
                "project_types": ["ml-pipeline"],
                "trigger": "GPU out-of-memory error during training",
                "rule": "always set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
                "why": "prevents fragmentation OOM",
                "frequency": 4,
                "last_used": "2026-05-10",
                "tags": ["gpu", "ml"],
            },
            {
                "id": "L-docs",
                "stage": [1],
                "project_types": ["documentation"],
                "trigger": "writing docs for a docs-only project",
                "rule": "use mkdocs not sphinx",
                "why": "team convention",
                "frequency": 2,
                "last_used": "2026-05-01",
                "tags": ["docs"],
            },
        ])
        r = _run(str(tmp_path))
        assert "GPU out-of-memory" in r.stdout
        assert "mkdocs" not in r.stdout

    def test_non_matching_project_type_excluded(self, tmp_path):
        _make_state(tmp_path, stage=6, project_type="fullstack")
        _make_lessons(tmp_path, [{
            "id": "L-001",
            "stage": [],
            "project_types": ["ml-pipeline"],  # only for ML projects
            "trigger": "ml-only lesson trigger",
            "rule": "use GPU",
            "why": "ML needs GPU",
            "frequency": 5,
            "last_used": "2026-05-01",
            "tags": ["ml"],
        }])
        r = _run(str(tmp_path))
        assert "ml-only lesson trigger" not in r.stdout

    def test_lessons_sorted_by_frequency_descending(self, tmp_path):
        _make_state(tmp_path, stage=6, project_type="fullstack")
        _make_lessons(tmp_path, [
            {
                "id": "L-low",
                "stage": [],
                "project_types": [],
                "trigger": "low-frequency trigger",
                "rule": "rare rule",
                "why": "why",
                "frequency": 1,
                "last_used": "2026-05-01",
                "tags": [],
            },
            {
                "id": "L-high",
                "stage": [],
                "project_types": [],
                "trigger": "high-frequency trigger",
                "rule": "common rule",
                "why": "why",
                "frequency": 10,
                "last_used": "2026-05-01",
                "tags": [],
            },
        ])
        r = _run(str(tmp_path))
        high_pos = r.stdout.find("high-frequency")
        low_pos = r.stdout.find("low-frequency")
        assert high_pos != -1 and low_pos != -1
        assert high_pos < low_pos


class TestTokenBudget:
    def test_output_under_2000_tokens(self, tmp_path):
        _make_state(tmp_path, stage=6, project_type="fullstack")
        lessons = [
            {
                "id": f"L-{i:03d}",
                "stage": [],
                "project_types": [],
                "trigger": "x" * 200,  # long triggers
                "rule": "r" * 200,
                "why": "w",
                "frequency": i,
                "last_used": "2026-05-01",
                "tags": [],
            }
            for i in range(10)
        ]
        _make_lessons(tmp_path, lessons)
        r = _run(str(tmp_path))
        assert r.returncode == 0
        # rough token estimate: len / 4 < 2000 → len < 8000
        assert len(r.stdout) < 8000


class TestCorruptedState:
    def test_corrupted_state_exits_0(self, tmp_path):
        (tmp_path / "pipeline").mkdir()
        (tmp_path / "pipeline" / "state.md").write_text("not: valid: yaml: [[\n")
        r = _run(str(tmp_path))
        assert r.returncode == 0

    def test_corrupted_state_no_crash(self, tmp_path):
        (tmp_path / "pipeline").mkdir()
        (tmp_path / "pipeline" / "state.md").write_text("")
        r = _run(str(tmp_path))
        assert r.returncode == 0


class TestBackgroundCapability:
    """T-138 — REQ-F-001: session-start maintains .forge/capabilities.json and
    surfaces unread Observer findings, without blocking (NF-004)."""

    def test_capabilities_written_when_cli_absent(self, tmp_path):
        # No `claude` on PATH + kill switch OFF → synchronous available:false write.
        _make_state(tmp_path, stage=1, project_type="api")
        env = {**os.environ, "PATH": "/nonexistent", "FORGE_NO_BACKGROUND": "0"}
        r = _run(str(tmp_path), env=env)
        assert r.returncode == 0
        cap = json.loads((tmp_path / ".forge" / "capabilities.json").read_text())
        assert cap["forge_background_available"] is False

    def test_kill_switch_skips_capability_work(self, tmp_path):
        # Default _run sets FORGE_NO_BACKGROUND=1 → no capabilities.json, no crash.
        _make_state(tmp_path, stage=1, project_type="api")
        r = _run(str(tmp_path))
        assert r.returncode == 0
        assert not (tmp_path / ".forge" / "capabilities.json").exists()

    def test_unread_findings_surfaced(self, tmp_path):
        _make_state(tmp_path, stage=2, project_type="api")
        forge = tmp_path / ".forge"
        forge.mkdir(exist_ok=True)
        (forge / "observer-findings.jsonl").write_text('{"a":1}\n{"b":2}\n')
        r = _run(str(tmp_path))
        assert "2 unread Observer finding(s)" in r.stdout

    def test_no_findings_no_note(self, tmp_path):
        _make_state(tmp_path, stage=2, project_type="api")
        r = _run(str(tmp_path))
        assert "unread Observer" not in r.stdout
