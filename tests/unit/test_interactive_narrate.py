"""T-128 / REQ-INTERACTIVE-NARRATE-001: progress narration in /forge:build.

AC-NARRATE-001a: skills/forge-build/SKILL.md AND agents/builder.md direct per-task
                 start/result/next narration at task boundaries.
AC-NARRATE-001b: scripts/build-batch.py emits a per-task narration line (start +
                 task identifier) when listing a milestone's tasks, so a batch run
                 is observable from the tool layer (not only agent prose).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKILL = ROOT / "skills" / "forge-build" / "SKILL.md"
AGENT = ROOT / "agents" / "builder.md"
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
"""


def _project(tmp_path: Path) -> Path:
    (tmp_path / "pipeline" / "05-plan").mkdir(parents=True)
    (tmp_path / "pipeline" / "05-plan" / "task-dag.md").write_text(DAG)
    return tmp_path


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([PYTHON, SCRIPT] + args, capture_output=True, text=True, cwd=str(cwd))


# ---------- AC-NARRATE-001a: skill + agent direct narration ----------

def test_skill_directs_start_result_next_narration() -> None:
    text = SKILL.read_text()
    assert "REQ-INTERACTIVE-NARRATE-001" in text
    lowered = text.lower()
    assert "narrat" in lowered
    # start -> result -> next narration at task boundaries
    assert "starting" in lowered
    assert "result" in lowered
    assert "next" in lowered


def test_agent_reflects_per_task_narration() -> None:
    text = AGENT.read_text()
    assert "REQ-INTERACTIVE-NARRATE-001" in text
    assert "narrat" in text.lower()


# ---------- AC-NARRATE-001b: build-batch emits narration line ----------

def test_batch_emits_narration_line_on_stderr(tmp_path: Path) -> None:
    _project(tmp_path)
    r = run(["--milestone", "1"], tmp_path)
    assert r.returncode == 0, r.stderr
    # one narration line per task, carrying the task id, on stderr
    assert "[Forge] task T-202 — starting" in r.stderr
    assert "[Forge] task T-201 — starting" in r.stderr
    assert "[Forge] task T-203 — starting" in r.stderr


def test_stdout_stays_machine_readable_id_list(tmp_path: Path) -> None:
    """The narration must NOT pollute the stdout id contract (test_build_batch.py)."""
    _project(tmp_path)
    r = run(["--milestone", "1"], tmp_path)
    assert r.stdout.split() == ["T-202", "T-201", "T-203"]
    assert "[Forge]" not in r.stdout
