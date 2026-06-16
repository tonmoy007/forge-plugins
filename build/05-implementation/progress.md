# Implementation Progress

> Updated by Claude as work progresses. This is the first thing to read after CLAUDE.md
> at session start to know where we are.

## Current State

- **v0.3.6 (context-aware autopilot) BUILT on `feat/v0.3.6-context-aware`** — at a
  configurable context threshold, autopilot checkpoints → compacts → continues.
  Background: `should_rotate_for_context` rotates the reused session on a real
  token-pressure signal (`usage.input_tokens`) past `context_threshold_percent ×
  context_window_size` (T-185); shared atomic, schema-versioned checkpoint
  `.forge/autopilot-checkpoint.json` + `checkpoint` subcommand, run-log idempotency
  (T-186). In-session: new `PreCompact` hook checkpoints before native compaction
  (T-187); `SessionStart(source=compact)` re-injects resume state (T-188). Docs
  (T-189). Opt-in, default 80%; zero change when `context_window_size` unset. 1496
  tests pass; validate 0; full-pipeline 12/12. Manifests 0.3.6; CHANGELOG `[0.3.6]`.
  SRS `build/01-srs/srs-v0.3.6.md`, DAG `build/04-plan/task-dag-v0.3.6.md`.
  **Pre-release verification + ship (PR develop→main→tag v0.3.6→mirror) in progress.**

- **v0.3.5 (semantic skill mining + skill-creator) BUILT on `feat/v0.3.5-skill-mining`** —
  replaces the tool-name-n-gram miner with a semantic, success-gated,
  anti-unification pipeline: enrichment + episode segmentation
  (`_trace_semantics.py`, T-177), anti-unify motif miner + success gate
  (`_antiunify.py` / `skill_miner_v2.py`, T-178), LLM induction w/ graceful
  degradation (T-179), `/forge:skill-creator` + agentskills.io `SKILL.md`
  emission (T-180), replay verification (`skill_verify.py`, T-181), library
  curation (`skill_curate.py`, T-182), n-gram path retired + docs (T-183).
  Built autonomously via a fan-out workflow (sequential core spine →
  parallel tail → integrate → adversarial verify). 1473 tests pass; validate
  0; full-pipeline 12/12. Manifests 0.3.5; CHANGELOG `[0.3.5]`. SRS
  `build/01-srs/srs-v0.3.5.md`, DAG `build/04-plan/task-dag-v0.3.5.md`.
  **Pre-release verification + ship (PR develop→main→tag v0.3.5→mirror) in progress.**
- **v0.3.4 (M4 sprint) BUILT on `feat/v0.3.4-m4-sprint`** — closes the long-deferred v0.2
  M4 backlog: `/forge:sprint` plan/review as a view over the task DAG (T-153),
  `docs/forge-sync.md` cross-machine guidance + opt-in local-only telemetry (T-154), and a
  cross-platform hook-timeout fix (Windows degrades, never crashes; T-155). Manifests
  0.3.4; CHANGELOG `[0.3.4]`. **Pre-release verification + ship (PR develop→main→tag
  v0.3.4→mirror) in progress.**
- **v0.3.3 (complete autonomy + modernized harness) RELEASED** — modernized harness
  (T-167..T-170, folded; no separate v0.3.2 tag) + complete local autonomy: self-heal
  (T-172), verifier subagents (T-173), `--unattended` (T-174), enforcing rules (T-175).
  Tag `v0.3.3` (`8e827a1` merge) on origin + polygon; GitHub releases published; manifests
  0.3.3. SRS `build/01-srs/srs-v0.3.3.md`, DAG `build/04-plan/task-dag-v0.3.3.md`.
- **v0.3 program (v0.3.0 + v0.3.1) COMPLETE + RELEASED** — "Hands-off Forge — autonomy +
  governance": user-authored **Rules** (v0.3.0) + **Autopilot** cross-stage execution
  (v0.3.1), T-157..T-166. Tags `v0.3.0` (`9102b78`) + `v0.3.1` (`7525a7e`) on origin +
  polygon; GitHub releases published. SRS `build/01-srs/srs-v0.3.md`, DAG
  `build/04-plan/task-dag-v0.3.md`.
- **NEXT**: finish shipping v0.3.4. The v0.2 M4 backlog is now closed.
- **Prior program v0.2** (phased v0.2.0→v0.2.3) — "a system that works alongside
  you": daemons, orchestration, brownfield, sprint. COMPLETE + RELEASED through v0.2.3
  (sprint M4, T-153–156, deferred).
- **v0.2.0 (M1 foundation) COMPLETE + RELEASED** — T-136..T-141. Cost cap + ledger,
  background-agent dispatch (`claude -p`, session reuse), capability probe wired into
  session-start, background skill-miner instrumentation, `/forge:set-profile`. Tag
  `v0.2.0` (`bd9d58a`) + GitHub release; main `16839ee`, develop `709710c`;
  **origin/polygon parity**. 1124 tests pass; validate 0; full-pipeline 12/12.
  - Planning (Stages 1/3/5): SRS reviewed, **spike PASS** (O-1 dispatch + O-2 cost
    RESOLVED — `claude -p --output-format json` headless, `--resume` cuts cost 10×:
    $0.053→$0.0046), architecture + ADR-005/006/007 (OQ-001..008 resolved), DAG
    `task-dag-v0.2.md` (T-136..T-156).
- **v0.2.1 (M3 orchestration + brownfield) COMPLETE + RELEASED** — shipped ahead of the
  spike-gated daemons (not gated; needs only the cost cap). T-148–T-152.
- **v0.2.2 (skill-miner cost fix) STAGED on develop** — pins the background skill-miner
  to a cheap model (`haiku`), cutting an unpinned ~$1.07/run (Opus-class default) to
  ~$0.022/run; six live dispatches 6/6 → **T-139's O-2 gate CLEARED**. Also a
  date-robust over-cap test fix + README hero banner. On `develop`; **the develop→main
  promotion + tag are BLOCKED** by a new `MAIN PROTECTION` ruleset (no bypass actors).
- **v0.2.3 (M2 background daemons) BUILT** — Observer / Dreamer / Health + async
  skill-miner production path + log rotation (T-142–T-146) on the proven adapter (cheap
  model + session reuse, capability-gated, never-raises). Staged for develop; promotes
  to main together with v0.2.2 once the ruleset is resolved.
- **NEXT**: resolve the `MAIN PROTECTION` ruleset, then promote v0.2.2 + v0.2.3 to main
  (two tags) and mirror to polygon. Then M4 sprint (T-153–T-156).
- **Prior release**: v0.1.7 — "Three more project-type profiles" — scope locked
  2026-06-09 (`build/01-srs/srs-v0.1.7.md`, `build/04-plan/task-dag-v0.1.7.md`).
- **v0.1.7 COMPLETE + RELEASED** — all 5 tasks (T-131..T-135). monorepo / mobile /
  data-contract profiles, each with auto-detection + a real gate
  (check_monorepo_graph.py, check_store_readiness.py, check_schema_compat.py).
  Built SERIALLY (shared detection trio). Tag `v0.1.7` (`a1192fc`) + GitHub
  release on both remotes; 1076 tests pass; validate 0; full-pipeline 12/12;
  manifests at 0.1.7; CHANGELOG `[0.1.7]` on top. origin/polygon parity.
- **v0.1.6 COMPLETE + RELEASED** — all 5 tasks (T-126..T-130). CLARIFY / CONFIRM /
  NARRATE via a 3-agent parallel fan-out. Tag `v0.1.6` (`baccc5e`) + GitHub
  release on both remotes; CHANGELOG `[0.1.6]`. origin/polygon parity.
- **v0.1.5 COMPLETE + RELEASED** — all 25 tasks (T-101..T-125); tag `v0.1.5` +
  hotfix `v0.1.5.1` (PyYAML fail-soft) on both remotes; release-infra hardening on
  main (hard CI gates w/ subprocess coverage ~72%, `scripts/bump-version.py`).
  plugin.json + marketplace.json at 0.1.5.1; CHANGELOG current.
- **Workflow**: branch from `main` → PR into `develop` → test → merge `develop→main`
  → tag from `main`. Two remotes kept in sync: `origin` + `polygon`.
- **Last hotfix**: v0.1.5.1 — PyYAML fail-soft guard in the 6 active hooks.

## v0.3.3 Task Status

> DAG: `build/04-plan/task-dag-v0.3.3.md` (T-167..T-176). M1 Harness (T-167..T-171,
> originally scoped as v0.3.2, folded into v0.3.3); M2 Autonomy (T-172..T-176). Both
> shipped under `v0.3.3`. SRS `build/01-srs/srs-v0.3.3.md`.

### M1 — Modernized harness (v0.3.2) — branch `feat/v0.3.2-autonomy`

| Task | Status | Notes |
|------|--------|-------|
| T-167 | 🟢 done | Structured outputs — `dispatch(output_schema)` → `claude -p --json-schema` (CLI 2.1.177+); `_orchestrate.fan_out` threads it; parse/retry/drop fallback. +4 tests |
| T-168 | 🟢 done | Per-dispatch `--max-budget-usd` ceiling (config `autopilot.max_budget_usd`) atop `_cost_cap`. +4 tests |
| T-169 | 🟢 done | Per-stage model routing — `autopilot.models` (numeric or command-word key); `model_for_stage()`. +5 tests |
| T-170 | 🟢 done | Long-run session rotation — `autopilot.session_max_dispatches` + `should_rotate_session()`; CLI auto-compacts within a session, this bounds reuse across dispatches. +5 tests |
| T-171 | 🟡 staged | Release v0.3.2 — bump 0.3.2, CHANGELOG `[0.3.2]`, README config note, ROADMAP/progress. Pre-release green. **Push/PR/tag/mirror pending user OK.** |

### M2 — Complete autonomy (v0.3.3) — planned

| Task | Status | Notes |
|------|--------|-------|
| T-172 | 🔲 todo | Self-heal loop (blocker → bounded `/forge:resolve` → re-gate) |
| T-173 | 🔲 todo | Verifier subagents (independent fresh-context verification) |
| T-174 | 🔲 todo | `--unattended` mode (no checkpoints; answers/assumptions; bounded) |
| T-175 | 🔲 todo | Enforcing rules guardrail (`enforce: true` → block on write) |
| T-176 | 🔲 todo | Release v0.3.3 |

## v0.3 Task Status

> DAG: `build/04-plan/task-dag-v0.3.md` (T-157..T-166). Two phases: M1 Rules (v0.3.0,
> T-157..T-161), M2 Autopilot (v0.3.1, T-162..T-166). SRS `build/01-srs/srs-v0.3.md`.

### M1 — Rules / governance (v0.3.0) — branch `feat/v0.3.0-rules`

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| T-157 | 🟢 done | 2026-06-15 | (this commit) | `scripts/rules.py` — `.forge/rules/*.md` loader: frontmatter (stdlib split + fail-soft PyYAML, no `frontmatter` dep), scope model always/stage/glob/manual, `select()` + budget-bounded `render()`, fnmatch globs with `**` handling, CLI list/validate (argparse SUPPRESS). Never-raises. +14 tests |
| T-158 | 🟢 done | 2026-06-15 | (this commit) | `/forge:rules` skill (`name: forge-rules`) — init (idempotent scaffold) / add (no-clobber) / list / validate; `rules.py` gained those CLI subcommands. `references/rules-format.md` documents the schema + 4 scopes. +7 tests (init/add CLI + structural). validate-plugin 0 |
| T-159 | 🟢 done | 2026-06-15 | (this commit) | `hooks/session-start.py` injects `always` + current-`stage` rules (`_rules_block`, render cap 500 chars) after lessons; budget path trims lessons then drops rules last-resort to hold ≤2000 tokens. Never-raises. +6 tests (always/stage/off-stage/no-dir/glob-excluded/budget) |
| T-160 | 🟢 done | 2026-06-15 | (this commit) | `hooks/pre-tool-write.py` refactored into `_glob_rules_message` (any file type) + `_design_violations_message` (UI, existing); glob rules surface as advisory `additionalContext`, never block (exit 0). Design-system path behavior preserved. +5 tests. Full suite 1257 pass |
| T-161 | 🟢 done | 2026-06-15 | 9102b78 | Release **v0.3.0** — bump 0.3.0, CHANGELOG `[0.3.0]`, README "Project Rules" + commands/hooks rows, ROADMAP. Shipped via PR #19→develop→#20→main; **tag `v0.3.0`** + GitHub release; mirrored to polygon. Pre-release green (1295 unit, validate 0, full-pipeline 12/12). |

### M2 — Autopilot / autonomy (v0.3.1) — branch (later)

| Task | Status | Notes |
|------|--------|-------|
| T-162 | 🟢 done | `scripts/autopilot.py` deterministic planner — resolve_plan (targets --to/--stages/--until-gate, cycle entry/exit + bounds clamp, config stop_before/max_stages), plan_stages (state → {stage,skill,label}, --resume skips run-log), load_config; never-raises (malformed state → []). CLI --json/--dry-run. +18 tests |
| T-163 | 🟢 done | `/forge:autopilot` skill (`name: forge-autopilot`) — in-session loop: plan → per-stage run agent → check-gate → advance on pass / STOP on blocker (never force unless `allow_force`+reason); narrates + records run-log; checkpoint policy; honors always-rules. `autopilot.py record` subcommand (run-log via `_error_log.append_jsonl`). +3 record tests +4 structural. validate 0 |
| T-164 | 🟢 done | `--mode background` substrate — `run_stage` dispatches one stage via `_background_agent.dispatch` (cost+capability gated, session reuse), clean `unavailable` no-op under kill switch / no capability; never raises. `autopilot.py dispatch` subcommand + config `autopilot.model`. Skill documents the background path. +6 tests |
| T-165 | 🟢 done | `/forge:autopilot-stop` skill + session model in `autopilot.py` (`.forge/autopilot-session.json`): start (idempotent — warns already_running), stop (cooperative stop_requested flag checked between stages), status, finish (idle + clears flag). Skill starts/finishes the session; loop honors the flag. +7 tests |
| T-166 | 🟢 done | Release **v0.3.1** — bump 0.3.1, CHANGELOG `[0.3.1]`, README "Autopilot" + command rows, ROADMAP. Shipped combined with v0.3.0 in PR #19 (both phases); **tag `v0.3.1`** + GitHub release; mirrored to polygon. Manifests at 0.3.1; main `ebb94ef`. |

## v0.2 Task Status

> DAG: `build/04-plan/task-dag-v0.2.md` (T-136..T-156, 4 phased milestones).
> M1 (v0.2.0) is the current build target; M2 is gated on T-139 (≥90% completion).

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| T-136 | 🟢 done | 2026-06-10 | (this commit) | `hooks/_cost_cap.py` — hard-prereq spend gate (ADR-007): caps from config.yaml (fail-soft), ledger `cost-ledger.jsonl` (actual_usd from API), precheck `spent+floor` vs daily/monthly, over-cap → events.jsonl skip, never raises. test_cost_cap.py (13 cases) |
| T-137 | 🟢 done | 2026-06-10 | (this commit) | `_background_agent.dispatch()` — synchronous `claude -p --output-format json [--resume]`, captures session_id/total_cost_usd/usage/result, cost-gated via _cost_cap (precheck→skip event on over-cap; record actual after), never raises. +7 dispatch tests (ok/resume-flags/over-cap/missing-bin/nonzero/non-json/timeout) |
| T-138 | 🟢 done | 2026-06-10 | (this commit) | Probe wired into session-start: cached `.forge/capabilities.json` + **detached refresh** (TTL 24h; claude absent → sync `available:false`; present → fire-and-forget Popen — never blocks, NF-004). `FORGE_NO_BACKGROUND=1` kill switch. Unread-findings note (dormant till M2). _background_agent gains write/read_capabilities + CLI entry. +7 tests |
| T-139 | 🟢 done / **gate PASS** | 2026-06-11 | eb42b03+a8a630e | `scripts/skill_miner_bg.py` — capability-gated background skill-miner (session reuse, cost-gated) + completion/cost markers in `.forge/skill-miner-runs.jsonl`; `completion_stats()` reader. stop-reflect Step 4 branches bg↔inline. **O-2 gate CLEARED (v0.2.2): pinned `MINER_MODEL=haiku`; 6/6 live dispatches @ ~$0.022/run (was ~$1.07/run unpinned).** +8 tests |
| T-140 | 🟢 done | 2026-06-10 | (this commit) | `/forge:set-profile <type>` — `scripts/set-profile.py` validates against the 10 `## Profile:` names, updates project_type in state.md atomically (read-modify-write via _state_lib), `--dry-run` preview; `skills/forge-set-profile/SKILL.md`. +6 tests |
| T-141 | 🟢 done | 2026-06-10 | (this commit) | Release v0.2.0 — `bump-version.py 0.2.0`, CHANGELOG `[0.2.0]` (P0 foundation + spike PASS); pre-release green (1124 pass, validate 0, full-pipeline 12/12, manifests 0.2.0). PR→develop→main→tag→mirror follows. |

### M3 — Orchestration + brownfield (released as **v0.2.1**, NOT spike-gated) — branch `feat/v0.2.2-orchestration`

> Shipped as v0.2.1 (contiguous) ahead of the spike-gated daemons (originally planned
> v0.2.1); daemons land in a later version once T-139's O-2 gate clears.

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| T-148 | 🟢 done | 2026-06-10 | 07263a2 | `scripts/_orchestrate.py` — deterministic bounded fan-out: index-ordered (parallel==sequential, NF-009), delegates each call to `_background_agent.dispatch` (NF-010), parse+validate+retry-once+drop-with-reason, max_parallel/max_total bounds, dedup. ADR-006 corrected (script can't drive in-session Agent tool → delegates to claude -p). +8 tests |
| T-149 | 🟢 done | 2026-06-10 | (this commit) | `/forge:review` — `scripts/review_synthesize.py` fans 4 dimensions (correctness/security/performance/conventions) out via `_orchestrate.fan_out`, validates each reviewer's structured findings, drops malformed dims without sinking the review, synthesizes a deduped severity-sorted Markdown report. `skills/forge-review/SKILL.md`. First E2E consumer of T-148. +5 tests |
| T-150 | 🟢 done | 2026-06-10 | (this commit) | `/forge:adopt` brownfield onboarding (EF-014) — `scripts/adopt.py`: reuse `detect()`, bounded deterministic file sampling (excludes meta dirs, prioritizes manifests; `adopt.max_files` default 40), fan out requirements+architecture extractors via `_orchestrate`, write INFERRED srs.md/architecture.md drafts (confidence + provenance) + seeded state.md (Stage 1). **Read-only to user source** (only pipeline/+.forge/), `--dry-run` (no spend), refuses if already initialized, tolerates dropped aspects. `skills/forge-adopt/SKILL.md`. +7 tests |
| T-151 | 🟢 done | 2026-06-10 | (this commit) | `/forge:why` LLM fallback (REQ-F-050) — on a deterministic miss, if background capability available + not opted out, dispatch one orchestrated explainer (`_orchestrate`, cost-gated) and return a clearly-marked best-effort answer (exit 0); unchanged `not found`/exit 1 otherwise. `_should_try_fallback` + `_llm_fallback` in why.py; skill note. +3 tests |
| T-152 | 🟢 done | 2026-06-10 | (this commit) | Release **v0.2.1** (M3, contiguous) — `bump-version.py 0.2.1`, CHANGELOG `[0.2.1]`, ROADMAP re-map (daemons deferred). Pre-release green. PR→develop→main→tag→mirror. |

### M2 — Background daemons (built as **v0.2.3**, O-2 gate cleared by v0.2.2) — branch `feat/v0.2.3-daemons`

> Renumbered from the DAG's "v0.2.1" (that label was consumed when M3 shipped early).
> All daemons: cheap model + session reuse, capability-gated no-op, never-raises.

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| T-146 | 🟢 done | 2026-06-11 | bb03b28 | `hooks/_error_log.py` — shared stdlib rotation (`rotate_if_needed`/`append_jsonl`), numbered backups at a byte ceiling via atomic `os.replace`; wired into `_emit_error` (`FORGE_LOG_MAX_BYTES`). +11 tests |
| T-142 | 🟢 done | 2026-06-11 | 1284457 | Observer — `scripts/observer.py`, `/forge:watch`+`/forge:watch-stop`. Reused-session poll, idempotent start, findings→`observer-findings.jsonl` (rotated), cursor-tracked surfacing at session start + `/forge:status`, lazy detached poll, `.forge`-only boundary. `references/daemon-bus.md`. +16 tests |
| T-143 | 🟢 done | 2026-06-11 | d54dd68 | Dreamer — `scripts/dreamer.py`, `/forge:dreamer-run`. Confidence decay→dormant, dup (Jaccard≥0.8) + contradiction detection **flag-only**, idempotent daily digest `pipeline/log/daily-<date>.md`, atomic lessons.yaml, optional cheap-model consolidation. +26 tests |
| T-144 | 🟢 done | 2026-06-11 | 38efec5 | Health — `scripts/health_check.py`, `/forge:health-check`. Hook-test + lesson-integrity aggregation → healthy/degraded/failing; auto-disable policy-gated + **never silent** (events.jsonl + `health-surface.txt`, surfaced at session start, cleared on recovery). +28 tests (+4 session-start) |
| T-145 | 🟢 done | 2026-06-11 | c0a5f4f | Async miner production path — bg miner now drafts `proposed-skills/<slug>/SKILL.md` (was a dead-end `proposals.jsonl`), so it feeds the same approval flow as inline. +1 regression test |
| T-147 | 🟡 staged | 2026-06-11 | (this commit) | Release **v0.2.3** — `bump-version.py 0.2.3`, CHANGELOG `[0.2.3]`, ROADMAP/progress. Pre-release green. PR→develop done; **develop→main + tag BLOCKED by MAIN PROTECTION ruleset** — promotes with v0.2.2 once resolved. |

## v0.1.7 Task Status

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| T-131 | 🟢 done | 2026-06-09 | 3cbc4ad | REQ-PROFILE-MONOREPO-001: monorepo profile + detection (top of detect(); workspace markers / `workspaces` / `[workspace]` / packages+apps) + check_monorepo_graph.py (internal dep-graph cycle detection); test_check_monorepo_graph.py |
| T-132 | 🟢 done | 2026-06-09 | 06d3d84 | REQ-PROFILE-MOBILE-001: mobile profile + detection (Flutter/iOS/Android/RN, before fullstack so RN≠fullstack) + check_store_readiness.py (per-platform store metadata); test_check_store_readiness.py |
| T-133 | 🟢 done | 2026-06-09 | 23e4c1b | REQ-PROFILE-DATACONTRACT-001: data-contract profile + detection (.proto/schemas/buf, before api, guarded so gRPC-with-server-dep stays api) + check_schema_compat.py (proto field-number hygiene + buf policy; not a semantic diff); test_check_schema_compat.py |
| T-134 | 🟢 done | 2026-06-09 | (this commit) | Wiring: load-profile parity test extended to all 8 standard profiles; monorepo gained a stage_5 override (≥3 invariant); README profile table + Detection Heuristics doc synced; progress + ROADMAP |
| T-135 | 🟢 done | 2026-06-09 | 7ddb408 | Release: bump-version.py 0.1.7 + CHANGELOG [0.1.7]; pre-release green (1076 pass, validate 0, full-pipeline 12/12); tagged v0.1.7, GitHub release, mirrored to polygon |

## v0.1.6 Task Status

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| T-126 | 🟢 done | 2026-06-09 | f8275bb | REQ-INTERACTIVE-CLARIFY-001: /forge:srs asks one bounded clarifying-question round (single batch, not a drip) before writing srs.md + records assumptions; reconciled "3 rounds"→"1 round" in architecture.md + 2 references; test_interactive_clarify.py; 1026 pass |
| T-127 | 🟢 done | 2026-06-09 | 047a361 | REQ-INTERACTIVE-CONFIRM-001: /forge:spec + /forge:plan present an outline + pause for confirmation before the full artifact; spec-writer/planner reflect it; test_interactive_confirm.py asserts confirm-precedes-write ordering |
| T-128 | 🟢 done | 2026-06-09 | 58483aa | REQ-INTERACTIVE-NARRATE-001: /forge:build narrates start/result/next per task; build-batch.py emits per-task `[Forge] task T-XXX — starting` on stderr (stdout id-list contract preserved); test_interactive_narrate.py (behavioral subprocess check) |
| T-129 | 🟢 done | 2026-06-09 | (this commit) | Wiring: progress + ROADMAP + traceability for v0.1.6; ACs marked satisfied in srs-v0.1.6.md §6 |
| T-130 | 🟢 done | 2026-06-09 | 894d1fc | Release: bump-version.py 0.1.6 (first real use) + CHANGELOG [0.1.6]; pre-release verification green (1026 pass, validate 0, full-pipeline 12/12); tagged v0.1.6, GitHub release, mirrored to polygon |

## v0.1.5 Task Status

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| T-101 | 🟢 done | 2026-06-09 | — | `references/stage-order.md` + `scripts/_stage_table.py` loader + 38 tests; single source of truth (dirs, prereqs, next-hints, bounds, cycles); resolves EF-005 dir-name drift; 745/745 pass |
| T-102 | 🟢 done | 2026-06-09 | — | canonicalized ALL stage paths (broader than EF-005: stages 4/8/9/10/11 wedged). 17 files (7 skills + 9 agents + CHANGELOG); dir+filename renames to match gates; added feedback-log.md & backlog-updates.md (gate blockers skills never wrote); test_canonical_paths.py guard; 753/753 pass |
| T-103 | 🟢 done | 2026-06-09 | 1 commit | `next-hint` subcommand reads canonical hint from stage table; all 12 stage skills invoke it; fixed 2 dead-command hints + forge-status table; test_next_hint.py (57 tests); 810 pass |
| T-104 | 🟢 done | 2026-06-09 | 442c2af | REQ-PIPEBOUNDS-001: advance rejects out-of-range, cycle-wraps past 12 to (cycle+1,0); validate_frontmatter range-checks current_stage; set -1/99/13 rejected, state intact; test_pipebounds.py; 821 pass |
| T-105 | 🟢 done | 2026-06-09 | df811ea | REQ-GATE-ENTRY-001: check_prerequisite + `preflight --stage N` (exit 2); advance skips need --force; 10 stage skills gated; force-advance routes via force=True; test_entry_gates.py; 847 pass |
| T-106 | 🟢 done | 2026-06-09 | 51a843a | REQ-SILENTSTATE-001: hooks/_state_read.py helper; 6 hook read-sites route through it (warn + log to .forge/errors.log); check-gate inconclusive+exit2 on unreadable state; doctor check_state_read_failures; session-end footer; test_silentstate.py (9); 856 pass |
| T-107 | 🟢 done | 2026-06-09 | 2a5d0e9 | REQ-DOCTOR-001: doctor runs current-stage gate inline; overall_status healthy/wedged/broken; JSON carries overall_status; test_doctor_gate.py; 864 pass |
| T-108 | 🟢 done | 2026-06-09 | 1d1bb47 | REQ-GATESTUB-001 fail-loud: missing script → inconclusive + blocker-promoted + exit2; doctor/status banner; stop-reflect parses gate JSON regardless of exit; test_gatestub.py; full-pipeline xfail until M4; 866 pass |
| T-109 | 🟢 done | 2026-06-09 | 220a320 | 5 req+spec scripts: check_srs_acceptance, traceability-check, spec-coverage, check_dag_completeness, check_dag_completion; test_gate_scripts_req_spec.py; 883 pass |
| T-110 | 🟢 done | 2026-06-09 | 2d22e21 | 5 build+eval scripts: token-audit, check_coverage, check_todos, check_progress_sync, check_nfr_coverage; test_gate_scripts_build_eval.py; 901 pass |
| T-111 | 🟢 done | 2026-06-09 | d1541b4 | 5 release+health scripts: check_open_bugs, check_health, check_hotfix_tests, check_git_tag; some_check.py = doc-example only (justified); 917 pass |
| T-112 | 🟢 done | 2026-06-09 | 387192f (+T-125 fixtures) | AC-GATESTUB-001b audit green; traceability all argv modes; heading-based task detection. Fixture harmonization landed in T-125 → full-pipeline xfail removed, passes 12/12 |
| T-113 | 🟢 done | 2026-06-09 | f049195 | REQ-EXTRACT-CWD-001: extract-lessons.py --cwd derives input/output; explicit overrides; test_extract_lessons_cwd.py; 923 pass |
| T-114 | 🟢 done | 2026-06-09 | feat/t-114-lesson-signals | REQ-LESSON-SOURCES-001: _signal_producers.py (5 producers reading .forge/errors.log); _state_read.log_event sink; pre-tool-write logs violations, post-tool-use logs heredoc bypass, stop-reflect logs gate_outcome, session-end runs producers + materializes via extract/sync; test_lesson_signals.py (12); 942 pass |
| T-115 | 🟢 done | 2026-06-09 | 7aeed8a | REQ-LESSON-SOURCES-001 EF-026: promote freq≥2 gate + 30-day TTL recall in session-start; is_stale(); test_promote_ttl.py + isolation guard; 930 pass |
| T-116 | 🟢 done | 2026-06-09 | d40b5a4 | REQ-BUILDBATCH-001: build-batch.py (ordered tasks, --resume, large-batch warn); forge-build Milestone Batch Mode; test_build_batch.py; 950 pass |
| T-117 | 🟢 done | 2026-06-09 | cb9f185 | REQ-WHYCI-001: why.py _GATE_PATTERN IGNORECASE + target.upper(); test_why additions; 953 pass |
| T-118 | 🟢 done | 2026-06-09 | a58cb12 | REQ-SESSIONLOG-001: session-end appends .forge/session.jsonl (commands/tokens/reflection_ref, PII-free, versioned); test_session_log.py; 957 pass |
| T-119 | 🟢 done | 2026-06-09 | a24a7b8 | REQ-STAGEREFLECT-001: stage-reflect.py rollup → pipeline/0X/reflection.md; stop-reflect spawns on advance; test_stage_reflect.py; 961 pass |
| T-120 | 🟢 done | 2026-06-09 | e3b675b | REQ-PATTERN-001: schema_version on patterns; references/pattern-schema.md; test_pattern_bus.py (schema-valid + 3-use proposal); 963 pass |
| T-121 | 🟢 done | 2026-06-09 | a86445d | REQ-WEBSEARCH-001: spec-writer gains WebSearch; cite-or-skip rule on 4 research/spec agents; planner excluded; test_agent_tools.py; 972 pass |
| T-122 | 🟢 done | 2026-06-09 | 2ce8b9c | AC-INTERACTIVE-001a: REQ-INTERACTIVE-001 → CLARIFY/CONFIRM/NARRATE-001 (v0.1.6); test_interactive_decomposition.py |
| T-123 | 🟢 done | 2026-06-09 | c971d32 | REQ-LARGEDOC-001: large-doc-layout.md + read-doc.py resolver (single/multi-file); forge-spec uses it; test_large_doc.py |
| T-124 | 🟢 done | 2026-06-09 | aa9183a | REQ-DOCS-001 + REQ-FEEDBACK-001: third-party-hook troubleshooting + README entry + issue template; test_docs_troubleshooting.py |
| T-125 | 🟢 done | 2026-06-09 | (this commit) | Release: CHANGELOG [0.1.5] + version bump 0.1.5; sample-todo-api fixture harmonization → full-pipeline passes 12/12, xfail removed; 986 pass |

## Task Status

| Task | Status | Started | Completed | Commit | Notes |
|------|--------|---------|-----------|--------|-------|
| T-001 | 🟢 done | 2026-05-06 | 2026-05-07 | 86a0b03 | plugin.json, 7 stubs, validate-plugin.py, tests |
| T-002 | 🟢 done | 2026-05-07 | 2026-05-07 | 80e4f1f | forge-init skill, init-pipeline.sh, detect-project-type.py, 14 tests |
| T-003 | 🟢 done | 2026-05-10 | 2026-05-10 | 0950935 | _state_lib.py, state-manager.py CLI, 36 tests, 93% cov |
| T-004 | 🟢 done | 2026-05-10 | 2026-05-10 | — | forge-status SKILL.md |
| T-005 | 🟢 done | 2026-05-07 | 2026-05-07 | b023844 | pre-authored in foundation commit; 12 stages, all YAML valid |
| T-006 | 🟢 done | 2026-05-10 | 2026-05-10 | — | check-gate.py, 14 tests, all 4 check types |
| T-007 | 🟢 done | 2026-05-10 | 2026-05-10 | — | session-start.py hook, 17 tests, token budget enforced |
| T-008 | 🟢 done | 2026-05-10 | 2026-05-10 | — | prompt-submit.py hook, 16 tests, stage intent + correction flagging |
| T-009 | 🟢 done | 2026-05-10 | 2026-05-10 | — | stop-reflect.py, _invoke_agent.py, 20 unit + 8 integration tests |
| T-010 | 🟢 done | 2026-05-10 | 2026-05-10 | — | session-end.py, 18 tests, session summary to .forge/sessions/ |
| T-011 | 🟢 done | 2026-05-10 | 2026-05-10 | — | pre-tool-write.py, 35 tests, 5 violation types detected |
| T-012 | 🟢 done | 2026-05-10 | 2026-05-10 | — | post-tool-use.py, 18 tests, session-log + patterns.jsonl |
| T-013 | 🟢 done | 2026-05-10 | 2026-05-10 | — | plugin.json pre-wired in T-001; validate-plugin.py confirms all 7 hooks valid |
| T-014 | 🟢 done | 2026-05-10 | 2026-05-10 | — | 12 agent persona files; role/goal/scope/output/workflow per spec |
| T-015 | 🟢 done | 2026-05-10 | 2026-05-10 | — | 12 stage SKILL.md files + prompt-submit aliases (product, arch) |
| T-016 | 🟢 done | 2026-05-10 | 2026-05-10 | — | 4 cross-stage agent personas: reflector, lesson-extractor, skill-miner, gate-checker |
| T-017 | 🟢 done | 2026-05-11 | 2026-05-11 | — | context-pruner.py, 35 tests, stage 6 exclusions verified |
| T-018 | 🟢 done | 2026-05-11 | 2026-05-11 | — | forge-resume SKILL.md; uses context-pruner + state-manager |
| T-019 | 🟢 done | 2026-05-11 | 2026-05-11 | — | extract-lessons.py, 43 tests, done-when criterion verified |
| T-020 | 🟢 done | 2026-05-12 | 2026-05-12 | — | 3 new tests: ml/gpu done-when, project-type exclusion, frequency sort |
| T-021 | 🟢 done | 2026-05-12 | 2026-05-12 | — | sync-lessons.py, 37 tests; session-start auto-syncs on stale md |
| T-022 | 🟢 done | 2026-05-12 | 2026-05-12 | — | promote-lessons.py, ~/.forge/ scaffold, 39 tests; session-start auto-registers+promotes |
| T-023 | 🟢 done | 2026-05-12 | 2026-05-12 | — | detect-project-type.py: train.py+ML libs+notebooks+API types; 10 new tests; forge-init SKILL.md updated |
| T-024 | 🟢 done | 2026-05-12 | 2026-05-12 | — | fullstack profile extended (stage_3 + stage_6); all 5 profiles ≥3 stage overrides; YAML valid; 427/427 tests pass |
| T-025 | 🟢 done | 2026-05-12 | 2026-05-12 | — | load-profile.py + 24 tests; 12 stage skills wired to call it; ML stage 7 surfaces G7-ML-005 drift; 451/451 tests pass |
| T-026 | 🟢 done | 2026-05-12 | 2026-05-12 | — | sliding 3-tool window with sha1 signature; 22 tests; done-when 3-occurrence signature stability verified; 455/455 |
| T-027 | 🟢 done | 2026-05-12 | 2026-05-12 | — | mine-skills.py + 33 tests; freq≥3 → SKILL.md draft with name/description/steps; blacklist + skill-name collision filters; 488/488 tests pass |
| T-028 | 🟢 done | 2026-05-12 | 2026-05-12 | — | skill-approval.py (list/approve/reject) + 22 tests; stop-reflect.py surfaces proposals; mine-skills.py skips existing to preserve edits; full approve/modify/reject cycle verified end-to-end; 515/515 tests pass |
| T-029 | 🟢 done | 2026-05-12 | 2026-05-12 | — | forge-retro SKILL.md + 16 structural tests; retro covers what went well / didn't / lessons / skills proposed; writes to pipeline/12-release/retro.md; 531/531 tests pass |
| T-030 | 🟢 done | 2026-05-12 | 2026-05-12 | — | user-facing README; install, quickstart, 12-stage table, hooks, profiles, config, tests |
| T-031 | 🟢 done | 2026-05-12 | 2026-05-12 | — | CONTRIBUTING.md rewritten; docs/agent-authoring.md created — walkthroughs for adding agents, stages, profiles; 531/531 tests pass |
| T-032 | 🟢 done | 2026-05-12 | 2026-05-12 | — | full-pipeline.sh + 29 fixture artifacts (12 stages); check_dir_nonempty.py; gate checks + traceability chain; test isolation fix for TestLessonsFiltering; 532/532 tests pass |
| T-033 | 🟢 done | 2026-05-12 | 2026-05-12 | — | CHANGELOG.md; ROADMAP.md updated; v0.1.0 tagged |

## Status Legend

- 🔲 todo
- 🟡 in progress
- 🟢 done
- 🔴 blocked

## Session History

*(Filled in by session-end summaries.)*

## Resume Hint

To continue work in a new session:
```
Read CLAUDE.md, then this file (build/05-implementation/progress.md).
The first 🔲 task in the table is your next task.
Read its corresponding prompt at prompts/development/T-XXX-*.md.
```
