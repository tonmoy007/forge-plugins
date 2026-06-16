# Autopilot context management (`checkpoint → compact → continue`)

> Loaded on demand. Explains how `/forge:autopilot` survives a context boundary on a long
> hands-off run (v0.3.6, REQ-CTX-001..010). **Opt-in**: off entirely unless
> `autopilot.context_window_size` is set.

## The problem

A long autopilot run fills the context window. The user wants Forge to, at a configurable
threshold, **add/update a checkpoint → compact → continue** so the run resumes without
losing "what was I doing / what's next."

## The platform constraint (why there are two substrates)

Claude Code does **not** expose live context-usage % to hooks/scripts, and hooks **cannot
trigger** compaction — only the user (`/compact`) or the runtime (native auto-compact) can.
So a configurable in-session threshold is not measurable today (tracked upstream:
anthropics/claude-code #46695, #25689). Forge therefore handles the two substrates
differently:

| Substrate | Signal | "Compact" mechanism | Trigger |
|-----------|--------|---------------------|---------|
| **Background** (`--mode background`) | the dispatch envelope's `usage.input_tokens` (for a resumed session, ≈ current context size) | **session rotation** — discard the bloated session, start a fresh one seeded by the checkpoint + run-log | `input_tokens ≥ context_threshold_percent% × context_window_size` (configurable) |
| **In-session** (default) | none available | Claude Code's **native auto-compaction** | the runtime's own threshold (~near capacity) |

## The shared checkpoint

`.forge/autopilot-checkpoint.json` — a single, atomic (temp-then-rename),
schema-versioned snapshot written **before** a context boundary:

```json
{
  "schema_version": 1,
  "run_started_at": "2026-06-16T09:00:00Z",
  "current_stage": 6,
  "remaining_stages": [6, 7, 8],
  "dispatch_count": 4,
  "last_input_tokens": 170000,
  "last_session_id": "…",
  "next_action": "resume at stage 6 via /forge:build",
  "ts": "2026-06-16T09:42:00Z"
}
```

It records **task state, not transcript**. Stage-level **idempotency** is the existing
run-log (`.forge/autopilot-runs.jsonl` + `--resume`): completed stages are never re-run, so
resuming across a compaction boundary cannot duplicate work (guards the known
post-compaction re-execution failure mode).

## How it flows

**Background:** each `autopilot.py dispatch` returns `input_tokens`; the loop carries it
into the next dispatch as `--last-input-tokens`. When it crosses the threshold,
`should_rotate_for_context` fires (OR-combined with the count-based
`session_max_dispatches`), a checkpoint is written, and the next dispatch starts a fresh
session (`resume=None`). That fresh session *is* "compact → continue."

**In-session:** the `PreCompact` hook (`hooks/pre-compact.py`) writes/refreshes the
checkpoint when a run is active, just before native compaction. After compaction,
`SessionStart(source=compact)` re-injects a concise resume block — current stage, next
action, and an explicit "do **not** redo completed stages." The loop keeps walking the plan.

## Configuration (`.forge/config.yaml`)

```yaml
autopilot:
  context_window_size: 200000      # REQUIRED to enable — Forge cannot auto-detect the
                                   # model window; set it to your model's context size
  context_threshold_percent: 80    # rotate/checkpoint at this % of the window (default 80)
  session_max_dispatches: 8        # complementary count-based bound (still honored)
```

With `context_window_size` unset, the feature is **off** and behavior is identical to
v0.3.5 (count-based rotation only).

## Guarantees

- **Opt-in / zero-change default**, **never-raises**, `.forge`-only **atomic** writes.
- The `PreCompact` hook **never blocks** compaction (always exits 0).
- Reuses the existing safety envelope (cost cap, capability gate, kill switch, `max_stages`,
  `max_budget_usd`) and the run-log idempotency.

## Out of scope (future)

- A true in-session configurable-% trigger (waits on upstream Claude Code support).
- Programmatic API-level compaction (`context_management: compact_20260112`) — not
  injectable via `claude -p`.
