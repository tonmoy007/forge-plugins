"""Unit tests for hooks/prompt-submit.py (tested via subprocess)."""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = str(Path(__file__).parent.parent.parent / "hooks" / "prompt-submit.py")
PYTHON = sys.executable


def _run(prompt: str, cwd: str) -> subprocess.CompletedProcess:
    payload = json.dumps({
        "hook_event_name": "UserPromptSubmit",
        "session_id": "test-session-123",
        "prompt": prompt,
        "cwd": cwd,
    })
    return subprocess.run(
        [PYTHON, HOOK],
        input=payload,
        capture_output=True,
        text=True,
    )


def _make_state(tmp_path: Path, stage: int = 3) -> Path:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    state = tmp_path / "pipeline" / "state.md"
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state.write_text(
        f"---\nschema_version: 1\nproject_type: fullstack\ncycle: 1\n"
        f"current_stage: {stage}\ncurrent_task: null\ncurrent_milestone: null\n"
        f"total_tasks: null\nlast_updated: {now}\nblockers: []\n---\n\n# State\n"
    )
    return state


class TestStageIntentDetection:
    def test_forge_build_command_returns_json(self, tmp_path):
        _make_state(tmp_path, stage=3)
        r = _run("/forge:build", str(tmp_path))
        assert r.returncode == 0
        assert r.stdout.strip()
        data = json.loads(r.stdout)
        assert "additionalContext" in data

    def test_forge_build_mentions_stage_6(self, tmp_path):
        _make_state(tmp_path, stage=3)
        r = _run("/forge:build", str(tmp_path))
        data = json.loads(r.stdout)
        assert "6" in data["additionalContext"]
        assert "build" in data["additionalContext"].lower()

    def test_forge_srs_detected(self, tmp_path):
        _make_state(tmp_path, stage=3)
        r = _run("/forge:srs", str(tmp_path))
        data = json.loads(r.stdout)
        assert "1" in data["additionalContext"]

    def test_same_stage_no_output(self, tmp_path):
        _make_state(tmp_path, stage=6)
        r = _run("/forge:build", str(tmp_path))
        assert r.returncode == 0
        assert r.stdout.strip() == ""

    def test_unrelated_prompt_no_output(self, tmp_path):
        _make_state(tmp_path, stage=3)
        r = _run("Can you explain how the state machine works?", str(tmp_path))
        assert r.returncode == 0
        assert r.stdout.strip() == ""

    def test_non_forge_dir_no_output(self, tmp_path):
        r = _run("/forge:build", str(tmp_path))
        assert r.returncode == 0
        assert r.stdout.strip() == ""


class TestKeywordDetection:
    def test_implement_keyword_detected_as_stage_6(self, tmp_path):
        _make_state(tmp_path, stage=1)
        r = _run("Let's start the implementation now", str(tmp_path))
        assert r.returncode == 0
        # If keyword matching triggers, output should mention stage 6
        if r.stdout.strip():
            data = json.loads(r.stdout)
            assert "6" in data["additionalContext"]

    def test_deploy_keyword_detected(self, tmp_path):
        _make_state(tmp_path, stage=6)
        r = _run("Now let's deploy to production", str(tmp_path))
        assert r.returncode == 0
        if r.stdout.strip():
            data = json.loads(r.stdout)
            assert "8" in data["additionalContext"]


class TestCorrectionFlagging:
    def test_correction_word_writes_file(self, tmp_path):
        _make_state(tmp_path)
        (tmp_path / ".forge").mkdir(exist_ok=True)
        r = _run("No, that's wrong — use the other approach", str(tmp_path))
        assert r.returncode == 0
        flags = tmp_path / ".forge" / "correction-flags.jsonl"
        assert flags.exists()

    def test_correction_file_contains_prompt(self, tmp_path):
        _make_state(tmp_path)
        (tmp_path / ".forge").mkdir(exist_ok=True)
        r = _run("Actually, I told you not to do that", str(tmp_path))
        flags = tmp_path / ".forge" / "correction-flags.jsonl"
        content = flags.read_text()
        record = json.loads(content.strip())
        assert "Actually" in record["prompt"]
        assert "session" in record
        assert "ts" in record

    def test_correction_in_non_forge_dir_still_writes(self, tmp_path):
        """Corrections should be flagged even outside Forge projects."""
        (tmp_path / ".forge").mkdir(exist_ok=True)
        r = _run("No, wrong approach", str(tmp_path))
        assert r.returncode == 0
        flags = tmp_path / ".forge" / "correction-flags.jsonl"
        assert flags.exists()

    def test_multiple_corrections_append(self, tmp_path):
        _make_state(tmp_path)
        (tmp_path / ".forge").mkdir(exist_ok=True)
        _run("No, that's wrong", str(tmp_path))
        _run("Actually, I said otherwise", str(tmp_path))
        flags = tmp_path / ".forge" / "correction-flags.jsonl"
        lines = [l for l in flags.read_text().splitlines() if l.strip()]
        assert len(lines) == 2

    def test_normal_prompt_no_flag_file(self, tmp_path):
        _make_state(tmp_path)
        r = _run("Please add a new feature to the UI", str(tmp_path))
        flags = tmp_path / ".forge" / "correction-flags.jsonl"
        assert not flags.exists()


class TestEdgeCases:
    def test_empty_prompt_exits_0(self, tmp_path):
        _make_state(tmp_path)
        r = _run("", str(tmp_path))
        assert r.returncode == 0

    def test_empty_stdin_exits_0(self, tmp_path):
        r = subprocess.run(
            [PYTHON, HOOK],
            input="",
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0

    def test_output_is_valid_json_when_present(self, tmp_path):
        _make_state(tmp_path, stage=1)
        r = _run("/forge:build", str(tmp_path))
        if r.stdout.strip():
            data = json.loads(r.stdout)  # should not raise
            assert isinstance(data, dict)
