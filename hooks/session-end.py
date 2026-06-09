#!/usr/bin/env python3
"""SessionEnd hook: final state persist + session summary write.

Writes .forge/sessions/{timestamp}.md with:
  - Session ID and end time
  - Current stage and task
  - Recent lessons from tasks/lessons.md
  - Files modified from .forge/session-log.jsonl (if present)

Silent exit on non-Forge projects. Never crashes loudly.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys
from pathlib import Path

_PLUGIN_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
import _state_lib as lib
import _state_read
from _hook_runner import run_hook

def _recent_lessons(cwd: Path, limit: int = 3) -> list[str]:
    """Return the last `limit` lesson titles from tasks/lessons.md."""
    lessons_path = cwd / "tasks" / "lessons.md"
    if not lessons_path.exists():
        return []
    try:
        text = lessons_path.read_text(errors="replace")
        headings = re.findall(r"^###\s+(.+)$", text, re.MULTILINE)
        return headings[-limit:]
    except Exception:  # noqa: BLE001
        return []


def _recent_files(forge_dir: Path, limit: int = 10) -> list[str]:
    """Return last `limit` file paths from .forge/session-log.jsonl."""
    log_path = forge_dir / "session-log.jsonl"
    if not log_path.exists():
        return []
    try:
        lines = [ln for ln in log_path.read_text(errors="replace").splitlines() if ln.strip()]
        paths: list[str] = []
        for line in lines:
            try:
                record = json.loads(line)
                p = record.get("path") or record.get("file_path", "")
                if p:
                    paths.append(p)
            except json.JSONDecodeError:
                pass
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for p in paths:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        return unique[-limit:]
    except Exception:  # noqa: BLE001
        return []


def _write_session_summary(
    forge_dir: Path,
    session_id: str,
    state: dict,
    lessons: list[str],
    files: list[str],
) -> Path:
    """Write the session summary markdown and return its path."""
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_file = ts.replace(":", "-")
    sessions_dir = forge_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    stage = state.get("current_stage", "?")
    task = state.get("current_task") or "none"
    project_type = state.get("project_type", "unknown")

    lines = [
        f"# Session Summary",
        f"",
        f"- **Session ID**: {session_id}",
        f"- **End time**: {ts}",
        f"- **Project type**: {project_type}",
        f"- **Stage**: {stage}",
        f"- **Task**: {task}",
        f"",
    ]

    lines.append("## Lessons Added")
    lines.append("")
    if lessons:
        for lesson in lessons:
            lines.append(f"- {lesson}")
    else:
        lines.append("_(none this session)_")
    lines.append("")

    lines.append("## Files Modified")
    lines.append("")
    if files:
        for f in files:
            lines.append(f"- `{f}`")
    else:
        lines.append("_(session-log.jsonl not present or empty)_")
    lines.append("")

    content = "\n".join(lines)
    out_path = sessions_dir / f"{ts_file}.md"
    out_path.write_text(content)
    return out_path


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}

    cwd = Path(payload.get("cwd", os.getcwd()))
    session_id: str = payload.get("session_id", "unknown")

    if not (cwd / "pipeline" / "state.md").exists():
        sys.exit(0)

    forge_dir = cwd / ".forge"

    state, warning = _state_read.read_state_safe(str(cwd), session_id)
    if warning:
        print(warning)

    # REQ-SILENTSTATE-001: footer summarizing state-read failures this session.
    failures = _state_read.count_state_read_failures(forge_dir, session_id)
    if failures > 0:
        print(
            f"[Forge] {failures} state-read failure(s) this session — "
            f"pipeline/state.md could not be read. Run /forge:doctor."
        )

    lessons = _recent_lessons(cwd)
    files = _recent_files(forge_dir)

    try:
        _write_session_summary(forge_dir, session_id, state, lessons, files)
    except Exception:  # noqa: BLE001
        pass  # never block session end on logging failure

    sys.exit(0)


if __name__ == "__main__":
    run_hook(main, hook_name="session-end")
