# Sprint Risk and Allocation Rules

## Risk Analysis

Maintain a `SPRRISK-NNN` register per sprint. Every risk record has:

- **ID**: `SPRRISK-NNN`, sequential, never reused.
- **Category**: Dependency, Capacity, Technical, External, Scope.
- **Description**: concrete, falsifiable — not "things might go wrong."
- **Likelihood**: Low / Medium / High.
- **Impact**: Low / Medium / High.
- **Linked records**: affected `TASK`/`WP` IDs.
- **Mitigation**: specific action, not "monitor closely."
- **Owner**: role or agent responsible for the mitigation.

Populate the register from objective signals already present in the Stage 5
artifacts and current sprint state: tasks with many dependents (fan-out risk),
tasks near capacity ceiling, tasks with no completed precedent in
`progress.md`, external integrations flagged in Stage 4 contracts, and any
carry-over task entering its second or later sprint (schedule risk). Do not
invent risks with no evidentiary basis.

## AI Allocation

Support assigning each committed task's **execution owner** — never its
scope or definition — to a human developer or a named AI agent. Allocation is
configurable via the project profile and/or explicit user instruction at
plan time.

```
TASK-021 → Claude
TASK-022 → Codex
TASK-023 → GPT
TASK-024 → Human Developer
```

Rules:

- A task has exactly one execution owner per sprint. Never assign a task
  twice in the same sprint (a Validation failure — see
  `references/sprint-plan/04-traceability-validation.md`).
- Allocation is advisory metadata for the sprint, not a contract change —
  `TASK-*` ownership as defined in the Implementation Plan is untouched.
- When no allocation preference is configured, leave the assignee column
  blank rather than guessing; do not default every task to one agent.
- Parallel streams identified in
  `references/sprint-plan/02-capacity-dependency.md` are the primary signal
  for balancing allocation across owners — prefer spreading independent
  streams across distinct owners over stacking them on one.
