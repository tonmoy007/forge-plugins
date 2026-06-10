# Implementation Progress

> Updated by Claude as work progresses. This is the first thing to read after CLAUDE.md
> at session start to know where we are.

## Current State

- **Active program: v0.2** (phased v0.2.0→v0.2.3) — "a system that works alongside
  you": daemons, orchestration, brownfield, sprint.
- **v0.2.0 (M1 foundation) COMPLETE + RELEASED** — T-136..T-141. Cost cap + ledger,
  background-agent dispatch (`claude -p`, session reuse), capability probe wired into
  session-start, background skill-miner instrumentation, `/forge:set-profile`. Tag
  `v0.2.0` (`bd9d58a`) + GitHub release; main `16839ee`, develop `709710c`;
  **origin/polygon parity**. 1124 tests pass; validate 0; full-pipeline 12/12.
  - Planning (Stages 1/3/5): SRS reviewed, **spike PASS** (O-1 dispatch + O-2 cost
    RESOLVED — `claude -p --output-format json` headless, `--resume` cuts cost 10×:
    $0.053→$0.0046), architecture + ADR-005/006/007 (OQ-001..008 resolved), DAG
    `task-dag-v0.2.md` (T-136..T-156).
- **NEXT**: **M2 daemons (v0.2.1) are SPIKE-GATED** on T-139's O-2 completion-rate
  (≥90% over ≥5 real sessions) — accruing via `skill_miner_bg.completion_stats`.
  **M3 (v0.2.2 orchestration + brownfield) is NOT gated** (needs only the cost cap,
  shipped) and may proceed in parallel — T-148 next there.
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

## v0.2 Task Status

> DAG: `build/04-plan/task-dag-v0.2.md` (T-136..T-156, 4 phased milestones).
> M1 (v0.2.0) is the current build target; M2 is gated on T-139 (≥90% completion).

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| T-136 | 🟢 done | 2026-06-10 | (this commit) | `hooks/_cost_cap.py` — hard-prereq spend gate (ADR-007): caps from config.yaml (fail-soft), ledger `cost-ledger.jsonl` (actual_usd from API), precheck `spent+floor` vs daily/monthly, over-cap → events.jsonl skip, never raises. test_cost_cap.py (13 cases) |
| T-137 | 🟢 done | 2026-06-10 | (this commit) | `_background_agent.dispatch()` — synchronous `claude -p --output-format json [--resume]`, captures session_id/total_cost_usd/usage/result, cost-gated via _cost_cap (precheck→skip event on over-cap; record actual after), never raises. +7 dispatch tests (ok/resume-flags/over-cap/missing-bin/nonzero/non-json/timeout) |
| T-138 | 🟢 done | 2026-06-10 | (this commit) | Probe wired into session-start: cached `.forge/capabilities.json` + **detached refresh** (TTL 24h; claude absent → sync `available:false`; present → fire-and-forget Popen — never blocks, NF-004). `FORGE_NO_BACKGROUND=1` kill switch. Unread-findings note (dormant till M2). _background_agent gains write/read_capabilities + CLI entry. +7 tests |
| T-139 | 🟡 code shipped / gate PENDING | 2026-06-10 | (this commit) | `scripts/skill_miner_bg.py` — capability-gated background skill-miner (session reuse, cost-gated) + completion/cost markers in `.forge/skill-miner-runs.jsonl`; `completion_stats()` reader. stop-reflect Step 4 branches bg↔inline. **Gate (≥90%/≥5 sessions) accrues over real use — not fabricated.** +7 tests |
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
