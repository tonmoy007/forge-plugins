---
name: forge-sprint-pro
description: >
  Optional Sprint Planning & Execution layer over the Stage 5 Pro
  Implementation Plan. Orchestrates Sprint Planner Pro to slice
  `pipeline/05-plan/` into deterministic, capacity-bounded,
  traceable sprint backlogs. Not a pipeline stage — never advances or
  mutates pipeline state.
allowed-tools:
  - Read
  - Write
  - WebSearch
  - WebFetch
  - Grep
---

# /forge:sprint-pro

## Aliases

- `/forge:sprint-pro`
- `/forge:sprint plan-pro` (informal alias some users may type)

## Purpose

This skill orchestrates optional Sprint Planning over the **Stage 5 Pro**
Implementation Plan (`agents/planner-pro.md` / `skills/forge-plan-pro`). It
performs entry verification, profile loading, persona loading, deterministic
script delegation where applicable, artifact/traceability verification, and
result reporting.

This skill does not perform sprint planning logic. `agents/sprint-planner-pro.md`
is the sole authority for sprint scope selection, capacity, dependency
validation, risk, allocation, traceability, validation, and completion
behavior.

## Stage Ownership

| Component | Owns |
|---|---|
| This skill | Orchestration only — no scope, capacity, or traceability logic |
| Sprint Planner Pro (`agents/sprint-planner-pro.md`) | All sprint planning knowledge and rules |
| `scripts/sprint.py` | Deterministic selection **for the legacy DAG shape only** (see Script Integration) |
| State Manager | Read-only status check — never invoked to advance or set state here |

Sprint Planning is **not** a numbered pipeline stage. This skill never calls
`state-manager.py advance` and never calls `state-manager.py set`. Do not
duplicate or reinterpret persona logic in this skill.

## Pre-flight Check

### Forge Project Verification

Read `pipeline/state.md`:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py read --cwd .
```

Verify Forge is initialized and `current_stage >= 5`. If `pipeline/state.md`
does not exist, or `current_stage < 5`, STOP: Sprint Planning has nothing to
operate on yet. Tell the user to complete Stage 5 first (`/forge:plan` or
`/forge:plan-pro`). This is a read-only check — never write to
`pipeline/state.md` from this skill.

Do not call `state-manager.py preflight --stage 6` for this check. That
command validates the **legacy** Stage 6 prerequisite
(`pipeline/05-plan/task-dag.md`, per `references/stage-order.md`), which is a
different artifact shape than the Stage 5 Pro output this skill reads. Using
it here would silently gate on the wrong file. Verify the Stage 5 Pro artifact
directly, as described next.

### Stage 5 Pro Artifact Verification

Resolve every required Stage 5 Pro input with the document resolver — never
assume a flat file layout:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/read-doc.py pipeline/05-plan/implementation-plan
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/read-doc.py pipeline/05-plan/work-packages
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/read-doc.py pipeline/05-plan/task-breakdown
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/read-doc.py pipeline/05-plan/dependency-graph
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/read-doc.py pipeline/05-plan/traceability
```

If any required document does not resolve, STOP. List every missing artifact.
Do not infer, regenerate, or substitute a missing Stage 5 Pro artifact — and
do not fall back to the legacy `pipeline/05-plan/task-dag.md` shape from this
skill. A project whose only Stage 5 output is the legacy task DAG should use
the existing `forge-sprint` skill (`/forge:sprint`) instead; tell the user
this explicitly rather than silently degrading.

Read `pipeline/06-implementation/progress.md` if it exists (optional,
read-only) for done-task status. Its absence is not an error.

## Load Project Profile

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 5 --format markdown
```

Sprint Planning has no dedicated stage number in
`references/project-type-profiles.md`, so it reuses the Stage 5 profile
override block — the same one Stage 5 Pro itself loads — since Sprint
Planning operates directly on Stage 5's output and shares its domain
(Microservices, Monolith, Library, CLI, Mobile, ML, Embedded, Infrastructure,
etc.). Load and pass the result unchanged to Sprint Planner Pro. The
persona's `references/sprint-plan/05-workflow-governance.md` Profile
Overrides section controls handling of `additional_artifacts`,
`additional_steps`, `additional_concerns`, and `skip_steps`, and states that
`replace_with` does not apply to Sprint Planning. Never let a profile bypass
Validation, Traceability, or the never-mutate-pipeline-state rule.

## Load Sprint Planner Pro and References

Read `agents/sprint-planner-pro.md`, adopt Sprint Planner Pro, and follow its
Reference Loading Protocol exactly. The following files are mandatory agent
instructions:

```text
references/sprint-plan/01-foundation.md
references/sprint-plan/02-capacity-dependency.md
references/sprint-plan/03-risk-allocation.md
references/sprint-plan/04-traceability-validation.md
references/sprint-plan/05-workflow-governance.md
```

Load each reference when the agent requires it and load all five before final
validation or completion. Do not omit, summarize away, substitute, or weaken a
reference instruction. Follow the Workflow in
`references/sprint-plan/05-workflow-governance.md` exactly for `plan`, its
Sprint Review Workflow for `review`, and its Retrospective Workflow alongside
review.

## Script Integration

`scripts/sprint.py` implements `plan`, `review`, and `list` as a **deterministic,
no-LLM** selector, but it is hardwired to the legacy artifact shape:
`pipeline/05-plan/task-dag.md`, `T-\d+` identifiers, and
`pipeline/05-plan/sprint-NN.md` output. It has no awareness of
`pipeline/05-plan/`, `TASK-\d+` identifiers, or the
`sprints/` output directory this skill uses. This skill does not modify
`scripts/sprint.py` — the legacy `forge-sprint` skill continues to depend on
it unchanged.

Two cases follow from this:

1. **Stage 5 Pro artifacts are present (the case this skill is for).**
   `scripts/sprint.py` cannot parse them. Sprint Planner Pro performs the
   selection itself, following the same deterministic algorithm class the
   script implements (topological/dependency-first ordering, carry-over
   tasks lead, capacity-bounded fill — see
   `references/sprint-plan/02-capacity-dependency.md` and the Workflow in
   `references/sprint-plan/05-workflow-governance.md`) but reading
   `dependency-graph.md` and `task-breakdown.md` directly instead of shelling
   out to the script. This
   is not a duplication of business logic for the shape the script already
   handles — it is the only way to support a shape the script was never
   built to parse, without editing the script.
2. **Only a legacy task DAG is present.** This skill's pre-flight fails (see
   Stage 5 Pro Artifact Verification) and directs the user to the existing
   `/forge:sprint` skill, which continues to call `scripts/sprint.py`
   unchanged.

Never invoke `scripts/sprint.py` against `pipeline/05-plan/`
paths — it will not find its expected files and will exit non-zero with a
message about the legacy DAG, which would be confusing and incorrect in this
context.

## Execute

Provide Sprint Planner Pro only the context authorized by its Context Scope.
Use `read-doc.py` for every document that may be single-file or split. Execute
the requested sub-workflow:

- **`plan`** — run the persona's Workflow (steps 1–15). Produces
  `sprint-NNN.md`, `sprint-NNN-capacity.md`, `sprint-NNN-dependencies.md`,
  `sprint-NNN-risk-register.md`, `sprint-NNN-traceability.md`.
- **`review`** — run the persona's Sprint Review workflow. Produces
  `sprint-NNN-review.md` and `sprint-NNN-metrics.md`.
- **`retro`** — run the persona's Retrospective workflow (typically alongside
  `review`). Produces `sprint-NNN-retrospective.md`.
- **`list`** — read existing files under
  `pipeline/05-plan/sprints/` and report sprint numbers, task
  counts, and done/carried/blocked status per sprint. Read-only; writes
  nothing.

Apply the loaded profile overrides exactly as the persona's governance rules
allow.

## Verification

Before reporting completion, verify through the document resolver that every
plan-time (or review-time) deliverable for the affected sprint resolves
successfully, and that:

- Sprint Planner Pro reports PASS for Validation and every Quality Gate.
- Every committed task resolves to existing Stage 5 lineage
  (`WP`/`MOD`/`SPEC`/`REQ`) — no orphan tasks, no invented lineage.
- No task is assigned to more than one owner in the sprint.
- No `TASK`, `WP`, `MOD`, `SPEC`, `ADR`, or any Stage 1–5 identifier was
  created, renamed, or removed.
- No Stage 1–5 artifact and no `progress.md` entry was modified.
- `pipeline/state.md` is unchanged from its pre-run content — diff it if there
  is any doubt.

If verification fails, report the failures and affected artifacts per the
persona's Failure Behaviour. Do not present the sprint as usable. Do not
attempt to repair a Stage 5 defect from this skill or the persona — report it
upstream.

## Never Mutate Pipeline State

This skill SHALL NOT call `state-manager.py advance`, `state-manager.py set`,
or `state-manager.py history-add`. Sprint Planning has no stage number to
advance to and no state field it owns. The only state-manager subcommand this
skill uses is the read-only `read`, for the pre-flight check above.

## Completion Report

Present the Sprint Planner Pro Completion Report (or, for `list`, the plain
sprint status listing) derived from the artifacts just verified. Do not
summarize the full sprint content unless requested. Explicitly state that
`pipeline/state.md` and all Stage 1–5 artifacts are unchanged.

## Next Step

Sprint Planning has no canonical `next-hint` — it is optional and does not
gate Stage 6. After a successful `plan`, tell the user they may build the
committed tasks directly (`/forge:build`), with or without running
`/forge:sprint-pro review` at the end of the sprint. Never call
`state-manager.py next-hint` from this skill; that command is scoped to
numbered stages.

## Orchestration Rules

This skill SHALL: verify Stage 5 Pro artifacts resolve before doing anything
else; load the Stage 5 profile block; read Sprint Planner Pro in full; use the
document resolver for every input and output; delegate to the persona's own
deterministic selection logic when the Stage 5 Pro shape is present; route
legacy-DAG-only projects to the existing `/forge:sprint` skill instead of
attempting to plan against a shape it does not support; verify resolved
artifacts, validation, quality gates, and traceability; and present results
without ever advancing or mutating pipeline state.

This skill SHALL NOT: duplicate sprint planning logic; modify
`scripts/sprint.py`, `agents/planner.md`, `skills/forge-sprint/`, or any
existing (non-`-pro`) sprint or plan file; redefine any Stage 1–5 artifact or
`TASK`/`WP`/`MOD`/`SPEC` identifier; call `state-manager.py advance`, `set`, or
`next-hint`; bypass a Validation or Quality Gate failure; or claim a sprint is
usable when Sprint Planner Pro reports FAIL.
