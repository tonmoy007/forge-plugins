---
name: forge-build-pro
description: >
  Run Stage 6 of the Forge pipeline -- Implementation -- via the Builder Pro
  Execution Orchestrator: scripts/build_executor.py handles context resolution,
  gate execution, commit, progress write, and traceability update;
  agents/builder-pro.md handles code and test generation. Use when the user says
  /forge:build-pro, wants "pro" or orchestrated implementation, or explicitly asks
  for the deterministic-engine builder pipeline. Requires Stage 1-5. Does not
  replace or modify /forge:build -- both coexist; use /forge:build for the
  original single-persona flow.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
---

# /forge:build-pro — Implementation (Pro)

## Aliases

- `/forge:build-pro`

## Purpose

This skill orchestrates Stage 6 — Implementation — through Builder Pro's
script/agent split: `scripts/build_executor.py` performs every mechanical step
(context resolve, gate, commit, progress write, traceability update, build-log),
and `agents/builder-pro.md` performs the one generative step (code + tests). This
skill's own job is narrow: resolve the current task, invoke the script, invoke the
agent, invoke the script again to close out the attempt, and drive state
advancement/narration.

This skill does not itself resolve context, write code, or run quality gates.
`scripts/build_executor.py` and `agents/builder-pro.md` are the sole authorities
for their own slices of Stage 6 — do not duplicate or reinterpret their logic here.

**This skill never touches `skills/forge-build/SKILL.md` or `agents/builder.md`.**
Those remain the original, unmodified single-persona flow for `/forge:build`. The
two tiers coexist — same pattern as every other stage's Pro variant
(`forge-plan-pro`, `forge-spec-pro`, `forge-arch-pro`, `forge-product-pro`,
`forge-sprint-pro`, `forge-srs-pro`).

## Stage Ownership

| Component | Owns |
|---|---|
| This skill | Stage orchestration, current-task resolution, state advancement, narration |
| `scripts/build_executor.py` | Context resolve, gate execution, commit, progress write, traceability update, `build-log.jsonl`, resume, batch delegation |
| `agents/builder-pro.md` | Code generation, test generation, self-check against the spec excerpt |
| State Manager | Pipeline entry and progression |

## Pre-flight Check

### Entry Gate

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py preflight --stage 6
```

If it exits non-zero, **STOP**: present its message verbatim — the prior stage must
be completed first (or `/forge:force-advance` to skip intentionally).

### Forge Project and Task Resolution

1. Read `pipeline/state.md` — confirm this is a Forge project.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-gate.py --stage 5` to confirm
   Stage 5's gate passes. If it fails, show what's missing and pause.
3. Identify the current task ID: the first task in `pipeline/05-plan/task-dag`
   (via `read-doc.py`) not already marked done by
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/build_executor.py`'s own resume tracking
   (`pipeline/06-implementation/progress.md`).

## Resolve Context

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/build_executor.py context --task T-XXX --cwd .
```

This prints the resolved context bundle as JSON (Task ID, Files, REQ-IDs, Task
description, Spec excerpt(s), Architecture excerpt(s), Applicable
additional_criteria). If it exits non-zero, **STOP** and present its stderr message
verbatim — a non-zero exit means context-resolution failed closed (missing task, or
no REQ-ID resolves against the SRS — see
`references/build/02-context-resolution.md`'s Hard Requirement Invariant). Do not
invent a bundle or work around the failure; the missing requirement/spec citation
is a real upstream gap to report, not something to paper over.

## Execute Builder Pro

Read `agents/builder-pro.md`, adopt Builder Pro, and hand it the resolved context
bundle. Follow its Reference Loading Protocol exactly — it reads
`references/build/01..05.md` in order before generating. It returns the list of
files it wrote and a self-check verdict (informational only; the authoritative
verdict is the next step's gate).

## Finish — Gate, Commit, Progress, Traceability

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/build_executor.py finish \
  --task T-XXX --files <files Builder Pro wrote> --cwd . \
  --message "feat(T-XXX): <description>"
```

This runs the four-check gate (compile/lint/test/static analysis) plus any Stage 6
`additional_criteria`, and — **only if every check passes** — commits, updates
`pipeline/06-implementation/progress.md`, extends
`pipeline/05-plan/traceability.md`'s `CODE` leaf, and appends a
`build-log.jsonl` line. On any check failure, nothing is committed; the exit code
is non-zero and stdout's `committed` field is `false`.

## Verification

Parse `finish`'s JSON output:

- `committed: true` — proceed to Advance Pipeline State below.
- `committed: false`, `defect_id: null` — a normal first-attempt failure. Report
  exactly which check(s) failed (from the gate report on stderr) and offer to
  retry: re-invoke Builder Pro against the same context bundle, then `finish`
  again. Do not advance, do not claim completion.
- `committed: false`, `defect_id` set — a `DEFECT-###` was opened (second
  consecutive failure on this task). **STOP** the batch/task loop. Present the
  defect id, the failing check(s), and the evidence. Wait for explicit user
  direction (fix and retry, or explicit skip) before continuing — never
  auto-retry past a `DEFECT-###` (`references/build/05-workflow-governance.md`).

## Advance Pipeline State

Only after a successful `finish` (`committed: true`), and only for the first task
of this stage:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 6
```

If advancement fails, display the returned message verbatim and stop.

## Narrate Progress at Task Boundaries (REQ-INTERACTIVE-NARRATE-001)

Do not work silently. At every task boundary, narrate three things in one short
line:

- **Starting**: `Starting T-207 — add auth middleware (pro pipeline)`.
- **Result**: `T-207 ✓ gate passed (4/4 checks), committed feat(T-207)` or
  `T-207 ✗ DEFECT-001 open (test failing)`.
- **Next**: `Next: T-208` (or `Next: milestone done`).

## Milestone Batches

`scripts/build_executor.py` exposes `run_batch()`, which delegates to
`scripts/parallel_build.py`'s `run_parallel_build` for a milestone's ready tasks —
same engine `/forge:build --milestone N` uses via `build-batch.py`, not a
duplicated fan-out. This skill's primary flow above is single-task; batch mode is
advanced usage invoked the same way `build-batch.py` is a separate helper from the
main `forge-build` flow. Do not build a second fan-out implementation here.

## Next Step

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 6
```

Present the helper output verbatim. While tasks remain in the plan, keep running
`/forge:build-pro` per the workflow above.

## Orchestration Rules

This skill SHALL run the entry gate first; resolve the current task; resolve
context via `build_executor.py context`; let `agents/builder-pro.md` generate code
and tests from that bundle; run `build_executor.py finish` to gate, commit, and
record; verify a `committed: true` result before advancing state; advance state
only on the first task; and present the canonical next hint.

This skill SHALL NOT modify `skills/forge-build/SKILL.md` or `agents/builder.md`;
duplicate context-resolution, gate-execution, commit, or fan-out logic that belongs
to `scripts/build_executor.py`; commit or advance when `finish` reports
`committed: false`; auto-retry past an open `DEFECT-###` without explicit user
direction; or claim task completion before `finish` confirms it.
