"""T-106 / REQ-SILENTSTATE-001: state-read failures surface visibly.

AC-SILENTSTATE-001a: an unreadable pipeline/state.md produces (i) a visible hook
                     warning, (ii) inconclusive gate output, (iii) a /forge:doctor
                     callout, and (iv) a Stop/session-end footer with the count.
AC-SILENTSTATE-001b: no hook catches an exception around read_state() without a
                     user-visible signal — enforced by routing all hook reads
                     through hooks/_state_read.py (grep guard).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
HOOKS = ROOT / "hooks"
PYTHON = sys.executable

sys.path.insert(0, str(HOOKS))
sys.path.insert(0, str(SCRIPTS))
import _state_read  # noqa: E402

CORRUPT_FRONTMATTER = "---\nschema_version: 1\ncurrent_stage: [1, 2\n---\n\n# broken\n"


def _corrupt_state(tmp_path: Path) -> Path:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    (tmp_path / "pipeline" / "state.md").write_text(CORRUPT_FRONTMATTER)
    return tmp_path


def _good_state(tmp_path: Path) -> Path:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    (tmp_path / "pipeline" / "state.md").write_text(
        "---\nschema_version: 1\nproject_type: unknown\ncycle: 1\n"
        "current_stage: 2\ncurrent_task: null\ncurrent_milestone: null\n"
        "total_tasks: null\nlast_updated: 2026-06-09T00:00:00Z\nblockers: []\n---\n\n# ok\n"
    )
    return tmp_path


# ---------- helper-level: first failure warns + logs ----------

def test_read_state_safe_warns_and_logs_on_first_failure(tmp_path: Path) -> None:
    _corrupt_state(tmp_path)
    state, warning = _state_read.read_state_safe(str(tmp_path), session_id="s1")
    assert state == {}
    assert warning and "state.md" in warning
    assert _state_read.count_state_read_failures(tmp_path / ".forge", "s1") == 1


def test_read_state_safe_dedupes_warning_within_session(tmp_path: Path) -> None:
    _corrupt_state(tmp_path)
    _state_read.read_state_safe(str(tmp_path), session_id="s1")
    _, warning2 = _state_read.read_state_safe(str(tmp_path), session_id="s1")
    assert warning2 is None  # already warned this session
    assert _state_read.count_state_read_failures(tmp_path / ".forge", "s1") == 2


def test_read_state_safe_clean_state_no_warning(tmp_path: Path) -> None:
    _good_state(tmp_path)
    state, warning = _state_read.read_state_safe(str(tmp_path), session_id="s1")
    assert warning is None
    assert state.get("current_stage") == 2


# ---------- (i) visible hook warning ----------

def test_hook_prints_warning_on_corrupt_state(tmp_path: Path) -> None:
    _corrupt_state(tmp_path)
    payload = json.dumps({
        "cwd": str(tmp_path), "session_id": "s1",
        "tool_name": "Write", "tool_input": {"file_path": "x.py"}, "tool_response": {},
    })
    r = subprocess.run(
        [PYTHON, str(HOOKS / "post-tool-use.py")],
        input=payload, capture_output=True, text=True,
    )
    assert "state.md" in r.stdout


# ---------- (ii) inconclusive gate output ----------

def test_gate_inconclusive_on_corrupt_state(tmp_path: Path) -> None:
    _corrupt_state(tmp_path)
    r = subprocess.run(
        [PYTHON, str(SCRIPTS / "check-gate.py"),
         "--stage", "1", "--cwd", str(tmp_path), "--plugin-dir", str(ROOT)],
        capture_output=True, text=True,
    )
    assert r.returncode == 2
    data = json.loads(r.stdout)
    assert data["inconclusive"] is True
    assert any(d["id"] == "STATE-READ" for d in data["details"])


def test_gate_no_state_read_failure_on_good_state(tmp_path: Path) -> None:
    """A readable state must not produce a STATE-READ inconclusive detail.

    (The gate may still be inconclusive for an unrelated reason — e.g. a missing
    check script per REQ-GATESTUB-001 — so we assert specifically on STATE-READ.)
    """
    _good_state(tmp_path)
    r = subprocess.run(
        [PYTHON, str(SCRIPTS / "check-gate.py"),
         "--stage", "1", "--cwd", str(tmp_path), "--plugin-dir", str(ROOT)],
        capture_output=True, text=True,
    )
    data = json.loads(r.stdout)
    assert not any(d["id"] == "STATE-READ" for d in data["details"])


# ---------- (iii) doctor callout ----------

def test_doctor_surfaces_state_read_failures(tmp_path: Path) -> None:
    _corrupt_state(tmp_path)
    # produce a state_read_failed event
    _state_read.read_state_safe(str(tmp_path), session_id="s1")
    r = subprocess.run(
        [PYTHON, str(SCRIPTS / "doctor.py"), "--cwd", str(tmp_path), "--json"],
        capture_output=True, text=True,
    )
    results = json.loads(r.stdout)
    srf = [c for c in results if c["name"] == "state_read_failures"]
    assert srf and srf[0]["status"] == "fail"


# ---------- (iv) session-end footer ----------

def test_session_end_footer_reports_count(tmp_path: Path) -> None:
    _corrupt_state(tmp_path)
    _state_read.read_state_safe(str(tmp_path), session_id="s1")  # seed a failure
    payload = json.dumps({"cwd": str(tmp_path), "session_id": "s1"})
    r = subprocess.run(
        [PYTHON, str(HOOKS / "session-end.py")],
        input=payload, capture_output=True, text=True,
    )
    assert "state-read failure" in r.stdout


# ---------- AC-SILENTSTATE-001b: grep guard ----------

def test_no_hook_reads_state_outside_helper() -> None:
    """Every hook reads state through _state_read; none call lib.read_state directly."""
    offenders = []
    for path in HOOKS.glob("*.py"):
        if path.name == "_state_read.py":
            continue
        text = path.read_text()
        if "read_state(" in text:
            offenders.append(path.name)
    assert offenders == [], f"hooks calling read_state directly (must use _state_read): {offenders}"
