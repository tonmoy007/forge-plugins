"""Tests for hooks/pre-compact.py (T-187, REQ-CTX-006).

The PreCompact hook checkpoints an active autopilot run *before* native compaction so
SessionStart(source=compact) can resume it. It must NEVER block (always exit 0) and
NEVER raise; it writes a checkpoint only when an autopilot run is active.
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK = _ROOT / "hooks" / "pre-compact.py"
PYTHON = sys.executable
_CHECKPOINT = "autopilot-checkpoint.json"


def _state(tmp_path: Path, stage: int = 6) -> None:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "pipeline" / "state.md").write_text(
        f"---\nschema_version: 1\nproject_type: api\ncycle: 1\n"
        f"current_stage: {stage}\ncurrent_task: null\ncurrent_milestone: null\n"
        f"total_tasks: null\nlast_updated: {now}\nblockers: []\n---\n\n# State\n")


def _session(tmp_path: Path, status: str) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    (forge / "autopilot-session.json").write_text(json.dumps({"status": status}))


def _run(tmp_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run([PYTHON, str(_HOOK)], input=json.dumps({"cwd": str(tmp_path)}),
                          capture_output=True, text=True)


def test_writes_checkpoint_when_run_active(tmp_path):
    _state(tmp_path)
    _session(tmp_path, "running")
    res = _run(tmp_path)
    assert res.returncode == 0
    assert (tmp_path / ".forge" / _CHECKPOINT).exists()


def test_noop_when_run_not_active(tmp_path):
    _state(tmp_path)
    _session(tmp_path, "idle")
    res = _run(tmp_path)
    assert res.returncode == 0
    assert not (tmp_path / ".forge" / _CHECKPOINT).exists()


def test_noop_when_no_session_file(tmp_path):
    _state(tmp_path)
    res = _run(tmp_path)
    assert res.returncode == 0
    assert not (tmp_path / ".forge" / _CHECKPOINT).exists()


def test_noop_on_non_forge_project(tmp_path):
    res = _run(tmp_path)  # no pipeline/state.md
    assert res.returncode == 0
    assert not (tmp_path / ".forge" / _CHECKPOINT).exists()


def test_never_blocks_on_malformed_session(tmp_path):
    _state(tmp_path)
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "autopilot-session.json").write_text("{garbage")
    res = _run(tmp_path)
    assert res.returncode == 0  # never blocks (exit 0), never raises
    assert not (tmp_path / ".forge" / _CHECKPOINT).exists()


def test_handles_empty_stdin(tmp_path):
    res = subprocess.run([PYTHON, str(_HOOK)], input="", capture_output=True, text=True)
    assert res.returncode == 0
