# SRS — Forge v0.2 (program scope, phased)

> **Status**: **Reviewed — ready for Stage 3** (validated 2026-06-10; P0 spike folded
> in). Composes with `srs.md` and the
> v0.1.x deltas. Formalized into `build/` from the abandoned dogfood draft on
> branch `v0.2-background-daemons` (`pipeline/01-srs/srs.md`, 2026-05-14),
> refreshed to the current baseline and broadened to the **full v0.2 backlog**.
>
> **Baseline**: Forge **v0.1.7** is released — `main` at `566532e`, **1076 tests**
> green, 10 project-type profiles, hardened CI, `bump-version.py`. v0.2 builds on
> that, additively.
>
> **Theme**: move Forge from *a pipeline you drive* to *a system that works
> alongside you* — background intelligence (daemons), parallel agent
> orchestration, brownfield adoption, and sprint cadence.

---

## 1. Overview

### 1.1 Objective

Add four capability areas on top of v0.1's working foundation, **without breaking
any v0.1 behavior** and **without making any of it mandatory**: (a) background
daemons, (b) multi-agent orchestration primitives, (c) brownfield onboarding,
(d) sprint workflow. Everything degrades to a clean no-op where the underlying
capability (the Claude Code background-agent API; agent teams) is unavailable.

### 1.2 Phasing

v0.2 is too large for one release. It ships as phased sub-releases, each its own
tag, each independently green:

| Phase | Tag | Scope | Gate |
|-------|-----|-------|------|
| **P0 Foundation + Spike** | v0.2.0 | capability probe, background adapter, cost cap, and the **feasibility spike** | spike result decides P1 |
| **P1 Daemons** | v0.2.1 | Observer, Dreamer, Health Daemon, async skill-miner | **spike must pass** (else P1 deferred) |
| **P2 Orchestration + Brownfield** | v0.2.2 | in-session multi-agent orchestration primitives + brownfield onboarding (EF-014) | orchestration primitive lands first |
| **P3 Sprint** | v0.2.3 | sprint planning + per-sprint review over the DAG (EF-011) | — |

Minor v0.2 items (log rotation, `/forge:why` LLM fallback, `set-profile`, `~/.forge`
sync, opt-in telemetry, Windows exploration) attach to the phase they fit.

### 1.3 Scope

**In scope (the full v0.2 backlog)** — the four areas above + the minor items in §2.10.

**Out of scope (v0.3+)** — Python package extraction; IR-Core / event-sourcing
rework; multi-tenancy; ACP / standalone CLI; channel adapters; third-party
integrations. (Carried from the original draft's deferrals.)

### 1.4 Backlog provenance (tester feedback closure)

v0.2 closes the two tester findings explicitly deferred from v0.1.x:

| Finding | Becomes | Phase |
|---------|---------|-------|
| **EF-014** — brownfield: fan out agents to extract current project state | REQ-F-038..043 (§2.8) | P2 |
| **EF-011** — sprint planning + per-sprint review | REQ-F-044..048 (§2.9) | P3 |

---

## 2. Functional Requirements

> **[SPIKE-GATED]** requirements (P1) are conditional on the T-spike (REQ-F-028)
> passing. If it fails, P1 is deferred and v0.2.0 ships P0 only.

### 2.1 Foundation (P0 — not gated)

- **REQ-F-001 — Background capability probe.** `session-start.py` probes for
  background-agent capability and writes `.forge/capabilities.json`
  (`{"forge_background_available": bool}`). No error on machines without it.
- **REQ-F-002 — Background adapter module.** A single `hooks/_background_agent.py`
  wraps **every** `claude agents …` (monitor) / `claude -p` (dispatch) call; no other
  file invokes the background API directly (so a host-API change touches one file).
  Dispatch uses `claude -p --output-format json`, **captures the returned
  `session_id`**, and **reuses that session via `--resume` for subsequent polls** —
  mandatory, because a fresh session pays a ~$0.05 cache-creation tax vs ~$0.005
  resumed (spike O-2). Correlation is by the captured `session_id`, not
  `claude agents --json` (a `-p` run does not appear there). *(The spike corrected the
  surface from the draft's assumed `claude --bg`/`/bg`/`/tasks`; the probe half is
  built — see `build/06-evaluation/spike-background-agents.md`.)*
- **REQ-F-003 — Degraded no-ops.** When capability is false, every adapter call
  returns `{"status":"unavailable","reason":...}` and never raises.
- **REQ-F-004 — Daily cost cap.** `hooks/_cost_cap.py` enforces a configurable
  daily budget (default $0.50/day, `.forge/config.yaml` → `cost_cap.daily_usd`).
- **REQ-F-005 — Monthly cost cap.** Optional rolling-30-day budget
  (`cost_cap.monthly_usd`).
- **REQ-F-006 — Cost ledger.** Background costs append to
  `.forge/cost-ledger.jsonl` (`timestamp, feature, session_id, input_tokens,
  output_tokens, estimated_usd, actual_usd`). `actual_usd` is the
  **API-reported `total_cost_usd`** from the dispatch's `--output-format json`
  envelope (spike O-2); `estimated_usd` is the conservative pre-dispatch floor used
  only to gate spend before the run.
- **REQ-F-007 — Cost cap is a hard prerequisite.** No daemon feature integrates
  until `_cost_cap.py` + its tests are green.

### 2.2 Feasibility spike (P0)

- **REQ-F-028 — Spike + reliability gate.** Convert the skill-miner step in
  `stop-reflect.py` to a background subagent and evaluate over ≥5 sessions. If
  completion rate < 90% **or** est. cost > $0.10/session typical, the gate fails
  and all [SPIKE-GATED] (P1) requirements defer. Report:
  `build/06-evaluation/spike-background-agents.md` (sessions, completion rate,
  cost/session, verdict). **Status (2026-06-10): verdict PASS.** Monitor
  (`claude agents --json`) and dispatch (`claude -p --output-format json`) are both
  proven headless. **O-1 (dispatch) RESOLVED** — capture the returned `session_id`,
  reuse it via `--resume`. **O-2 cost RESOLVED** — measured **$0.053 fresh /
  $0.0046 resumed** per dispatch (the ~42k-token system prompt is a one-time
  cache-creation tax per session; reuse makes it a cache read). **Only the O-2
  completion-rate number remains OPEN** (≥90% over ≥5 real sessions), measured inside
  P0 once `_cost_cap.py` lands; it alone gates P1. If completion fails, v0.2.0 ships
  foundation-only.

### 2.3 Observer daemon (P1) [SPIKE-GATED]

- **REQ-F-008 — `/forge:watch`** spawns the Observer as a background agent;
  idempotent (no double-spawn; warns if already running).
- **REQ-F-009 — Observer session record** → `.forge/observer-session.json`.
- **REQ-F-010 — `/forge:watch-stop`** cleanly terminates Observer, preserving its
  last poll output.
- **REQ-F-011 — Findings output** → `.forge/observer-findings.jsonl`
  (`timestamp, severity, source, message`).
- **REQ-F-012 — Unread findings at session start**, within the v0.1 2000-token
  context budget.
- **REQ-F-013 — Proposal boundary.** Observer never writes pipeline artifacts
  directly; all state-mutating output flows through the existing
  proposal/validator/executor boundary.
- **REQ-F-014 — Stage-9 status line** in `/forge:status` (running state, session,
  last poll, unread count).

### 2.4 Dreamer daemon (P1) [SPIKE-GATED]

- **REQ-F-015 — `/forge:dreamer-run`** (manual trigger) consolidates lessons now.
- **REQ-F-016 — Daily digest** → `pipeline/log/daily-YYYY-MM-DD.md` (reviewed,
  confidence changes, duplicates, contradictions, dormant count); idempotent/day.
- **REQ-F-017 — Confidence decay**; lessons below 0.3 → `status: dormant`.
- **REQ-F-018 — Duplicate detection** (string + token-overlap on `trigger`+`rule`);
  flagged for human review, **never auto-merged**.
- **REQ-F-019 — Contradiction detection** (same trigger, conflicting rule);
  flagged, **never auto-resolved**.
- **REQ-F-020 — Nightly schedule** via the background adapter (REQ-F-002 — detached
  `claude -p`, session reused via `--resume`; *not* the draft's `claude --bg`);
  manual-only when unavailable. Dispatch + correlation resolved (OQ-008 / spike O-1).
- **REQ-F-021 — Atomic writes** to `.forge/lessons.yaml` (temp + rename).

### 2.5 Health daemon (P1) [SPIKE-GATED]

- **REQ-F-022 — `/forge:health-check`** (manual) → report with hook-test results,
  lesson integrity, overall status (`healthy|degraded|failing`).
- **REQ-F-023 — Hook unit-test execution** summarized in the report.
- **REQ-F-024 — Lesson integrity checks** (malformed YAML, broken xrefs,
  out-of-range confidence, missing required fields).
- **REQ-F-025 — Auto-disable requires explicit policy** (`auto_disable_hooks:true`).
- **REQ-F-026 — No silent auto-disable** — logged to `.forge/events.jsonl` +
  surfaced next session start.

### 2.6 Async skill-miner (P1) [SPIKE-GATED]

- **REQ-F-027 — Background skill-mining.** When capability is true, `stop-reflect.py`
  offloads skill-mining to a background subagent (proposals land in
  `.forge/proposals.jsonl`); inline fallback otherwise.

### 2.7 Multi-agent orchestration primitives (P2)

> The foundation brownfield + parallel-review features build on. **In-session,
> deterministic** fan-out — NOT dependent on the background-agent API (distinct
> from P1 daemons). Reserve the `G-MAS-*` / `G7-MAS-*` gate families already
> placeholdered in v0.1.3 docs.

- **REQ-F-031 — Orchestration helper.** A `scripts/_orchestrate.py` primitive that
  spawns N subagents over a work-list, collects **structured** results, and
  returns them deterministically (parallel where the host supports it, sequential
  fallback otherwise). One module wraps the agent-team/subagent mechanism (mirrors
  the adapter discipline of REQ-F-002).
- **REQ-F-032 — Degraded sequential fallback.** When agent-team/parallel spawn is
  unavailable, the primitive runs the work-list sequentially with identical
  outputs — no feature loss, only wall-clock.
- **REQ-F-033 — Bounded fan-out + cost.** Concurrency and total agent count are
  capped (config `orchestration.max_parallel`, default small); every spawned agent
  routes its cost through `_cost_cap.py` (REQ-F-004/006).
- **REQ-F-034 — Parallel reviewers (first consumer).** A `/forge:review` mode (or
  the existing eval path) fans out independent review dimensions and synthesizes a
  deduplicated report — proving the primitive end-to-end.
- **REQ-F-035 — Proposal boundary.** Orchestrated agents never mutate pipeline
  state directly; results flow through the proposal/validator/executor boundary.

### 2.8 Brownfield onboarding (P2 — closes EF-014)

- **REQ-F-038 — `/forge:adopt`** runs Forge against an **existing** codebase: fans
  out agents (via REQ-F-031) to extract current project state.
- **REQ-F-039 — Reverse-engineered artifacts.** Adopt produces a seeded
  `pipeline/state.md`, a detected `project_type` (reusing `detect-project-type.py`),
  and draft reverse-engineered artifacts: an inferred REQ list
  (`pipeline/01-srs/srs.md` draft) and an architecture map
  (`pipeline/03-architecture/architecture.md` draft), each clearly marked
  **inferred / needs human confirmation**.
- **REQ-F-040 — Read-only by default.** Adopt never modifies the user's source; it
  only writes under `pipeline/` and `.forge/`. A `--dry-run` previews what it would
  create (mirrors `init --dry-run`, REQ-UX-001).
- **REQ-F-041 — Confidence + provenance.** Each inferred item carries a confidence
  and the files it was derived from, so a human can audit it.
- **REQ-F-042 — Resumes the normal pipeline.** After adopt, the project enters the
  standard 12-stage flow at the appropriate stage with gates intact.
- **REQ-F-043 — Graceful scale limits.** Adopt bounds how many files/agents it
  fans out (config) and `log()`s what it sampled vs. skipped — no silent
  truncation.

### 2.9 Sprint workflow (P3 — closes EF-011)

- **REQ-F-044 — `/forge:sprint plan`** groups ready tasks from the task DAG into a
  sprint (by milestone / dependency order / a target size), writing
  `pipeline/05-plan/sprint-NN.md`.
- **REQ-F-045 — Sprint view over the DAG**, not a parallel tracker — sprints
  reference T-IDs; the DAG stays the single source of truth.
- **REQ-F-046 — `/forge:sprint review`** produces a per-sprint retro (done vs
  carried-over, blockers, lessons) → `pipeline/12-release/sprint-NN-review.md`.
- **REQ-F-047 — Carry-over** of unfinished tasks into the next sprint, preserving
  their T-IDs and history.
- **REQ-F-048 — Optional.** Sprint cadence is opt-in; projects that don't use it
  see no change.

### 2.10 Minor v0.2 items (attach to a phase)

- **REQ-F-049 — Hook-error log rotation** (`.forge/hook-errors.log`) — paired with
  the daemon-bus rotation policy (OQ-2 from v0.1.3). [P1]
- **REQ-F-050 — `/forge:why` LLM fallback** for unknown IDs via a subagent, when
  deterministic lookup misses (OQ-3). [P2, uses REQ-F-031]
- **REQ-F-051 — `/forge:set-profile`** runtime profile switching (the long-standing
  T-111 candidate). [P0/P1]
- **REQ-F-052 — `~/.forge` sync guidance** across machines (Q-002) — at minimum a
  documented, conflict-safe layout; no server. [P3]
- **REQ-F-053 — Opt-in skill-mining telemetry** (Q-004), default **off**, local
  only unless the user explicitly enables export. [P3]
- **REQ-F-054 — Windows support exploration** — replace the POSIX-only `SIGALRM`
  hook-timeout path (NFR-COMPAT-001) with a cross-platform mechanism, or document
  the limitation precisely. [P3, spike-style]

### 2.11 Release (per phase)

- **REQ-F-029 — CHANGELOG per phase tag** (`[0.2.0]`…`[0.2.3]`) documenting scope +
  the spike verdict where relevant.
- **REQ-F-030 — Full suite green.** Every phase ships only with the **entire
  current suite** (≥1076 tests at v0.1.7 baseline, plus new) passing, 0 regressions.

---

## 3. Non-Functional Requirements

- **REQ-NF-001 — v0.1 backward compatibility.** Identical behavior for users
  without background/agent-team capability; nothing removed or altered.
- **REQ-NF-002 — Additive + schema-compatible.** Existing artifacts
  (`state.md`, `lessons.yaml`, `patterns.jsonl`, …) stay v0.1-schema-compatible.
- **REQ-NF-003 — No new runtime deps.** Python 3.11+ stdlib + PyYAML only.
- **REQ-NF-004 — Foreground isolation.** Background/orchestration work never
  breaches the v0.1 hook latency budget (session-start p95 ≤ 200ms).
- **REQ-NF-005 — Proposal/validator boundary** for all daemon + orchestrated
  output; no direct writes to pipeline artifacts.
- **REQ-NF-006 — Graceful degradation.** Every capability-dependent feature is a
  silent no-op (daemons) or sequential fallback (orchestration) when unavailable —
  no errors, no tracebacks.
- **REQ-NF-007 — Atomic writes** for all shared mutable files.
- **REQ-NF-008 — Cost transparency** via the human-readable cost ledger.
- **REQ-NF-009 — Determinism.** Orchestration results are deterministic given the
  same inputs (sequential and parallel paths produce the same synthesized output).
- **REQ-NF-010 — One adapter per external mechanism.** `_background_agent.py`
  (background API) and `_orchestrate.py` (agent teams/subagents) are the **only**
  call sites for their respective host mechanisms.

---

## 4. Constraints

| ID | Constraint |
|----|-----------|
| C-001 | Background agents have **shipped** (command `claude agents`, Claude Code v2.1.169 — the spike retired the "is it usable?" risk). P1 is gated not on capability *existence* but on the spike's **reliability/cost** numbers (REQ-F-028 O-2) and **headless dispatch** (OQ-008/O-1) clearing |
| C-002 | Python 3.11+ stdlib + PyYAML only — no new pip deps |
| C-003 | One adapter file per host mechanism (REQ-NF-010) |
| C-004 | Cost cap (`_cost_cap.py`) is a hard prerequisite for any daemon/orchestration feature |
| C-005 | Branch from current `main` (v0.1.7, `566532e`); per-phase tags `v0.2.0`…`v0.2.3` via the standard release flow + `bump-version.py` |
| C-006 | Task IDs continue from **T-136** in `build/04-plan/task-dag-v0.2.md` (Stage 5); this SRS maps REQs to phases/milestones, not task numbers |

---

## 5. Assumptions

| ID | Assumption |
|----|-----------|
| A-001 | The Claude Code background-agent API is reachable on at least some plans during P1 development (spike confirms) |
| A-002 | The v0.1 proposal/validator/executor boundary is sufficient for daemon + orchestrated output without redesign |
| A-003 | Agent-team / subagent fan-out is available in-session for P2 (the spawn mechanism the orchestration primitive wraps) |
| A-004 | Duplicate detection uses word-level token overlap (no embeddings) |
| A-005 | Brownfield inference is best-effort and human-confirmed — Forge proposes, the user disposes |
| A-006 | A fresh dispatched session costs ~$0.05 (one-time ~42k-token cache-creation tax); reuse via `--resume` drops it to ~$0.005. Daemons MUST reuse one session — naive per-poll fresh dispatch (~10×) breaks the budget. (Spike O-2, 2026-06-10.) |

---

## 6. Open Questions (→ resolve in Stage 3 architecture)

| ID | Question | Priority |
|----|----------|----------|
| OQ-001 | **Daemon execution model** — how does a "background daemon" actually run in a hook-based plugin, given the *shipped* surface? Candidates: a user-started long-lived `claude agents` session; per-event detached `claude -p` dispatched from a hook; or host-level cron. (The draft's `claude --bg` is dead — see spike.) This is the central P1 architecture decision; depends on OQ-008/O-1. | **High** |
| OQ-002 | Orchestration primitive — does it wrap the Agent tool / agent-teams, or shell out? What's the structured-output contract? | **High** |
| OQ-003 | Observer polling interval — fixed, configurable, event-driven? | High |
| OQ-004 | ✅ **RESOLVED** (spike O-2): **actual** API-reported `total_cost_usd` is in the dispatch JSON; ledger records actuals, cap pre-check uses a conservative floor constant. | ~~Medium~~ |
| OQ-005 | Exact identity of the v0.1 proposal/validator/executor boundary modules (`_proposals.py` / `_validator.py`?) the daemons must use | High |
| OQ-006 | Brownfield: how deep does REQ inference go — headings/docstrings only, or full code analysis? Bounded by cost. | Medium |
| OQ-007 | Duplicate/contradiction token-overlap threshold (80% assumed) | Low |
| OQ-008 | ✅ **RESOLVED** (spike O-1): dispatch = detached `claude -p --output-format json`; correlate via the **returned `session_id`** (captured from stdout), reused with `--resume`. `claude agents --json` is monitor-only and does not list `-p` runs. | ~~High~~ |

---

## 7. Traceability

| Area | REQs | Phase | EF source |
|------|------|-------|-----------|
| Foundation | F-001..007 | P0 | — |
| Spike | F-028 | P0 | — |
| Observer | F-008..014 | P1 | — |
| Dreamer | F-015..021 | P1 | — |
| Health | F-022..026 | P1 | — |
| Async miner | F-027 | P1 | — |
| Orchestration | F-031..035 | P2 | — |
| Brownfield | F-038..043 | P2 | **EF-014** |
| Sprint | F-044..048 | P3 | **EF-011** |
| Minor items | F-049..054 | P0–P3 | OQ-2/3, Q-002/004, T-111 |
| Release | F-029..030 | all | — |
| Non-functional | NF-001..010 | all | — |

Task IDs (T-136+) are assigned in `build/04-plan/task-dag-v0.2.md`.

> **Numbering note.** REQ-F IDs are non-contiguous by design: F-028 (spike) and
> F-029/030 (release) were carried from the 2026-05-14 draft and kept at their
> original numbers for traceability; **F-036/037 are intentionally unallocated**
> (reserved). The traceability table above is authoritative for which REQs exist.

## 8. Acceptance Definition (per phase)

A phase tag ships when: its REQs' acceptance passes; the **full** suite is green
(0 regressions) + `validate-plugin.py` exit 0 + `full-pipeline.sh` 12/12;
capability-dependent features no-op/fallback cleanly when the capability is
absent; both manifests + CHANGELOG bumped via `bump-version.py`; origin/polygon
parity. P1 additionally requires the spike (REQ-F-028) to have **passed**.
