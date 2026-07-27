---
name: health-check
description: Run a full self-diagnostic of the Forge plugin — executes hook unit
  tests, checks lesson-store integrity, and reports overall status as healthy,
  degraded, or failing. Use when the user types `/forge:health-check`, asks "is
  forge healthy?", "check the plugin health", "run the health check", or "are the
  hooks working?". Never silently disables hooks — any auto-disable action requires
  explicit opt-in via the `health.auto_disable_hooks` config flag in .forge/config.yaml and
  is always surfaced to events.jsonl and health-surface.txt.
allowed-tools: [Bash]
---

# Forge Health Check

Runs the Health daemon (REQ-F-022..026). Executes hook unit tests as a subprocess,
checks `.forge/lessons.yaml` for structural integrity, and produces a markdown health
report. Overall status is `healthy`, `degraded`, or `failing` based on clear rules.
Auto-disable of hooks is gated on explicit policy and is **never silent**.

## When to Use

- User types `/forge:health-check` or asks to check if the plugin/hooks are working.
- After a session where hooks behaved unexpectedly.
- Before a release to verify the plugin is in good shape.

## When NOT to Use

- The user wants to run the full test suite — use `pytest tests/` directly.
- The user wants pipeline status (stage gates) — that is `/forge:status`.

## Steps

1. Run the health check:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/health_check.py --run --cwd "$(pwd)"
   ```
2. Present the full markdown report verbatim. The report covers:
   - **Hook tests**: pass/fail counts from hook-focused pytest run.
   - **Lesson store**: any integrity issues in `.forge/lessons.yaml` (missing fields,
     out-of-range confidence, broken `[[xref]]` cross-references, malformed YAML).
   - **Status summary**: `HEALTHY`, `DEGRADED`, or `FAILING`.
3. Interpret the status for the user:
   - **HEALTHY** — all hooks pass and lesson store is clean. No action needed.
   - **DEGRADED** — hooks pass but lesson store has issues. Recommend reviewing
     `.forge/lessons.yaml` and fixing flagged entries.
   - **FAILING** — hook tests failed. Show the failing detail and suggest running
     `pytest tests/unit -k "hook or session_start"` directly for full output.
4. If `FAILING` and auto-disable fired (policy was `true`):
   - Tell the user that `.forge/health-surface.txt` has been written and will surface
     at the next session start.
   - Tell the user that `.forge/events.jsonl` has the audit record.
   - Emphasise this was NOT silent — the policy was explicitly opted into.

## Verification

- Exit code 0 = healthy, non-zero = degraded or failing.
- Re-running `/forge:health-check` after fixing tests should flip status to `HEALTHY`.
