"""T-104 / REQ-PIPEBOUNDS-001: state machine enforces stage bounds + cycle-wrap.

AC-PIPEBOUNDS-001a: advance from stage 12 with no --to wraps to (cycle+1, 0),
                    never produces current_stage: 13.
AC-PIPEBOUNDS-001b: set current_stage to -1 or 99 exits non-zero, state unchanged.
AC-PIPEBOUNDS-001c: state-layer and gate-layer agree rejecting stage 13.
"""

from __future__ import annotations

import datetime
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import _state_lib as lib  # noqa: E402

SM = str(SCRIPTS / "state-manager.py")
PYTHON = sys.executable


def _write_state(tmp_path: Path, *, current_stage: int, cycle: int = 1) -> None:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "pipeline" / "state.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "project_type: unknown\n"
        f"cycle: {cycle}\n"
        f"current_stage: {current_stage}\n"
        "current_task: null\n"
        "current_milestone: null\n"
        "total_tasks: null\n"
        f"last_updated: {now}\n"
        "blockers: []\n"
        "---\n\n# Pipeline State\n"
    )


def run(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run([PYTHON, SM] + args, capture_output=True, text=True, cwd=cwd)


# ---------- AC-PIPEBOUNDS-001a: cycle-wrap ----------

def test_advance_past_last_stage_wraps_to_next_cycle(tmp_path: Path) -> None:
    _write_state(tmp_path, current_stage=12, cycle=1)
    new = lib.advance_stage(str(tmp_path))
    assert new["current_stage"] == 0
    assert new["cycle"] == 2


def test_advance_from_12_never_lands_on_13(tmp_path: Path) -> None:
    _write_state(tmp_path, current_stage=12, cycle=3)
    new = lib.advance_stage(str(tmp_path))
    assert new["current_stage"] != 13
    assert new["current_stage"] == 0
    assert new["cycle"] == 4


# ---------- AC-PIPEBOUNDS-001b: set range rejection ----------

@pytest.mark.parametrize("bad", ["-1", "99", "13"])
def test_set_out_of_range_stage_rejected_and_unchanged(tmp_path: Path, bad: str) -> None:
    _write_state(tmp_path, current_stage=4)
    result = run(["set", "--field", "current_stage", "--value", bad], cwd=str(tmp_path))
    assert result.returncode != 0
    # state.md unchanged
    assert lib.read_state(str(tmp_path))["current_stage"] == 4


def test_set_in_range_stage_accepted(tmp_path: Path) -> None:
    _write_state(tmp_path, current_stage=4)
    result = run(["set", "--field", "current_stage", "--value", "6"], cwd=str(tmp_path))
    assert result.returncode == 0
    assert lib.read_state(str(tmp_path))["current_stage"] == 6


# ---------- AC-PIPEBOUNDS-001c: advance --to out-of-range rejected ----------

@pytest.mark.parametrize("bad", [13, -1, 99])
def test_advance_to_out_of_range_rejected(tmp_path: Path, bad: int) -> None:
    _write_state(tmp_path, current_stage=5)
    with pytest.raises(SystemExit):
        lib.advance_stage(str(tmp_path), to=bad)
    # unchanged on disk
    assert lib.read_state(str(tmp_path))["current_stage"] == 5


def test_advance_to_13_via_cli_nonzero(tmp_path: Path) -> None:
    _write_state(tmp_path, current_stage=12)
    result = run(["advance", "--to", "13"], cwd=str(tmp_path))
    assert result.returncode != 0
    assert lib.read_state(str(tmp_path))["current_stage"] == 12


# ---------- validate_frontmatter range guard ----------

def test_validate_frontmatter_rejects_out_of_range_stage() -> None:
    base = {
        "schema_version": 1,
        "project_type": "unknown",
        "cycle": 1,
        "current_stage": 13,
        "current_task": None,
        "current_milestone": None,
        "total_tasks": None,
        "last_updated": "2026-06-09T00:00:00Z",
        "blockers": [],
    }
    ok, errors = lib.validate_frontmatter(base)
    assert not ok
    assert any("current_stage" in e for e in errors)
