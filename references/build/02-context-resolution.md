# Stage 6 Pro — Context Resolution

## Algorithm

`scripts/build_executor.py` resolves context for one task deterministically — no LLM
judgment involved:

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
`context-loader.md` agent's algorithm, ported from an LLM read into deterministic
script logic (regex extraction + `read-doc.py` resolution, not judgment), because the
underlying operation was already mechanical: find the block matching a task id, find
the sections matching that task's `Files`/`REQ-IDs`.

**Not a flat-file grep.** Every canonical input below is resolved through
`read-doc.py`'s single-file-or-split-directory layout
(`pipeline/04-spec/technical-spec.md` *or* `pipeline/04-spec/technical-spec/index.md`
+ parts) — never a hardcoded assumption that one `.md` file is the whole document.
`references/stage-order.md`'s `primary_artifact` field is the single source of truth
for each canonical base path; this document's path list below must match it, not the
other way around.

## Inputs

The script reads, in order:

1. `pipeline/05-plan/task-dag` (via `read-doc.py`) — resolves the task id's
   `### T-XXX` entry: Description, Files, Depends on, REQ-IDs, Done when. This is
   `references/stage-order.md`'s stage-5 `primary_artifact`
   (`pipeline/05-plan/task-dag.md`), tier-agnostic — Classic `planner.md` and Pro
   `planner-pro.md` both converge on it (confirmed by cross-reference: `forge-sprint-
   pro`, a sibling Pro skill, already reads the same path).
2. `pipeline/06-implementation/progress.md` — the task's current state (not
   started / in progress / done), for resume (see
   `references/build/05-workflow-governance.md`).
3. `pipeline/04-spec/technical-spec` (via `read-doc.py`) — only the section(s)
   referencing the task's REQ-IDs or declared Files, never the full resolved
   document.
4. `pipeline/state.md` — `project_type`, to resolve Stage 6 `additional_criteria`
   via `load-profile.py --cwd . --stage 6`; and the optional `build_context_depth`
   field (see Context Depth below).
5. `pipeline/01-srs/srs.md` — to validate the task's REQ-IDs actually resolve (see
   Hard Requirement Invariant below). Not excerpted into the bundle; existence-checked
   only.

**Architecture is not read by default.** `pipeline/03-architecture/*` is only pulled
in at the `spec_arch_plan` or `full_chain` depth (see Context Depth below) — the
default `spec_plan` depth resolves spec + plan only, on the principle that a task's
spec excerpt is the already-distilled, implementation-ready contract; Builder Pro
does not need to re-derive structural context Stage 4 already folded in.

## Context Depth (REQ-BUILDCTX-002)

Depth is read from `pipeline/state.md`'s optional `build_context_depth` field
(`_state_lib`, same read pattern as `project_type`), default `spec_plan` when
absent or malformed (fail-soft, same posture as every other optional config field in
this repo):

| Depth | Additionally resolves |
|---|---|
| `spec_plan` (default) | nothing beyond Inputs 1-5 above |
| `spec_arch_plan` | `pipeline/03-architecture/*` (via `read-doc.py`) — matching excerpts fold into the bundle's Architecture excerpt(s) field |
| `full_chain` | the full Stage 1-5 canonical set: SRS+traceability, PRD+user-stories+flows, full architecture, full spec, full plan, sprint-plan when present — informational context only |

The prompt/persist UX at Stage 5 entry (`forge-plan-pro`'s pre-flight) and the
`spec_arch_plan`/`full_chain` widening logic are **T-252/T-253** — sequenced after
T-251, not blocking this phase's critical path. Phase 2 ships fully working at the
`spec_plan` default.

## Hard Requirement Invariant

Regardless of depth: if a task's REQ-IDs (from Input 1) do not include at least one
id that resolves against `pipeline/01-srs/srs.md` (Input 5), context-resolution
**fails closed** — no bundle is produced, Builder Pro is never invoked, no code is
generated. Nothing builds without a traceable requirement or specification behind it.
This is not a warning-level check; it is the same severity as a missing task-dag
entry.

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
| Spec excerpt(s) | matching section(s) from the `read-doc.py`-resolved `pipeline/04-spec/technical-spec`, quoted not paraphrased; only task-relevant sections |
| Architecture excerpt(s) | `(not resolved at this depth)` at the default `spec_plan` depth; at `spec_arch_plan`/`full_chain`, matching excerpts from the `read-doc.py`-resolved `pipeline/03-architecture/*`, quoted not paraphrased, or `(none found)` if no matching section exists |
| Applicable additional_criteria | Stage 6 `additional_criteria` entries (id, description, severity) from the active profile; `(none)` if no profile is active |

Only files/sections tied to the task's declared `Files`/`REQ-IDs` are included —
never the entire spec or architecture doc (AC-BUILDEXEC-001a).

## Determinism

Given the same task id, the same resolved content behind `pipeline/05-plan/
task-dag` and `pipeline/04-spec/technical-spec`, and the same `build_context_depth`
setting, context resolution produces a byte-identical bundle every run. This is what
makes a resumed or re-dispatched task safe: the script re-derives the same starting
context rather than depending on session state.

## Token Budget

Because only task-relevant sections load — never the full spec or architecture
document — token usage per task stays small regardless of overall project size. A
project with a
10,000-line technical spec and a 50-task plan costs the same per-task context as a
project with a 500-line spec and 5 tasks, as long as each task's declared `Files`/
`REQ-IDs` stay narrow.

## Reconciliation with `scripts/build_executor.py`

This document specifies the bundle shape; T-248's implementation is the source of
truth for the actual extraction regexes and section-matching heuristics. If the two
drift, this document is stale — update it alongside the next change to
`build_executor.py`'s context-resolution function, don't let prose and code diverge.
