# Task DAG — Forge v0.1.5

> Scope locked 2026-06-09 (`build/01-srs/srs-v0.1.5.md` §6). 25 tasks across
> 7 milestones. Work them in topological order; the first unblocked task is
> the next to start.
>
> Format: `T-NNN [size] title`
> Size: S (small, ~30min), M (medium, ~2hr), L (large, ~half-day)
> Numbering continues from the build DAG (T-001…T-033 are v0.1.0–v0.1.3).
>
> **Theme**: sand off v0.1.3 sharp edges and kill the surface-healthy /
> substance-inert antipattern family at every layer (state, hook, doctor,
> gate-config, lesson-store).
>
> **Prerequisite (not a task)**: PR #1 (`develop`) carrying EF-021/022/023
> hotfixes merges to `main` first, so v0.1.5 builds on a green base.

---

## Milestone 1: Single Source of Truth + Paths

> The bug fixes for next-step hint, entry gates, path collision, and state
> bounds all need one authoritative stage table. Build it first; everything
> downstream reads from it.

### T-101 [M] Canonical stage-order + prerequisite table
- **Description**: One machine-readable table (stages 0–12) holding: canonical
  directory name (`04-spec`, not `04-technical-spec`), next-step hint text,
  prior-stage prerequisite artifact, and the post-stage-12 wrap semantics.
  Single source for NEXTHINT, GATE-ENTRY, PATHS, PIPEBOUNDS.
- **Files**: `references/stage-order.md` (+ a tiny `scripts/_stage_table.py`
  loader if skills/hooks need it programmatically), `tests/unit/test_stage_table.py`
- **Done when**: loader returns the correct next-stage + prerequisite for all
  12 transitions; table validates; no duplicate dir names.
- **Depends on**: none
- **REQ-IDs**: REQ-NEXTHINT-001, REQ-GATE-ENTRY-001, REQ-PATHS-001, REQ-PIPEBOUNDS-001

### T-102 [S] Fix canonical path collision (`04-spec`)
- **Description**: Change `skills/forge-spec/SKILL.md` step 4 from
  `pipeline/04-technical-spec/` to `pipeline/04-spec/`; add a one-time
  migration note to the CHANGELOG for v0.1.3.x projects with a populated
  `04-technical-spec/`.
- **Files**: `skills/forge-spec/SKILL.md`, `CHANGELOG.md`
- **Done when**: no skill writes to `04-technical-spec/`; integration test
  asserts every stage writes inside its canonical dir.
- **Depends on**: T-101
- **REQ-IDs**: REQ-PATHS-001

### T-103 [S] Next-step hint derived from the table
- **Description**: Refactor stage skills / `state-manager` to read the
  next-step hint from T-101 instead of hardcoded strings; after `01-srs` the
  hint names **product/UX**, not architecture.
- **Files**: stage `SKILL.md` files, `scripts/state-manager.py`,
  `tests/unit/test_next_hint.py`
- **Done when**: a test enumerates each transition and asserts the hint names
  the correct next stage; grep test finds no hardcoded "next step" strings
  outside the helper.
- **Depends on**: T-101
- **REQ-IDs**: REQ-NEXTHINT-001

---

## Milestone 2: State Integrity & Entry Gates

### T-104 [M] Stage-bound enforcement + cycle-wrap
- **Description**: `_state_lib.advance_stage` enforces [0,12], rejects (not
  warns) out-of-range; `cmd_set` validates `current_stage` type/range; past
  stage 12 either wraps to (cycle+1, stage 0) or blocks with a `/forge:retro`
  hint per the T-101 table.
- **Files**: `scripts/_state_lib.py`, `scripts/state-manager.py`,
  `tests/unit/test_state_manager.py`
- **Done when**: AC-PIPEBOUNDS-001a/b/c pass — no `current_stage: 13`,
  negative/oversized `set` rejected, state and gate layers agree.
- **Depends on**: T-101
- **REQ-IDs**: REQ-PIPEBOUNDS-001, REQ-GATE-ENTRY-001

### T-105 [M] Pre-flight entry blocks for stages 2–11
- **Description**: Each stage skill checks its prior-stage prerequisite
  artifact (from T-101) before adopting its persona; exits 2 with a one-line
  message naming the missing file + the skill to run instead. `advance_stage`
  rejects `to > old + 1` unless invoked via `/forge:force-advance`.
- **Files**: stage `SKILL.md` files (2–11), `scripts/_state_lib.py`,
  `scripts/force-advance.py`, `tests/unit/test_entry_gates.py`
- **Done when**: AC-GATE-ENTRY-001a/b/c — one passing test per stage 2–11;
  `advance --to N>current+1` non-zero without `--force`.
- **Depends on**: T-101, T-104
- **REQ-IDs**: REQ-GATE-ENTRY-001

---

## Milestone 3: Fail-Loud Surfacing (antipattern family)

### T-106 [M] Surface state-read failures
- **Description**: Hooks stop silently swallowing `read_state` errors —
  visible one-line warning on first failure, `inconclusive` gate output on
  unreadable state, `/forge:doctor` + Stop-hook footer surface the
  `state_read_failed` count.
- **Files**: `hooks/*.py`, `scripts/check-gate.py`, `scripts/doctor.py`,
  `hooks/session-end.py`, `tests/unit/test_silentstate.py`
- **Done when**: AC-SILENTSTATE-001a/b — synthetic unreadable state produces
  all four signals; grep test finds no bare state-read `except` without a
  user-visible signal.
- **Depends on**: none
- **REQ-IDs**: REQ-SILENTSTATE-001

### T-107 [M] Doctor runs current-stage gate inline
- **Description**: `doctor.py` runs the current stage's gate as part of its
  check set; top-line status becomes `healthy` / `wedged` / `broken`; names
  failing G-IDs; can never contradict `/forge:status`.
- **Files**: `scripts/doctor.py`, `skills/forge-doctor/SKILL.md`,
  `tests/unit/test_doctor.py`
- **Done when**: AC-DOCTOR-001a/b/c — wedged stage → `wedged` + failing IDs;
  all-pass → `healthy`; doctor/status back-to-back diff shows no contradiction.
- **Depends on**: T-106
- **REQ-IDs**: REQ-DOCTOR-001

### T-108 [M] `check-gate.py` fails loud on missing scripts
- **Description**: A `script_returns_zero` criterion pointing at a missing
  script reports `inconclusive` (not soft-pass), promotes `warning`→blocker at
  eval time, and surfaces a "N criteria unimplemented" banner in doctor/status.
- **Files**: `scripts/check-gate.py`, `scripts/doctor.py`,
  `skills/forge-status/SKILL.md`, `tests/unit/test_check_gate.py`
- **Done when**: AC-GATESTUB-001a/c — nonexistent script → inconclusive +
  non-zero gate regardless of severity; banner appears.
- **Depends on**: none
- **REQ-IDs**: REQ-GATESTUB-001 (fail-loud half)

---

## Milestone 4: Implement the 15 Missing Gate Scripts

> AC-GATESTUB-001b. Each script reads its inputs, exits 0 on pass / non-zero
> on fail, follows the `--cwd` convention, and ships with a unit test.

### T-109 [L] Requirements + spec gate scripts (5)
- **Description**: `check_srs_acceptance.py`, `traceability-check.py`,
  `spec-coverage.py`, `check_dag_completeness.py`, `check_dag_completion.py`.
- **Files**: `scripts/*.py`, `tests/unit/test_gate_scripts_req_spec.py`
- **Done when**: each exits correctly on pass/fail fixtures; referenced by the
  matching `references/gate-criteria.md` entries.
- **Depends on**: T-108
- **REQ-IDs**: REQ-GATESTUB-001 (implement half)

### T-110 [L] Build + evaluation gate scripts (5)
- **Description**: `token-audit.py`, `check_coverage.py`, `check_todos.py`,
  `check_progress_sync.py`, `check_nfr_coverage.py`.
- **Files**: `scripts/*.py`, `tests/unit/test_gate_scripts_build_eval.py`
- **Done when**: pass/fail fixtures verified; wired into gate-criteria.
- **Depends on**: T-108
- **REQ-IDs**: REQ-GATESTUB-001 (implement half)

### T-111 [L] Release + health gate scripts (5)
- **Description**: `check_open_bugs.py`, `check_health.py`,
  `check_hotfix_tests.py`, `check_git_tag.py`, `some_check.py` (rename/remove
  with explicit justification if it has no real criterion).
- **Files**: `scripts/*.py`, `tests/unit/test_gate_scripts_release.py`
- **Done when**: pass/fail fixtures verified; wired into gate-criteria.
- **Depends on**: T-108
- **REQ-IDs**: REQ-GATESTUB-001 (implement half)

### T-112 [S] Gate-criteria audit (no dangling scripts)
- **Description**: Enumerate every `script_returns_zero` criterion in
  `references/gate-criteria.md`; assert each referenced script exists. CI test
  that fails if any criterion points at a missing file.
- **Files**: `tests/unit/test_gate_criteria_audit.py`, `references/gate-criteria.md`
- **Done when**: AC-GATESTUB-001b — zero dangling script references at audit.
- **Depends on**: T-109, T-110, T-111
- **REQ-IDs**: REQ-GATESTUB-001

---

## Milestone 5: Lesson Capture

### T-113 [S] `extract-lessons.py --cwd` flag
- **Description**: Add `--cwd PATH` (default `.`) and derive default
  `--input`/`--output` relative to it; explicit paths still override.
- **Files**: `scripts/extract-lessons.py`, `tests/unit/test_extract_lessons.py`
- **Done when**: AC-EXTRACT-CWD-001a/b — `--cwd` discovers flags + writes
  lessons; explicit `--input` still honored.
- **Depends on**: none
- **REQ-IDs**: REQ-EXTRACT-CWD-001

### T-114 [L] Implicit lesson-signal producers (5)
- **Description**: Emit `correction-flags.jsonl` rows (pattern-match-friendly
  prompt text) on: (1) hook-error cluster ≥5, (2) repeated PreToolUse block
  ≥2, (3) bash-heredoc after Write block, (4) gate pass→wedge in session,
  (5) state-read regression. Extractor reused unchanged.
- **Files**: `hooks/post-tool-use.py`, `hooks/pre-tool-write.py`,
  `hooks/session-end.py`, `scripts/_signal_producers.py`,
  `tests/unit/test_lesson_signals.py`
- **Done when**: AC-LESSON-SOURCES-001a/b/c — one test per producer; lessons
  land; clean control session yields zero flags.
- **Depends on**: T-106 (state-read regression), T-107/T-108 (wedge signal)
- **REQ-IDs**: REQ-LESSON-SOURCES-001

### T-115 [M] Global-lessons TTL + promotion gate (EF-026)
- **Description**: `promote-lessons.py` only promotes lessons with frequency
  ≥2; recall skips global lessons with `last_used` > 30 days; tests point the
  global path at `tmp_path`, never real `~/.forge/global-lessons.yaml`.
- **Files**: `scripts/promote-lessons.py`, `tests/unit/test_promote_lessons.py`
- **Done when**: AC-LESSON-SOURCES-001d — one-shot `tmp_path` lesson not
  promoted; stale lesson not surfaced; suite leaves real home store untouched.
- **Depends on**: none
- **REQ-IDs**: REQ-LESSON-SOURCES-001

---

## Milestone 6: UX Nudges

### T-116 [M] `/forge:build --milestone N`
- **Description**: Walk every T-ID under `## Milestone N:` in dependency
  order; per-task persona/tests/commit/progress; pause on first failure with
  prior commits intact; `--milestone N --resume`; warn when N > 10.
- **Files**: `skills/forge-build/SKILL.md`, `scripts/build-batch.py` (if
  needed), `tests/unit/test_build_batch.py`
- **Done when**: AC-BUILDBATCH-001a/b/c — 3-task milestone → 3 commits;
  scripted failure halts + resumes; no-flag invocation unchanged.
- **Depends on**: none
- **REQ-IDs**: REQ-BUILDBATCH-001

### T-117 [S] `/forge:why` case-insensitive gate-ID lookup
- **Description**: Normalize gate-ID input to uppercase before lookup in
  `why.py` (`_GATE_PATTERN`); unknown IDs still report not-found.
- **Files**: `scripts/why.py`, `tests/unit/test_why.py`
- **Done when**: AC-WHYCI-001a/b — `g1-001` == `G1-001`; unknown ID still
  misses.
- **Depends on**: none
- **REQ-IDs**: REQ-WHYCI-001

### T-118 [M] `session.jsonl` enrichment
- **Description**: Record per session: commands invoked, token usage, and a
  `reflection_ref` back-reference. Schema versioned; no PII.
- **Files**: `hooks/session-end.py`, `tests/unit/test_session_log.py`
- **Done when**: AC-SESSIONLOG-001a/b — row has `commands`/`tokens`/
  `reflection_ref`; a consumer rebuilds the timeline from it alone.
- **Depends on**: none
- **REQ-IDs**: REQ-SESSIONLOG-001

### T-119 [M] Per-stage reflection rollup
- **Description**: At stage exit (gate pass + advance), emit
  `pipeline/0X-stage/reflection.md` summarizing decisions/surprises/lessons
  across that stage's sessions; references contributing session_ids + gate
  outcome.
- **Files**: `hooks/stop-reflect.py` or `scripts/stage-reflect.py`,
  `tests/unit/test_stage_reflect.py`
- **Done when**: AC-STAGEREFLECT-001a/b.
- **Depends on**: none
- **REQ-IDs**: REQ-STAGEREFLECT-001

### T-120 [S] `pattern.jsonl` carries actionable events + schema
- **Description**: Versioned schema for skill invocations / gate outcomes /
  tool patterns; non-empty on a real session; skill-miner ≥3-use trigger
  fires on synthetic data.
- **Files**: `hooks/post-tool-use.py`, `references/pattern-schema.md`,
  `tests/unit/test_pattern_bus.py`
- **Done when**: AC-PATTERN-001a/b — every line parses against schema;
  3-use sequence fires a proposal.
- **Depends on**: none
- **REQ-IDs**: REQ-PATTERN-001

### T-121 [S] WebSearch for research/spec agents
- **Description**: Add `WebSearch` to the tool allowlist for SRS / product /
  architecture / spec agents (planner excluded per OQ-3); add a cite-or-skip
  rule to each persona.
- **Files**: `agents/*.md`, `tests/unit/test_agent_tools.py`
- **Done when**: AC-WEBSEARCH-001a/b — affected agents list WebSearch + the
  rule; outputs cite when used.
- **Depends on**: none
- **REQ-IDs**: REQ-WEBSEARCH-001

---

## Milestone 7: Conventions, Docs & Decomposition

### T-122 [S] Decompose REQ-INTERACTIVE-001 into ≥2 concrete REQs
- **Description**: Using the two testers' signal (EF-013), replace
  REQ-INTERACTIVE-001 with ≥2 concrete REQs (candidates: clarifying-question
  pattern in requirements-analyst, staged confirmation in spec/plan, progress
  narration in builder) — or drop it with rationale. Spec task, runs before
  any interactive impl.
- **Files**: `build/01-srs/srs-v0.1.5.md`
- **Done when**: AC-INTERACTIVE-001a — REQ replaced by ≥2 REQs or explicitly
  dropped.
- **Depends on**: none
- **REQ-IDs**: REQ-INTERACTIVE-001

### T-123 [S] Large-doc split convention
- **Description**: Document `pipeline/0X-stage/<doc>/` + `index.md` manifest
  layout (backward-compatible with single-file); one stage skill (likely
  `forge:spec`) reads either layout.
- **Files**: `references/large-doc-layout.md`, `skills/forge-spec/SKILL.md`,
  `tests/unit/test_large_doc.py`
- **Done when**: AC-LARGEDOC-001a/b.
- **Depends on**: T-101
- **REQ-IDs**: REQ-LARGEDOC-001

### T-124 [S] Troubleshooting third-party hooks doc + issue template
- **Description**: Add a "Troubleshooting third-party hooks" section
  (identify hook owner via `/plugin list`; Forge's only PreToolUse hook is
  `pre-tool-write.py`); carry forward the v0.1.4 GitHub issue template
  (REQ-FEEDBACK-001) deferred from the amended dogfood.
- **Files**: `README.md` or `docs/getting-feedback.md`,
  `.github/ISSUE_TEMPLATE/forge-feedback.md`
- **Done when**: AC-DOCS-001a/b — section exists + linked from README "if
  something looks wrong"; issue template present.
- **Depends on**: none
- **REQ-IDs**: REQ-DOCS-001, REQ-FEEDBACK-001 (carried from v0.1.4)

### T-125 [S] Release: CHANGELOG, version bump, meta-validation
- **Description**: `[0.1.5]` CHANGELOG entry (including the "v0.1.4 amended,
  not tagged" version-history note); bump `plugin.json` + `marketplace.json`
  to `0.1.5`; full suite green; `validate-plugin.py` exit 0; Forge-on-Forge
  gate pass.
- **Files**: `CHANGELOG.md`, `.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`
- **Done when**: §6 acceptance items 5–7 satisfied; tag `0.1.5`.
- **Depends on**: all prior tasks
- **REQ-IDs**: (release)

---

## Dependency Summary

```
T-101 ─┬─ T-102
       ├─ T-103
       ├─ T-104 ── T-105
       └─ T-123
T-106 ── T-107
T-106, T-108 ──┐
T-108 ── T-109, T-110, T-111 ── T-112
T-106 ──────────┴── T-114
(independent: T-113, T-115, T-116, T-117, T-118, T-119, T-120, T-121, T-122, T-124)
T-125 depends on all
```

## Suggested execution order

M1 (T-101→103) → M2 (T-104→105) → M3 (T-106→108) → M4 (T-109→112) →
M5 (T-113→115) → M6 (T-116→121) → M7 (T-122→125).

T-122 (interactive decomposition) is a spec task — do it early so any REQs it
spawns can be scheduled into M6 before implementation.
