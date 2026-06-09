#!/usr/bin/env python3
"""Shared state-read helper for hooks (REQ-SILENTSTATE-001 / T-106).

Hooks must never silently swallow a `pipeline/state.md` read failure. Every hook
reads state through `read_state_safe()`, which:

  1. logs a `state_read_failed` row to `.forge/errors.log` on failure, and
  2. returns a one-line user-visible warning for the FIRST failure of the session
     (deduped via the log itself, so repeated failures don't spam the user).

Gate checks (`check-gate.py`) and `/forge:doctor` / the Stop-hook footer read the
same log via `count_state_read_failures()` so a degraded session is impossible to
mistake for a healthy one.

stdlib + PyYAML only (imported transitively via _state_lib) — safe in the hot path.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _state_lib as lib  # noqa: E402

ERRORS_LOG_RELPATH = ".forge/errors.log"
STATE_READ_FAILED = "state_read_failed"


def _errors_log(forge_dir: Path) -> Path:
    return forge_dir / "errors.log"


def count_state_read_failures(forge_dir: Path, session_id: str = "") -> int:
    """Count `state_read_failed` rows in `.forge/errors.log` (optionally per session)."""
    log = _errors_log(forge_dir)
    if not log.exists():
        return 0
    n = 0
    try:
        for line in log.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("kind") != STATE_READ_FAILED:
                continue
            if session_id and row.get("session", "") != session_id:
                continue
            n += 1
    except OSError:
        return n
    return n


def log_event(forge_dir: Path, kind: str, detail: str = "", session_id: str = "") -> None:
    """Append one `{ts, kind, detail, session}` row to .forge/errors.log.

    Shared event sink for hooks — feeds the implicit lesson-signal producers
    (scripts/_signal_producers.py / T-114) as well as state-read surfacing.
    """
    try:
        forge_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        row = {"ts": ts, "kind": kind, "detail": str(detail), "session": session_id}
        with _errors_log(forge_dir).open("a") as f:
            f.write(json.dumps(row) + "\n")
    except OSError:
        pass


def _log_state_read_failure(forge_dir: Path, detail: str, session_id: str = "") -> None:
    log_event(forge_dir, STATE_READ_FAILED, detail, session_id)


def read_state_safe(cwd, session_id: str = "") -> tuple[dict, str | None]:
    """Read pipeline/state.md, surfacing failures instead of swallowing them.

    Returns (state, warning). On success warning is None. On failure state is {}
    (so `.get(...)` callers keep working) and warning is a one-line message for the
    FIRST failure this session, else None (already warned — still logged).
    """
    cwd = Path(cwd)
    forge_dir = cwd / ".forge"
    try:
        return lib.read_state(str(cwd)), None
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - state-read must fail loud
        first = count_state_read_failures(forge_dir, session_id) == 0
        _log_state_read_failure(forge_dir, str(exc), session_id)
        warning = None
        if first:
            warning = (
                f"[Forge] Warning: could not read pipeline/state.md ({exc}). "
                f"Forge state checks are degraded — run /forge:doctor."
            )
        return {}, warning
