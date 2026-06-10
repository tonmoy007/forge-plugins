# Architecture — Forge v0.2 (delta)

> **Status**: Draft (2026-06-10). **Composes with** `architecture.md` (the v0.1
> base) — it does not replace it. Everything in the base still holds; this delta
> adds the four v0.2 capability areas and **resolves the Stage-3 open questions**
> OQ-001…OQ-008 from `build/01-srs/srs-v0.2.md`.
>
> **Inputs**: `build/01-srs/srs-v0.2.md` (reviewed), the P0 spike
> (`build/06-evaluation/spike-background-agents.md`, verdict **PASS**; O-1 dispatch
> and O-2 cost **RESOLVED** 2026-06-10 — only O-2 completion-rate remains, in P0).
>
> **Design spine** (unchanged from v0.1, extended here): every capability-dependent
> feature degrades to a **clean no-op or sequential fallback** (REQ-NF-006); all
> state-mutating output flows through the **existing** proposal → validator →
> executor boundary (REQ-NF-005); adapters are **stdlib-only** and there is **one
> adapter file per host mechanism** (REQ-NF-010).

---

## 0. What v0.2 adds (one screen)

```
                    Claude Code session (foreground — v0.1, unchanged)
                                      │
                  ┌───────────────────┼─────────────────────┐
                  │                   │                     │
          hooks (v0.1)        NEW adapters (P0)       NEW skills (P1–P3)
          session-start ─────▶ _background_agent.py    /forge:watch  /forge:adopt
          stop-reflect  ─────▶ _cost_cap.py            /forge:dreamer-run
          …                    _orchestrate.py (P2)    /forge:health-check
                  │                   │                /forge:sprint …
                  │                   ▼
                  │        ┌──────────────────────┐
                  │        │  detached dispatch    │   claude -p  (one-shot, headless)
                  │        │  via background API   │   claude agents --json (list/monitor)
                  │        └──────────┬───────────┘
                  │                   ▼
                  │        background agent run (separate context, own cost)
                  │                   │  writes findings to .forge/*.jsonl
                  ▼                   ▼
        ┌───────────────────────────────────────────────┐
        │  proposal → validator → executor boundary      │  (v0.1 — REUSED, not rebuilt)
        │  _proposals.py → _validator.py → _executor.py  │  atomic writes + events.jsonl
        └───────────────────────────────────────────────┘
                                      │
                                      ▼
                       pipeline/* , .forge/*  (Tier-2 state)
```

The single most important invariant: **a background agent never writes a pipeline
artifact directly.** It emits findings to `.forge/*.jsonl`; those are read on the
next foreground event and promoted only through the v0.1 boundary
(REQ-F-013/035, REQ-NF-005). This is why v0.2 needs **no new trust machinery** —
`_proposals.py` already pins LLM-originated content to `trust="ephemeral"`.

---

## 1. New components (and their status)

| Component | Kind | Responsibility | REQ | Status |
|-----------|------|----------------|-----|--------|
| `hooks/_background_agent.py` | adapter (stdlib) | **Only** wrapper for `claude agents` (monitor) / `claude -p` (dispatch, `--resume` reuse). Probe, list, monitor, dispatch. | F-001/002/003 | **probe built** (spike); **dispatch design resolved** (O-1) — code is P0 |
| `hooks/_cost_cap.py` | adapter (stdlib) | Daily/monthly budget enforcement + cost ledger append; **hard prerequisite** for any dispatch | F-004/005/006/007 | **P0 — to build** |
| `scripts/_orchestrate.py` | adapter (stdlib) | **Only** wrapper for in-session subagent fan-out; structured collect + dedup; sequential fallback | F-031/032/033 | **P2 — to build** |
| `skills/forge-watch/` (+ `-watch-stop`) | skill | Start/stop the Observer daemon | F-008/010 | P1 |
| `skills/forge-dreamer-run/` | skill | Manual lesson-consolidation pass | F-015 | P1 |
| `skills/forge-health-check/` | skill | Hook + lesson integrity report | F-022 | P1 |
| `skills/forge-adopt/` | skill | Brownfield onboarding (fans out via `_orchestrate.py`) | F-038..043 | P2 |
| `skills/forge-sprint/` | skill | `plan` / `review` sub-commands over the DAG | F-044..048 | P3 |
| `agents/observer.md`, `dreamer.md`, `health.md` | agent personas | The background-dispatched personas | F-008/015/022 | P1 |
| `references/daemon-bus.md` | reference | Findings-file schemas + polling contract | F-009/011 | P1 |

**No new boundary module.** Daemon and orchestration outputs reuse
`_proposals.py` / `_validator.py` / `_executor.py` verbatim (resolves **OQ-005**).
A daemon finding becomes a `LessonProposal`/`ReflectionProposal` (or a new
`FindingProposal` of the same Pydantic shape) → validated → executed atomically.

---

## 2. Daemon execution model — resolves OQ-001 (the central P1 decision)

A hook-based plugin owns **no long-lived process** of its own; hooks are
short-lived subprocesses Claude Code spawns per event. So a "daemon" in Forge is
**not a resident process**. It is a **recurring detached one-shot dispatch**:

> **Decision (ADR-005): a Forge daemon = a detached `claude -p` agent run,
> dispatched from a foreground hook when a poll is due, that writes its findings to
> `.forge/` and exits.** Monitoring uses `claude agents --json [--cwd]`. There is no
> Forge-owned supervisor thread.

This is the **direct extension of the v0.1 precedent** (ADR-004): the Stop hook's
skill-miner already spawns a *detached subprocess that does not block*. v0.2
generalizes that one pattern into the `_background_agent.py` dispatch path.

**Scheduling is lazy + event-driven, not timer-based** (resolves **OQ-003**):

```
foreground hook fires (session-start / post-tool-use)
        │
        ▼
read .forge/observer-session.json  →  last_poll, interval (default 30 min, config), session_id
        │
   now - last_poll > interval ?
        │ yes                                  │ no
        ▼                                      ▼
_cost_cap.py: under budget?                 return (no-op, ~file-read latency)
        │ yes                  │ no
        ▼                      ▼
dispatch detached agent     skip + log "cost cap reached" to events.jsonl
claude -p … --resume <sid> &
capture session_id from JSON,
stamp last_poll, return     ← hook NEVER waits on the agent (REQ-NF-004 p95 ≤ 200ms)
```

The nightly **Dreamer** (REQ-F-016/020) is the one case that wants a wall-clock
trigger independent of session activity. Model: **host cron is optional and
documented, not required** — if absent, Dreamer runs lazily on the first session of
the day and via the manual `/forge:dreamer-run`. We do not ship or require a cron
install (keeps NFR-COMPAT and "no server" intact, REQ-F-052 spirit).

**Idempotency (REQ-F-008):** `/forge:watch` writes/reads `observer-session.json`
with a correlation id; a second `watch` that sees a live session under this `--cwd`
warns and no-ops instead of double-spawning.

---

## 3. Background adapter & headless dispatch — resolves OQ-008 / spike O-1

`_background_agent.py` is the **only** file that shells to the host. Two halves:

| Half | Call | State | Used by |
|------|------|-------|---------|
| **monitor** | `claude agents --json [--cwd]` → JSON array of *user-started* agents (`pid/status/kind/sessionId`) | proven headless (spike #3/#4) | probe (F-001), `/forge:status` line for a user-started watch session (F-014) |
| **dispatch** | `claude -p "<prompt>" --output-format json [--resume <sid>]` detached | ✅ **proven (spike O-1, 2026-06-10)** | Observer/Dreamer/Health poll, async skill-miner (F-027) |

**Dispatch + correlation design (confirmed by the O-1 probe):**

1. **Before** the *first* dispatch, write `.forge/observer-session.json` with `cwd`,
   `started_at`, `interval`, `last_poll`, and `session_id: null`.
2. Dispatch detached: `claude -p <prompt> --output-format json` with `stdin=DEVNULL`,
   `start_new_session=True`, stdout → `.forge/runs/<ts>.json`. The **prompt instructs
   the agent** to append findings to `.forge/observer-findings.jsonl`.
3. **Capture the correlation key from the dispatch's own JSON envelope**: it returns
   `session_id`, `total_cost_usd` (actual), `usage`, `is_error`, `result`. Persist
   `session_id` into `observer-session.json`. *(Confirmed: a `claude -p` run does
   **not** appear in `claude agents --json` — that surface lists user-started agents
   only. So the join key is the **returned `session_id`**, not a hand-rolled id and
   not the monitor list.)*
4. **Reuse the session on every subsequent poll**: `claude -p <prompt> --resume
   <session_id> …`. This is **mandatory for cost** (next section): a fresh session
   bills the ~42k-token system prompt as `cache_creation` (~$0.053); `--resume` turns
   it into a `cache_read` (~$0.0046, **9%**). Only the first poll/day pays the tax.
5. **Cost accounting**: read `total_cost_usd` straight from the JSON envelope →
   `_cost_cap.py` records the **actual**; the pre-dispatch cap check uses a
   conservative floor constant (≈$0.06 fresh / ≈$0.01 resumed) to gate *before* spend.

**Graceful degradation (REQ-F-003) is unchanged**: every entry point returns a
structured `{"status":"unavailable","reason":…}` and never raises when the CLI is
missing/old/non-JSON (8 existing tests cover the monitor half; dispatch adds the
same failure-mode matrix + a "no session_id in envelope" path).

> **Fallback (still single-call-site).** If `--resume` continuity ever breaks (e.g.
> session eviction), the adapter transparently starts a fresh session (pays the tax
> once) and re-persists the new `session_id`. The alternative model — a user-started
> long-lived `claude agents` session driven by `/forge:watch` — remains available for
> the foreground-style Observer; the choice touches only this one file (REQ-NF-010).

---

## 4. Cost governance — resolves OQ-004; the hard gate (ADR-007)

`_cost_cap.py` is a **hard prerequisite**: no daemon/orchestration dispatch is wired
until it + its tests are green (REQ-F-007, C-004).

```
cost ledger  .forge/cost-ledger.jsonl   (append-only, human-readable — REQ-F-006/NF-008)
{ "ts", "feature", "session_id", "input_tokens", "output_tokens",
  "estimated_usd", "actual_usd" }
```

- **Cost is API-reported, not estimated (OQ-004 — resolved by spike O-2):** every
  dispatch returns `total_cost_usd` in its `--output-format json` envelope; the
  ledger records that as `actual_usd`. `estimated_usd` is only a **conservative
  pre-dispatch floor constant** (≈$0.06 fresh, ≈$0.01 resumed) used to gate spend
  *before* the run — there is **no model price table to maintain**.
- **Enforcement is pre-dispatch and local:** check `running_sum(actual_usd) + floor`
  against the cap with a single ledger read, no network — preserves the latency
  budget (REQ-NF-004).
- **Caps:** daily `cost_cap.daily_usd` (default $0.50), optional monthly
  `cost_cap.monthly_usd` (rolling 30 days) — `.forge/config.yaml`.
- **Over cap → skip + log**, never raise: the dispatch becomes a no-op and an event
  lands in `.forge/events.jsonl`, surfaced next session start.

**The measured cost reality (spike O-2, 2026-06-10) — why session reuse is a rule,
not a tweak:**

| Mode | Cost/dispatch | Why |
|------|--------------|-----|
| Fresh session | **$0.0528** | ~42k-token system prompt billed as `cache_creation` (`cache_read=0`) |
| `--resume` session | **$0.0046** (9%) | same 42k tokens become a `cache_read` |

At a naive 15-min fresh-poll cadence (8h/day) that is **~$50/mo** — over budget and
only 1.9× under the $0.10/session gate. With one **reused** session per daemon
(REQ-F-002), only the first poll/day pays the tax; ~960 polls/mo ≈ **$4.4/mo**. So:
**default poll interval can stay moderate (30 min) because the cost backstop is the
cap, and reuse keeps each poll ~$0.005.**

This ledger is also how the spike's remaining **O-2 completion-rate** number gets
measured (REQ-F-028): instrument the async skill-miner dispatch, run ≥5 real
sessions, read completion markers + `cost-ledger.jsonl`. **Cost is already cleared;
only completion-rate (≥90%) remains** — P0 work that gates P1.

---

## 5. Orchestration primitive — resolves OQ-002 (P2, NOT the background API)

`scripts/_orchestrate.py` is a **distinct** adapter from `_background_agent.py`. It
wraps the **in-session** subagent/agent-team mechanism for *deterministic* fan-out —
parallel where the host supports it, identical-output sequential fallback otherwise
(REQ-F-031/032, REQ-NF-009).

```
work_list (N items)  ─┐
                      ├─▶ _orchestrate.fan_out(work_list, agent_spec, schema, max_parallel)
config max_parallel  ─┘            │
                                   ├─ parallel path : host agent-team spawn (bounded)
                                   └─ sequential path: one-at-a-time, same prompts
                                   │
                                   ▼
                    each subagent returns ONE JSON object  ← validated against a
                    Pydantic result schema (reuses the _proposals.py pattern)
                                   │
                                   ▼
                    deterministic collect → dedup → ordered list  (REQ-NF-009)
                                   │
                                   ▼
                    results flow through proposal/validator/executor (REQ-F-035)
```

- **Structured-output contract (OQ-002 decision):** every fan-out item declares a
  Pydantic result schema; a subagent that returns malformed output is retried at the
  call layer (mirrors how the Workflow harness forces structured output), then
  dropped to `null` and `log()`ged — **no silent truncation** (REQ-F-043 spirit).
- **Bounded (REQ-F-033):** `orchestration.max_parallel` (default small, e.g. 4) and a
  total-agent cap; every spawned agent routes cost through `_cost_cap.py`.
- **Determinism (REQ-NF-009):** ordering is by input index, not completion order;
  the sequential and parallel paths synthesize **byte-identical** reports given the
  same inputs. This is a *test invariant*, not just a claim.
- **First consumer (REQ-F-034):** a `/forge:review` mode fans out independent review
  dimensions and synthesizes a deduplicated report — proving the primitive E2E
  before brownfield depends on it.

---

## 6. Brownfield onboarding `/forge:adopt` — P2 (closes EF-014)

```
/forge:adopt [--dry-run]
        │
        ▼
detect-project-type.py  ──▶ project_type  (REUSES v0.1.7 detection — no new detector)
        │
        ▼
_orchestrate.fan_out(  sampled files (bounded by adopt.max_files),  extractor_agent )
        │  each agent reads headings/docstrings/manifests (OQ-006: NOT full AST by default)
        ▼
inferred artifacts, each stamped { confidence, derived_from:[files] }   (REQ-F-041)
        ├─ pipeline/01-srs/srs.md        (draft, marked **INFERRED — needs confirmation**)
        ├─ pipeline/03-architecture/architecture.md (draft, same marking)
        └─ pipeline/state.md             (seeded: project_type, entry stage)
        │
        ▼
read-only guarantee: writes ONLY under pipeline/ and .forge/  (REQ-F-040)
--dry-run previews the file list, writes nothing  (mirrors init --dry-run)
        │
        ▼
project enters the standard 12-stage flow at the right stage, gates intact (REQ-F-042)
```

- **OQ-006 decision:** inference depth defaults to **structural** (headings,
  docstrings, manifests/config), not full code analysis — bounded by cost and
  `adopt.max_files`; deeper analysis is opt-in. What was sampled vs skipped is
  `log()`ged (REQ-F-043).
- **Best-effort, human-confirmed** (A-005): every inferred artifact is a draft
  carrying provenance; Forge proposes, the user disposes.

---

## 7. Sprint workflow `/forge:sprint` — P3 (closes EF-011)

A **view over the DAG, not a parallel tracker** (REQ-F-045). The
`build/04-plan/task-dag*.md` stays the single source of truth.

| Sub-command | Reads | Writes | REQ |
|-------------|-------|--------|-----|
| `sprint plan` | task DAG (ready tasks by milestone / deps / target size) | `pipeline/05-plan/sprint-NN.md` (references T-IDs only) | F-044/045 |
| `sprint review` | sprint-NN + DAG state | `pipeline/12-release/sprint-NN-review.md` (done vs carried, blockers, lessons) | F-046 |

- **Carry-over (REQ-F-047):** unfinished T-IDs roll into `sprint-(NN+1)` preserving
  their identity and history — no renumbering.
- **Opt-in (REQ-F-048):** projects that never call `/forge:sprint` see zero change.

---

## 8. Data flow additions (extends base §3)

### 8.1 Session start (Observer findings surfaced) — extends base §3.1

```
session-start.py (v0.1 context compose)
        │
        ├─ read .forge/observer-findings.jsonl  → unread since last session
        ├─ filter to the v0.1 2000-token budget  (REQ-F-012, NFR unchanged)
        ├─ read .forge/capabilities.json         (probe result, REQ-F-001)
        └─ if a poll is due AND under cost cap → dispatch (detached, non-blocking)
        │
        ▼
context block now includes: stage/task (v0.1) + "N unread Observer findings"
```

### 8.2 Async skill-miner (REQ-F-027) — modifies base §3.2 step 4

The Stop-hook skill-miner (already detached per ADR-004) becomes a
`_background_agent.py` dispatch when capability is true; **inline `mine-skills.py`
fallback** when false. Proposals still land in `.forge/proposals.jsonl` and still
pass through the v0.1 approval path — only the *execution locus* moves.

---

## 9. Failure modes (extends base §7)

| Failure | Detection | Response |
|---------|-----------|----------|
| Background CLI absent/old | `_background_agent` probe → `available:false` | All daemons silent no-op; foreground identical to v0.1 (REQ-NF-001/006) |
| Cost cap reached | `_cost_cap` pre-dispatch sum ≥ cap | Skip dispatch, log to `events.jsonl`, surface next session (REQ-F-004/NF) |
| Detached agent never writes findings | next poll sees stale `correlation_id`, no findings file | Mark run abandoned in `events.jsonl`; next poll re-dispatches (bounded by cost) |
| Orchestration parallel spawn unavailable | host returns no agent-team | Sequential fallback, identical output (REQ-F-032/NF-009) |
| Subagent returns malformed structured output | schema validation fails | Retry at call layer, then drop item to `null` + `log()` — no silent truncation |
| Daemon tries to write a pipeline artifact directly | — (prevented by construction) | Not possible: only path to Tier-2 is proposal→validator→executor (REQ-F-013/035) |
| Two `/forge:watch` invocations | live session under `--cwd` in `observer-session.json` | Second warns + no-ops (REQ-F-008 idempotent) |

---

## 10. Non-functional mapping (REQ-NF-001…010)

| NFR | How the design satisfies it |
|-----|-----------------------------|
| NF-001 backward compat | No v0.1 file/behavior changed; all v0.2 entry points gate on `available` |
| NF-002 schema-compatible | New state is **new files** under `.forge/` (findings, ledger, sessions); v0.1 schemas untouched |
| NF-003 no new deps | Adapters stdlib-only; structured boundary reuses the **already-present** Pydantic |
| NF-004 foreground isolation | Dispatch is fire-and-forget detached; hooks do only local file reads → p95 ≤ 200ms |
| NF-005 proposal boundary | §0 invariant; daemons/orchestration emit findings, never write Tier-2 directly |
| NF-006 graceful degradation | §9; every feature is a no-op (daemons) or sequential fallback (orchestration) |
| NF-007 atomic writes | All Tier-2 writes go through `_executor.py` (temp+rename, already atomic) |
| NF-008 cost transparency | Human-readable `cost-ledger.jsonl` (§4) |
| NF-009 determinism | §5 — index-ordered collect; sequential == parallel output (test invariant) |
| NF-010 one adapter per mechanism | `_background_agent.py` (background API) and `_orchestrate.py` (in-session agents) are the only call sites |

---

## 11. Open questions — resolution status

| OQ | Resolution | Where |
|----|-----------|-------|
| OQ-001 daemon execution model | Detached `claude -p` one-shot per due poll; no resident supervisor; lazy event-driven schedule | §2, ADR-005 |
| OQ-002 orchestration primitive | `_orchestrate.py` wraps in-session subagents; Pydantic structured-output contract | §5, ADR-006 |
| OQ-003 polling interval | Configurable (default 15 min), checked lazily at foreground hook events | §2 |
| OQ-004 cost: estimated vs actual | **RESOLVED** (spike O-2): actual `total_cost_usd` is in the dispatch JSON — record actuals, no price table; pre-check uses a floor constant | §4, ADR-007 |
| OQ-005 boundary modules | `_proposals.py` / `_validator.py` / `_executor.py` — reused verbatim, no new boundary | §1, §0 |
| OQ-006 brownfield depth | Structural (headings/docstrings/manifests) by default, bounded by `adopt.max_files`; deeper opt-in | §6 |
| OQ-007 dup/contradiction threshold | Jaccard 0.8 on word-set of `trigger`+`rule`, config `dreamer.dup_threshold` | (Dreamer; §1) |
| **OQ-008 headless dispatch** | **RESOLVED** (spike O-1): detached `claude -p --output-format json`; correlate via returned `session_id`; reuse via `--resume`; `claude agents --json` is monitor-only | §3, ADR-005 |

**Still genuinely open after this architecture (carried to P0):**
- **O-2 completion-rate only** — the ≥90%-over-≥5-real-sessions reliability number
  (REQ-F-028), measured in P0 once `_cost_cap.py` lands. *(O-1 dispatch and O-2 cost
  are now RESOLVED, 2026-06-10 — see `spike-background-agents.md`.)*

---

## 12. ADRs (new in v0.2)

Living in `02-architecture/adr/`:

- **ADR-005**: Daemons are detached one-shot dispatches, not resident processes —
  `adr/005-daemon-execution-model.md`
- **ADR-006**: Orchestration primitive wraps in-session subagents with a structured
  (Pydantic) contract, distinct from the background API —
  `adr/006-orchestration-primitive.md`
- **ADR-007**: Cost cap is a hard prerequisite gate, enforced pre-dispatch on a
  two-phase ledger — `adr/007-cost-cap-hard-gate.md`

---

## 13. Traceability (v0.2 REQ → component)

| Component | Maps to |
|-----------|---------|
| `_background_agent.py` | F-001, F-002, F-003, F-020, F-027; OQ-008 |
| `_cost_cap.py` + ledger | F-004, F-005, F-006, F-007; NF-008 |
| Spike instrumentation | F-028 (O-2) |
| Observer (skill+agent+bus) | F-008..014 |
| Dreamer | F-015..021 |
| Health daemon | F-022..026 |
| `_orchestrate.py` | F-031, F-032, F-033, F-034, F-035; NF-009, NF-010 |
| `/forge:adopt` | F-038..043 (EF-014) |
| `/forge:sprint` | F-044..048 (EF-011) |
| Minor items | F-049 (log rotation), F-050 (`/forge:why` fallback), F-051 (`set-profile`), F-052 (`~/.forge` sync), F-053 (telemetry), F-054 (Windows) |
| Reused boundary | F-013, F-035; NF-005, NF-007 → `_proposals.py`/`_validator.py`/`_executor.py` |
