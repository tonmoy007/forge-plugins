#!/usr/bin/env python3
"""PostToolUse hook: session logging, stage-6 activity tracking, pattern tracking.

Writes to:
  .forge/session-log.jsonl — every tool call (file, success, stage marker)
  .forge/patterns.jsonl   — sliding 3-tool window with stable signature
                            (one entry per tool call once ≥3 tools are in the log;
                            downstream `mine-skills.py` aggregates by signature)

No stdout output. Never blocks. Always exits 0.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Optional
_PLUGIN_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
import _state_lib as lib
import _state_read
from _hook_runner import run_hook

_WINDOW_SIZE = 3
_SIGNATURE_LEN = 12  # hex chars; sha1 truncated for compactness


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def _read_last_n(path: Path, n: int) -> list[dict]:
    """Read last n records from a JSONL file. Returns [] on any failure."""
    if not path.exists():
        return []
    try:
        lines = [ln for ln in path.read_text(errors="replace").splitlines() if ln.strip()]
        records: list[dict] = []
        for line in lines:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return records[-n:]
    except Exception:  # noqa: BLE001
        return []


def _window_signature(tools: list[str]) -> str:
    """Stable short signature for a tool sequence.

    Same sequence of tool names → same signature, regardless of session,
    timestamps, or which files were touched. Used downstream (T-027) to
    group occurrences and propose skills for frequently repeated patterns.
    """
    joined = "|".join(tools)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:_SIGNATURE_LEN]


def _build_window_record(
    recent: list[dict], session_id: str, ts: str
) -> Optional[dict]:
    """Build a patterns.jsonl record from the last _WINDOW_SIZE tool entries.

    Returns None if fewer than _WINDOW_SIZE entries are available, or if
    any of them has no tool name.
    """
    if len(recent) < _WINDOW_SIZE:
        return None
    window = [r.get("tool", "") for r in recent[-_WINDOW_SIZE:]]
    if any(not t for t in window):
        return None
    return {
        "schema_version": 1,  # REQ-PATTERN-001 — see references/pattern-schema.md
        "ts": ts,
        "kind": f"tool_seq_{_WINDOW_SIZE}",
        "tools": window,
        "signature": _window_signature(window),
        "session": session_id,
    }


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}

    tool_name: str = payload.get("tool_name", "")
    tool_input_raw = payload.get("tool_input", {})
    tool_input: dict = tool_input_raw if isinstance(tool_input_raw, dict) else {}
    tool_response_raw = payload.get("tool_response", {})
    tool_response: dict = tool_response_raw if isinstance(tool_response_raw, dict) else {}
    session_id: str = payload.get("session_id", "")
    cwd = Path(payload.get("cwd", os.getcwd()))

    forge_dir = cwd / ".forge"
    log_path = forge_dir / "session-log.jsonl"

    # Best-effort stage read (skip if no state file)
    current_stage = 0
    if (cwd / "pipeline" / "state.md").exists():
        state, warning = _state_read.read_state_safe(str(cwd), session_id)
        if warning:
            print(warning)
        current_stage = state.get("current_stage", 0)

    # Step 1: Append session log entry
    file_path = tool_input.get("file_path", "")
    log_entry: dict = {
        "ts": _now(),
        "session": session_id,
        "tool": tool_name,
        "file": file_path,
        "success": bool(tool_response.get("success", True)),
    }
    if current_stage == 6 and tool_name == "Write":
        log_entry["build_stage"] = True

    try:
        _append_jsonl(log_path, log_entry)
    except Exception:  # noqa: BLE001
        pass

    # Step 1b: T-114 heredoc-bypass signal — a bash heredoc writing a UI file
    # after the design-system check already flagged a violation this session is
    # the EF-003 "route around the hook" pattern.
    if tool_name == "Bash":
        command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
        ui_ext = (".css", ".scss", ".tsx", ".jsx", ".vue", ".html")
        if "<<" in command and any(ext in command for ext in ui_ext):
            try:
                import _signal_producers
                prior_violation = any(
                    e.get("kind") == "pretool_violation"
                    for e in _signal_producers.read_events(forge_dir, session_id)
                )
                if prior_violation:
                    _state_read.log_event(forge_dir, "heredoc_bypass", command[:120], session_id)
            except Exception:  # noqa: BLE001 - signal logging must never break the hook
                pass

    # Step 2: Pattern tracking — sliding 3-tool window with stable signature
    try:
        recent = _read_last_n(log_path, _WINDOW_SIZE)
        record = _build_window_record(recent, session_id, _now())
        if record is not None:
            _append_jsonl(forge_dir / "patterns.jsonl", record)
    except Exception:  # noqa: BLE001
        pass

    sys.exit(0)


if __name__ == "__main__":
    run_hook(main, hook_name="post-tool-use")