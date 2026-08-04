# Stage 6 Pro — Context Resolution

## Algorithm

`scripts/build_executor.py` resolves context for one task deterministically — no LLM
judgment involved — following `BUILDER_PRO-PLAN.md`'s own "Context Resolution"
shape:

```text
task id
  → find module           (declared Files → owning module/interface)
  → find interfaces        (interface/DTO excerpts touching those Files)
  → find DTO
  → find requirements       (REQ-IDs cited by the task)
  → load ONLY relevant docs (never the full spec, never the full architecture doc)
  → hand off to Builder Pro for generation
```

Task resolution — reading the task-dag entry itself — is folded into this step;
there is no separate Task Resolver. This mirrors the deleted Revision-1
`context-loader.md` agent's algorithm exactly, ported from an LLM read into
deterministic script logic (grep/regex extraction, not judgment), because the
underlying operation was already mechanical: find the block matching a task id,
find the sections matching that task's `Files`/`REQ-IDs`.

## Inputs

The script reads, in order:

1. `pipeline/05-plan/task-dag.md` — resolves the task id's `### T-XXX` entry:
   Description, Files, Depends on, REQ-IDs, Done when.
2. `pipeline/06-implementation/progress.md` — the task's current state (not
   started / in progress / done), for resume (see
   `references/build/05-workflow-governance.md`).
3. `pipeline/04-spec/technical-spec.md` — only the section(s) referencing the
   task's REQ-IDs or declared Files, never the full document.
4. `pipeline/03-architecture/architecture.md` — only interface/DTO/component
   excerpts referencing the task's REQ-IDs or Files, never the full document.
5. `pipeline/state.md` — `project_type`, to resolve Stage 6 `additional_criteria`
   from the active project-type profile via
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 6`.

Use `read-doc.py` for any of these that may be single-file or split. Never assume a
flat file is the only supported layout.

## Context Bundle — Output Shape

The script produces exactly one **context bundle** per task, in this field order —
this is a stable contract Builder Pro consumes, ported field-for-field from the
deleted Revision-1 `context-loader.md` bundle so nothing was lost in the
LLM-persona-to-script move:

| Field | Source |
|---|---|
| Task ID | the resolved `T-XXX` |
| Files | the task-dag entry's `Files:` line, verbatim list |
| REQ-IDs | the task-dag entry's declared REQ-IDs |
| Task description | the entry's Description and Done-when text, verbatim |
| Spec excerpt(s) | matching `pipeline/04-spec/technical-spec.md` section(s), quoted not paraphrased; only task-relevant sections |
| Architecture excerpt(s) | matching `pipeline/03-architecture/architecture.md` excerpt(s), quoted not paraphrased; `(none found)` if no matching section exists rather than omitting the field |
| Applicable additional_criteria | Stage 6 `additional_criteria` entries (id, description, severity) from the active profile; `(none)` if no profile is active |

Only files/sections tied to the task's declared `Files`/`REQ-IDs` are included —
never the entire spec or architecture doc (AC-BUILDEXEC-001a).

## Determinism

Given the same task id and the same state of `pipeline/05-plan/task-dag.md`,
`pipeline/04-spec/technical-spec.md`, and `pipeline/03-architecture/architecture.md`,
context resolution produces a byte-identical bundle every run. This is what makes a
resumed or re-dispatched task safe: the script re-derives the same starting context
rather than depending on session state.

## Token Budget

Because only task-relevant sections load — never the full spec or architecture
document — token usage per task stays small regardless of overall project size
(`BUILDER_PRO-PLAN.md`: "Token usage becomes tiny"). A project with a
10,000-line technical spec and a 50-task plan costs the same per-task context as a
project with a 500-line spec and 5 tasks, as long as each task's declared `Files`/
`REQ-IDs` stay narrow.

## Reconciliation with `scripts/build_executor.py`

This document specifies the bundle shape; T-248's implementation is the source of
truth for the actual extraction regexes and section-matching heuristics. If the two
drift, this document is stale — update it alongside the next change to
`build_executor.py`'s context-resolution function, don't let prose and code diverge.
