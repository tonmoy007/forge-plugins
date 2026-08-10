# Task DAG — Forge v0.8.0 (Builder Pro — BUILDER_PRO-PLAN.md Phase 2)

> **Status**: Ready to build (2026-08-03). **Revision 2** — derived from
> `build/01-srs/srs-v0.8.0.md` Revision 2, itself derived from `BUILDER_PRO-PLAN.md`'s
> own appended Phase 2 section (not the trimmed 3-agent plan `docs/
> builder-pro-plan-analysis.md` recommended, which was Revision 1 and is now removed
> by T-241).
>
> T-235..T-240 (Revision 1) **shipped and were then superseded** — see
> `build/05-implementation/progress.md` for that history. This revision is
> **T-241..T-251**.
>
> | Milestone | Tasks | Gate |
> |-----------|-------|------|
> | M1 Remove superseded Revision 1 | T-241 | v0.6.1 landed + Revision 1 commits present |
> | M2 References (parallelizable) | T-242, T-243, T-244, T-245, T-246 | M1 landed |
> | M3 Engine + agent (parallelizable with each other, not with M2) | T-247, T-248 | M2 landed |
> | M4 Skill wiring | T-249 | M3 landed |
> | M5 Tests + verification | T-250, T-251 | M4 landed |

**Invariants**: `skills/forge-build/SKILL.md` and `agents/builder.md` stay byte-identical
to the pre-T-235 baseline (commit `6a22fa1`) through every task in this revision —
re-verified by `test_builder_pipeline_wiring.py` (rewritten in T-250, same guard
approach as Revision 1's version). `scripts/build_executor.py` is stdlib-first and may
import in-repo modules (`_workflow`, `parallel_build`) but no new third-party
dependency. TDD red-first per task. Full unit suite green after every task.

---

## Milestone 1: Remove superseded Revision 1

### T-241 [S] Remove Revision 1's sub-agent decomposition
- **Description**: Delete the three Revision-1 sub-agent persona files and their tests
  — they implemented context-resolution and gate-execution as LLM personas, which
  `BUILDER_PRO-PLAN.md`'s actual Phase 2 section specifies as deterministic script
  logic instead (`scripts/build_executor.py`, built in T-248). Their domain content
  (the context-bundle field list, the four-check gate enumeration) carries forward into
  `references/build/02-context-resolution.md` (T-243) and
  `references/build/03-execution-verification.md` (T-244) — read them before deleting
  so nothing of value is lost, just relocated from persona prose to reference-doc prose
  and script code.
- **Files removed**: `agents/context-loader.md`, `agents/code-generator.md`,
  `agents/quality-gate-runner.md`, `tests/unit/test_context_loader_agent.py`,
  `tests/unit/test_code_generator_agent.py`, `tests/unit/test_quality_gate_runner_agent.py`,
  `tests/unit/test_builder_pipeline_wiring.py` (rewritten from scratch in T-250 against
  the new architecture, not edited in place).
- **Files kept, to be rewritten in place** (not deleted): `agents/builder-pro.md`,
  `skills/forge-build-pro/SKILL.md` — correct final paths, wrong content; T-247/T-249
  rewrite them.
- **Done when**: The four superseded files (and their tests) no longer exist; full
  suite still passes (no dangling references to the removed files anywhere else);
  `build/05-implementation/progress.md`'s existing T-235/236/237 entries are left as
  historical record with a note that they were superseded, not deleted from history.
- **Depends on**: none (T-235..T-240 already merged to this branch)
- **REQ-IDs**: (removal task, no new REQ)

---

## Milestone 2: `references/build/` (independent of each other — parallelizable)

### T-242 [S] `references/build/01-foundation.md`
- **Description**: Ownership (Builder Pro vs. Classic `agents/builder.md` boundary),
  scope, ID conventions reused from the existing scheme (T-IDs, REQ-IDs), and the
  Output Contract (code + tests + a pass/fail verification verdict) — mirrors
  `references/plan/01-foundation.md`'s shape and level of detail.
- **Files**: `references/build/01-foundation.md`
- **Done when**: File exists, one topic (foundation/ownership/output-contract), no
  overlap with 02-05.
- **Depends on**: T-241
- **REQ-IDs**: REQ-BUILDREF-001

### T-243 [S] `references/build/02-context-resolution.md`
- **Description**: Documents the task → module → interfaces → DTO → requirements →
  minimal-load algorithm `scripts/build_executor.py` (T-248) implements, and the exact
  shape of the context bundle it hands to `agents/builder-pro.md` (field names/order —
  carry forward Revision 1's `context-loader.md` bundle shape: Task ID, Files, REQ-IDs,
  Task description, Spec excerpt(s), Architecture excerpt(s), Applicable
  additional_criteria — read that file's content before it's deleted in T-241, or from
  git history after, to reuse the field list precisely).
- **Files**: `references/build/02-context-resolution.md`
- **Done when**: File exists; documents only context-resolution, not generation or
  gates; the bundle field list matches what T-248's implementation actually produces
  (reconcile after T-248, don't let the doc and the code drift).
- **Depends on**: T-241
- **REQ-IDs**: REQ-BUILDREF-001, REQ-BUILDEXEC-001 (AC-BUILDEXEC-001a)

### T-244 [S] `references/build/03-execution-verification.md`
- **Description**: The per-task loop (load context → generate → gate → escalate-or-
  commit), the four-check gate list (compile/lint/test/static analysis — carry forward
  Revision 1's `quality-gate-runner.md` enumeration and per-check-report requirement),
  and a new `DEFECT-###` identifier scheme for an escalation when verification fails
  repeatedly (first use of this identifier type in the repo — define its lifecycle here:
  when one is opened, what it records, how it's resolved).
- **Files**: `references/build/03-execution-verification.md`
- **Done when**: File exists; gate list matches T-248's actual checks; `DEFECT-###` is
  fully specified (format, fields, lifecycle), not just named.
- **Depends on**: T-241
- **REQ-IDs**: REQ-BUILDREF-001, REQ-BUILDEXEC-001 (AC-BUILDEXEC-001b)

### T-245 [S] `references/build/04-traceability-validation.md`
- **Description**: Extends the existing REQ → SPEC → ADR → MOD → TASK traceability
  chain (`scripts/traceability-check.py`, `agents/traceability-matrix.md`) to include
  the generated file as the final link — reuses existing traceability machinery,
  doesn't invent a parallel one.
- **Files**: `references/build/04-traceability-validation.md`
- **Done when**: File exists; explicitly references `traceability-check.py`'s existing
  chain format rather than redefining one.
- **Depends on**: T-241
- **REQ-IDs**: REQ-BUILDREF-001

### T-246 [S] `references/build/05-workflow-governance.md`
- **Description**: Supported modes — single task, and a milestone-batch equivalent to
  today's `--milestone N` — explicitly stating the wider six-mode list (module/
  work-package/sprint/project) from the original unscoped vision stays deferred.
  Resume semantics (skip-if-done, matching `build-batch.py --resume`), profile
  interaction (Stage 6 `additional_criteria`), when the parallel/worktree path
  (`parallel_build.py`) applies vs. plain single-task, failure handling, and the
  completion report shape.
- **Files**: `references/build/05-workflow-governance.md`
- **Done when**: File exists; modes section explicitly scopes to single-task +
  milestone-batch and states the 6-mode list is deferred (AC-BUILDREF-001b).
- **Depends on**: T-241
- **REQ-IDs**: REQ-BUILDREF-001 (AC-BUILDREF-001b)

---

## Milestone 3: Engine + agent

### T-247 [M] Rewrite `agents/builder-pro.md` as a thin router
- **Description**: Replace the Revision-1 content (which orchestrated three sub-agent
  personas) with a ~130-line thin router matching `agents/planner-pro.md`'s shape: a
  short Role/Goal, then a Reference Loading Protocol table naming
  `references/build/01..05.md` in order. Its own job is narrow — generate code,
  generate tests, verify the result against the spec — using the context bundle and
  gate results `build_executor.py` (T-248) provides/consumes; it does not resolve
  context, run the full gate chain, commit, or write progress.md itself.
- **Files**: `agents/builder-pro.md`
- **Done when**: File is close to 130 lines; Reference Loading Protocol table names all
  five `references/build/0N-*.md` files in order (AC-BUILDAGENT-001a); Output Contract
  explicitly excludes committing/progress-write/full-gate-running
  (AC-BUILDAGENT-001b).
- **Depends on**: T-242, T-243, T-244, T-245, T-246 (needs final reference filenames/
  content to point to)
- **REQ-IDs**: REQ-BUILDAGENT-001

### T-248 [L] `scripts/build_executor.py` — the deterministic engine
- **Description**: New script implementing the Script-owns list: context resolve
  (deterministic, per `references/build/02-context-resolution.md`), gate execution
  (per-check pass/fail, per `03-execution-verification.md`), commit + progress write
  (only after all gates pass), **traceability update** (extend the REQ → SPEC → ADR →
  MOD → TASK chain to include the generated file, per `04-traceability-validation.md`
  — required, not deferred: it's the last step of `BUILDER_PRO-PLAN.md`'s own per-task
  pipeline, not optional documentation), a `build-log.jsonl` append per task attempt,
  resume (skip done tasks), and — for a multi-task batch — delegating to
  `scripts/parallel_build.py`'s `run_parallel_build` for worktree isolation and bounded
  parallel dispatch rather than reimplementing fan-out.
- **Files**: `scripts/build_executor.py`, `tests/unit/test_build_executor.py`
- **Done when**: Unit tests cover context-resolve scoping (AC-BUILDEXEC-001a), gate
  per-check reporting (AC-BUILDEXEC-001b), commit/progress-write-only-on-pass,
  traceability-chain extension after commit (AC-BUILDEXEC-001d), build-log.jsonl
  append shape, resume skip-logic, and that the batch path calls into
  `parallel_build.run_parallel_build` rather than duplicating its logic
  (AC-BUILDEXEC-001c) — TDD red-first.
- **Depends on**: T-243, T-244, T-245 (needs the algorithms/gate-list/traceability
  format they document)
- **REQ-IDs**: REQ-BUILDEXEC-001

---

## Milestone 4: Skill wiring

### T-249 [M] Rewrite `skills/forge-build-pro/SKILL.md`
- **Description**: Replace the Revision-1 draft (which never referenced a script) with
  one that actually invokes `scripts/build_executor.py` for the deterministic steps and
  adopts `agents/builder-pro.md` for the generative step in between — zero domain logic
  duplicated in the skill file itself. Keeps the existing gating/profile-loading/
  narration/next-hint structure already present from Revision 1 (that part was
  correctly scoped, only the missing script call and the wrong agent content need
  fixing).
- **Files**: `skills/forge-build-pro/SKILL.md`
- **Done when**: Steps reference both `scripts/build_executor.py` and
  `agents/builder-pro.md` (AC-BUILDSKILL-001a); `skills/forge-build/SKILL.md` and
  `agents/builder.md` remain byte-identical to the pre-T-235 baseline
  (AC-BUILDSKILL-001b).
- **Depends on**: T-247, T-248
- **REQ-IDs**: REQ-BUILDSKILL-001

---

## Milestone 5: Tests + verification

### T-250 [S] Rewrite the cross-file wiring test
- **Description**: Replace `test_builder_pipeline_wiring.py` (deleted in T-241) with a
  version asserting the *new* architecture: `forge-build-pro/SKILL.md` references
  `build_executor.py` and `builder-pro.md`; `builder-pro.md` references all five
  `references/build/0N-*.md` files in order; `skills/forge-build/SKILL.md` and
  `agents/builder.md` are still byte-identical to the `6a22fa1` baseline (same
  regression guard as Revision 1, just re-applied to the corrected file set).
- **Files**: `tests/unit/test_builder_pipeline_wiring.py`
- **Done when**: All assertions pass against the T-247/T-248/T-249 output.
- **Depends on**: T-249
- **REQ-IDs**: REQ-BUILDSKILL-001 (AC-BUILDSKILL-001a/b)

### T-251 [S] Full regression sweep + progress/changelog update
- **Description**: Run the full unit suite, `scripts/validate-plugin.py`, and
  `tests/integration/full-pipeline.sh`. Update `build/05-implementation/progress.md`
  (mark T-241..T-250 done with commit refs, and annotate the superseded T-235/236/237
  entries), replace the Revision-1 CHANGELOG `[Unreleased]` entry with one describing
  the actual Phase 2 shape, and add a lessons.md entry on reading the *actual* source
  document in full before scoping from a secondary analysis of it.
- **Files**: `build/05-implementation/progress.md`, `CHANGELOG.md`, `tasks/lessons.md`
- **Done when**: Full suite green, `validate-plugin.py` exits 0, `full-pipeline.sh`
  exits 0.
- **Depends on**: T-250
- **REQ-IDs**: NFR-BUILDPHASE2-001

---

## Follow-On (tracked, not blocking the Critical Path) — DONE

Discovered mid-build (REQ-BUILDCTX-002): context-resolution depth should be
configurable rather than fixed forever at spec+plan. Design lives in
`references/build/02-context-resolution.md` and the SRS; these two tasks implement
the Stage 5 prompt/persist UX and the widening logic. Sequenced after T-251 —
Phase 2 shipped and was fully usable with the `spec_plan` default before either
landed. **Both now complete**: T-252 `412fba8`, T-253 `0442b88` — see
`build/05-implementation/progress.md`.

### T-252 [S] `forge-plan-pro` Stage 5 entry: prompt + persist `build_context_depth`

- **Description**: Add a pre-flight step to `skills/forge-plan-pro/SKILL.md`: if
  `pipeline/state.md` has no `build_context_depth` field, ask the user once
  (`spec_plan` default / `spec_arch_plan` / `full_chain`) and persist the answer via
  `_state_lib.write_state` — same read-modify-write pattern
  `scripts/set-profile.py` uses for `project_type`. Never re-prompts once set.
- **Files**: `skills/forge-plan-pro/SKILL.md`
- **Done when**: A fresh project with no `build_context_depth` gets prompted once at
  Stage 5 entry; a project with it already set is not re-prompted
  (AC-BUILDCTX-002c); unset stays `spec_plan` (AC-BUILDCTX-002b).
- **Depends on**: T-251
- **REQ-IDs**: REQ-BUILDCTX-002

### T-253 [M] Wire `build_context_depth` into `build_executor.py`'s context-resolve

- **Description**: Read the optional `build_context_depth` field via `_state_lib`
  (default `spec_plan` when absent/malformed, fail-soft). At `spec_arch_plan`, also
  `read-doc.py` resolve `pipeline/03-architecture/*` and fold matching excerpts into
  the bundle's Architecture excerpt(s) field. At `full_chain`, additionally resolve
  the full Stage 1-5 canonical set (SRS+traceability, PRD+user-stories+flows, sprint
  plan when present) — informational context only, the Output Contract and hard
  REQ-ID invariant are unchanged by depth.
- **Files**: `scripts/build_executor.py`, `tests/unit/test_build_executor.py`
- **Done when**: Unit tests cover all three depths + the unset-defaults-to-`spec_plan`
  case (AC-BUILDCTX-002a/b) — TDD red-first.
- **Depends on**: T-248, T-252
- **REQ-IDs**: REQ-BUILDCTX-002

---

## Critical Path

```
T-241 ─┬─→ T-242 ─┐
       ├─→ T-243 ─┼─→ T-247 ─┐
       ├─→ T-244 ─┤          ├─→ T-249 ─→ T-250 ─→ T-251
       ├─→ T-245 ─┘          │
       └─→ T-246 ────────────┘
                    T-243+T-244 ─→ T-248 ─┘
```

**Critical path length**: 6 tasks (T-241 → one of T-242..T-246 → T-247/T-248 → T-249 →
T-250 → T-251). **Parallelizable**: T-242..T-246 (5-way); T-247 and T-248 (2-way, after
M2).

## Risk Register

| ID | Risk | Impact | Likelihood | Mitigation |
|----|------|--------|------------|------------|
| R-1 | A second scope misread on the same feature | H | L (now read the primary source directly, not a secondary analysis of it) | This revision quotes `BUILDER_PRO-PLAN.md`'s Phase 2 section verbatim in the SRS rather than paraphrasing |
| R-2 | `build_executor.py` duplicates `parallel_build.py` logic instead of reusing it | M | M | AC-BUILDEXEC-001c + a test asserting the batch path calls `run_parallel_build` |
| R-3 | `references/build/0N-*.md` content drifts from what `build_executor.py` actually implements | M | M | T-243/T-244 explicitly say "reconcile after T-248" |
| R-4 | Reintroducing the deferred 6-mode builder list by accident via 05-workflow-governance.md | L | M | AC-BUILDREF-001b requires an explicit "deferred" statement in that file |
