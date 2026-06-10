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


def _read_patterns(tmp_path: Path) -> list[dict]:
    patterns_path = tmp_path / ".forge" / "patterns.jsonl"
    if not patterns_path.exists():
        return []
    records = []
    for line in patterns_path.read_text().splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


class TestPatternTracking:
    def test_three_tools_creates_window_record(self, tmp_path):
        entries = [
            {"ts": "2026-05-10T00:00:00Z", "session": "s", "tool": "Read",
             "file": "", "success": True},
            {"ts": "2026-05-10T00:00:01Z", "session": "s", "tool": "Read",
             "file": "", "success": True},
        ]
        _seed_log(tmp_path, entries)
        _run(tool_name="Read", cwd=str(tmp_path))
        records = _read_patterns(tmp_path)
        assert len(records) == 1
        r = records[0]
        assert r["kind"] == "tool_seq_3"
        assert r["tools"] == ["Read", "Read", "Read"]
        assert "signature" in r

    def test_three_different_tools_logs_window(self, tmp_path):
        # Read → Edit → Bash: every 3-tool window gets logged, including
        # non-repeating ones, so the miner can decide downstream.
        entries = [
            {"ts": "t", "session": "s", "tool": "Read", "file": "", "success": True},
            {"ts": "t", "session": "s", "tool": "Edit", "file": "", "success": True},
        ]
        _seed_log(tmp_path, entries)
        _run(tool_name="Bash", cwd=str(tmp_path))
        records = _read_patterns(tmp_path)
        assert len(records) == 1
        assert records[0]["tools"] == ["Read", "Edit", "Bash"]

    def test_fewer_than_three_tools_no_pattern_file(self, tmp_path):
        _run(tool_name="Write", cwd=str(tmp_path))
        _run(tool_name="Read", cwd=str(tmp_path))
        patterns_path = tmp_path / ".forge" / "patterns.jsonl"
        assert not patterns_path.exists()

    def test_window_record_includes_session_id(self, tmp_path):
        entries = [
            {"ts": "t", "session": "my-sess", "tool": "Bash",
             "file": "", "success": True},
            {"ts": "t", "session": "my-sess", "tool": "Bash",
             "file": "", "success": True},
        ]
        _seed_log(tmp_path, entries)
        _run(tool_name="Bash", session_id="my-sess", cwd=str(tmp_path))
        records = _read_patterns(tmp_path)
        assert records[0]["session"] == "my-sess"

    def test_window_record_has_timestamp(self, tmp_path):
        entries = [
            {"ts": "t", "session": "s", "tool": "Write", "file": "", "success": True},
            {"ts": "t", "session": "s", "tool": "Write", "file": "", "success": True},
        ]
        _seed_log(tmp_path, entries)
        _run(tool_name="Write", cwd=str(tmp_path))
        records = _read_patterns(tmp_path)
        assert "ts" in records[0]


# ---------------------------------------------------------------------------
# T-026: Signature stability and the done-when criterion
# ---------------------------------------------------------------------------

class TestSignature:
    def test_signature_stable_for_same_sequence(self, tmp_path1=None):
        """Same 3-tool sequence → identical signature each occurrence."""
        # Import the hook module to call the helper directly.
        import importlib.util
        spec = importlib.util.spec_from_file_location("post_tool_use", HOOK)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["post_tool_use"] = mod
        spec.loader.exec_module(mod)
        sig1 = mod._window_signature(["Read", "Edit", "Bash"])
        sig2 = mod._window_signature(["Read", "Edit", "Bash"])
        assert sig1 == sig2
        assert len(sig1) == 12

    def test_signature_differs_for_different_sequences(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("post_tool_use", HOOK)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["post_tool_use"] = mod
        spec.loader.exec_module(mod)
        sig_a = mod._window_signature(["Read", "Edit", "Bash"])
        sig_b = mod._window_signature(["Read", "Bash", "Edit"])
        sig_c = mod._window_signature(["Write", "Edit", "Bash"])
        assert sig_a != sig_b
        assert sig_a != sig_c
        assert sig_b != sig_c

    def test_done_when_same_sequence_thrice_same_signature(self, tmp_path):
        """T-026 done-when: same 3-tool sequence appearing 3 times → 3 entries
        in patterns.jsonl all sharing the same signature."""
        # Drive 3 full occurrences of Read → Edit → Bash through the hook.
        # The first occurrence needs 2 prior tool calls before its 3rd lands a
        # window, so total 9 tool calls = 3 full sequences after warm-up.
        sequence = ["Read", "Edit", "Bash"]
        for _ in range(3):
            for tool in sequence:
                _run(tool_name=tool, cwd=str(tmp_path))
        records = _read_patterns(tmp_path)
        # Find every Read→Edit→Bash window
        matching = [r for r in records if r["tools"] == sequence]
        assert len(matching) >= 3, f"expected ≥3 Read→Edit→Bash windows, got {len(matching)}"
        sigs = {r["signature"] for r in matching}
        assert len(sigs) == 1, f"all matching windows should share one signature, got {sigs}"

    def test_signature_field_present_in_every_record(self, tmp_path):
        entries = [
            {"ts": "t", "session": "s", "tool": "Read", "file": "", "success": True},
            {"ts": "t", "session": "s", "tool": "Edit", "file": "", "success": True},
        ]
        _seed_log(tmp_path, entries)
        _run(tool_name="Bash", cwd=str(tmp_path))
        _run(tool_name="Grep", cwd=str(tmp_path))
        records = _read_patterns(tmp_path)
        assert len(records) == 2
        for r in records:
            assert "signature" in r
            assert isinstance(r["signature"], str)
            assert len(r["signature"]) == 12


# ---------------------------------------------------------------------------
# EF-022 regression: string tool_input / tool_response from non-Write tools
# ---------------------------------------------------------------------------

class TestStringPayloadGuard:
    """Regression tests for EF-022: isinstance guard on tool_input/tool_response.

    Bash, Read, and other non-Write tools can send string payloads instead of
    dicts. The hook must not crash when it receives one.
    """

    def _run_raw_payload(self, payload: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            [PYTHON, HOOK],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
        )

    def test_string_tool_input_from_bash(self, tmp_path):
        """Bash tools emit string tool_input — hook must not crash."""
        r = self._run_raw_payload({
            "hook_event_name": "PostToolUse",
            "session_id": "s",
            "tool_name": "Bash",
            "tool_input": "git status",
            "tool_response": {"exit_code": 0, "stdout": ""},
            "cwd": str(tmp_path),
        })
        assert r.returncode == 0

    def test_string_tool_response_from_read(self, tmp_path):
        """Read tools emit string tool_response — hook must not crash."""
        r = self._run_raw_payload({
            "hook_event_name": "PostToolUse",
            "session_id": "s",
            "tool_name": "Read",
            "tool_input": {"file_path": "foo.py"},
            "tool_response": "# file content",
            "cwd": str(tmp_path),
        })
        assert r.returncode == 0

    def test_both_payloads_string(self, tmp_path):
        """Both tool_input and tool_response are strings."""
        r = self._run_raw_payload({
            "hook_event_name": "PostToolUse",
            "session_id": "s",
            "tool_name": "Bash",
            "tool_input": "ls -la",
            "tool_response": "total 42",
            "cwd": str(tmp_path),
        })
        assert r.returncode == 0

    def test_dict_tool_input_still_works(self, tmp_path):
        """Normal dict payloads still log correctly after the guard."""
        r = self._run_raw_payload({
            "hook_event_name": "PostToolUse",
            "session_id": "s",
            "tool_name": "Write",
            "tool_input": {"file_path": "src/app.py"},
            "tool_response": {"success": True},
            "cwd": str(tmp_path),
        })
        assert r.returncode == 0
