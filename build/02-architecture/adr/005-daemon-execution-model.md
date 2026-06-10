# ADR-005: Daemons Are Detached One-Shot Dispatches, Not Resident Processes

**Status**: Accepted — spike O-1 **confirmed** (2026-06-10)
**Date**: 2026-06-10
**Supersedes the assumption in**: the 2026-05-14 v0.2 draft (`claude --bg` daemons)

## Context

v0.2 introduces three "daemons" — Observer (REQ-F-008..014), Dreamer
(REQ-F-015..021), Health (REQ-F-022..026). The word *daemon* implies a long-lived
resident process. But Forge is a **hook-based Claude Code plugin**: it owns no
process of its own. Hooks are short-lived subprocesses Claude Code spawns per
lifecycle event and reaps immediately. There is nowhere for a resident daemon to
live without Forge shipping and supervising its own OS-level service — which would
break "no server" (REQ-F-052 spirit), the stdlib-only constraint, and Windows/POSIX
portability (NFR-COMPAT-001).

The P0 spike (`build/06-evaluation/spike-background-agents.md`) established the real
host surface in Claude Code v2.1.169:
- `claude agents --json [--cwd]` — lists/monitors background sessions, headless,
  scriptable. **Proven.**
- `claude -p` — headless one-shot ("print") agent run. **The dispatch path
  (confirmed by O-1 in the Decision below).**

The draft's `claude --bg` / `/bg` / `/tasks` API does not exist.

We also already have a precedent: ADR-004 made the Stop-hook skill-miner a
**detached subprocess that does not block** the hook. v0.2 needs to generalize that
exact pattern, not invent a new execution model.

## Decision

**A Forge daemon is a recurring _detached one-shot_ `claude -p` agent run,
dispatched from a foreground hook when a poll is due, that writes its findings to
`.forge/*.jsonl` and exits. Monitoring uses `claude agents --json [--cwd]`. There is
no Forge-owned supervisor thread or resident process.**

Concretely:
- **Scheduling is lazy + event-driven**, not timer-based: foreground hooks
  (`session-start`, `post-tool-use`) check `now - last_poll > interval` and dispatch
  only when due and under the cost cap. The hook never waits on the agent.
- **The nightly Dreamer** may use host cron *optionally and documented* — but never
  requires it; absent cron, it runs lazily on the day's first session plus the
  manual `/forge:dreamer-run`.
- **All dispatch goes through the single adapter** `hooks/_background_agent.py`
  (REQ-NF-010), so any future host-API change touches one file.
- **Correlation** (O-1 confirmed): the dispatch's `--output-format json` envelope
  returns a `session_id`; Forge captures it and persists it in
  `.forge/observer-session.json`. A `claude -p` run does **not** appear in
  `claude agents --json` (monitor-only surface), so the returned `session_id` is the
  join key — not a hand-rolled id and not the monitor list.
- **Session reuse is mandatory (O-2 cost):** each daemon reuses its one session via
  `claude -p --resume <session_id>`. A fresh session bills the ~42k-token system
  prompt as `cache_creation` (~$0.053); `--resume` makes it a `cache_read`
  (~$0.0046, 9%). Only the first poll/day pays the tax. If `--resume` continuity
  breaks, the adapter starts a fresh session, pays the tax once, and re-persists the
  new `session_id`.

## Rationale

1. **Matches the host's actual surface** — `claude -p` is a one-shot, so the unit of
   work is naturally one-shot. Fighting that with a fake resident loop adds failure
   modes for no gain.
2. **Preserves the latency budget** (REQ-NF-004): dispatch is fire-and-forget; the
   hot path is a local file read + a `Popen`, well under p95 ≤ 200ms.
3. **Inherits v0.1's safety** — findings are data, promoted only through the existing
   proposal→validator→executor boundary (REQ-F-013). No daemon can corrupt Tier-2
   state because it has no write path to it.
4. **Degrades cleanly** (REQ-NF-006): no capability → no dispatch → foreground is
   byte-identical to v0.1.

## Alternatives considered

- **A user-started long-lived `claude agents` session** (foreground-ish, driven by
  `/forge:watch`). This is the **fallback if O-1 shows detached `claude -p` is
  unreliable**. Kept as a documented Plan B precisely because the call site is the
  one adapter — switching costs nothing elsewhere.
- **A Forge-shipped OS service / cron-required model.** Rejected: server-ful, breaks
  portability and "no server," needs privileged install.
- **An in-hook synchronous poll.** Rejected: blocks the foreground, blows the
  latency budget, and serializes the user behind the agent.

## Consequences

- O-1 (headless dispatch) is **resolved** (2026-06-10). The only P1-gating unknown
  left is O-2's completion-rate (≥90% over ≥5 real sessions) — a P0 measurement.
- "Daemon" in all v0.2 docs means *recurring detached dispatch*, not a process —
  reviewers and `/forge:status` copy should reflect that.
- A missed/abandoned run is self-healing: the next due poll re-dispatches (bounded by
  the cost cap), and the abandonment is logged to `.forge/events.jsonl`.
