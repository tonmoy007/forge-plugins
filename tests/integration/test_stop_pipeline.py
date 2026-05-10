"""Integration test for hooks/stop-reflect.py against a real fixture project.

Sets up a minimal Forge project via init-pipeline.sh, injects a transcript,
runs the Stop hook, and asserts end-to-end outcomes.
"""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = str(Path(__file__).parent.parent.parent / "hooks" / "stop-reflect.py")
INIT_SCRIPT = str(Path(__file__).parent.parent.parent / "scripts" / "init-pipeline.sh")
PYTHON = sys.executable


def _run_hook(cwd: str, session_id: str = "integ-test",
              transcript_path: str = "", extra: dict | None = None) -> subprocess.CompletedProcess:
    payload = {
        "hook_event_name": "Stop",
        "session_id": session_id,
        "cwd": cwd,
        "transcript_path": transcript_path,
    }
    if extra:
        payload.update(extra)
    return subprocess.run(
        [PYTHON, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


def _scaffold_project(tmp_path: Path) -> Path:
    """Run init-pipeline.sh to create a full Forge project skeleton."""
    result = subprocess.run(
        ["bash", INIT_SCRIPT],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, f"init-pipeline.sh failed: {result.stderr}"
    return tmp_path


def _make_transcript(tmp_path: Path, messages: list[dict]) -> str:
    p = tmp_path / "transcript.jsonl"
    p.write_text("\n".join(json.dumps(m) for m in messages) + "\n")
    return str(p)


def _read_state_md(project: Path) -> str:
    return (project / "pipeline" / "state.md").read_text()


class TestEndToEnd:
    def test_hook_exits_0_on_fresh_project(self, tmp_path):
        project = _scaffold_project(tmp_path)
        r = _run_hook(str(project))
        assert r.returncode == 0

    def test_reflection_written_to_state_md(self, tmp_path):
        project = _scaffold_project(tmp_path)
        transcript = _make_transcript(tmp_path, [
            {"role": "user", "content": "Let's start the SRS"},
            {"role": "assistant", "content": "Sure, here's the SRS outline."},
            {"role": "user", "content": "Looks good, add more detail"},
        ])
        r = _run_hook(str(project), transcript_path=transcript)
        assert r.returncode == 0
        state_text = _read_state_md(project)
        assert "Timestamp" in state_text
        assert "Stage" in state_text

    def test_reflection_records_user_turn_count(self, tmp_path):
        project = _scaffold_project(tmp_path)
        transcript = _make_transcript(tmp_path, [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "Response"},
            {"role": "user", "content": "Second message"},
        ])
        _run_hook(str(project), transcript_path=transcript)
        state_text = _read_state_md(project)
        assert "2 user message" in state_text

    def test_gate_warning_printed_for_active_stage(self, tmp_path):
        """Gate check prints criteria summary for stage 1 (all fail in fresh project)."""
        project = _scaffold_project(tmp_path)
        # Advance state to stage 1 so gate criteria are evaluated
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (project / "pipeline" / "state.md").write_text(
            f"---\nschema_version: 1\nproject_type: fullstack\ncycle: 1\n"
            f"current_stage: 1\ncurrent_task: null\ncurrent_milestone: null\n"
            f"total_tasks: null\nlast_updated: {now}\nblockers: []\n---\n\n"
            "# Pipeline State\n\n## Stage History\n\n## Last Reflection\n"
        )
        transcript = _make_transcript(tmp_path, [
            {"role": "user", "content": "keep working"},
        ])
        r = _run_hook(str(project), transcript_path=transcript)
        assert r.returncode == 0
        # Gate summary should appear: "Stage 1: X/Y gate criteria met"
        assert "Stage 1" in r.stdout

    def test_done_signal_blocks_on_unmet_gate(self, tmp_path):
        """Done signal + stage 1 failing criteria → exit 2."""
        project = _scaffold_project(tmp_path)
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (project / "pipeline" / "state.md").write_text(
            f"---\nschema_version: 1\nproject_type: fullstack\ncycle: 1\n"
            f"current_stage: 1\ncurrent_task: null\ncurrent_milestone: null\n"
            f"total_tasks: null\nlast_updated: {now}\nblockers: []\n---\n\n"
            "# Pipeline State\n\n## Stage History\n\n## Last Reflection\n"
        )
        transcript = _make_transcript(tmp_path, [
            {"role": "user", "content": "ship it"},
        ])
        r = _run_hook(str(project), transcript_path=transcript)
        assert r.returncode == 2
        assert "Cannot advance" in r.stdout

    def test_corrections_flagged_no_crash_without_script(self, tmp_path):
        """Correction flags exist but extract-lessons.py is absent → exit 0."""
        project = _scaffold_project(tmp_path)
        forge_dir = project / ".forge"
        forge_dir.mkdir(exist_ok=True)
        record = json.dumps({
            "ts": "2026-05-10T00:00:00Z",
            "session": "integ-test",
            "prompt": "No, that was wrong",
        })
        (forge_dir / "correction-flags.jsonl").write_text(record + "\n")
        r = _run_hook(str(project))
        assert r.returncode == 0

    def test_loop_prevention_no_reflection(self, tmp_path):
        project = _scaffold_project(tmp_path)
        r = _run_hook(str(project), extra={"stop_hook_active": True})
        assert r.returncode == 0
        assert r.stdout.strip() == ""
        state_text = _read_state_md(project)
        assert "Timestamp" not in state_text

    def test_second_reflection_appended_not_replaced(self, tmp_path):
        """Running the hook twice appends two reflections, doesn't overwrite."""
        project = _scaffold_project(tmp_path)
        _run_hook(str(project))
        _run_hook(str(project))
        state_text = _read_state_md(project)
        # Two Timestamp lines should appear
        assert state_text.count("**Timestamp**") >= 2
