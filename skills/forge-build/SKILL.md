---
name: forge-build
description: Run Stage 6 of the Forge pipeline — implementation. Use when the user says
  /forge:build, wants to start coding, implement a feature, or work the task DAG.
  Requires Stage 1–5. Invokes the builder persona. Works one task at a time.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# /forge:build — Implementation

## When to Use

- User says `/forge:build`
- User wants to implement a task, write code, or work through the task DAG
- Working in a Forge project at Stage 5 or 6

## Pre-flight Check

**Entry gate (REQ-GATE-ENTRY-001)** — before adopting the persona, verify the
prior stage's artifact exists:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py preflight --stage 6
```

If it exits non-zero, **STOP**: present its message verbatim and do not proceed —
the prior stage must be completed first (or use `/forge:force-advance` to skip
intentionally).

1. Read `pipeline/state.md` — confirm Forge project.
2. Confirm `pipeline/05-plan/task-dag.md` exists. If not: "Complete Stage 5 first (`/forge:plan`)."
3. Read `build/05-implementation/progress.md` (or create it) to identify the current task.
4. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-gate.py --stage 5` to confirm Stage 5 gate passes.
   If gate fails, show what's missing and pause.
5. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 6` to load project-type overrides — these add build-stage criteria (e.g., fullstack: design tokens enforced, bundle budget, RSC boundary) that the Builder must respect.

## Steps

1. Read `agents/builder.md` to load the Builder persona.
2. Adopt that persona — you are now the Builder.
3. Read the current task from the task DAG and the corresponding spec section.
4. Follow the Builder workflow: read before editing, implement, test, verify, commit. Treat any `additional_criteria` from the profile as additional pre-commit checks (run them or document why they're deferred).
5. Mark the task complete in `build/05-implementation/progress.md`.
6. If this is the first task: run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 6`.

## Milestone Batch Mode (`--milestone N`)

When invoked as `/forge:build --milestone N`, build every task in that milestone,
one at a time, instead of a single task (REQ-BUILDBATCH-001):

1. Get the ordered task list (dependency order):
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/build-batch.py --milestone N --cwd .
   ```
   If it warns "large batch" (N > 10 tasks), tell the user and ask whether to
   proceed or split before starting.
2. For **each** T-ID in that order, run the full single-task Steps above:
   Builder persona → implement → tests → **one commit `feat(T-XXX): …`** →
   mark done in progress.md. No batched commits, no batched tests.
3. **Pause on the first failure** (red tests, gate failure, or a hook block):
   stop the batch, report which T-ID failed and why, and leave the preceding
   task commits in place. Do not continue to later tasks.
4. After the user fixes the failure, resume with
   `/forge:build --milestone N --resume` — `build-batch.py --resume` skips tasks
   already marked done in progress.md, so the batch picks up at the failed task.

Plain `/forge:build` (no flag) keeps the single-task behavior unchanged.

## Verification

After each task, confirm:
- All specified files for the task exist
- Tests pass (`bash -c "pytest tests/ -q"` or equivalent)
- Task marked done in progress.md
- Commit created with `feat(T-XXX):` prefix

## Next Step

Derive the hint from the canonical stage table — never hardcode it
(REQ-NEXTHINT-001, single source of truth). Run the helper and present its
output to the user verbatim:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 6
```

(While tasks remain in the plan, keep running `/forge:build` per the workflow
above; the hint above is the cross-stage handoff once the milestone is done.)
