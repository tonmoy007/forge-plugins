# Sprint Traceability and Validation

## Traceability Rules

Sprint artifacts **extend** Stage 5; they never invent parent artifacts. The
complete lineage:

```
BG → REQ → EP → CAP → FEAT → US → UF → SCR → CMP → API → SRV → ADR → SPEC → MOD → TASK → SPR
```

Worked example:

```
SPR-002 → TASK-041 → WP-005 → MOD-007 → SPEC-003 → REQ-F-018
```

Every `SPR`, `SPRGOAL`, `SPRRISK`, `SPRCAP` record must resolve to at least
one `TASK` ID that already exists in `task-breakdown.md`, and that `TASK`'s
existing lineage to `WP`/`MOD`/`SPEC`/`REQ` (as recorded in Stage 5's own
`traceability.md`) is **re-affirmed**, never re-derived or corrected here. If
a selected `TASK` has no resolvable upstream lineage in Stage 5 traceability,
that is a Stage 5 defect — stop and report it as a Dependency Analysis failure
(`references/sprint-plan/02-capacity-dependency.md`); do not backfill a
lineage on Stage 5's behalf.

Write the resolved chain for every committed task to
`sprint-NNN-traceability.md` as `SPRTRACE-NNN` records, append-only across
sprints — never rewrite a prior sprint's traceability file.

## Validation

**Fail sprint generation when:**

- No Implementation Plan exists (`pipeline/05-plan/` does not
  resolve).
- The dependency graph is invalid or unreadable.
- Circular dependencies exist among candidate tasks.
- Committed scope exceeds available capacity (see the Capacity Planning
  sizing rule).
- The same task is assigned to more than one owner in one sprint.
- Any task appears in more than one open (not-yet-reviewed) sprint
  simultaneously.
- The sprint has no measurable Sprint Goal.
- The sprint lacks explicit acceptance criteria (Definition of Done +
  Acceptance Gates).
- The sprint contains an orphan task (no resolvable upstream lineage).

On any failure: do not write `sprint-NNN.md` or advance sprint numbering.
Report the exact failing condition, the affected `TASK`/`WP`/`SPR` IDs, and
the corrective action available to the user (e.g., "reduce scope," "resolve
blocker on TASK-041," "re-run Stage 5 to repair traceability").

## Quality Gates

Before completion, verify every applicable gate passes:

| Gate | Required condition |
|---|---|
| Sprint Goal | Every sprint has a Sprint Goal with a Business Value citation to an upstream `REQ`/`FEAT` ID. |
| Dependency validation | Every committed task passed Dependency Analysis; no orphan, blocked, or unresolved-blocker task is committed. |
| Capacity | Committed scope does not exceed available capacity after Risk Buffer. |
| Risk analysis | A `SPRRISK` register exists and is populated from objective signals. |
| Traceability | Every committed task resolves to existing upstream `WP`/`MOD`/`SPEC`/`REQ` lineage; 0 unresolved. |
| Ready/Done | Definition of Ready, Definition of Done, and Acceptance Gates are defined for the sprint. |
| Review/Retro criteria | Review and Retrospective criteria are defined (apply once the sprint is reviewed). |
| No duplicate assignment | No task is assigned to more than one execution owner in the sprint. |
| No circular dependencies | The committed-scope subgraph is acyclic. |
| Upstream integrity | No Stage 1–5 artifact was modified; no `TASK` ID was created, renamed, or removed. |
| State integrity | `pipeline/state.md` is byte-identical to its pre-run state. |

Report warnings separately. Unresolved errors always block writing the
sprint's plan-time artifacts.
