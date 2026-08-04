# Stage 6 Pro — Traceability and Validation

## Extending, Not Forking, the Existing Chain

Stage 5's own traceability chain (`references/plan/04-traceability-validation.md`)
already ends:

```text
... → SPEC → MOD → INT → DTO → CFG → ERR → PLAN → PHASE → WP → TASK → CHK → CODE
```

`CODE` is already the terminal link in that chain — Stage 5 defined the slot, Stage 6
Pro is the first stage to actually fill it. After a task's commit passes every gate
check (`references/build/03-execution-verification.md`), `scripts/build_executor.py`
appends the generated file path(s) as the `CODE` leaf under that task's existing
`### T-XXX` entry in **the same file Stage 5 already owns and produces**:
`pipeline/05-plan/traceability.md`. This is required, not deferred — it is the last
step of `BUILDER_PRO-PLAN.md`'s own per-task pipeline (Context Resolution → Task
Execution → Code Generation → Verification → Commit → Progress Tracking →
**Traceability Update**), and every other Stage 1–5 Pro tier already treats
traceability as mandatory (`references/srs|product|architect|spec|plan|sprint-plan/`
each ship a `04-traceability-validation.md`) — Builder Pro closes the same gap for
Stage 6 rather than leaving `CODE` permanently empty.

There is deliberately **no new file** for this — no
`pipeline/06-implementation/traceability.md`, no parallel matrix. Builder Pro
extends Stage 5's existing artifact append-only; it does not redefine its format,
renumber its entries, or fork a second source of truth.

## Update Procedure

After a gate-passing commit:

1. Read `pipeline/05-plan/traceability.md`.
2. Find the `### T-XXX` block matching the just-committed task id (the same
   heading convention `scripts/traceability-check.py`'s `TASK_HEADING`/`TASK_LINE`
   patterns already match).
3. Append a `**Code:**` line listing the exact file paths the task wrote, in the
   order Builder Pro reported them. Never remove or reorder existing content in the
   block — append-only, same as every other Stage 5 traceability rule.
4. If no matching `### T-XXX` block exists (a task built without a prior Stage 5
   traceability entry — e.g. under a permitted profile skip), append a new minimal
   block at the end of the file rather than fabricating upstream lineage it doesn't
   have.

## Reusing `scripts/traceability-check.py`

No parallel validator. `traceability-check.py`'s existing `--from`/`--to`/`--prefix`
chain-pair check already validates `TASK → REQ` lineage
(`pipeline/05-plan/task-dag.md` → `pipeline/01-srs/srs.md`, the `--full-chain`
second link). The `CODE` leaf this stage adds is a file path, not an
`REQ`/`NFR`/`FEAT`/`UF`-prefixed id token — `traceability-check.py`'s `REF_ID` regex
is deliberately not extended to match it. Validating a `CODE` line means checking the
listed path exists on disk, not resolving it against an id namespace; that check is a
plain `Path.exists()` in `build_executor.py` after the append, not a new mode of
`traceability-check.py`.

## Required, Not Optional

`AC-BUILDEXEC-001d`: after every successful commit, the traceability chain is
extended to include the generated file(s) — not merely documented as a step that
*could* happen. A task is not "done" until its `CODE` leaf is recorded; a commit
without the traceability append is an incomplete task execution, the same severity
as a commit without a `build-log.jsonl` line.
