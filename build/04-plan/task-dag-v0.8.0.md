# Task DAG — Forge v0.8.0 (Builder Phase 1: decompose the Stage 6 monolith)

> **Status**: Ready to build (2026-08-03). Derived from `build/01-srs/srs-v0.8.0.md`,
> itself derived from `docs/builder-pro-plan-analysis.md`'s "Recommended Execution Plan"
> (Phase 1 only — decompose the builder monolith into 3 focused sub-agents wired through
> the existing `forge-build` skill).
>
> Numbering continues from v0.7.0 (`T-227..T-234`, planned but not yet built); this is
> **T-235..T-240**. Independent of v0.7.0's Docker workflow feature — no shared files.
>
> Format: `T-NNN [size] title` — Size: S (~30min), M (~2hr), L (~half-day). Every task
> in this DAG is sized S or M by design — the analysis's own risk register flags
> "13 sub-agents = untestable surface" and "scope consumes months" as the top risks, so
> each task here is small enough to execute (and review) in a short context window.
>
> | Milestone | Tasks | Gate |
> |-----------|-------|------|
> | M1 Sub-agents (parallelizable) | T-235, T-236, T-237 | v0.6.1 landed |
> | M2 Wiring | T-238 | M1 landed |
> | M3 Verification + release | T-239, T-240 | M2 landed |

**Invariants** (every task): TDD red-first (write the failing structural test before the
agent `.md` file); each new `agents/*.md` follows the existing frontmatter contract
(`name`, `description`, `allowed-tools`) exactly as seen in `agents/builder.md` /
`agents/reflector.md`; no task deletes or behavior-changes `agents/builder.md` (it stays
as-is per REQ-BUILDPIPE-001 / AC-BUILDPIPE-001b); no task touches `build-batch.py`,
`state-manager.py`, or narration contract behavior (REQ-BUILDCOMPAT-001); full unit
suite green after every task, not just at the end.

---

## Milestone 1: Sub-agents (T-235, T-236, T-237 are independent — safe to build in parallel)

### T-235 [S] Extract Context Loader sub-agent
- **Description**: New `agents/context-loader.md` persona. Given a task ID, it resolves
  the task-dag entry (task resolution — folded in, no separate Task Resolver agent per
  AC-BUILDCTX-001b), then returns only the technical-spec section, architecture/
  interface/DTO excerpts, and profile `additional_criteria` tied to that task's declared
  `Files` — not the full spec or architecture doc. Read-only: `allowed-tools: [Read, Grep, Glob]`.
- **Files**: `agents/context-loader.md`, `tests/unit/test_context_loader_agent.py`
- **Done when**: `test_context_loader_agent.py` passes — frontmatter valid, `allowed-tools`
  is exactly `[Read, Grep, Glob]` (no `Write`/`Edit`/`Bash` — it never mutates), file
  documents the "only task-relevant docs" contract (AC-BUILDCTX-001a) and the folded-in
  task-resolution responsibility (AC-BUILDCTX-001b).
- **Depends on**: none
- **REQ-IDs**: REQ-BUILDCTX-001, REQ-BUILDTEST-001

### T-236 [S] Extract Code Generator sub-agent
- **Description**: New `agents/code-generator.md` persona. Consumes the context bundle
  produced by Context Loader (T-235's output contract) plus the task definition; writes
  production code and tests only — no context resolution, no commit, no progress.md
  write, no gate-running. This is the narrowed-down remainder of `agents/builder.md`'s
  "implement + write tests" steps, with everything else stripped out.
- **Files**: `agents/code-generator.md`, `tests/unit/test_code_generator_agent.py`
- **Done when**: `test_code_generator_agent.py` passes — frontmatter valid,
  `allowed-tools` includes `Write`/`Edit`/`Bash`/`Read`/`Grep`/`Glob` but the persona's
  Output Contract section lists only code + test files (AC-BUILDGEN-001a) and explicitly
  states it does not commit or update progress.md.
- **Depends on**: none (built against the context-bundle contract defined in this task's
  test/spec, not against T-235's actual file — safe to run in parallel with T-235)
- **REQ-IDs**: REQ-BUILDGEN-001, REQ-BUILDTEST-001

### T-237 [S] Build Quality Gate Runner sub-agent
- **Description**: New `agents/quality-gate-runner.md` persona — **one** agent chaining
  compile → lint → test → static analysis, reusing existing project-detected commands
  and `scripts/load-profile.py` `additional_criteria` (the same pattern `forge-build`
  already calls). Explicitly not four separate agents — Linter/Static Analyzer/Build
  Runner stay as shell steps this one persona runs in sequence, per the analysis's
  correction of the original 13-agent plan.
- **Files**: `agents/quality-gate-runner.md`, `tests/unit/test_quality_gate_runner_agent.py`
- **Done when**: `test_quality_gate_runner_agent.py` passes — frontmatter valid,
  `allowed-tools` includes `Bash`/`Read`, persona documents all four checks with
  per-check pass/fail reporting (AC-BUILDGATE-001a), not a single aggregate boolean.
- **Depends on**: none
- **REQ-IDs**: REQ-BUILDGATE-001, REQ-BUILDTEST-001

---

## Milestone 2: Wiring

### T-238 [M] Wire the three sub-agents into `forge-build` SKILL.md
- **Description**: Rewrite the "Steps" section of `skills/forge-build/SKILL.md`: replace
  the single "Read `agents/builder.md`, adopt persona" step with a sequence — adopt
  Context Loader (produce context bundle) → adopt Code Generator (consumes the bundle,
  produces code+tests) → adopt Quality Gate Runner (gates pass/fail) → on pass, run the
  *existing* commit + progress-update steps inline (unchanged, not a new persona).
  `agents/builder.md` is left in the repo untouched (AC-BUILDPIPE-001b) — it is no
  longer referenced by the default single-task flow, but nothing deletes it this phase.
  Milestone batch mode (`--milestone N`) calls this same per-task sequence once per task
  in the batch — no separate code path.
- **Files**: `skills/forge-build/SKILL.md`
- **Done when**: SKILL.md references `context-loader.md` → `code-generator.md` →
  `quality-gate-runner.md` in that order (AC-BUILDPIPE-001a); existing narration
  contract (Starting/Result/Next), pause-on-first-failure, and Verification/Next Step
  sections are unchanged; `test_build_batch.py` and any existing narration tests still
  pass unmodified (AC-BUILDCOMPAT-001a).
- **Depends on**: T-235, T-236, T-237
- **REQ-IDs**: REQ-BUILDPIPE-001, REQ-BUILDCOMPAT-001

---

## Milestone 3: Verification + release

### T-239 [S] Cross-file pipeline-order test
- **Description**: A structural test asserting `forge-build/SKILL.md` names all three
  new agent files in the correct order and that each referenced agent file exists on
  disk — makes AC-BUILDPIPE-001a mechanically verifiable and regression-proof (a future
  edit that reorders or drops a step fails CI, not just review).
- **Files**: `tests/unit/test_builder_pipeline_wiring.py`
- **Done when**: New test passes; test fails (red) if the SKILL.md step order is broken,
  proven by a scratch mutation during authoring (not committed).
- **Depends on**: T-238
- **REQ-IDs**: REQ-BUILDTEST-001, AC-BUILDPIPE-001a

### T-240 [S] Full regression sweep + progress/changelog update
- **Description**: Run the full unit suite, `scripts/validate-plugin.py`, and
  `tests/integration/full-pipeline.sh`. Update `build/05-implementation/progress.md`
  (mark T-235..T-239 done with commit refs), append a `tasks/lessons.md` entry only if
  something surprising came up during the build, and add a `[Unreleased]` entry to
  `CHANGELOG.md` describing the Builder Phase 1 decomposition.
- **Files**: `build/05-implementation/progress.md`, `CHANGELOG.md`,
  `tasks/lessons.md` (conditional)
- **Done when**: Full suite green (same pass count or higher than the pre-T-235
  baseline, zero new failures), `validate-plugin.py` exits 0, `full-pipeline.sh` exits 0.
- **Depends on**: T-239
- **REQ-IDs**: NFR-BUILDPHASE1-001

---

## Critical Path

```
T-235 ─┐
T-236 ─┼─→ T-238 ─→ T-239 ─→ T-240
T-237 ─┘
```

**Critical path length**: 4 tasks (one of T-235/236/237 → T-238 → T-239 → T-240).
**Parallelizable**: T-235, T-236, T-237 (no shared files, no dependency between them).

---

## Risk Register

(Carried forward from `docs/builder-pro-plan-analysis.md`'s Risk Assessment table —
not re-litigated here.)

| ID | Risk | Impact | Likelihood | Mitigation |
|----|------|--------|------------|------------|
| R-1 | Scope creep back toward the full 17-task plan | H | M | This DAG is the only authorized scope; Phases 2-4 need a new SRS before any code |
| R-2 | Wiring (T-238) breaks existing `--milestone N` batch or narration | M | M | AC-BUILDCOMPAT-001a: existing tests must pass unmodified, not just new tests added |
| R-3 | Sub-agent contracts (context bundle shape) drift between T-235/T-236 since built in parallel | M | L | Contract is fixed in this doc's task descriptions before either task starts |
| R-4 | `agents/builder.md` silently rots (unreferenced but still shown to users as Stage 6 agent) | L | M | Left explicitly as documented fallback (AC-BUILDPIPE-001b); revisit in a future phase, not this one |
