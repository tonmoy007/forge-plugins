# Sprint Capacity and Dependency Rules

## Capacity Planning

Every sprint requires an explicit, auditable capacity model before scope is
committed. Support the following inputs, all optional except where noted:

| Field | Source | Required |
|---|---|---|
| Velocity | Rolling average of completed estimated-effort from prior reviewed sprints (`sprint-NNN-metrics.md`); absent for sprint 1 | No |
| Developer Capacity | Human hours/points available this sprint (user-supplied or profile default) | Yes |
| AI Capacity | AI-agent execution slots/hours available this sprint | No |
| Estimated Hours | Sum of `TASK` effort estimates from `task-breakdown.md` | Yes |
| Story Points | Optional relative-sizing overlay on top of hours | No |
| Risk Buffer | Percentage held back for unknowns (default 15%, profile-configurable) | Yes |
| Slack | Explicit unallocated capacity for interrupts | No |
| Critical Tasks | Tasks on the critical path from `dependency-graph.md` | Yes |
| Stretch Tasks | Ready tasks beyond committed capacity, pulled only if the sprint finishes early | No |

**Sizing rule:** committed scope's total estimated effort must not exceed
`(Developer Capacity + AI Capacity) × (1 − Risk Buffer)`. Critical-path tasks
are prioritized into the committed set before non-critical ready tasks of
equal priority. Never commit Stretch Tasks as part of the sprint goal — they
are explicitly optional over-capacity fill.

If no velocity history exists (sprint 1, or a profile that skips metrics),
size the sprint from raw capacity input only, and say so explicitly in
`sprint-NNN-capacity.md` — do not fabricate a velocity figure.

## Dependency Analysis

Before planning any sprint, verify, against `dependency-graph.md`,
`task-breakdown.md`, and `progress.md`:

- Every predecessor of a candidate task is complete (done in `progress.md`) or
  already committed earlier in the same sprint in valid order.
- The specification (`SPEC`/`MOD`) each candidate task implements exists in
  Stage 4 traceability.
- The architecture (`ADR`/`SRV`) each candidate task depends on exists in
  Stage 3 traceability.
- No unresolved blocker is recorded against the candidate task.
- No circular dependency exists in the subgraph of candidate tasks.
- No orphan task (a `TASK` with no upstream lineage to `WP`/`MOD`/`SPEC`/`REQ`)
  is selected.
- Each candidate task meets Definition of Ready (below).

Selection uses the same deterministic shape as the legacy sprint selector:
dependency-first (topological) ordering, **carry-over tasks lead**, then
fill to capacity with the next ready tasks in declared order. Ties break by
declared order in `task-breakdown.md`. This procedure is applied here because
`scripts/sprint.py` cannot parse the Stage 5 Pro artifact shape — see the
orchestrating skill's Script Integration section for exactly which cases
delegate to the script unchanged and which do not.

**Definition of Ready** — a task may be selected into a sprint only when:

- Its upstream `WP`/`MOD`/`SPEC`/`REQ` lineage resolves.
- All its `Depends on` tasks are done or are carry-over already committed.
- Its acceptance checks and verification method are defined in
  `task-breakdown.md`.
- No open blocker is recorded against it.

A task failing any of these is **blocked**, not selected, and is listed under
Blocked Tasks in `sprint-NNN.md` with the specific unmet condition.

## Parallel Execution

Identify, from `dependency-graph.md` only — never by inventing new edges:

- Independent work streams (task subsets with no cross-dependencies)
- The critical path (longest dependency chain within committed scope)
- Merge points (tasks where independent streams reconverge)
- Blocking tasks (tasks with the highest fan-out of dependents)
- Concurrent opportunities (ready tasks with no shared owner or resource
  conflict)

Record these in `sprint-NNN-dependencies.md`. Parallel streams inform
Developer/AI Allocation (`references/sprint-plan/03-risk-allocation.md`) but
never change task scope, estimates, or dependency edges — those remain
Stage 5's authority.
