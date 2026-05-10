#!/usr/bin/env python3
"""PostToolUse hook: session logging, stage-6 activity tracking, pattern counting.

Writes to:
  .forge/session-log.jsonl — every tool call (file, success, stage marker)
  .forge/patterns.jsonl   — when repeated tool sequences are detected

No stdout output. Never blocks. Always exits 0.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

_PLUGIN_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
import _state_lib as lib


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


def _detect_pattern(recent: list[dict]) -> bool:
    """Return True if recent tool calls form a repeated sequence worth noting.

    Detects two patterns:
      - Same tool 3+ times in a row (e.g., Read→Read→Read)
      - Alternating 2-tool cycle (e.g., Read→Edit→Read→Edit)
    """
    if len(recent) < 3:
        return False
    tools = [r.get("tool", "") for r in recent]
    # Single tool repeated 3+ consecutive times
    if tools[-3] == tools[-2] == tools[-1]:
        return True
    # 2-tool alternating cycle (need 4 entries)
    if len(tools) >= 4 and tools[-4:-2] == tools[-2:]:
        return True
    return False


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}

    tool_name: str = payload.get("tool_name", "")
    tool_input: dict = payload.get("tool_input") or {}
    tool_response: dict = payload.get("tool_response") or {}
    session_id: str = payload.get("session_id", "")
    cwd = Path(payload.get("cwd", os.getcwd()))

    forge_dir = cwd / ".forge"
    log_path = forge_dir / "session-log.jsonl"

    # Best-effort stage read (skip if no state file)
    current_stage = 0
    if (cwd / "pipeline" / "state.md").exists():
        try:
            state = lib.read_state(str(cwd))
            current_stage = state.get("current_stage", 0)
        except Exception:  # noqa: BLE001
            pass

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

    # Step 2: Pattern tracking
    try:
        recent = _read_last_n(log_path, 5)
        if _detect_pattern(recent):
            _append_jsonl(
                forge_dir / "patterns.jsonl",
                {
                    "ts": _now(),
                    "kind": "tool_seq",
                    "tools": [r.get("tool", "") for r in recent],
                    "session": session_id,
                },
            )
    except Exception:  # noqa: BLE001
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
