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
import subprocess
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


SESSION_LOG_SCHEMA_VERSION = 1


def _session_commands(forge_dir: Path, session_id: str) -> list[str]:
    """Distinct tool/command names used this session, from session-log.jsonl."""
    log = forge_dir / "session-log.jsonl"
    if not log.exists():
        return []
    seen: list[str] = []
    try:
        for line in log.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("session") != session_id:
                continue
            tool = row.get("tool")
            if tool and tool not in seen:
                seen.append(tool)
    except OSError:
        return seen
    return seen


def _extract_tokens(payload: dict) -> dict:
    """Pull numeric token counts from the hook payload (no PII, numbers only)."""
    raw = payload.get("usage") or payload.get("tokens") or payload.get("token_usage") or {}
    if isinstance(raw, int):
        return {"total": raw}
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, (int, float))}


def _append_session_record(
    forge_dir: Path, session_id: str, state: dict, payload: dict,
    *, lessons_added: int, files_modified: int, reflection_ref: str,
) -> None:
    """REQ-SESSIONLOG-001: append one versioned, PII-free row to .forge/session.jsonl.

    The row is self-contained — a consumer can rebuild the session timeline from
    session.jsonl alone (no prompt content, no file paths).
    """
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record = {
        "schema_version": SESSION_LOG_SCHEMA_VERSION,
        "session_id": session_id,
        "ended_at": ts,
        "stage": state.get("current_stage"),
        "project_type": state.get("project_type", "unknown"),
        "commands": _session_commands(forge_dir, session_id),
        "tokens": _extract_tokens(payload),
        "reflection_ref": reflection_ref,
        "lessons_added": lessons_added,
        "files_modified": files_modified,
    }
    try:
        forge_dir.mkdir(parents=True, exist_ok=True)
        with (forge_dir / "session.jsonl").open("a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass


def _run_signal_producers(cwd: Path, forge_dir: Path, session_id: str) -> None:
    """T-114: emit implicit lesson-signal flags, then materialize them into lessons.

    The flags use prompt text the rule-based extractor already matches, so we
    reuse extract-lessons.py (→ tasks/lessons.md) and sync-lessons.py
    (→ .forge/lessons.yaml) unchanged. Best-effort; never raises.
    """
    import _signal_producers

    emitted = _signal_producers.run(forge_dir, session_id)
    if not emitted:
        return
    scripts = _PLUGIN_DIR / "scripts"
    for name in ("extract-lessons.py", "sync-lessons.py"):
        script = scripts / name
        if not script.exists():
            continue
        try:
            subprocess.run(
                [sys.executable, str(script), "--cwd", str(cwd)],
                capture_output=True, timeout=30,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass


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

    # T-114: evaluate implicit lesson-signal producers and materialize any flags
    # into lessons before the session closes. Never block session end on failure.
    try:
        _run_signal_producers(cwd, forge_dir, session_id)
    except Exception:  # noqa: BLE001
        pass

    lessons = _recent_lessons(cwd)
    files = _recent_files(forge_dir)

    try:
        _write_session_summary(forge_dir, session_id, state, lessons, files)
    except Exception:  # noqa: BLE001
        pass  # never block session end on logging failure

    # REQ-SESSIONLOG-001: append a structured session record (reflection_ref is the
    # session_id, the join key back to the reflection in state.md / sessions/).
    try:
        _append_session_record(
            forge_dir, session_id, state, payload,
            lessons_added=len(lessons), files_modified=len(files),
            reflection_ref=session_id,
        )
    except Exception:  # noqa: BLE001
        pass

    sys.exit(0)


if __name__ == "__main__":
    run_hook(main, hook_name="session-end")
