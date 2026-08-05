# Stage 6 Pro — Workflow and Governance

## Supported Modes

This phase supports exactly two modes, both driven by `scripts/build_executor.py`:

- **single task** — build one `T-XXX`, gate it, commit or escalate.
- **milestone batch** — equivalent to today's `build-batch.py --milestone N`: every
  ready task under one `## Milestone N:` section, in dependency order, one task at a
  time (or in bounded parallel — see Parallel/Worktree Path below).

A broader six-mode vision (`build task`, `build module`, `build work-package`,
`build milestone`, `build sprint`, `build project`) was considered during scoping.
Module/work-package/sprint/project scope are **explicitly deferred** — not
implemented, not partially implemented, not silently aliased to milestone. Do not
reintroduce them without a new SRS revision.

## Resume Semantics

Skip-if-done, matching `build-batch.py --resume`: a task already marked done in
`pipeline/06-implementation/progress.md` is skipped on a re-run of the same batch.
Resume never re-opens a task whose `DEFECT-###` is `resolved`; it only re-attempts a
task that is not-started or has an `open` `DEFECT-###`.

## Profile Interaction

The active project-type profile's Stage 6 `additional_criteria`
(`load-profile.py --cwd . --stage 6`) are additional gate checks — reported
individually per `references/build/03-execution-verification.md`'s report shape,
never folded into one of the four core checks, never silently skipped.

## Parallel/Worktree Path

For a milestone-batch run, when `orchestration.parallel_build` and/or
`orchestration.worktree_isolation` are enabled in the loaded config,
`scripts/build_executor.py` delegates the ready-task fan-out to
`scripts/parallel_build.py`'s `run_parallel_build` — it does not reimplement
worktree isolation, bounded dispatch, or adversarial-verify joining
(AC-BUILDEXEC-001c). With both toggles off (the default), the batch runs plain
sequential, one task at a time — byte-identical in outcome to running each task
individually through single-task mode. Single-task mode never touches
`parallel_build.py`; there is nothing to fan out for one task.

## Failure Handling

On any gate check failure: no commit, no progress-write, no traceability update. The
first failure on a task is a normal retry signal (`references/build/03-execution-
verification.md`); a second consecutive failure on the same task opens a
`DEFECT-###` and stops automatic retries for that task. In a milestone batch, an open
`DEFECT-###` halts the batch at that task — it does not skip ahead to the next ready
task by default. The invoking skill surfaces the defect to the user and waits for
explicit direction (retry after a fix, or explicit skip) before continuing the batch.

## Completion Report Shape

Per task, `scripts/build_executor.py` records (and the invoking skill presents):

```text
Task: T-XXX
Files: <list>
Gate: compile <verdict> | lint <verdict> | test <verdict> | static analysis <verdict>
Commit: <sha> | Duration: <seconds>
Traceability: CODE leaf recorded
```

Per batch, the invoking skill additionally reports: tasks attempted, tasks committed,
tasks with an open `DEFECT-###`, and total duration. This is a CI-pipeline-style
report scoped to the fields this phase's two artifacts (`build-log.jsonl`,
`progress.md`) actually carry — not a broader eleven-field superset (coverage,
dependency-report, rollback, etc.) that was considered and cut during scoping.
