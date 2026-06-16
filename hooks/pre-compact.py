#!/usr/bin/env python3
"""PreCompact hook — checkpoint an active autopilot run before context compaction.

Claude Code fires PreCompact just before it compacts the conversation (automatically
near context capacity, or on `/compact`). Forge cannot trigger or measure compaction,
but it CAN make a long *in-session* autopilot run survive it: when a run is active, write
or refresh the durable checkpoint (`.forge/autopilot-checkpoint.json`) so that
`SessionStart(source=compact)` can re-inject "resume at stage N" afterwards
(REQ-CTX-006, v0.3.6). Stage-level idempotency stays in the run-log, so resume never
redoes completed work.

Best-effort: this hook **never blocks** (always exits 0 — only exit 2 would block
compaction) and **never raises**. Compaction must proceed regardless of whether the
checkpoint write succeeds.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_PLUGIN_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))


def _autopilot_active(forge_dir: Path) -> bool:
    """True only when an autopilot run is currently running. Reads the session JSON
    directly (no heavy imports) so a missing/garbage file is a clean no-op. Never raises.
    """
    try:
        data = json.loads((forge_dir / "autopilot-session.json").read_text())
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("status") == "running"


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}

    cwd = Path(payload.get("cwd", os.getcwd()))
    forge_dir = cwd / ".forge"

    # No-op on non-Forge projects or when no autopilot run is active.
    if not (cwd / "pipeline" / "state.md").exists() or not _autopilot_active(forge_dir):
        sys.exit(0)

    # Write the checkpoint only when we actually need it — keeps the heavy autopilot
    # import (which pulls PyYAML via _state_lib) off the path for inactive sessions.
    try:
        import autopilot  # noqa: E402
        autopilot.build_and_write_checkpoint(cwd)
    except Exception:  # noqa: BLE001 — checkpoint is best-effort; never block compaction
        pass

    sys.exit(0)


if __name__ == "__main__":
    from _hook_runner import run_hook

    run_hook(main, hook_name="pre-compact")
