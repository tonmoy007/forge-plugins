"""T-107 / REQ-DOCTOR-001: doctor runs the current-stage gate inline.

AC-DOCTOR-001a: current_stage=4 with stage-4 artifacts missing -> wedged + G4-* IDs.
AC-DOCTOR-001b: all current-stage blockers pass -> healthy; warnings don't wedge.
AC-DOCTOR-001c: doctor's gate verdict and a direct check-gate run never disagree.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
PYTHON = sys.executable


def _load_doctor():
    spec = importlib.util.spec_from_file_location("doctor", SCRIPTS / "doctor.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["doctor"] = mod
    spec.loader.exec_module(mod)
    return mod


doctor = _load_doctor()
CR = doctor.CheckResult


def _state(tmp_path: Path, stage: int) -> Path:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "pipeline" / "state.md").write_text(
        "---\nschema_version: 1\nproject_type: unknown\ncycle: 1\n"
        f"current_stage: {stage}\ncurrent_task: null\ncurrent_milestone: null\n"
        f"total_tasks: null\nlast_updated: {now}\nblockers: []\n---\n\n# state\n"
    )
    return tmp_path


# ---------- AC-DOCTOR-001a/b: overall_status verdict logic ----------

def test_overall_status_healthy() -> None:
    results = [
        CR("python", "environment", "pass", ""),
        CR("manifest", "plugin", "pass", ""),
        CR("current_stage_gate", "project", "pass", ""),
    ]
    assert doctor.overall_status(results) == "healthy"


def test_overall_status_wedged_on_gate_fail() -> None:
    results = [
        CR("python", "environment", "pass", ""),
        CR("manifest", "plugin", "pass", ""),
        CR("current_stage_gate", "project", "fail", "G4-001 ..."),
    ]
    assert doctor.overall_status(results) == "wedged"


def test_overall_status_broken_on_env_fail() -> None:
    results = [
        CR("python", "environment", "fail", ""),
        CR("current_stage_gate", "project", "fail", ""),
    ]
    assert doctor.overall_status(results) == "broken"


def test_warnings_do_not_wedge() -> None:
    results = [
        CR("python", "environment", "pass", ""),
        CR("manifest", "plugin", "pass", ""),
        CR("current_stage_gate", "project", "pass", ""),
        CR("disk", "global", "warn", "low disk"),
    ]
    assert doctor.overall_status(results) == "healthy"


# ---------- AC-DOCTOR-001a: wedged stage names failing G-IDs ----------

def test_wedged_stage_gate_names_failing_ids(tmp_path: Path) -> None:
    _state(tmp_path, stage=4)  # no stage-4 artifacts created
    gate = doctor.check_current_stage_gate(ROOT, tmp_path)
    assert gate is not None
    assert gate.status == "fail"
    assert "G4" in gate.detail


def test_no_active_stage_yields_no_gate_check(tmp_path: Path) -> None:
    _state(tmp_path, stage=0)
    assert doctor.check_current_stage_gate(ROOT, tmp_path) is None


# ---------- AC-DOCTOR-001c: doctor and check-gate agree ----------

def test_doctor_gate_matches_direct_check_gate(tmp_path: Path) -> None:
    _state(tmp_path, stage=4)
    gate = doctor.check_current_stage_gate(ROOT, tmp_path)
    direct = subprocess.run(
        [PYTHON, str(SCRIPTS / "check-gate.py"),
         "--stage", "4", "--cwd", str(tmp_path), "--plugin-dir", str(ROOT)],
        capture_output=True, text=True,
    )
    data = json.loads(direct.stdout)
    direct_blockers = [
        d["id"] for d in data["details"]
        if not d["passed"] and d.get("severity") == "blocker"
    ]
    # Every blocker the direct run reports is named in the doctor verdict.
    for bid in direct_blockers:
        assert bid in gate.detail


# ---------- JSON still a list, now carrying overall_status ----------

def test_json_carries_overall_status(tmp_path: Path) -> None:
    _state(tmp_path, stage=4)
    r = subprocess.run(
        [PYTHON, str(SCRIPTS / "doctor.py"), "--json", "--cwd", str(tmp_path)],
        capture_output=True, text=True,
    )
    data = json.loads(r.stdout)
    assert isinstance(data, list)
    overall = [c for c in data if c["name"] == "overall_status"]
    assert overall and overall[0]["detail"].startswith("status: ")
