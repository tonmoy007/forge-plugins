---
name: forge-autopilot-stop
description: Stop a running Forge autopilot. Use when the user runs /forge:autopilot-stop,
  says "stop autopilot", "cancel the autopilot", "halt the pipeline run", or "stop running
  the pipeline". Sets a stop flag the autopilot loop checks between stages, so it halts
  cleanly at the next stage boundary (the in-progress stage finishes; nothing is forced).
allowed-tools: [Bash]
---

# forge-autopilot-stop — halt a running autopilot

Requests a clean stop of an in-progress `/forge:autopilot` run. The flag is checked
**between stages**, so the current stage finishes and the loop stops before the next one —
no work is interrupted mid-stage and no gate is forced.

## When to Use

- User runs `/forge:autopilot-stop` or asks to stop/cancel the autopilot run.

## Steps

1. Request the stop:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/autopilot.py stop --cwd .
   ```
2. Confirm to the user that autopilot will halt at the next stage boundary, and that they
   can resume later with `/forge:autopilot --resume` (already-completed stages are
   skipped via `.forge/autopilot-runs.jsonl`).

## Notes

- Stopping is cooperative: it sets `stop_requested` in `.forge/autopilot-session.json`;
  the autopilot loop honors it on its next between-stages check. If no autopilot is
  running, this is a harmless no-op.
- This stops Forge's autopilot only — it is unrelated to any other tool's "autopilot".
