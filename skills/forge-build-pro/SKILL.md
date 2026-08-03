---
name: forge-build-pro
description: Run Stage 6 of the Forge pipeline — Implementation — via Builder Pro's
  three-sub-agent pipeline (Context Loader, Code Generator, Quality Gate Runner)
  instead of the single monolithic Builder persona. Use when the user says
  /forge:build-pro, wants "pro" or orchestrated implementation, or explicitly asks for
  the decomposed builder pipeline. Requires Stage 1–5. Does not replace or modify
  /forge:build — both coexist; use /forge:build for the original single-persona flow.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# /forge:build-pro — Implementation (Pro)

## Aliases

- `/forge:build-pro`

## Purpose

This skill orchestrates Stage 6 — Implementation — using the Pro tier: Builder Pro
sequences three focused sub-agents (Context Loader, Code Generator, Quality Gate
Runner) instead of one monolithic persona doing everything. This skill performs stage
gating, profile loading, current-task resolution, persona adoption, verification,
commit + progress tracking, state advancement, and canonical next-stage guidance.

This skill does not itself resolve context, write code, or run quality gates.
`agents/builder-pro.md` is the sole authority for sequencing the three sub-agents; the
sub-agents themselves (`agents/context-loader.md`, `agents/code-generator.md`,
`agents/quality-gate-runner.md`) are the sole authority for their own slice of the
work. Do not duplicate or reinterpret their logic in this skill.

**This skill never touches `skills/forge-build/SKILL.md` or `agents/builder.md`.**
Those remain the original, unmodified single-persona flow for `/forge:build`. The two
tiers coexist — same pattern as every other stage's Pro variant
(`forge-plan-pro`, `forge-spec-pro`, `forge-arch-pro`, `forge-product-pro`,
`forge-sprint-pro`, `forge-srs-pro`).

## Stage Ownership

| Component | Owns |
|---|---|
| This skill | Stage orchestration, current-task resolution, commit + progress tracking only |
| Builder Pro (`agents/builder-pro.md`) | Sequencing the three sub-agents, handoff between them |
| Context Loader / Code Generator / Quality Gate Runner | Their own slice of Stage 6 work (context resolution / implementation / verification) |
| State Manager | Pipeline entry and progression |

## Pre-flight Check

### Entry Gate

Before adopting Builder Pro, verify the prior stage's artifact exists:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py preflight --stage 6
```

If it exits non-zero, **STOP**: present its message verbatim and do not proceed — the
prior stage must be completed first (or use `/forge:force-advance` to skip
intentionally).

### Forge Project and Task Resolution

1. Read `pipeline/state.md` — confirm this is a Forge project.
2. Confirm `pipeline/05-plan/task-dag.md` exists. If not: "Complete Stage 5 first
   (`/forge:plan` or `/forge:plan-pro`)."
3. Read `build/05-implementation/progress.md` (or create it) to identify the current
   task ID.
4. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-gate.py --stage 5` to confirm Stage
   5's gate passes. If it fails, show what's missing and pause.

## Load Project Profile

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 6
```

Pass the result unchanged into Builder Pro's pipeline — Quality Gate Runner treats its
`additional_criteria` as additional checks in its per-check report, exactly as
`forge-build`'s inline gate step already does.

## Execute Builder Pro

Read `agents/builder-pro.md`, adopt Builder Pro, and follow its Sub-Agent
Orchestration Protocol exactly: it reads and adopts `agents/context-loader.md`, then
`agents/code-generator.md`, then `agents/quality-gate-runner.md`, in that order,
passing each step's output to the next. Give it the current task ID and the loaded
profile. Do not skip, reorder, or collapse its three steps.

## Verification

After Builder Pro reports back, confirm:

- Builder Pro's verdict is **all checks passed** — if it reports any check failed,
  **STOP**: present exactly which check(s) failed and why (from the Quality Gate
  Runner's per-check report), leave the task marked not-done, and do not commit.
- All files named in the context bundle / Code Generator's output actually exist on
  disk.
- Tests pass (the Quality Gate Runner report already covers this; re-run
  `bash -c "pytest tests/ -q"` or equivalent only if the report is ambiguous).

## Commit and Update Progress

Only after verification passes:

1. Commit with message `feat(T-XXX): <description>`.
2. Mark the task complete in `build/05-implementation/progress.md`.
3. If this is the first task: run
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 6`.

## Narrate Progress at Task Boundaries (REQ-INTERACTIVE-NARRATE-001)

Do not work silently. At every task boundary, narrate three things in one short line:

- **Starting**: which T-ID you are starting, e.g. `Starting T-207 — add auth
  middleware (pro pipeline)`.
- **Result**: the test/commit outcome, e.g. `T-207 ✓ gate passed (4/4 checks),
  committed feat(T-207)`.
- **Next**: what comes next, e.g. `Next: T-208` (or `Next: milestone done`).

## Next Step

Derive the hint from the canonical stage table — never hardcode it
(REQ-NEXTHINT-001, single source of truth):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 6
```

Present the helper output verbatim. While tasks remain in the plan, keep running
`/forge:build-pro` per the workflow above.

## Orchestration Rules

This skill SHALL run the entry gate first; resolve the current task; load the
profile; read Builder Pro and let it sequence Context Loader → Code Generator →
Quality Gate Runner; verify an all-checks-passed verdict before committing; commit and
update progress only on that verdict; advance state only on the first task; and
present the canonical next hint.

This skill SHALL NOT modify `skills/forge-build/SKILL.md` or `agents/builder.md`;
duplicate context-resolution, code-generation, or gate-running logic that belongs to a
sub-agent; commit when Builder Pro reports any failed check; advance state before a
successful commit; or claim task completion before verification passes.
