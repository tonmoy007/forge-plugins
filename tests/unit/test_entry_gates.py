"""T-105 / REQ-GATE-ENTRY-001: pre-flight entry blocks for stages 2-11.

AC-GATE-ENTRY-001a: for each stage 2-11, a synthetic invocation with the prior
                    artifact missing exits 2 and names the missing file.
AC-GATE-ENTRY-001b: advance --to N where N > current+1 exits non-zero unless --force.
AC-GATE-ENTRY-001c: the pre-flight check and the next-step hint both derive from
                    the same stage-order table (no duplicated stage logic).
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
import _stage_table as st  # noqa: E402

SM = str(SCRIPTS / "state-manager.py")
PYTHON = sys.executable


def _init_project(tmp_path: Path, current_stage: int = 1) -> Path:
    (tmp_path / "pipeline").mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "pipeline" / "state.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "project_type: unknown\n"
        "cycle: 1\n"
        f"current_stage: {current_stage}\n"
        "current_task: null\n"
        "current_milestone: null\n"
        "total_tasks: null\n"
        f"last_updated: {now}\n"
        "blockers: []\n"
        "---\n\n# Pipeline State\n"
    )
    return tmp_path


def _make_prereq(tmp_path: Path, stage: int) -> None:
    """Create the prior-stage artifact required to enter `stage`."""
    prereq = st.prerequisite(stage)
    path = tmp_path / prereq
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# stub artifact\n")


def run(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run([PYTHON, SM] + args, capture_output=True, text=True, cwd=cwd)


STAGES_WITH_PREREQ = list(range(2, 12))  # 2..11


# ---------- AC-GATE-ENTRY-001a: missing prerequisite blocks with exit 2 ----------

@pytest.mark.parametrize("stage", STAGES_WITH_PREREQ)
def test_missing_prerequisite_exits_2_and_names_file(tmp_path: Path, stage: int) -> None:
    _init_project(tmp_path)
    result = run(["preflight", "--stage", str(stage)], cwd=str(tmp_path))
    assert result.returncode == 2, f"stage {stage}: {result.stderr}"
    assert st.prerequisite(stage) in result.stderr


@pytest.mark.parametrize("stage", STAGES_WITH_PREREQ)
def test_present_prerequisite_exits_0(tmp_path: Path, stage: int) -> None:
    _init_project(tmp_path)
    _make_prereq(tmp_path, stage)
    result = run(["preflight", "--stage", str(stage)], cwd=str(tmp_path))
    assert result.returncode == 0, f"stage {stage}: {result.stderr}"


def test_stage1_has_no_prerequisite(tmp_path: Path) -> None:
    _init_project(tmp_path, current_stage=0)
    result = run(["preflight", "--stage", "1"], cwd=str(tmp_path))
    assert result.returncode == 0


# ---------- AC-GATE-ENTRY-001b: skip rejection unless --force ----------

def test_advance_skip_rejected_without_force(tmp_path: Path) -> None:
    _init_project(tmp_path, current_stage=1)
    result = run(["advance", "--to", "4"], cwd=str(tmp_path))  # 4 > 1+1
    assert result.returncode != 0
    assert "force" in result.stderr.lower()


def test_advance_skip_allowed_with_force(tmp_path: Path) -> None:
    _init_project(tmp_path, current_stage=1)
    result = run(["advance", "--to", "4", "--force"], cwd=str(tmp_path))
    assert result.returncode == 0


def test_advance_single_step_no_force_needed(tmp_path: Path) -> None:
    _init_project(tmp_path, current_stage=1)
    result = run(["advance", "--to", "2"], cwd=str(tmp_path))
    assert result.returncode == 0


# ---------- AC-GATE-ENTRY-001c: shared source of truth ----------

def test_preflight_and_hint_share_stage_table() -> None:
    """The prerequisite a stage checks is the previous stage's primary artifact —
    the same table the next-step hint is derived from (T-101 invariant)."""
    for stage in STAGES_WITH_PREREQ:
        assert st.prerequisite(stage) == st.primary_artifact(stage - 1)
