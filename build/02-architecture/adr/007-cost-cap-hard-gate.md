# ADR-007: Cost Cap Is a Hard Prerequisite Gate on a Two-Phase Ledger

**Status**: Accepted
**Date**: 2026-06-10

## Context

v0.2 lets Forge spend money on the user's behalf: every daemon poll and every
orchestrated subagent is a billable agent run. Background spend is invisible (it
happens off the foreground), so an unbounded or mis-estimated loop could quietly run
up cost. The SRS makes cost control a first-class constraint: `_cost_cap.py` is a
**hard prerequisite** (REQ-F-007, C-004) — no daemon/orchestration feature integrates
until it and its tests are green — and asks (OQ-004) whether the ledger records
*estimated* (model-priced) or *actual* (API-reported) cost.

## Decision

**`hooks/_cost_cap.py` enforces a configurable budget pre-dispatch on an append-only
`.forge/cost-ledger.jsonl`, using two-phase accounting: estimate at dispatch,
reconcile to actual on return. No dispatch is wired anywhere until the cap module +
tests are green.**

- **Two-phase ledger** (OQ-004): each entry carries `estimated_usd` (token counts ×
  a model price table, written at dispatch) and `actual_usd` (from the agent's
  `--output-format json` usage, written on return; `null` until then).
- **Conservative enforcement**: caps are checked on the running sum of `actual_usd`
  where present, else `estimated_usd` — so an in-flight run counts at its estimate.
- **Caps**: daily `cost_cap.daily_usd` (default $0.50) and optional rolling-30-day
  `cost_cap.monthly_usd`, from `.forge/config.yaml`.
- **Local + pre-dispatch**: enforcement is a single ledger read + sum, no network —
  preserving the foreground latency budget (REQ-NF-004).
- **Over cap → skip + log, never raise**: the dispatch becomes a no-op and an event
  lands in `.forge/events.jsonl`, surfaced at the next session start.

## Rationale

1. **Invisible spend needs a visible guard.** A human-readable ledger (REQ-NF-008)
   plus a hard pre-dispatch cap is the minimum responsible design for autonomous
   background billing.
2. **Estimate-then-reconcile** gives a real-time guard (you cannot know actual cost
   before the run) while keeping the ledger honest after the fact.
3. **Hard prerequisite ordering** prevents a half-built system from ever dispatching
   uncapped — the gate is structural, not a runtime flag.
4. **It is also the measurement instrument** for the spike's O-2 numbers
   (REQ-F-028): completion rate + cost/session over ≥5 sessions are read straight off
   this ledger.

## Alternatives considered

- **Estimated-only ledger.** Simpler, but never converges to truth; rejected because
  O-2 needs real per-session cost and users deserve accurate history.
- **Actual-only (post-hoc) accounting.** Cannot guard *before* spend — useless as a
  pre-dispatch cap; rejected.
- **A soft warning instead of a hard skip.** Rejected: invisible background spend
  with only a warning is how you wake up to a surprise bill.

## Consequences

- `_cost_cap.py` lands in **P0**, before any daemon (P1) or orchestration (P2) wiring.
- The model price table is a small, versioned constant in the adapter; updating
  prices touches one file.
- Every dispatch path (background and orchestration) must call the cap — enforced by
  routing all spend through the two adapters (`_background_agent.py`,
  `_orchestrate.py`), which are the only callers of `_cost_cap.py`.
