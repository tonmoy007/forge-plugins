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

1. Read `pipeline/state.md` — confirm Forge project.
2. Confirm `pipeline/05-plan/task-dag.md` exists. If not: "Complete Stage 5 first (`/forge:plan`)."
3. Read `build/05-implementation/progress.md` (or create it) to identify the current task.
4. Run `python3 ${CLAUDE_PLUGIN_DIR}/scripts/check-gate.py --stage 5` to confirm Stage 5 gate passes.
   If gate fails, show what's missing and pause.

## Steps

1. Read `agents/builder.md` to load the Builder persona.
2. Adopt that persona — you are now the Builder.
3. Read the current task from the task DAG and the corresponding spec section.
4. Follow the Builder workflow: read before editing, implement, test, verify, commit.
5. Mark the task complete in `build/05-implementation/progress.md`.
6. If this is the first task: run `python3 ${CLAUDE_PLUGIN_DIR}/scripts/state-manager.py advance --to 6`.

## Verification

After each task, confirm:
- All specified files for the task exist
- Tests pass (`bash -c "pytest tests/ -q"` or equivalent)
- Task marked done in progress.md
- Commit created with `feat(T-XXX):` prefix

## Next Step

"Task complete. Run `/forge:build` again for the next task, or `/forge:eval` when all tasks are done."
