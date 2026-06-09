"""T-119 / REQ-STAGEREFLECT-001: per-stage reflection rollup.

AC-STAGEREFLECT-001a: completing a stage produces pipeline/0X-stage/reflection.md.
AC-STAGEREFLECT-001b: the file references the contributing session_ids + gate outcome.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = str(ROOT / "scripts" / "stage-reflect.py")
PYTHON = sys.executable


def _seed_sessions(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    rows = [
        {"schema_version": 1, "session_id": "s-A", "stage": 4, "commands": ["Write"],
         "lessons_added": 1},
        {"schema_version": 1, "session_id": "s-B", "stage": 4, "commands": ["Bash", "Read"],
         "lessons_added": 2},
        {"schema_version": 1, "session_id": "s-C", "stage": 5, "commands": ["Write"],
         "lessons_added": 0},  # different stage — must be excluded
    ]
    forge.joinpath("session.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([PYTHON, SCRIPT] + args, capture_output=True, text=True, cwd=str(cwd))


def test_produces_reflection_at_canonical_path(tmp_path: Path) -> None:
    _seed_sessions(tmp_path)
    r = run(["--stage", "4", "--gate-status", "pass"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "pipeline" / "04-spec" / "reflection.md").exists()


def test_references_sessions_and_gate_outcome(tmp_path: Path) -> None:
    _seed_sessions(tmp_path)
    run(["--stage", "4", "--gate-status", "pass"], tmp_path)
    text = (tmp_path / "pipeline" / "04-spec" / "reflection.md").read_text()
    assert "s-A" in text and "s-B" in text          # contributing sessions
    assert "s-C" not in text                          # other stage excluded
    assert "pass" in text                             # gate outcome
    assert "Lessons captured this stage**: 3" in text  # 1 + 2 aggregated


def test_no_sessions_still_writes_file(tmp_path: Path) -> None:
    (tmp_path / ".forge").mkdir()
    r = run(["--stage", "7", "--gate-status", "pass"], tmp_path)
    assert r.returncode == 0
    out = (tmp_path / "pipeline" / "07-evaluation" / "reflection.md").read_text()
    assert "none recorded" in out.lower()


def test_folds_in_session_reflection_snippets(tmp_path: Path) -> None:
    _seed_sessions(tmp_path)
    (tmp_path / ".forge" / "sessions").mkdir()
    (tmp_path / ".forge" / "sessions" / "s1.md").write_text(
        "# Session Summary\nWatch: flaky migration test.\n"
    )
    run(["--stage", "4", "--gate-status", "pass"], tmp_path)
    text = (tmp_path / "pipeline" / "04-spec" / "reflection.md").read_text()
    assert "flaky migration test" in text
