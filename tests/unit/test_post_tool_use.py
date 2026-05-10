"""Unit tests for hooks/post-tool-use.py (tested via subprocess)."""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = str(Path(__file__).parent.parent.parent / "hooks" / "post-tool-use.py")
PYTHON = sys.executable


def _run(
    tool_name: str = "Write",
    file_path: str = "src/app.py",
    cwd: str | None = None,
    session_id: str = "test-session",
    success: bool = True,
    extra_input: dict | None = None,
) -> subprocess.CompletedProcess:
    tool_input = {"file_path": file_path}
    if extra_input:
        tool_input.update(extra_input)
    payload = json.dumps({
        "hook_event_name": "PostToolUse",
        "session_id": session_id,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_response": {"success": success},
        "cwd": cwd or "",
    })
    return subprocess.run(
        [PYTHON, HOOK],
        input=payload,
        capture_output=True,
        text=True,
    )


def _make_state(tmp_path: Path, stage: int = 3) -> None:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "pipeline" / "state.md").write_text(
        f"---\nschema_version: 1\nproject_type: fullstack\ncycle: 1\n"
        f"current_stage: {stage}\ncurrent_task: null\ncurrent_milestone: null\n"
        f"total_tasks: null\nlast_updated: {now}\nblockers: []\n---\n\n# State\n"
    )


def _read_log(tmp_path: Path) -> list[dict]:
    log_path = tmp_path / ".forge" / "session-log.jsonl"
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text().splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def _seed_log(tmp_path: Path, entries: list[dict]) -> None:
    forge_dir = tmp_path / ".forge"
    forge_dir.mkdir(exist_ok=True)
    log_path = forge_dir / "session-log.jsonl"
    with log_path.open("a") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


class TestAlwaysExits0:
    def test_empty_stdin_exits_0(self):
        r = subprocess.run([PYTHON, HOOK], input="", capture_output=True, text=True)
        assert r.returncode == 0

    def test_normal_call_exits_0(self, tmp_path):
        r = _run(cwd=str(tmp_path))
        assert r.returncode == 0

    def test_no_output_to_stdout(self, tmp_path):
        r = _run(cwd=str(tmp_path))
        assert r.stdout.strip() == ""

    def test_invalid_json_exits_0(self):
        r = subprocess.run(
            [PYTHON, HOOK], input="not json", capture_output=True, text=True
        )
        assert r.returncode == 0


class TestSessionLogging:
    def test_log_file_created(self, tmp_path):
        _run(cwd=str(tmp_path))
        assert (tmp_path / ".forge" / "session-log.jsonl").exists()

    def test_log_entry_has_required_fields(self, tmp_path):
        _run(tool_name="Write", file_path="src/foo.py",
             session_id="sess-abc", cwd=str(tmp_path))
        records = _read_log(tmp_path)
        assert len(records) == 1
        r = records[0]
        assert r["tool"] == "Write"
        assert r["file"] == "src/foo.py"
        assert r["session"] == "sess-abc"
        assert "ts" in r
        assert "success" in r

    def test_log_success_true(self, tmp_path):
        _run(success=True, cwd=str(tmp_path))
        records = _read_log(tmp_path)
        assert records[0]["success"] is True

    def test_log_success_false(self, tmp_path):
        _run(success=False, cwd=str(tmp_path))
        records = _read_log(tmp_path)
        assert records[0]["success"] is False

    def test_multiple_calls_append(self, tmp_path):
        _run(tool_name="Read", cwd=str(tmp_path))
        _run(tool_name="Write", cwd=str(tmp_path))
        _run(tool_name="Bash", cwd=str(tmp_path))
        records = _read_log(tmp_path)
        assert len(records) == 3

    def test_no_pipeline_still_logs(self, tmp_path):
        """Logs even outside Forge projects."""
        _run(cwd=str(tmp_path))
        assert (tmp_path / ".forge" / "session-log.jsonl").exists()


class TestStage6Tracking:
    def test_stage_6_write_flagged(self, tmp_path):
        _make_state(tmp_path, stage=6)
        _run(tool_name="Write", file_path="src/app.py", cwd=str(tmp_path))
        records = _read_log(tmp_path)
        assert records[0].get("build_stage") is True

    def test_stage_6_non_write_not_flagged(self, tmp_path):
        _make_state(tmp_path, stage=6)
        _run(tool_name="Read", file_path="src/app.py", cwd=str(tmp_path))
        records = _read_log(tmp_path)
        assert "build_stage" not in records[0]

    def test_stage_3_write_not_flagged(self, tmp_path):
        _make_state(tmp_path, stage=3)
        _run(tool_name="Write", file_path="src/app.py", cwd=str(tmp_path))
        records = _read_log(tmp_path)
        assert "build_stage" not in records[0]


class TestPatternTracking:
    def test_three_same_tools_creates_pattern(self, tmp_path):
        entries = [
            {"ts": "2026-05-10T00:00:00Z", "session": "s", "tool": "Read",
             "file": "", "success": True},
            {"ts": "2026-05-10T00:00:01Z", "session": "s", "tool": "Read",
             "file": "", "success": True},
        ]
        _seed_log(tmp_path, entries)
        _run(tool_name="Read", cwd=str(tmp_path))
        patterns_path = tmp_path / ".forge" / "patterns.jsonl"
        assert patterns_path.exists()
        pattern = json.loads(patterns_path.read_text().strip())
        assert pattern["kind"] == "tool_seq"
        assert "Read" in pattern["tools"]

    def test_alternating_pattern_detected(self, tmp_path):
        entries = [
            {"ts": "t", "session": "s", "tool": "Read", "file": "", "success": True},
            {"ts": "t", "session": "s", "tool": "Edit", "file": "", "success": True},
            {"ts": "t", "session": "s", "tool": "Read", "file": "", "success": True},
        ]
        _seed_log(tmp_path, entries)
        _run(tool_name="Edit", cwd=str(tmp_path))
        patterns_path = tmp_path / ".forge" / "patterns.jsonl"
        assert patterns_path.exists()

    def test_no_pattern_no_file(self, tmp_path):
        _run(tool_name="Write", cwd=str(tmp_path))
        _run(tool_name="Read", cwd=str(tmp_path))
        patterns_path = tmp_path / ".forge" / "patterns.jsonl"
        assert not patterns_path.exists()

    def test_pattern_includes_session_id(self, tmp_path):
        entries = [
            {"ts": "t", "session": "my-sess", "tool": "Bash",
             "file": "", "success": True},
            {"ts": "t", "session": "my-sess", "tool": "Bash",
             "file": "", "success": True},
        ]
        _seed_log(tmp_path, entries)
        _run(tool_name="Bash", session_id="my-sess", cwd=str(tmp_path))
        pattern = json.loads(
            (tmp_path / ".forge" / "patterns.jsonl").read_text().strip()
        )
        assert pattern["session"] == "my-sess"

    def test_pattern_has_timestamp(self, tmp_path):
        entries = [
            {"ts": "t", "session": "s", "tool": "Write", "file": "", "success": True},
            {"ts": "t", "session": "s", "tool": "Write", "file": "", "success": True},
        ]
        _seed_log(tmp_path, entries)
        _run(tool_name="Write", cwd=str(tmp_path))
        pattern = json.loads(
            (tmp_path / ".forge" / "patterns.jsonl").read_text().strip()
        )
        assert "ts" in pattern
