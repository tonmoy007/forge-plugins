"""Tests for scripts/sprint.py (v0.3.4 / M4 — REQ-F-044..048).

`/forge:sprint` is a deterministic **view over the task DAG** (no LLM): `plan` groups the
next ready tasks into `pipeline/05-plan/sprint-NN.md`; `review` reports done-vs-carried
into `pipeline/12-release/sprint-NN-review.md`. T-IDs are the identity — the DAG and
progress.md remain the source of truth. Fully opt-in; never raises into the caller.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_mod_path = _ROOT / "scripts" / "sprint.py"
_spec = importlib.util.spec_from_file_location("sprint", _mod_path)
_sp = importlib.util.module_from_spec(_spec)
sys.modules["sprint"] = _sp
_spec.loader.exec_module(_sp)

PYTHON = sys.executable

_DAG = """# Task DAG — Demo

## Tasks

### T-001 [S] — Schema (REQ-001)
Depends on: none

### T-002 [M] — Auth (REQ-002)
Depends on: T-001

### T-003 [M] — Tokens (REQ-002)
Depends on: T-002

### T-004 [S] — CRUD (REQ-003)
Depends on: T-001

### T-005 [L] — Pagination (REQ-004)
Depends on: T-004
"""


def _make_dag(cwd: Path, text: str = _DAG) -> None:
    d = cwd / "pipeline" / "05-plan"
    d.mkdir(parents=True, exist_ok=True)
    (d / "task-dag.md").write_text(text)


def _make_progress(cwd: Path, done_ids: list[str]) -> None:
    d = cwd / "pipeline" / "06-implementation"
    d.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"- 🟢 {tid} — done" for tid in done_ids)
    (d / "progress.md").write_text("# Progress\n\n" + lines + "\n")


# --- parsing ---------------------------------------------------------------

def test_parse_tasks_reads_id_title_size_deps():
    tasks = _sp.parse_tasks(_DAG)
    by_id = {t.id: t for t in tasks}
    assert set(by_id) == {"T-001", "T-002", "T-003", "T-004", "T-005"}
    assert by_id["T-002"].deps == {"T-001"}
    assert by_id["T-001"].size == "S"
    assert "Auth" in by_id["T-002"].title


def test_parse_tasks_arrow_dependencies():
    dag = (
        "# DAG\n\n## Tasks\n\n### T-001 — A\n\n### T-002 — B\n\n### T-003 — C\n\n"
        "## Dependencies\n\n```\nT-001 → T-002 → T-003\n```\n"
    )
    by_id = {t.id: t for t in _sp.parse_tasks(dag)}
    assert by_id["T-002"].deps == {"T-001"}
    assert by_id["T-003"].deps == {"T-002"}


def test_parse_tasks_empty_on_garbage():
    assert _sp.parse_tasks("no tasks here") == []


# --- done detection --------------------------------------------------------

def test_done_tasks_reads_progress(tmp_path):
    _make_progress(tmp_path, ["T-001", "T-002"])
    assert _sp.done_tasks(tmp_path) == {"T-001", "T-002"}


def test_done_tasks_absent_progress_is_empty(tmp_path):
    assert _sp.done_tasks(tmp_path) == set()


# --- selection (topo, size, milestone) -------------------------------------

def test_select_sprint_topo_and_size():
    tasks = _sp.parse_tasks(_DAG)
    sel = _sp.select_sprint(tasks, done=set(), size=3)
    ids = [t.id for t in sel]
    # Dependency-first, ties broken by declared order, capped at 3.
    assert ids == ["T-001", "T-002", "T-003"]


def test_select_sprint_skips_done():
    tasks = _sp.parse_tasks(_DAG)
    sel = _sp.select_sprint(tasks, done={"T-001", "T-002"}, size=3)
    ids = [t.id for t in sel]
    assert "T-001" not in ids and "T-002" not in ids
    assert ids[0] == "T-003" or ids[0] == "T-004"  # next ready tasks


def test_select_sprint_size_caps_count():
    tasks = _sp.parse_tasks(_DAG)
    assert len(_sp.select_sprint(tasks, done=set(), size=2)) == 2


# --- sprint numbering ------------------------------------------------------

def test_next_sprint_number_starts_at_one(tmp_path):
    assert _sp.next_sprint_number(tmp_path) == 1


def test_next_sprint_number_increments(tmp_path):
    d = tmp_path / "pipeline" / "05-plan"
    d.mkdir(parents=True)
    (d / "sprint-01.md").write_text("# Sprint 01\n")
    (d / "sprint-02.md").write_text("# Sprint 02\n")
    assert _sp.next_sprint_number(tmp_path) == 3


# --- plan: writes sprint file with carry-over ------------------------------

def test_cli_plan_writes_sprint_file(tmp_path):
    _make_dag(tmp_path)
    r = subprocess.run([PYTHON, str(_mod_path), "plan", "--cwd", str(tmp_path),
                        "--size", "3"], capture_output=True, text=True)
    assert r.returncode == 0
    sprint = tmp_path / "pipeline" / "05-plan" / "sprint-01.md"
    assert sprint.exists()
    text = sprint.read_text()
    assert "T-001" in text and "T-002" in text and "T-003" in text
    assert "T-004" not in text  # capped at size 3 (declared-order, dependency-first)


def test_cli_plan_carries_unfinished_tasks(tmp_path):
    _make_dag(tmp_path)
    # Sprint 1 (size 3) → T-001, T-002, T-003.
    subprocess.run([PYTHON, str(_mod_path), "plan", "--cwd", str(tmp_path), "--size", "3"],
                   capture_output=True, text=True)
    # Only T-001 done; T-002 and T-003 carry over into sprint 2.
    _make_progress(tmp_path, ["T-001"])
    r = subprocess.run([PYTHON, str(_mod_path), "plan", "--cwd", str(tmp_path), "--size", "3"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    s2 = (tmp_path / "pipeline" / "05-plan" / "sprint-02.md").read_text()
    assert "T-002" in s2 and "T-003" in s2  # carried (preserve identity)
    assert "carried" in s2.lower()


def test_cli_plan_no_dag_is_clean_error(tmp_path):
    r = subprocess.run([PYTHON, str(_mod_path), "plan", "--cwd", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 1
    assert "task DAG not found" in (r.stdout + r.stderr).lower() or \
           "task-dag" in (r.stdout + r.stderr).lower()


# --- review: done vs carried -----------------------------------------------

def test_cli_review_reports_done_and_carried(tmp_path):
    _make_dag(tmp_path)
    subprocess.run([PYTHON, str(_mod_path), "plan", "--cwd", str(tmp_path), "--size", "3"],
                   capture_output=True, text=True)
    _make_progress(tmp_path, ["T-001", "T-002"])  # T-003 not done
    r = subprocess.run([PYTHON, str(_mod_path), "review", "--cwd", str(tmp_path),
                        "--sprint", "1"], capture_output=True, text=True)
    assert r.returncode == 0
    review = tmp_path / "pipeline" / "12-release" / "sprint-01-review.md"
    assert review.exists()
    text = review.read_text()
    assert "T-001" in text and "T-002" in text  # done
    assert "T-003" in text                        # carried
    assert "Done" in text and "Carried" in text


def test_cli_review_defaults_to_latest_sprint(tmp_path):
    _make_dag(tmp_path)
    subprocess.run([PYTHON, str(_mod_path), "plan", "--cwd", str(tmp_path), "--size", "2"],
                   capture_output=True, text=True)
    r = subprocess.run([PYTHON, str(_mod_path), "review", "--cwd", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert (tmp_path / "pipeline" / "12-release" / "sprint-01-review.md").exists()


def test_cli_review_missing_sprint_is_clean_error(tmp_path):
    _make_dag(tmp_path)
    r = subprocess.run([PYTHON, str(_mod_path), "review", "--cwd", str(tmp_path),
                        "--sprint", "9"], capture_output=True, text=True)
    assert r.returncode == 1


# --- list ------------------------------------------------------------------

def test_cli_list_shows_sprints(tmp_path):
    _make_dag(tmp_path)
    subprocess.run([PYTHON, str(_mod_path), "plan", "--cwd", str(tmp_path), "--size", "2"],
                   capture_output=True, text=True)
    r = subprocess.run([PYTHON, str(_mod_path), "list", "--cwd", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "sprint-01" in r.stdout.lower() or "sprint 01" in r.stdout.lower()


def test_cli_list_no_sprints_is_clean(tmp_path):
    r = subprocess.run([PYTHON, str(_mod_path), "list", "--cwd", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0  # opt-in: nothing to show, no error
