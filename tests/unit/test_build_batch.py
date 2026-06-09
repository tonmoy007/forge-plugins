"""T-116 / REQ-BUILDBATCH-001: /forge:build --milestone N batch planning.

AC-BUILDBATCH-001a: a 3-task milestone yields exactly its 3 T-IDs in dependency order.
AC-BUILDBATCH-001b: --resume skips tasks already marked done (resume after a failure).
AC-BUILDBATCH-001c: plain /forge:build (no flag) is unchanged — the skill keeps its
                    single-task Steps; the batch path is opt-in via --milestone.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = str(ROOT / "scripts" / "build-batch.py")
PYTHON = sys.executable

DAG = """# Task DAG

## Milestone 1: Foundation

### T-201 [S] first
- **Depends on**: T-202

### T-202 [S] second
- **Depends on**: none

### T-203 [S] third
- **Depends on**: T-201

## Milestone 2: Next

### T-204 [S] later
- **Depends on**: none
"""


def _project(tmp_path: Path, dag: str = DAG, progress: str = "") -> Path:
    (tmp_path / "pipeline" / "05-plan").mkdir(parents=True)
    (tmp_path / "pipeline" / "05-plan" / "task-dag.md").write_text(dag)
    if progress:
        (tmp_path / "pipeline" / "06-implementation").mkdir(parents=True)
        (tmp_path / "pipeline" / "06-implementation" / "progress.md").write_text(progress)
    return tmp_path


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([PYTHON, SCRIPT] + args, capture_output=True, text=True, cwd=str(cwd))


# ---------- AC-BUILDBATCH-001a: ordered task list ----------

def test_milestone_returns_three_tasks_in_dep_order(tmp_path: Path) -> None:
    _project(tmp_path)
    r = run(["--milestone", "1"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["T-202", "T-201", "T-203"]


def test_only_milestone_tasks_included(tmp_path: Path) -> None:
    _project(tmp_path)
    r = run(["--milestone", "2"], tmp_path)
    assert r.stdout.split() == ["T-204"]


def test_unknown_milestone_exits_1(tmp_path: Path) -> None:
    _project(tmp_path)
    r = run(["--milestone", "9"], tmp_path)
    assert r.returncode == 1


# ---------- AC-BUILDBATCH-001b: resume skips done tasks ----------

def test_resume_skips_done(tmp_path: Path) -> None:
    _project(tmp_path, progress="| T-202 | 🟢 done | first one shipped |\n")
    r = run(["--milestone", "1", "--resume"], tmp_path)
    assert r.stdout.split() == ["T-201", "T-203"]


def test_no_resume_returns_all(tmp_path: Path) -> None:
    _project(tmp_path, progress="| T-202 | 🟢 done | first one shipped |\n")
    r = run(["--milestone", "1"], tmp_path)  # without --resume, done tasks still listed
    assert r.stdout.split() == ["T-202", "T-201", "T-203"]


# ---------- large-batch warning ----------

def test_large_batch_warns(tmp_path: Path) -> None:
    tasks = "\n".join(
        f"### T-3{i:02d} [S] t\n- **Depends on**: none\n" for i in range(11)
    )
    _project(tmp_path, dag=f"## Milestone 1: Big\n\n{tasks}\n")
    r = run(["--milestone", "1"], tmp_path)
    assert r.returncode == 0
    assert "large batch" in r.stderr
    assert len(r.stdout.split()) == 11


def test_small_batch_no_warning(tmp_path: Path) -> None:
    _project(tmp_path)
    r = run(["--milestone", "1"], tmp_path)
    assert "large batch" not in r.stderr


# ---------- AC-BUILDBATCH-001c: single-task path unchanged ----------

def test_skill_keeps_single_task_steps() -> None:
    skill = (ROOT / "skills" / "forge-build" / "SKILL.md").read_text()
    assert "Milestone Batch Mode" in skill            # batch path documented
    assert "no flag) keeps the single-task behavior" in skill  # default unchanged
