"""T-108 / REQ-GATESTUB-001 (fail-loud half): gate criteria pointing at missing
check scripts fail loud instead of soft-passing.

AC-GATESTUB-001a: a criterion whose script does not exist -> inconclusive output
                  + non-zero gate exit, regardless of declared severity.
AC-GATESTUB-001c: /forge:doctor surfaces the "N criteria unimplemented" banner.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
CHECK_GATE = str(SCRIPTS / "check-gate.py")
PYTHON = sys.executable

STUB_CRITERIA = (
    "```yaml\n"
    "stage: 1\n"
    "name: srs\n"
    "criteria:\n"
    "  - id: G1-001\n"
    "    description: stub criterion\n"
    "    check: script_returns_zero\n"
    "    severity: warning\n"          # declared warning — must be promoted to blocker
    "    args:\n"
    "      script: scripts/does_not_exist.py\n"
    "```\n"
)


def _stub_plugin(tmp_path: Path) -> Path:
    plugin = tmp_path / "plugin"
    (plugin / "references").mkdir(parents=True)
    (plugin / "references" / "gate-criteria.md").write_text(STUB_CRITERIA)
    return plugin


def _load_doctor():
    spec = importlib.util.spec_from_file_location("doctor", SCRIPTS / "doctor.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["doctor"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------- AC-GATESTUB-001a ----------

def test_missing_script_is_inconclusive_and_nonzero(tmp_path: Path) -> None:
    plugin = _stub_plugin(tmp_path)
    proj = tmp_path / "proj"
    proj.mkdir()
    r = subprocess.run(
        [PYTHON, CHECK_GATE, "--stage", "1", "--cwd", str(proj), "--plugin-dir", str(plugin)],
        capture_output=True, text=True,
    )
    assert r.returncode == 2, r.stdout  # non-zero regardless of declared severity
    data = json.loads(r.stdout)
    assert data["inconclusive"] is True
    assert data["unimplemented"] == 1


def test_missing_script_criterion_promoted_to_blocker(tmp_path: Path) -> None:
    plugin = _stub_plugin(tmp_path)
    proj = tmp_path / "proj"
    proj.mkdir()
    r = subprocess.run(
        [PYTHON, CHECK_GATE, "--stage", "1", "--cwd", str(proj), "--plugin-dir", str(plugin)],
        capture_output=True, text=True,
    )
    data = json.loads(r.stdout)
    crit = next(d for d in data["details"] if d["id"] == "G1-001")
    assert crit["inconclusive"] is True
    assert crit["passed"] is False
    assert crit["severity"] == "blocker"  # promoted from warning


# ---------- AC-GATESTUB-001c: doctor banner ----------

def test_doctor_surfaces_unimplemented_banner(tmp_path: Path) -> None:
    # Build a forge_root with check-gate.py + _state_lib.py + stub criteria.
    fr = tmp_path / "forge_root"
    (fr / "scripts").mkdir(parents=True)
    (fr / "references").mkdir(parents=True)
    shutil.copy(SCRIPTS / "check-gate.py", fr / "scripts" / "check-gate.py")
    shutil.copy(SCRIPTS / "_state_lib.py", fr / "scripts" / "_state_lib.py")
    shutil.copy(SCRIPTS / "_stage_table.py", fr / "scripts" / "_stage_table.py")
    (fr / "references" / "stage-order.md").write_text(
        (ROOT / "references" / "stage-order.md").read_text()
    )
    (fr / "references" / "gate-criteria.md").write_text(STUB_CRITERIA)

    proj = tmp_path / "proj"
    (proj / "pipeline").mkdir(parents=True)
    (proj / "pipeline" / "state.md").write_text(
        "---\nschema_version: 1\nproject_type: unknown\ncycle: 1\n"
        "current_stage: 1\ncurrent_task: null\ncurrent_milestone: null\n"
        "total_tasks: null\nlast_updated: 2026-06-09T00:00:00Z\nblockers: []\n---\n\n# s\n"
    )

    doctor = _load_doctor()
    gate = doctor.check_current_stage_gate(fr, proj)
    assert gate is not None
    assert gate.status == "fail"
    assert "unimplemented" in gate.detail.lower()
