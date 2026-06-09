"""T-114 / REQ-LESSON-SOURCES-001: implicit lesson-signal producers.

AC-LESSON-SOURCES-001a: each producer emits >=1 correction-flag when its signal
                        is present (one test per producer).
AC-LESSON-SOURCES-001b: at session end the flags materialize into tasks/lessons.md
                        and .forge/lessons.yaml is regenerated non-empty.
AC-LESSON-SOURCES-001c: a clean control session yields zero flags.
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
HOOKS = ROOT / "hooks"
PYTHON = sys.executable

sys.path.insert(0, str(SCRIPTS))
import _signal_producers as sp  # noqa: E402

SESSION = "sess-1"


def _ev(kind: str, detail: str = "", session: str = SESSION) -> dict:
    return {"ts": "2026-06-09T10:00:00Z", "kind": kind, "detail": detail, "session": session}


def _seed_errors(forge_dir: Path, events: list[dict]) -> None:
    forge_dir.mkdir(parents=True, exist_ok=True)
    (forge_dir / "errors.log").write_text("".join(json.dumps(e) + "\n" for e in events))


# ---------- AC-001a: one test per producer (pure functions) ----------

def test_hook_error_cluster_fires_at_5() -> None:
    events = [_ev("reflection_failed") for _ in range(5)]
    assert sp.producer_hook_error_cluster(events)["signal"] == "hook_error_cluster"


def test_hook_error_cluster_quiet_below_threshold() -> None:
    events = [_ev("reflection_failed") for _ in range(4)]
    assert sp.producer_hook_error_cluster(events) is None


def test_repeated_block_fires_at_2_same_dir() -> None:
    events = [_ev("pretool_violation", "src/ui/a.css"),
              _ev("pretool_violation", "src/ui/b.css")]
    assert sp.producer_repeated_block(events)["signal"] == "repeated_design_block"


def test_repeated_block_quiet_single() -> None:
    assert sp.producer_repeated_block([_ev("pretool_violation", "src/ui/a.css")]) is None


def test_heredoc_bypass_fires() -> None:
    assert sp.producer_heredoc_bypass([_ev("heredoc_bypass", "cat <<EOF > a.css")])


def test_gate_pass_to_wedge_fires() -> None:
    events = [_ev("gate_outcome", "stage=4 blockers=0"),
              _ev("gate_outcome", "stage=4 blockers=2")]
    assert sp.producer_gate_pass_to_wedge(events)["signal"] == "gate_pass_to_wedge"


def test_gate_pass_only_does_not_fire() -> None:
    assert sp.producer_gate_pass_to_wedge([_ev("gate_outcome", "stage=4 blockers=0")]) is None


def test_state_read_regression_fires() -> None:
    assert sp.producer_state_read_regression([_ev("state_read_failed", "boom")])


# ---------- run(): writes flags, dedups ----------

def test_run_emits_flags_and_dedups(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _seed_errors(forge, [
        *[_ev("reflection_failed") for _ in range(5)],
        _ev("state_read_failed", "boom"),
        _ev("heredoc_bypass", "cat <<EOF > a.css"),
    ])
    emitted = sp.run(forge, SESSION)
    signals = {f["signal"] for f in emitted}
    assert {"hook_error_cluster", "state_read_regression", "heredoc_bypass"} <= signals
    # every flag row carries the fields the extractor reads
    for f in emitted:
        assert f["prompt"] and f["session"] == SESSION
    # re-run is idempotent (dedup per session+signal)
    assert sp.run(forge, SESSION) == []


# ---------- AC-001c: clean control yields zero flags ----------

def test_clean_control_zero_flags(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    _seed_errors(forge, [_ev("gate_outcome", "stage=4 blockers=0")])  # a healthy pass only
    assert sp.run(forge, SESSION) == []
    assert not (forge / "correction-flags.jsonl").exists() or \
        (forge / "correction-flags.jsonl").read_text().strip() == ""


def test_clean_control_no_errors_log(tmp_path: Path) -> None:
    assert sp.run(tmp_path / ".forge", SESSION) == []


# ---------- AC-001b: end-to-end materialization via session-end ----------

def _seed_project(tmp_path: Path, events: list[dict]) -> None:
    (tmp_path / "pipeline").mkdir(parents=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "pipeline" / "state.md").write_text(
        "---\nschema_version: 1\nproject_type: unknown\ncycle: 1\n"
        "current_stage: 4\ncurrent_task: null\ncurrent_milestone: null\n"
        f"total_tasks: null\nlast_updated: {now}\nblockers: []\n---\n\n# s\n"
    )
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "lessons.md").write_text("# Lessons\n\n## Lessons\n")
    _seed_errors(tmp_path / ".forge", events)


def test_session_end_materializes_lessons(tmp_path: Path) -> None:
    _seed_project(tmp_path, [_ev("state_read_failed", "boom")])
    payload = json.dumps({"cwd": str(tmp_path), "session_id": SESSION})
    r = subprocess.run([PYTHON, str(HOOKS / "session-end.py")],
                       input=payload, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    # a flag was produced...
    flags = (tmp_path / ".forge" / "correction-flags.jsonl").read_text()
    assert "state_read_regression" in flags
    # ...and extract-lessons turned it into a lesson in tasks/lessons.md
    lessons_md = (tmp_path / "tasks" / "lessons.md").read_text().lower()
    assert "state" in lessons_md and "###" in lessons_md
    # ...and .forge/lessons.yaml was regenerated non-empty
    yaml_path = tmp_path / ".forge" / "lessons.yaml"
    assert yaml_path.exists() and yaml_path.read_text().strip()
