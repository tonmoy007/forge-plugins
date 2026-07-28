---
name: forge-sprint
description: Group the project's task DAG into bounded sprints and review them. Use when
  the user runs /forge:sprint, says "plan a sprint", "start a sprint", "what's in this
  sprint", "sprint review", "sprint retro", or wants to batch the next ready tasks into a
  reviewable chunk. A deterministic VIEW over pipeline/05-plan/task-dag.md (T-IDs only) —
  the DAG and progress.md stay the source of truth. Fully opt-in; a project that never
  runs it sees no change.
allowed-tools: [Read, Bash, Glob, Grep]
---

# forge-sprint — a sprint view over the task DAG

`/forge:sprint` slices the project's task DAG into bounded **sprints**: `plan` commits the
next ready tasks to a sprint file; `review` reports what got done vs. what carries over.
It is **not** a parallel tracker — it references **T-IDs only**, and the task DAG
(`pipeline/05-plan/task-dag.md`) plus implementation progress
(`pipeline/06-implementation/progress.md`) remain the single source of truth (F-044/045).

The selection is deterministic — `scripts/sprint.py` does it (no LLM); this skill invokes
it and reports the result.

## When to Use

- `/forge:sprint plan` — commit the next chunk of ready tasks to `sprint-NN.md`.
- `/forge:sprint review` — at sprint end, summarize done vs. carried into a review file.
- `/forge:sprint list` — show existing sprints and their progress.

## When NOT to Use

- You just want to build a milestone end-to-end → `/forge:build --milestone N`.
- There is no task DAG yet → run `/forge:plan` (Stage 5) first.

## Steps

1. **Plan a sprint.**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sprint.py plan --cwd . \
     [--size K] [--milestone N]
   ```
   It selects the next `K` (default 5) **ready** tasks in dependency order — **carry-over
   first**: any task committed to the previous sprint that is not yet done in `progress.md`
   leads the new sprint and keeps its T-ID (F-047) — then writes
   `pipeline/05-plan/sprint-NN.md` and prints the committed T-IDs to stdout. Show the user
   the sprint contents. If it reports "nothing to plan", everything is done — say so.

2. **Work the sprint.** Build its tasks the normal way (`/forge:build`, per-task or
   `--milestone`). Mark tasks done in `progress.md` as usual — the sprint file is just a
   view; you do not edit it by hand.

3. **Review at sprint end.**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sprint.py review --cwd . [--sprint NN]
   ```
   Defaults to the latest sprint. It writes `pipeline/12-release/sprint-NN-review.md`
   (Done / Carried / Blockers / Lessons) by cross-referencing the sprint's T-IDs against
   `progress.md`. Summarize: how many done, what carries over, any blockers. Carried tasks
   automatically lead the next `/forge:sprint plan`.

4. **List anytime.**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sprint.py list --cwd .
   ```

## Notes

- **Opt-in (F-048).** Sprint files live under `pipeline/05-plan/` and `pipeline/12-release/`
  and are created only when you run this skill. A project that never uses sprints is
  unaffected.
- **T-IDs are identity (F-047).** Carry-over and review track tasks by T-ID, so a task that
  spans sprints keeps its history. Never renumber tasks to "fit" a sprint.
- The script writes only sprint files; it never mutates the DAG, `progress.md`, or pipeline
  state. It degrades cleanly (exit 1 + a message) when there is no DAG.
