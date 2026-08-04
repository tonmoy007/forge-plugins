# SRS — Forge v0.8.0 (Builder Pro — BUILDER_PRO-PLAN.md Phase 2)

> **Status**: Ready to build (2026-08-03). **Revision 2** — supersedes Revision 1 below.
>
> Revision 1 scoped this SRS from `docs/builder-pro-plan-analysis.md`'s trimmed
> "Recommended Execution Plan" (3 sub-agent persona files: Context Loader, Code
> Generator, Quality Gate Runner, orchestrated by in-session persona-swapping). That
> was built (T-235..T-240) and then **replaced** on user direction: the actual source of
> truth is `BUILDER_PRO-PLAN.md` itself, which has its own explicit phase plan appended
> at the bottom (added after the original vision, alongside a verified sanity-check):
>
> - **Phase 0** — fix-and-register the Pro tier (name collisions between Classic and
>   Pro agents/skills, Pro skills loading non-Pro agents by mistake). **Done.**
> - **Phase 1** — normalize Stages 1-3 to the thin-router pattern. **Done** — commit
>   `6a22fa1` (PR #62, `refactor/phase1-thin-router-stages-1-3`).
> - **Phase 2** — **Builder Pro. This SRS, this version.**
> - (No Phase 3/4 are defined for Builder in `BUILDER_PRO-PLAN.md` itself — the
>   13-sub-agent / AI-agnostic-adapter / enterprise-artifacts material earlier in that
>   same document is the *original, unscoped* vision; the appended sanity-check
>   explicitly cuts it down to what's below before Phase 2 starts.)
>
> Numbering continues from where Revision 1 left off. T-235..T-240 (Revision 1's sub-agent
> files) are **removed** by T-241 below and their task-DAG entries are kept only as
> historical record in `progress.md`. This revision's real work is **T-241..T-251**.

---

## Problem

Same as Revision 1: Stage 6 (`agents/builder.md` + `skills/forge-build/SKILL.md`) is a
single monolithic persona doing context loading, generation, testing, linting,
verification, progress tracking, and committing in one prompt. Revision 1's fix
(3 markdown sub-agent personas orchestrated by persona-swapping) was the wrong shape:
`BUILDER_PRO-PLAN.md`'s own Phase 2 section specifies a **script + thin-agent** split,
not a 3-persona pipeline — because context resolution and gate execution are
deterministic, mechanical work (grep, subprocess, file I/O), not generative work that
needs an LLM's judgment. Only code generation, test generation, and verifying output
against the spec need the model; everything else should be plain Python.

## Scope — `BUILDER_PRO-PLAN.md`'s Phase 2, verbatim

> ```
> agents/builder-pro.md              ~130 lines, thin router
> references/build/
>   01-foundation.md                 ownership, scope, IDs, output contract
>   02-context-resolution.md         task → module → interfaces → minimal load
>   03-execution-verification.md     per-task loop, gates, escalation, DEFECT-###
>   04-traceability-validation.md    file → TASK → SPEC → REQ, extends existing chain
>   05-workflow-governance.md        modes, resume, profiles, parallel, failure, report
> skills/forge-build-pro/SKILL.md    orchestration only, zero domain logic
> scripts/build_executor.py          deterministic engine — reuses parallel_build.py
> ```
>
> Split of labor:
> - Script owns: context resolve, gate execution, commit, progress write,
>   build-log.jsonl, resume, worktree/parallel
> - Agent owns: generate code, generate tests, verify against spec
> - Artifacts: progress.md + build-log.jsonl + traceability extension. Reports on demand.

### REQ-BUILDEXEC-001 — `scripts/build_executor.py`: the deterministic engine

A new stdlib-first script, following this repo's script conventions (type hints,
dataclasses, never-raises where the rest of the orchestration layer never-raises), that
owns everything mechanical:

- **Context resolve**: given a task ID, deterministically extract (grep/string-match,
  no LLM call) the task-dag entry, the technical-spec section(s) referencing that
  task's REQ-IDs/Files, the architecture/interface/DTO excerpts referencing the same,
  and the profile's Stage 6 `additional_criteria` (reusing `load-profile.py`'s output
  shape). This replaces Revision 1's `context-loader.md` agent with plain code.
- **Gate execution**: run compile → lint → test → static analysis (project-detected
  commands) plus profile `additional_criteria`, and report **pass/fail per check**
  (never a single aggregate boolean) — replaces Revision 1's `quality-gate-runner.md`
  agent with plain code.
- **Commit + progress write**: `feat(T-XXX): …` commit and
  `build/05-implementation/progress.md` update, only after all gates pass.
- **Traceability update**: after commit, extend the existing
  REQ → SPEC → ADR → MOD → TASK chain to include the file(s) just generated (per
  `references/build/04-traceability-validation.md`) — this is not optional
  documentation, it is a required step in `BUILDER_PRO-PLAN.md`'s own per-task
  pipeline (Context Resolution → Task Execution → Code Generation → Verification →
  Commit → Progress Tracking → **Traceability Update**), and every other Stage 1-5 Pro
  tier already treats traceability as a mandatory, not deferred, concern (confirmed by
  audit: `references/srs|product|architect|spec|plan|sprint-plan/` each ship a
  traceability-validation file). Reuses `scripts/traceability-check.py`'s existing
  chain/format rather than a parallel one.
- **`build-log.jsonl`**: one append-only JSON line per task attempt — task id,
  timestamp, files changed, gate results, commit sha, duration. The single new
  artifact this phase adds (`BUILDER_PRO-PLAN.md`'s original 8-file "enterprise
  artifacts" wishlist is still cut down to this one file, per the analysis's
  over-engineering finding — not resurrected).
- **Resume**: skip tasks already marked done in `progress.md` (same semantics as
  `build-batch.py --resume` today).
- **Worktree/parallel**: for a multi-task batch, reuse `scripts/parallel_build.py`'s
  `run_parallel_build` (worktree isolation + bounded parallel dispatch already built
  and tested there) rather than reimplementing fan-out. Single-task interactive use
  (the common case) does not need this path at all.

- **AC-BUILDEXEC-001a**: Context-resolve output is scoped to one task's declared
  `Files`/REQ-IDs, never the whole spec/architecture doc (same behavioral bar as
  Revision 1's AC-BUILDCTX-001a, now met by code instead of a persona).
- **AC-BUILDEXEC-001b**: Gate report is per-check pass/fail/skipped, never collapsed to
  one boolean (same bar as Revision 1's AC-BUILDGATE-001a, now met by code).
- **AC-BUILDEXEC-001c**: A batch/parallel run delegates to `parallel_build.py`'s engine
  rather than duplicating worktree or dispatch logic.
- **AC-BUILDEXEC-001d**: After every successful commit, the traceability chain is
  extended to include the generated file(s) — not merely documented as a step that
  *could* happen. Required, not deferred (`BUILDER_PRO-PLAN.md`'s own per-task pipeline
  ends Context Resolution → … → Commit → Progress Tracking → **Traceability Update**).

### REQ-BUILDAGENT-001 — `agents/builder-pro.md`: thin router, ~130 lines

Rewritten (not the Revision-1 3-agent-orchestrator content) to match the shape of
`agents/planner-pro.md`/`agents/spec-writer-pro.md`: a short Role/Goal plus a Reference
Loading Protocol table pointing at `references/build/01..05.md`, loaded in order. Its
own responsibility is narrow: **generate code, generate tests, verify the result
against the spec** — nothing else. Context resolution, gate mechanics, committing, and
progress tracking are `build_executor.py`'s job, handed to this agent as already-done
inputs/outputs, not re-derived by it.

- **AC-BUILDAGENT-001a**: File is close to 130 lines (a thin router, not a full
  workflow re-implementation) and contains a Reference Loading Protocol table naming
  all five `references/build/0N-*.md` files in order.
- **AC-BUILDAGENT-001b**: Its Output Contract explicitly excludes committing, writing
  `progress.md`, and running the full gate chain — those stay `build_executor.py`'s.

### REQ-BUILDREF-001 — `references/build/01..05.md`

Five reference documents, mirroring `references/plan/`'s granularity and one-topic-
per-file structure:

1. **01-foundation.md** — Stage 6 Pro ownership, scope boundary vs. Classic
   `agents/builder.md`, REQ-ID/TASK-ID conventions reused from this repo's existing
   scheme, the Output Contract (code + tests + verification verdict).
2. **02-context-resolution.md** — the task → module → interfaces → DTO → requirements
   → minimal-load algorithm `build_executor.py` implements; documents the contract the
   agent can rely on (what fields it receives, in what shape).
3. **03-execution-verification.md** — the per-task loop (load context → generate →
   gate → escalate-or-commit), the gate list, and a new **`DEFECT-###`** identifier
   scheme for a verification failure that needs to escalate beyond a simple
   retry (first use of this identifier type in the repo — define it here, don't borrow
   an existing one that doesn't fit).
4. **04-traceability-validation.md** — extends the existing
   REQ → SPEC → ADR → MOD → TASK chain (`traceability-check.py`,
   `traceability-matrix.md` agent) to include the generated file, reusing existing
   traceability machinery rather than inventing a parallel one.
5. **05-workflow-governance.md** — supported modes (single task, and a
   `--milestone N`-equivalent batch — **not** the six-mode
   task/module/work-package/milestone/sprint/project list from the original
   unscoped vision, which stays deferred per the analysis's finding), resume
   semantics, profile interaction, when to use the parallel/worktree path, failure
   handling, and the completion report shape.

- **AC-BUILDREF-001a**: All five files exist, one topic each, no content duplicated
  across them.
- **AC-BUILDREF-001b**: 05-workflow-governance.md's "modes" section documents only
  single-task and milestone-batch — explicitly notes the wider 6-mode list is out of
  scope, so a future reader doesn't assume it's missing by oversight.

### REQ-BUILDSKILL-001 — `skills/forge-build-pro/SKILL.md`: orchestration only

Rewritten to actually invoke `build_executor.py` for the deterministic steps (Revision
1's draft never referenced it) and adopt `agents/builder-pro.md` for the generative
step, in between. Zero domain logic duplicated in the skill file itself — it calls out
to the script and the agent, checks results, and drives state advancement/narration,
matching every other Pro skill's "orchestration only" framing.

- **AC-BUILDSKILL-001a**: SKILL.md's Steps reference both `scripts/build_executor.py`
  and `agents/builder-pro.md`.
- **AC-BUILDSKILL-001b**: `skills/forge-build/SKILL.md` and `agents/builder.md` remain
  byte-for-byte unchanged (same regression test as Revision 1, re-verified here since
  files were touched again during the correction).

## Explicitly Deferred

Unchanged from Revision 1, still out of scope: `forge explain <file>` traceability CLI,
a separate recovery state machine beyond progress.md + resume, the 8-artifact
"enterprise artifacts" wishlist (only `build-log.jsonl` ships), AI-agnostic provider
adapters, and the 6-mode builder scope list beyond single-task + milestone-batch.

## Non-Functional

- **NFR-BUILDPHASE2-001**: Zero regression — full unit suite, `validate-plugin.py`, and
  `tests/integration/full-pipeline.sh` all green.
- **NFR-BUILDPHASE2-002**: `build_executor.py` is stdlib-first; it may import existing
  in-repo modules (`_workflow`, `parallel_build`, `load-profile` helpers) but no new
  third-party dependency.
- **NFR-BUILDPHASE2-003**: `skills/forge-build/SKILL.md` and `agents/builder.md` stay
  byte-identical to the pre-T-235 baseline throughout this revision too.

---

## Revision 1 (superseded, kept for record)

<details>
<summary>Original Phase-1-only scope derived from docs/builder-pro-plan-analysis.md
(3 sub-agent persona files) — built as T-235..T-240, then removed by T-241 in favor of
the scope above.</summary>

Decompose the monolith into 3 focused sub-agents (`agents/context-loader.md`,
`agents/code-generator.md`, `agents/quality-gate-runner.md`), wired sequentially,
in-session, through a skill. Superseded because `BUILDER_PRO-PLAN.md`'s own Phase 2
section (only discovered after Revision 1 was built) specifies a script + thin-agent
split instead, with context-resolution and gate-execution as deterministic code, not
LLM personas.

</details>
