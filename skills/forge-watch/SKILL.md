---
name: watch
description: Start the Forge Observer — a background daemon (Stage 9) that periodically
  inspects recent project activity and records findings (risky changes, missing tests,
  drift) to .forge/observer-findings.jsonl, surfaced at session start and in
  /forge:status. Use when the user types `/forge:watch`, says "watch this project",
  "keep an eye on things", "start the observer", or "monitor in the background". The
  Observer reuses one cheap-model session per the cost cap; if background agents are
  unavailable it is a clean no-op.
allowed-tools: [Bash]
---

# Forge Watch — start the Observer

Starts the Observer daemon (REQ-F-008..014). Idempotent: starting an already-running
Observer warns instead of spawning a second session. The Observer reuses a single
`claude -p` session (resumed each poll) pinned to a cheap model, and writes only to
`.forge/` — it never touches pipeline artifacts.

## When to Use

- User types `/forge:watch` or asks to monitor/watch the project in the background.
- After a long build session, to start accumulating Observer findings for next time.

## When NOT to Use

- The user wants a one-off review of changes now → that's `/forge:review`, not the
  background watcher.
- Background agents are unavailable — the command is safe (clean no-op) but pointless;
  `/forge:status` will show "Observer: not running".

## Steps

1. Start (or confirm) the Observer:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/observer.py --start --cwd "$(pwd)"
   ```
2. Present the one-line result verbatim. Possible outcomes:
   - **started** — "Observer watching (session …); N finding(s) on first poll".
   - **already_running** — it was already watching; do not start a second one.
   - **unavailable** — background agents are off; tell the user it's a no-op and that
     findings won't accrue until a background-capable `claude` is present.
3. Mention that findings surface automatically at the next session start and in
   `/forge:status`, and that `/forge:watch-stop` stops it.

## Verification

- `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/observer.py --status --cwd "$(pwd)"` shows
  "Observer: running …" after a successful start.
- Re-running `/forge:watch` reports **already_running** (no duplicate session).
