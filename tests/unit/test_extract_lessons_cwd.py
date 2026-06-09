"""T-113 / REQ-EXTRACT-CWD-001: extract-lessons.py honors the --cwd convention.

AC-EXTRACT-CWD-001a: --cwd <proj> discovers the flags file and writes lessons
                     under <proj> with no --input/--output given.
AC-EXTRACT-CWD-001b: an explicit --input overrides the cwd-derived default.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = str(ROOT / "scripts" / "extract-lessons.py")
PYTHON = sys.executable

FLAG = json.dumps({
    "ts": "2026-06-09T10:00:00Z",
    "session": "s1",
    "prompt": "don't use subprocess for coverage; use importlib instead",
}) + "\n"


def _seed_flags(proj: Path, rel: str = ".forge/correction-flags.jsonl") -> Path:
    p = proj / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(FLAG)
    (proj / "tasks").mkdir(parents=True, exist_ok=True)
    (proj / "tasks" / "lessons.md").write_text("# Lessons\n\n## Lessons\n")
    return p


def run(args: list[str], cwd: str = ".") -> subprocess.CompletedProcess:
    return subprocess.run([PYTHON, SCRIPT] + args, capture_output=True, text=True, cwd=cwd)


def test_cwd_discovers_flags_and_writes_lessons(tmp_path: Path) -> None:
    _seed_flags(tmp_path)
    r = run(["--cwd", str(tmp_path)])
    assert r.returncode == 0, r.stderr
    out = (tmp_path / "tasks" / "lessons.md").read_text()
    assert "subprocess" in out.lower()


def test_cwd_default_input_resolves_under_cwd(tmp_path: Path) -> None:
    # Run from a *different* working dir; --cwd must still find the flags.
    _seed_flags(tmp_path)
    other = tmp_path.parent
    r = run(["--cwd", str(tmp_path)], cwd=str(other))
    assert r.returncode == 0, r.stderr
    assert "subprocess" in (tmp_path / "tasks" / "lessons.md").read_text().lower()


def test_explicit_input_overrides_cwd(tmp_path: Path) -> None:
    _seed_flags(tmp_path)  # default location (should be ignored)
    explicit = tmp_path / "custom" / "flags.jsonl"
    explicit.parent.mkdir(parents=True)
    explicit.write_text(json.dumps({
        "ts": "2026-06-09T11:00:00Z", "session": "s2",
        "prompt": "never hardcode paths; use a config constant instead",
    }) + "\n")
    r = run(["--cwd", str(tmp_path), "--input", str(explicit)])
    assert r.returncode == 0, r.stderr
    out = (tmp_path / "tasks" / "lessons.md").read_text().lower()
    assert "hardcode" in out          # from the explicit file
    assert "subprocess" not in out    # the default file was not read
