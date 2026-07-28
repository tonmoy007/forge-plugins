---
name: watch-stop
description: Stop the Forge Observer background daemon, preserving its last poll output
  and all recorded findings. Use when the user types `/forge:watch-stop`, says "stop
  watching", "stop the observer", "turn off monitoring", or "stop the background agent".
  Safe to run when nothing is watching (reports "not running").
allowed-tools: [Bash]
---

# Forge Watch Stop — stop the Observer

Cleanly stops the Observer daemon (REQ-F-010). The session record is marked stopped but
its **last poll output and all findings are preserved** — stopping never discards data.

## When to Use

- User types `/forge:watch-stop` or asks to stop monitoring / the observer.

## Steps

1. Stop the Observer:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/observer.py --stop --cwd "$(pwd)"
   ```
2. Present the result verbatim:
   - **stopped** — "Observer stopped; last poll output preserved".
   - **not_running** — nothing was watching; reassure the user (no error).
3. Note that recorded findings remain visible in `/forge:status` and that
   `/forge:watch` restarts monitoring.

## Verification

- `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/observer.py --status --cwd "$(pwd)"` shows
  "Observer: stopped · N finding(s) recorded" — the findings count is unchanged.
