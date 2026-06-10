# Task DAG — Forge v0.2 (program, phased)

> **Status**: **Draft — pending sign-off** (2026-06-10). Derived from
> `build/01-srs/srs-v0.2.md` (reviewed) and `build/02-architecture/architecture-v0.2.md`
> (+ ADR-005/006/007). Spike O-1 + O-2-cost are RESOLVED; only **O-2 completion-rate**
> (T-139) gates P1.
>
> Numbering continues from v0.1.7 (T-131..T-135); v0.2 is **T-136..T-156**.
>
> Format: `T-NNN [size] title`
> Size: S (small, ~30min), M (medium, ~2hr), L (large, ~half-day)
>
> **Phased shipping** — each milestone is its own tag, each independently green
> (full suite + `validate-plugin.py` exit 0 + `full-pipeline.sh` 12/12):
>
> | Milestone | Tag | Gate |
> |-----------|-----|------|
> | M1 Foundation + spike | v0.2.0 | none (build now) |
> | M2 Daemons | v0.2.1 | **T-139 ≥90% completion** (else defer, ship v0.2.0 only) |
> | M3 Orchestration + brownfield | v0.2.2 | **not** spike-gated — needs only T-136 |
> | M4 Sprint | v0.2.3 | — |
>
> **Parallelism**: M3 depends only on the cost cap (T-136), *not* on the spike gate,
> so M3 may proceed alongside M2. M4 depends only on the DAG itself.
>
> **Invariants** (every task): adapters stdlib-only; one adapter per host mechanism
> (`_background_agent.py`, `_orchestrate.py`); all state-mutating output flows through
> the v0.1 proposal→validator→executor boundary (`_proposals.py`/`_validator.py`/
> `_executor.py`); capability-dependent features no-op/fallback when unavailable;
> keep the whole suite green after each task (REQ-NF-001..010).

---

## Milestone 1: Foundation + spike (v0.2.0 — not gated)

> The cost cap (T-136) is a **hard prerequisite** (REQ-F-007, C-004): no dispatch is
> wired until it + its tests are green. Build order: T-136 → T-137 → T-138 → T-139.

### T-136 [M] Cost cap + ledger (`hooks/_cost_cap.py`)
- **Description**: The hard-prerequisite spend gate (ADR-007). Append-only ledger
  `.forge/cost-ledger.jsonl` (`ts, feature, session_id, input_tokens, output_tokens,
  estimated_usd, actual_usd`). `actual_usd` = API-reported `total_cost_usd` from a
  dispatch JSON envelope; `estimated_usd` = conservative pre-dispatch floor (≈$0.06
  fresh / ≈$0.01 resumed). Enforce daily `cost_cap.daily_usd` (default $0.50) and
  optional rolling-30-day `cost_cap.monthly_usd` from `.forge/config.yaml`. Pre-check
  is `running_sum(actual_usd) + floor` vs cap, a single local read (no network).
  Over cap → return a structured skip + append an event to `.forge/events.jsonl`;
  **never raise** (REQ-NF-006).
- **Files**: `hooks/_cost_cap.py` (new), `tests/unit/test_cost_cap.py` (new)
- **Done when**: under-cap allows + records actual on return; over-cap skips + logs
  the event; daily and monthly windows compute correctly; malformed/missing ledger
  degrades to "allow with floor", never raises; stdlib-only.
- **Depends on**: none
- **REQ-IDs**: REQ-F-004, F-005, F-006, F-007; NF-006, NF-008

### T-137 [M] Background adapter — dispatch half (`hooks/_background_agent.py`)
- **Description**: Add dispatch to the existing probe/monitor adapter (REQ-F-002,
  ADR-005). `dispatch(prompt, *, resume=None, model=None, timeout)` runs detached
  `claude -p <prompt> --output-format json [--resume <sid>]` with `stdin=DEVNULL`,
  `start_new_session=True`; parses the envelope; returns `{session_id, total_cost_usd,
  usage, is_error, result}` or a structured no-op. **Captures `session_id`** and, when
  a prior one is supplied, **reuses it via `--resume`** (mandatory — fresh $0.053 vs
  resumed $0.0046). Routes every dispatch's cost through `_cost_cap.py` (pre-check +
  record actual). Correlation is the returned `session_id`, **not** `claude agents
  --json`. Degrades to no-op on missing/old CLI / non-JSON / timeout (extend the
  8-test failure matrix + a "no session_id in envelope" path).
- **Files**: `hooks/_background_agent.py`, `tests/unit/test_background_agent.py`
- **Done when**: dispatch returns the parsed envelope from a fake `claude` shim;
  `--resume` is passed when a session_id is supplied; cost routed through `_cost_cap`
  (over-cap → dispatch no-ops); every failure mode degrades without raising.
- **Depends on**: T-136
- **REQ-IDs**: REQ-F-002, F-003; NF-004, NF-006, NF-010; OQ-008

### T-138 [S] Wire capability probe into session start
- **Description**: `session-start.py` calls `detect_capability()` and writes
  `.forge/capabilities.json` (`{"forge_background_available": bool, ...}`, REQ-F-001);
  add the unread-findings surface read (count only here, within the 2000-token budget
  — the findings file is produced by M2). No error on machines without the CLI.
- **Files**: `hooks/session-start.py`, `tests/unit/test_session_start*.py`
- **Done when**: capabilities.json written with the probe result; absent CLI →
  `available:false`, no error; session-start p95 ≤ 200ms preserved (no dispatch here).
- **Depends on**: T-137
- **REQ-IDs**: REQ-F-001; NF-004

### T-139 [M] Spike O-2 completion-rate measurement (the P1 gate)
- **Description**: Convert the `stop-reflect.py` skill-miner step to a **dispatched
  background subagent** via T-137, instrumented with the T-136 ledger. Run over **≥5
  real build sessions**; record completion rate and cost/session into
  `build/06-evaluation/spike-background-agents.md`. **Gate**: ≥90% completion AND
  typical cost within budget (cost already cleared: ~$0.005 resumed). If it fails,
  P1 (M2) defers and v0.2.0 ships foundation-only (SRS §6 contingency).
- **Files**: `hooks/stop-reflect.py` (background path + inline fallback),
  `build/06-evaluation/spike-background-agents.md` (results), tests for the dispatch
  path
- **Done when**: ≥5 sessions recorded with completion rate + cost/session; verdict
  written (PASS/FAIL); on PASS, M2 unlocked. **No fabricated runs** — real sessions only.
- **Depends on**: T-136, T-137, T-138
- **REQ-IDs**: REQ-F-028 (O-2 completion); F-027 (async path seed)

### T-140 [S] `/forge:set-profile` runtime profile switch
- **Description**: Minor P0 item (REQ-F-051). A `/forge:set-profile <type>` skill +
  `scripts/set-profile.py` that updates `project_type` in `pipeline/state.md` (atomic,
  via `_executor`/`_state_lib`) and validates against the known profile list. No
  background/cost dependency — independent.
- **Files**: `skills/forge-set-profile/SKILL.md` (new), `scripts/set-profile.py` (new),
  `tests/unit/test_set_profile.py` (new)
- **Done when**: switches to a valid profile (state.md updated atomically); rejects an
  unknown profile with a clear message; suite green.
- **Depends on**: none
- **REQ-IDs**: REQ-F-051

### T-141 [S] Release v0.2.0 — foundation + spike verdict
- **Description**: `scripts/bump-version.py 0.2.0`, fill `## [0.2.0]` (cost cap,
  adapter dispatch, probe wiring, spike verdict, set-profile), full pre-release
  verification. PR→develop→main→tag→mirror follows interactively.
- **Files**: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`
- **Done when**: both manifests at `0.2.0`; CHANGELOG `## [0.2.0]` on top + spike
  verdict noted; `pytest -q` green, `validate-plugin.py` 0, `full-pipeline.sh` 12/12.
- **Depends on**: T-139, T-140
- **REQ-IDs**: REQ-F-029, F-030

---

## Milestone 2: Daemons (v0.2.1) — [SPIKE-GATED on T-139 ≥90%]

> Build order: T-142 (establishes `references/daemon-bus.md` + the poll/reuse
> pattern) → {T-143, T-144} in parallel → T-145. All daemons reuse one session
> (`--resume`) and emit findings only (never write Tier-2 directly).

### T-142 [L] Observer daemon
- **Description**: `/forge:watch` spawns the Observer as a reused-session background
  dispatch (idempotent — warns if a live session exists in `observer-session.json`,
  REQ-F-008); `/forge:watch-stop` cleanly terminates, preserving last poll output
  (F-010). Session record `.forge/observer-session.json` (F-009); findings →
  `.forge/observer-findings.jsonl` (`ts, severity, source, message`, F-011); unread
  findings surfaced at session start within the 2000-token budget (F-012, builds on
  T-138). Lazy event-driven poll (default 30 min, config) dispatched via T-137; never
  writes pipeline artifacts directly (F-013); Stage-9 status line in `/forge:status`
  (F-014). `agents/observer.md` + `references/daemon-bus.md` (findings schemas + poll
  contract).
- **Files**: `skills/forge-watch/SKILL.md`, `skills/forge-watch-stop/SKILL.md`,
  `agents/observer.md`, `references/daemon-bus.md`, `hooks/session-start.py`
  (findings surface), `scripts/forge-status` path (status line), tests
- **Done when**: watch dispatches + is idempotent; findings written + surfaced;
  watch-stop preserves last output; status line shows running/last-poll/unread;
  capability-false → clean no-op; boundary respected (findings only).
- **Depends on**: T-137, T-138, T-139
- **REQ-IDs**: REQ-F-008..014; NF-004, NF-005, NF-006

### T-143 [L] Dreamer daemon
- **Description**: `/forge:dreamer-run` consolidates lessons now (F-015); daily digest
  → `pipeline/log/daily-YYYY-MM-DD.md` (idempotent/day, F-016); confidence decay →
  lessons < 0.3 become `status: dormant` (F-017); duplicate detection (Jaccard ≥ 0.8
  on word-set of `trigger`+`rule`, config `dreamer.dup_threshold`) flagged, **never
  auto-merged** (F-018); contradiction detection flagged, **never auto-resolved**
  (F-019); nightly schedule via reused-session dispatch, manual-only when unavailable
  (F-020); atomic writes to `.forge/lessons.yaml` (F-021). `agents/dreamer.md`.
- **Files**: `skills/forge-dreamer-run/SKILL.md`, `agents/dreamer.md`,
  `scripts/dreamer.py` (decay/dup/contradiction helpers), tests
- **Done when**: digest is idempotent/day; decay marks dormant correctly; dup +
  contradiction detection flag (never mutate); atomic lessons.yaml write; no-op when
  capability false.
- **Depends on**: T-142 (daemon-bus + dispatch pattern)
- **REQ-IDs**: REQ-F-015..021; NF-005, NF-007

### T-144 [L] Health daemon
- **Description**: `/forge:health-check` → report with hook unit-test results (F-023),
  lesson integrity checks (malformed YAML, broken xrefs, out-of-range confidence,
  missing fields, F-024), overall status `healthy|degraded|failing` (F-022).
  Auto-disable requires explicit `auto_disable_hooks: true` policy (F-025) and is
  **never silent** — logged to `.forge/events.jsonl` + surfaced next session start
  (F-026). `agents/health.md`.
- **Files**: `skills/forge-health-check/SKILL.md`, `agents/health.md`,
  `scripts/health_check.py`, tests
- **Done when**: report aggregates hook tests + lesson integrity + status; auto-disable
  gated on policy and logged+surfaced; no silent disable; no-op when capability false.
- **Depends on**: T-142
- **REQ-IDs**: REQ-F-022..026; NF-005, NF-006

### T-145 [M] Async skill-miner (production path)
- **Description**: Promote T-139's measurement path to the shipped behavior: when
  capability is true, `stop-reflect.py` offloads skill-mining to a background subagent
  (proposals → `.forge/proposals.jsonl`, through the v0.1 approval path); inline
  `mine-skills.py` fallback otherwise (REQ-F-027). Only the execution locus moves.
- **Files**: `hooks/stop-reflect.py`, `tests/unit/test_stop_reflect*.py`
- **Done when**: capable → background dispatch produces proposals; incapable → inline
  fallback produces identical proposals; same approval path; no regression.
- **Depends on**: T-139
- **REQ-IDs**: REQ-F-027

### T-146 [S] Hook-error log rotation
- **Description**: Minor P1 item (REQ-F-049). Size-bounded rotation of
  `.forge/hook-errors.log` (paired with the daemon-bus rotation policy, OQ-2 from
  v0.1.3). Stdlib-only, atomic.
- **Files**: `hooks/_error_log.py` or the existing error-log helper, tests
- **Done when**: log rotates at the configured size; no data loss; atomic.
- **Depends on**: none
- **REQ-IDs**: REQ-F-049

### T-147 [S] Release v0.2.1 — daemons
- **Description**: `bump-version.py 0.2.1`, fill `## [0.2.1]` (Observer/Dreamer/Health
  + async miner), full verification. **Only if T-139 PASSED.**
- **Files**: manifests + CHANGELOG
- **Done when**: manifests at `0.2.1`; CHANGELOG on top; all gates green.
- **Depends on**: T-142, T-143, T-144, T-145, T-146
- **REQ-IDs**: REQ-F-029, F-030

---

## Milestone 3: Orchestration + brownfield (v0.2.2) — NOT spike-gated

> Depends only on the cost cap (T-136); may run in parallel with M2. Build order:
> T-148 → {T-149, T-150, T-151}.

### T-148 [L] Orchestration primitive (`scripts/_orchestrate.py`)
- **Description**: The in-session fan-out adapter (ADR-006), distinct from the
  background API. `fan_out(work_list, agent_spec, schema, max_parallel)` spawns N
  subagents, each returning ONE JSON object validated against a Pydantic result
  schema (reuses the `_proposals.py` pattern); collects **index-ordered**, dedups,
  returns deterministically. Parallel where the host supports agent-teams; **identical-
  output sequential fallback** otherwise (F-032). Bounded by `orchestration.max_parallel`
  (default 4) + a total cap; every spawned agent routes cost through `_cost_cap.py`
  (F-033). Malformed output → retry, then drop to `null` + `log()` (no silent
  truncation). Results flow through the proposal boundary (F-035).
- **Files**: `scripts/_orchestrate.py` (new), `tests/unit/test_orchestrate.py` (new)
- **Done when**: **determinism test passes — sequential output == parallel output**
  for a fixed work-list (NF-009); bounded concurrency respected; cost routed; malformed
  item dropped+logged, not silently lost; sequential fallback identical when no
  agent-team.
- **Depends on**: T-136
- **REQ-IDs**: REQ-F-031, F-032, F-033, F-035; NF-009, NF-010

### T-149 [M] Parallel reviewers — first consumer (`/forge:review`)
- **Description**: Prove the primitive E2E (F-034): fan out independent review
  dimensions over the diff/target and synthesize a **deduplicated** report. First real
  consumer of `_orchestrate.py`.
- **Files**: `skills/forge-review/SKILL.md` (new), `scripts/review_synthesize.py`, tests
- **Done when**: dimensions fan out (parallel or sequential), report is deduped +
  deterministic; runs sequentially with identical output when parallel unavailable.
- **Depends on**: T-148
- **REQ-IDs**: REQ-F-034

### T-150 [L] Brownfield `/forge:adopt` (closes EF-014)
- **Description**: Run Forge against an existing codebase (F-038): reuse
  `detect-project-type.py`; fan out via `_orchestrate.py` (bounded by `adopt.max_files`)
  to extract current state; produce **inferred** drafts — `pipeline/01-srs/srs.md`,
  `pipeline/03-architecture/architecture.md`, seeded `pipeline/state.md` — each marked
  **INFERRED / needs confirmation** with `{confidence, derived_from:[files]}` (F-039/041).
  **Read-only** to user source; writes only under `pipeline/`+`.forge/`; `--dry-run`
  previews (F-040). Resumes the normal 12-stage flow at the right stage, gates intact
  (F-042). Logs sampled vs skipped — no silent truncation (F-043).
- **Files**: `skills/forge-adopt/SKILL.md` (new), `agents/brownfield-extractor.md` (new),
  `scripts/adopt.py`, tests + a brownfield fixture under `examples/`
- **Done when**: produces inferred artifacts with provenance; never writes user source;
  `--dry-run` writes nothing; bounded fan-out + sampling logged; project enters the
  pipeline with gates intact.
- **Depends on**: T-148
- **REQ-IDs**: REQ-F-038..043; NF-005

### T-151 [S] `/forge:why` LLM fallback
- **Description**: Minor P2 item (REQ-F-050). When deterministic ID lookup misses,
  fall back to a subagent (via `_orchestrate.py` single-item) to explain an unknown
  ID (OQ-3 from v0.1.3).
- **Files**: `skills/forge-why/SKILL.md` or the existing why path, `scripts/why_lookup.py`, tests
- **Done when**: known IDs use the deterministic path unchanged; unknown IDs get a
  bounded subagent explanation; no-op/clear message when capability false.
- **Depends on**: T-148
- **REQ-IDs**: REQ-F-050

### T-152 [S] Release v0.2.2 — orchestration + brownfield
- **Files**: manifests + CHANGELOG
- **Done when**: manifests at `0.2.2`; CHANGELOG on top; all gates green.
- **Depends on**: T-149, T-150, T-151
- **REQ-IDs**: REQ-F-029, F-030

---

## Milestone 4: Sprint (v0.2.3)

### T-153 [L] `/forge:sprint plan` + `review` (closes EF-011)
- **Description**: `sprint plan` groups ready DAG tasks (by milestone / dependency
  order / target size) into `pipeline/05-plan/sprint-NN.md`, referencing T-IDs only
  (F-044/045 — a **view over the DAG**, not a parallel tracker). `sprint review`
  produces a per-sprint retro → `pipeline/12-release/sprint-NN-review.md` (done vs
  carried, blockers, lessons, F-046). Carry-over preserves T-IDs + history (F-047).
  Fully opt-in (F-048).
- **Files**: `skills/forge-sprint/SKILL.md` (new), `scripts/sprint.py`, tests
- **Done when**: plan groups ready tasks referencing T-IDs; review reports done/carried;
  carry-over preserves identity; projects not using it see zero change.
- **Depends on**: none (DAG-based)
- **REQ-IDs**: REQ-F-044..048

### T-154 [S] `~/.forge` sync guidance + opt-in telemetry
- **Description**: Minor P3 (F-052/053). Document a conflict-safe `~/.forge` layout for
  cross-machine sync (no server, Q-002). Opt-in skill-mining telemetry, default **off**,
  local-only unless explicitly exported (Q-004).
- **Files**: `docs/forge-sync.md` (new), `scripts/telemetry.py` (opt-in flag), tests
- **Done when**: sync layout documented; telemetry off by default + local-only;
  enabling is explicit.
- **Depends on**: none
- **REQ-IDs**: REQ-F-052, F-053

### T-155 [M] Windows support exploration (spike-style)
- **Description**: Minor P3 (F-054). Replace the POSIX-only `SIGALRM` hook-timeout path
  (NFR-COMPAT-001) with a cross-platform mechanism, **or** document the limitation
  precisely. Spike → decision + either a fix or a documented constraint.
- **Files**: `hooks/_timeout.py` (if fixed), `build/06-evaluation/spike-windows.md` (new)
- **Done when**: either a cross-platform timeout lands with tests, or the limitation is
  documented with a clear rationale + workaround.
- **Depends on**: none
- **REQ-IDs**: REQ-F-054

### T-156 [S] Release v0.2.3 — sprint
- **Files**: manifests + CHANGELOG
- **Done when**: manifests at `0.2.3`; CHANGELOG on top; all gates green.
- **Depends on**: T-153, T-154, T-155
- **REQ-IDs**: REQ-F-029, F-030

---

## Dependency graph

```
M1 (v0.2.0):  T-136 ─▶ T-137 ─▶ T-138 ─▶ T-139 ─┐
              T-140 (independent) ───────────────┼─▶ T-141 (release)
                                                 │
M2 (v0.2.1) [GATED on T-139≥90%]:                │
              T-139 ─▶ T-142 ─▶ ┬─▶ T-143 ─┐     │
                                └─▶ T-144 ─┤     │
              T-139 ─▶ T-145 ─────────────┤     │
              T-146 (independent) ─────────┴─▶ T-147 (release)
                                                 │
M3 (v0.2.2) [NOT gated; needs only T-136]:       │
              T-136 ─▶ T-148 ─▶ ┬─▶ T-149 ─┐
                                ├─▶ T-150 ─┤
                                └─▶ T-151 ─┴─▶ T-152 (release)

M4 (v0.2.3):  T-153 ─┐
              T-154 ─┤
              T-155 ─┴─▶ T-156 (release)
```

**Critical path to first ship (v0.2.0)**: T-136 → T-137 → T-138 → T-139 → T-141.
**M3 may run in parallel with M2** (only T-136 in common). **M4 is independent.**

---

## Traceability (task → REQ → phase)

| Task | REQs | Phase |
|------|------|-------|
| T-136 | F-004/005/006/007 | P0 |
| T-137 | F-002/003 (OQ-008) | P0 |
| T-138 | F-001 | P0 |
| T-139 | F-028 (O-2), F-027 seed | P0 (P1 gate) |
| T-140 | F-051 | P0 |
| T-141 | F-029/030 | P0 |
| T-142 | F-008..014 | P1 |
| T-143 | F-015..021 | P1 |
| T-144 | F-022..026 | P1 |
| T-145 | F-027 | P1 |
| T-146 | F-049 | P1 |
| T-147 | F-029/030 | P1 |
| T-148 | F-031/032/033/035 (NF-009/010) | P2 |
| T-149 | F-034 | P2 |
| T-150 | F-038..043 (EF-014) | P2 |
| T-151 | F-050 | P2 |
| T-152 | F-029/030 | P2 |
| T-153 | F-044..048 (EF-011) | P3 |
| T-154 | F-052/053 | P3 |
| T-155 | F-054 | P3 |
| T-156 | F-029/030 | P3 |

All v0.2 functional REQs (F-001..054, minus the intentionally-unallocated F-036/037)
and NF-001..010 are covered. NF requirements are cross-cutting invariants enforced per
task (see header).
