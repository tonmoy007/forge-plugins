# Task DAG — Forge v0.1.6

> Scope locked 2026-06-09 (`build/01-srs/srs-v0.1.6.md` §6). 5 tasks across
> 2 milestones. Numbering continues from v0.1.5 (T-101…T-125); v0.1.6 is
> T-126…T-130.
>
> Format: `T-NNN [size] title`
> Size: S (small, ~30min), M (medium, ~2hr), L (large, ~half-day)
>
> **Theme**: make Forge interactive — clarify before scoping, confirm before
> expensive writes, narrate during builds.
>
> **Parallelism**: T-126 / T-127 / T-128 are independent (disjoint files, no
> shared edits) and are the fan-out batch. T-129 (wiring) depends on all three;
> T-130 (release) depends on T-129.

---

## Milestone 1: Interactive behaviors (parallel)

### T-126 [M] CLARIFY — clarifying-question pattern in /forge:srs
- **Description**: Make the requirements-analyst's clarifying-question step a
  reliable, bounded behavior. Add to `skills/forge-srs/SKILL.md` an explicit
  step: before writing `srs.md`, ask **one bounded batch** of clarifying
  questions (scope/users/constraints), then proceed recording explicit
  assumptions for unanswered items. Tighten `agents/requirements-analyst.md` so
  the bound ("one round / not a drip", existing "max 3 rounds") and the
  assumptions-recording rule are unambiguous.
- **Files**: `skills/forge-srs/SKILL.md`, `agents/requirements-analyst.md`,
  `tests/unit/test_interactive_clarify.py`
- **Done when**: AC-INTERACTIVE-CLARIFY-001a/b — test asserts both files contain
  the bounded clarifying-question directive *before* SRS write and the
  assumptions-recording rule; grep finds no "ask questions one at a time"/drip
  wording. Full suite green.
- **Depends on**: none
- **REQ-IDs**: REQ-INTERACTIVE-CLARIFY-001

### T-127 [M] CONFIRM — staged confirmation in /forge:spec and /forge:plan
- **Description**: Add an outline-then-confirm step to `skills/forge-spec/SKILL.md`
  and `skills/forge-plan/SKILL.md`: present a short outline / table of contents
  and pause for explicit user confirmation before generating the full technical
  spec / full task DAG. Reflect the same in `agents/spec-writer.md` and
  `agents/planner.md`.
- **Files**: `skills/forge-spec/SKILL.md`, `skills/forge-plan/SKILL.md`,
  `agents/spec-writer.md`, `agents/planner.md`,
  `tests/unit/test_interactive_confirm.py`
- **Done when**: AC-INTERACTIVE-CONFIRM-001a — test asserts both skills contain
  an outline/TOC step AND an explicit confirmation pause that precedes full-
  artifact generation. Full suite green.
- **Depends on**: none
- **REQ-IDs**: REQ-INTERACTIVE-CONFIRM-001

### T-128 [M] NARRATE — progress narration in /forge:build
- **Description**: Add per-task-boundary narration to `skills/forge-build/SKILL.md`
  and `agents/builder.md` (announce task starting → test/commit result → what's
  next). Add a narration line to `scripts/build-batch.py` so a `--milestone N`
  listing emits an observable per-task start line at the tool layer.
- **Files**: `skills/forge-build/SKILL.md`, `agents/builder.md`,
  `scripts/build-batch.py`, `tests/unit/test_interactive_narrate.py`
- **Done when**: AC-INTERACTIVE-NARRATE-001a/b — test asserts the narration
  directive in skill+agent and that `build-batch.py` emits a per-task narration
  line (start + task id). Existing `test_build_batch.py` stays green (extend it
  if the output contract changes). Full suite green.
- **Depends on**: none
- **REQ-IDs**: REQ-INTERACTIVE-NARRATE-001

---

## Milestone 2: Release wiring

### T-129 [S] Acceptance + traceability + docs wiring
- **Description**: Mark the three ACs satisfied in `srs-v0.1.6.md` §6, confirm
  the §4 traceability table maps every REQ → task → green test, and update
  `build/05-implementation/progress.md` (T-126..T-130 rows) and `ROADMAP.md`
  (v0.1.6 milestone). No new pipeline stage, so `references/gate-criteria.md`
  is unchanged (verify nothing references a v0.1.6 gate).
- **Files**: `build/01-srs/srs-v0.1.6.md`, `build/05-implementation/progress.md`,
  `ROADMAP.md`
- **Done when**: traceability complete; progress + roadmap reflect v0.1.6;
  full suite green.
- **Depends on**: T-126, T-127, T-128
- **REQ-IDs**: REQ-INTERACTIVE-CLARIFY-001, REQ-INTERACTIVE-CONFIRM-001, REQ-INTERACTIVE-NARRATE-001

### T-130 [S] Release v0.1.6 — version bump + CHANGELOG
- **Description**: Run `scripts/bump-version.py 0.1.6` (bumps both manifests +
  inserts the dated `## [0.1.6]` CHANGELOG skeleton), then fill the CHANGELOG
  section (the three interactive features). Run full pre-release verification.
  This is the Phase 3/4 gate of the release runbook; the PR→develop→main→tag
  →mirror steps follow interactively after this task is green.
- **Files**: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `CHANGELOG.md`
- **Done when**: both manifests at `0.1.6`; CHANGELOG `## [0.1.6]` at top;
  `pytest tests/ -q` green, `validate-plugin.py` exit 0,
  `tests/integration/full-pipeline.sh` 12/12.
- **Depends on**: T-129
- **REQ-IDs**: —

---

## Dependency graph

```
T-126 ┐
T-127 ┼─→ T-129 ─→ T-130
T-128 ┘
```
