# SRS — Forge v0.3.2 + v0.3.3 (complete autonomy + modernized harness)

> **Status**: **Draft — ready for build** (2026-06-15). Continues the v0.3 program
> (`srs-v0.3.md`: Rules v0.3.0 + Autopilot v0.3.1). Two phased sub-releases:
> **v0.3.2** modernizes the harness onto current Claude primitives; **v0.3.3** turns
> the supervised autopilot into a **self-healing, self-verifying, unattended** one.
>
> **Baseline**: Forge **v0.3.1** is released — autopilot drives the 12-stage pipeline
> in-session (stop-on-gate, never forces) with a dual in-session / `claude -p`
> substrate, run-log, cancel, cost cap, capability gating.
>
> **Theme**: move autopilot from *hands-off but supervised* to *complete (local)
> autonomy* — it heals its own gate blockers, verifies its own work, and runs to
> completion within a hard budget — while replacing Forge's hand-rolled machinery with
> first-class Claude capabilities.
>
> **Ground-truth note**: the current Claude API facts here were verified against the
> `claude-api` reference at authoring time (Opus 4.8 / Haiku 4.5, 1M context, prompt
> caching, structured outputs, task budgets [beta], compaction [beta], context editing).
> Claude Code **harness** specifics (subagents/Task, hooks, permission modes) move fast,
> so **every harness task carries a "verify the current Claude API/Code surface before
> implementing" step** and a graceful-degradation requirement (REQ-NF-013).

---

## 1. Overview

### 1.1 Objective

(a) Adopt current Claude primitives in place of Forge's hand-rolled equivalents
(structured outputs, task budgets, per-stage model routing, compaction), and
(b) extend autopilot to **finish unattended**: self-heal gate blockers, self-verify
stage output, and run within a bounded budget — **without** weakening the existing
safety posture (never force a gate without explicit opt-in; everything reversible).

**Out of scope (deferred):** the hosted **Managed Agents** substrate (`--mode managed`,
Outcomes/rubrics, scheduled deployments). Captured as a future v0.3.4+ option; this
program is **local-only** (in-session + `claude -p`).

### 1.2 Phasing

| Phase | Tag | Scope | Gate |
|-------|-----|-------|------|
| **P1 Harness** | v0.3.2 | structured outputs, task budgets, per-stage model routing, compaction | none — build now |
| **P2 Autonomy** | v0.3.3 | self-heal loop, verifier subagents, `--unattended` mode, enforcing rules | P1 landed |

### 1.3 Scope

**In scope** — the two phases above + docs/tests. Each adopts a current primitive *with a
fallback* to today's behavior when the primitive is unavailable on the running
Claude/model.

**Out of scope (v0.3.4+)** — Managed Agents / hosted execution; multi-pipeline parallel
autopilot; cross-project autonomy.

### 1.4 Provenance

Continues v0.3 ("Hands-off Forge"). v0.3.2 modernizes the substrate built in v0.2
(`_orchestrate`, `_background_agent`, `_cost_cap`); v0.3.3 closes autopilot's "stops at
the first blocker" gap (the main barrier to unattended runs) and folds in **enforcing
rules** (the governance counterpart to v0.3.0's advisory rules) as an unattended guardrail.

---

## 2. Functional Requirements

### 2.1 Harness modernization (P1 — v0.3.2)

- **REQ-HARNESS-001 — Structured outputs in orchestration.** `_orchestrate.fan_out`
  (and the reviewers/extractors built on it) request schema-constrained JSON via the
  current structured-outputs API instead of parsing free-form text with retry-once +
  drop. Falls back to the existing parse/retry path when structured outputs are
  unavailable for the model in use.
- **REQ-HARNESS-002 — Run-level task budget.** `_background_agent.dispatch` accepts an
  optional token **task budget** (the model self-moderates against it) in addition to the
  `_cost_cap` $ gate; autopilot threads a whole-run budget through its dispatches.
  Degrades to cost-cap-only when the task-budget primitive is unavailable.
- **REQ-HARNESS-003 — Per-stage model routing.** `.forge/config.yaml` →
  `autopilot.models` maps stages (or stage classes) to models — e.g. a capable model for
  build/architecture, a cheap model for gate-checks/narration. Read fail-soft; absent →
  current single-model behavior.
- **REQ-HARNESS-004 — Long-run context management.** Background autopilot dispatches
  enable **compaction** (and/or context editing) so a long unattended run does not exhaust
  the context window. No-op/fallback when unavailable.

### 2.2 Complete autonomy (P2 — v0.3.3)

- **REQ-AUTO-001 — Self-heal loop.** On a **blocking** gate failure, autopilot may
  dispatch a **bounded** fix attempt through the existing Stage-11 resolver
  (`/forge:resolve`), then re-run `check-gate`; on pass it advances. Cost- and
  budget-gated; never-raises.
- **REQ-AUTO-002 — Bounded heal + escalation.** Heal attempts per stage are capped
  (`autopilot.max_heal_attempts`, default 1; 0 = today's stop-on-gate). On exhaustion
  autopilot **STOPS** and surfaces the remaining blockers — it never force-advances unless
  `autopilot.allow_force` is set with a reason (unchanged from v0.3.1).
- **REQ-AUTO-003 — Self-verification.** After a stage's gate passes, autopilot may run an
  **independent verifier** (fresh-context subagent) that checks the artifact against the
  stage's intent beyond the mechanical gate; a verifier failure is treated like a blocker
  (heal or stop). Optional, bounded, structured verdict.
- **REQ-AUTO-004 — Unattended mode.** `/forge:autopilot --unattended`: no per-stage
  checkpoints; interactive stages (SRS/spec/plan CLARIFY/CONFIRM) proceed using a supplied
  answers file (`.forge/autopilot-answers.*`) or, absent one, **reasonable defaults
  recorded as assumptions** in the run-log — never a silent guess.
- **REQ-AUTO-005 — Unattended safety envelope.** An unattended run is always bounded by:
  the run task budget (REQ-HARNESS-002) **and** the `_cost_cap`, `max_heal_attempts`,
  `max_stages`/`stop_before`, the `FORGE_NO_BACKGROUND` kill switch, and `/forge:autopilot-stop`.
  Hitting any bound STOPS cleanly with state recorded for `--resume`.
- **REQ-AUTO-006 — Enforcing rules (guardrail).** Extend v0.3.0 rules with an optional
  `enforce: true` (+ `severity`): an enforcing `glob` rule may **block** a write via
  `pre-tool-write` (exit 2) during an unattended run — the governance guardrail that makes
  hands-off execution safe. Advisory remains the default; absent/!enforce ⇒ unchanged.

---

## 3. Non-Functional Requirements

> Reuses the v0.2/v0.3 NFR set; adds three.

- **REQ-NF-013 — Verify-then-adopt + graceful degradation.** Every harness-modernization
  feature (REQ-HARNESS-001..004) MUST verify the current Claude API/Code surface at build
  time and **degrade to the pre-existing behavior** when the primitive (structured outputs,
  task budgets, compaction) is absent or errors — never a hard failure on an older
  Claude/model.
- **REQ-NF-014 — Autonomy is bounded & reversible.** No unbounded loops: self-heal,
  verification, and the whole run are budget/attempt-capped; state mutation stays on the
  sanctioned `advance_stage` path; the kill switch and cost cap always apply.
- **REQ-NF-015 — No new runtime deps; never-raises.** Hooks/scripts stay stdlib + PyYAML
  fail-soft and never-raise (inherited, restated because autonomy touches the hot path).
- Inherited: capability + cost gating, `.forge/`-only writes for background work, one
  adapter per host mechanism, ≤2000-token session-start budget, two-remote parity,
  `python3`, TDD red-first.

---

## 4. Acceptance Criteria

- **AC-HARNESS-001** — A reviewer dimension returning malformed JSON is re-requested via
  schema constraint and parsed without the retry-once-then-drop path; with structured
  outputs unavailable, the legacy path still works.
- **AC-HARNESS-003** — With `autopilot.models: {build: <capable>, eval: <cheap>}`,
  dispatches use the mapped model; absent config ⇒ single-model behavior unchanged.
- **AC-AUTO-001/002** — A forced blocking gate triggers exactly one heal attempt
  (default), and on continued failure autopilot STOPS (no force) and records the blockers;
  with `max_heal_attempts: 0` behavior equals v0.3.1 stop-on-gate.
- **AC-AUTO-004/005** — `--unattended` runs with no checkpoints, records assumptions for
  unanswered interactive prompts, and STOPS cleanly when the run task budget or cost cap is
  hit, leaving a resumable run-log.
- **AC-AUTO-006** — A rule with `enforce: true` + matching `glob` blocks a violating write
  (exit 2) only in enforcing mode; advisory rules and non-matching writes are unaffected.

---

## 5. Traceability

| REQ-ID | Task |
|--------|------|
| REQ-HARNESS-001 | T-167 |
| REQ-HARNESS-002 | T-168 |
| REQ-HARNESS-003 | T-169 |
| REQ-HARNESS-004 | T-170 |
| (P1 release) | T-171 |
| REQ-AUTO-001, 002 | T-172 |
| REQ-AUTO-003 | T-173 |
| REQ-AUTO-004, 005 | T-174 |
| REQ-AUTO-006 | T-175 |
| (P2 release) | T-176 |
