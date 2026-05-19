#!/usr/bin/env python3
"""Force-advance a pipeline stage despite active blockers.

Captures the list of blockers from a fresh check-gate.py run, records a lesson
(in both `.forge/lessons.yaml` and `tasks/lessons.md`) tagged `force-advance`,
advances `pipeline/state.md` via `_state_lib.advance_stage()`, and appends a
history row marked `FORCE` to the Stage History table.

The blocker criteria themselves are not "fixed" — they remain failed in
subsequent gate runs. The override is per-advancement, not per-criterion.

Usage:
    python scripts/force-advance.py --reason "<text>"
    python scripts/force-advance.py --reason "<text>" --to N
    python scripts/force-advance.py --reason "<text>" --json
    python scripts/force-advance.py --reason "<text>" --allow-no-blockers  # tests/scripting

Exit codes:
    0 — advanced successfully
    1 — error (reason too short, malformed state, etc.)
    2 — no blockers at current stage (use a clean advance instead)

Ref: T-105
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

# Make _state_lib importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _state_lib as lib  # noqa: E402

import yaml  # noqa: E402

MIN_REASON_CHARS = 10
LESSON_TAG = "force-advance"


# ---------- helpers ----------

def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")


def _get_blockers(cwd: Path, plugin_dir: Path, stage: int) -> list[dict]:
    """Run check-gate.py for the given stage and return list of blocker failures."""
    check_gate = plugin_dir / "scripts" / "check-gate.py"
    if not check_gate.exists():
        # No check-gate available; can't determine blockers. Empty list lets the
        # caller decide via --allow-no-blockers.
        return []
    proc = subprocess.run(
        [sys.executable, str(check_gate),
         "--stage", str(stage),
         "--cwd", str(cwd),
         "--plugin-dir", str(plugin_dir)],
        capture_output=True, text=True, check=False,
    )
    out = proc.stdout.strip()
    if not out.startswith("{"):
        # check-gate.py errored before producing JSON
        print(proc.stderr or out or "check-gate produced no JSON",
              file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(out)
    except json.JSONDecodeError as e:
        print(f"error: check-gate output is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    return [
        c for c in data.get("details", [])
        if not c.get("passed") and c.get("severity") == "blocker"
    ]


def _build_lesson(stage: int, reason: str, blockers: list[dict]) -> dict:
    """Construct the lesson record appended to lessons.yaml."""
    blocker_ids = [b["id"] for b in blockers if b.get("id")]
    return {
        "trigger": f"Stage {stage} advanced with unresolved blockers",
        "rule": reason,
        "why": (
            f"Force-advance was used at Stage {stage}. The blockers listed below "
            f"were acknowledged but not resolved. Revisit before treating this "
            f"stage's deliverables as complete."
        ),
        "stage": [stage],
        "project_types": [],
        "frequency": 1,
        "tags": [LESSON_TAG],
        "source": "force-advance",
        "date": _today(),
        "blockers": blocker_ids,
        "reason": reason,
    }


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically (tempfile + fsync + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _append_to_lessons_yaml(cwd: Path, lesson: dict) -> None:
    """Append a lesson to .forge/lessons.yaml."""
    path = cwd / ".forge" / "lessons.yaml"
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError:
            data = {}
    else:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("schema_version", 1)
    data.setdefault("lessons", [])
    if not isinstance(data["lessons"], list):
        data["lessons"] = []
    data["lessons"].append(lesson)
    _atomic_write(path, yaml.safe_dump(data, sort_keys=False))


def _append_to_lessons_md(cwd: Path, lesson: dict) -> None:
    """Append a markdown summary under '## Lessons' in tasks/lessons.md.

    Silently no-ops if the file is missing (uninitialized project) — the YAML
    append still ran. The next /forge:init or sync-lessons run will reconcile.
    """
    path = cwd / "tasks" / "lessons.md"
    if not path.exists():
        return
    body = path.read_text()
    stage = lesson["stage"][0]
    blockers_str = ", ".join(lesson.get("blockers", [])) or "(none reported)"
    summary = (
        f"\n### force-advance @ Stage {stage} — {lesson['date']}\n\n"
        f"- **Trigger**: {lesson['trigger']}\n"
        f"- **Reason**: {lesson['reason']}\n"
        f"- **Blockers overridden**: {blockers_str}\n"
        f"- **Tags**: {', '.join(lesson.get('tags', []))}\n"
        f"- **Source**: /forge:force-advance\n"
    )
    if "*(None yet)*" in body:
        body = body.replace("*(None yet)*", summary.lstrip(), 1)
    else:
        body = body.rstrip("\n") + summary
    _atomic_write(path, body)


def _add_history_row(cwd: str, stage: int, reason: str, blockers: list[dict]) -> None:
    """Add a stage-history row marked FORCE."""
    blocker_ids = ",".join(b["id"] for b in blockers if b.get("id")) or "(none)"
    truncated_reason = reason[:60].replace("|", "\\|")
    if len(reason) > 60:
        truncated_reason += "…"
    row = (
        f"| {stage} | | {_today()} | FORCE | "
        f"force-advanced; blockers: {blocker_ids}; reason: \"{truncated_reason}\" |"
    )
    lib.append_to_section(cwd, "Stage History", row)


# ---------- main ----------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="force-advance.py",
        description="Override a blocking gate and advance pipeline stage; records a lesson.",
    )
    parser.add_argument(
        "--reason", required=True, metavar="TEXT",
        help=f"Justification (≥ {MIN_REASON_CHARS} chars); recorded as a lesson",
    )
    parser.add_argument(
        "--cwd", default=os.getcwd(), metavar="PATH",
        help="Project root (default: cwd)",
    )
    parser.add_argument(
        "--to", type=int, default=None, metavar="N",
        help="Jump to stage N instead of current+1",
    )
    parser.add_argument(
        "--plugin-dir",
        default=str(Path(__file__).resolve().parent.parent),
        metavar="PATH",
        help="Forge plugin root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON result",
    )
    parser.add_argument(
        "--allow-no-blockers", action="store_true",
        help="Proceed even when no blockers are present (testing/scripting only)",
    )
    args = parser.parse_args(argv)

    # Validate reason
    reason = args.reason.strip()
    if len(reason) < MIN_REASON_CHARS:
        print(
            f"error: --reason must be at least {MIN_REASON_CHARS} non-whitespace characters",
            file=sys.stderr,
        )
        return 1

    cwd = Path(args.cwd).resolve()
    plugin_dir = Path(args.plugin_dir).resolve()

    # Read current state
    state = lib.read_state(str(cwd))
    current_stage = state.get("current_stage", 0)
    if not isinstance(current_stage, int):
        print(f"error: current_stage is not an integer: {current_stage!r}", file=sys.stderr)
        return 1

    # Determine blockers at the current stage
    blockers = _get_blockers(cwd, plugin_dir, current_stage)

    if not blockers and not args.allow_no_blockers:
        print(
            f"error: no blockers reported at Stage {current_stage}. "
            f"Use a clean advance (`state-manager.py advance`) instead of "
            f"force-advance.",
            file=sys.stderr,
        )
        return 2

    # Record lesson (both yaml + md)
    lesson = _build_lesson(current_stage, reason, blockers)
    _append_to_lessons_yaml(cwd, lesson)
    _append_to_lessons_md(cwd, lesson)

    # Advance stage
    new_state = lib.advance_stage(str(cwd), to=args.to)
    new_stage = new_state["current_stage"]

    # Annotate history
    _add_history_row(str(cwd), current_stage, reason, blockers)

    # Report
    result = {
        "advanced_from": current_stage,
        "advanced_to": new_stage,
        "blockers_overridden": [b["id"] for b in blockers if b.get("id")],
        "lesson_recorded": True,
        "lesson_tag": LESSON_TAG,
        "reason": reason,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        blocker_str = ", ".join(result["blockers_overridden"]) or "(none reported)"
        print(f"Stage {current_stage} → {new_stage} (force-advanced)")
        print(f"  Blockers overridden: {blocker_str}")
        print(f"  Reason: {reason!r}")
        print(f"  Lesson recorded with tag: {LESSON_TAG}")
        print(f"  Will surface in /forge:retro at end of cycle.")

    return 0


if __name__ == "__main__":
    sys.exit(main())