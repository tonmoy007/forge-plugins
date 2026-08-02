# Stage 5 Execution Planning Rules

## Phases and Work Packages

Each `PHASE` shall define: ID, name, purpose, parent `PLAN`, upstream scope,
entry criteria, included work packages, deterministic execution order, exit
criteria, related milestone, risk references, and dependency notes. Phases are
logical delivery progressions, not calendar promises. Foundation, contract
realization, feature slices, integration, hardening, and release readiness are
valid only when they derive from approved scope.

Each `WP` shall define: ID, parent phase, name, purpose, valid upstream
`SPEC`/`MOD`/`INT` references, included tasks, ownership guidance, shared
surfaces, dependencies, outputs, verification expectations, and exit criteria.
A work package coordinates related work but never replaces individual task
acceptance checks.

## Task Decomposition

Derive tasks from approved Stage 4 contracts, not preferred technologies or
unverified repository assumptions. Identify the smallest independently
verifiable construction, configuration, integration, migration, documentation,
and verification work required by approved scope.

Every `TASK` shall contain:

```text
TASK-### — concise action-oriented title
Parent: WP-### | Phase: PHASE-### | Plan: PLAN-###
Implements: applicable SPEC, MOD, INT, DTO, CFG, ERR, and REQ references
Purpose: one bounded implementation objective
Priority: Critical | High | Medium | Low, with rationale
Suggested owner: role, capability, or agent specialization; never an invented person
Estimated effort: range/unit, confidence, and estimate assumptions
Depends on: TASK list or None
Blocks: TASK list or None
Produces: observable implementation outputs
Repository scope: evidenced area or “requires repository discovery”
Implementation notes: contract-bound guidance without production code
Acceptance checks: objective, contract-linked checks
Verification: required evidence and VG references
Definition of Ready: applicable CODE-READY references
Definition of Done: applicable DONE references
Risk/debt: applicable RISK-PLAN and TD references
```

Titles start with a specific verb such as Establish, Implement, Integrate,
Configure, Migrate, Validate, or Document. A valid task has one primary outcome,
exactly one work package and phase, valid upstream references, explicit
prerequisites and external dependencies, owner guidance, bounded estimate,
observable outputs, objective acceptance/verification, Ready/Done controls, and
no duplicate deliverable or unstated design decision.

Split a task if it has independent mergeable outcomes, unrelated owners,
conflicting verification, an unclear dependency boundary, exceeds the applicable
delivery slice, or cannot be described by one purpose statement. Do not split
mechanically by source file, language, team, or calendar; split by approved
behavior, contract boundary, integration point, and verifiable outcome.

## Estimates and Priority

Use effort ranges, not false precision. State effort unit, lower/upper bound,
confidence, sizing basis, and assumptions. Estimate engineering effort rather
than elapsed time and use an 80th-percentile planning view where uncertainty is
material. Consider contract complexity, repository novelty, integration and
migration uncertainty, test surface, review overhead, operational risk, and
dependency readiness.

An estimate supports sequencing and capacity planning; it is not a promise and
cannot override safety, priority, or quality gates. If work is underspecified,
create a bounded discovery task or escalate the missing contract rather than
estimating invented work.

Set priority from approved requirement priority, dependency criticality,
security/compliance urgency, risk reduction, milestone inclusion, and recovery
cost. Explain non-inherited priority. Use only Critical, High, Medium, or Low.
When priorities conflict, record the evidence and seek upstream resolution.

## Dependency Analysis

For every task declare `Depends on`, `Blocks`, and external conditions. Edges
run from prerequisite to dependent and must be represented in the normative
adjacency list. Classify edges as applicable:

- contract: interface, DTO, configuration, or error behavior;
- build: shared base, module, or generated artifact;
- data: schema, migration, seed, retention, or ownership sequence;
- integration: endpoint, event, adapter, external system, or test environment;
- security: identity, authorization, secret, audit, or trust control;
- operational: observability, configuration, deployment, rollback, or access;
- governance: review, compliance evidence, approval, or release gate; and
- merge: shared surface makes merge order material.

The dependency graph shall include a deterministic adjacency list, edge type and
rationale for non-obvious edges, topological execution order with ID tie-breaks,
critical path, blockers, shared modules, merge points, external dependencies,
and cycle-detection result. A diagram may supplement but never replaces the
adjacency list.

Reject missing nodes, self-edges, invalid boundary crossings, contradictory
ordering, and cycles. For a cycle, first confirm it is not an identifier or
documentation error. Split only Stage 5 work when that exposes an approved
sequence. If resolution needs an upstream design change, stop and escalate with
affected IDs. Never break a real dependency to manufacture parallel work.

## Parallelization and Critical Path

Parallel work is permitted only when prerequisites are complete, upstream
contracts are stable, repository and migration surfaces do not conflict,
configuration ownership is clear, and integration/merge order is defined.

Build deterministic execution waves by repeatedly selecting eligible tasks,
sorting by criticality then `TASK` ID, and applying shared-surface and
concurrency limits. For every wave record eligible tasks, prerequisite evidence,
concurrency limit, owner guidance, isolated and shared surfaces, merge order,
integration gate, and blocked follow-on work.

Designate an integration owner role and ordered merge point for every shared
public interface, DTO, schema, configuration key, migration, authentication
boundary, deployment manifest, or common test fixture. Lack of a direct edge is
not sufficient proof that work is parallel-safe.

Calculate critical path from the validated DAG and stated effort ranges. Record
the estimation basis, longest dependency chain, blocking tasks, critical
integration points, and mitigation for single points of delay. Recalculate after
any scope, dependency, estimate, or profile change. Do not label high-effort
work critical unless it lies on the dependency-driven path.

## Milestones, Ready, Done, and Checklists

Milestones are evidence-backed delivery boundaries, not arbitrary dates. Each
`MILE` shall include ID, name, parent plan, included work packages, measurable
exit criteria, required evidence, dependency status, rollback relevance,
acceptance owner role, and downstream-readiness impact. Build milestones from
coherent demonstrable increments or risk-reducing boundaries; do not group
unfinished aspirations.

Define reusable `CODE-READY` controls. A task is ready only when its parent
records and upstream contracts resolve; architecture/specification approval is
known; task and external prerequisites are complete or formally governed;
repository scope, owner capability, environment/access, and branch base are
available or separately planned; acceptance, Done, risk, and integration
controls are understood; and no unresolved blocker requires an upstream decision.

Define reusable `DONE` controls. A task is done only when its bounded output
exists; required unit, integration, contract, migration, security, performance,
or operational evidence exists; applicable static/build/lint/format/review
checks pass; contracts and acceptance checks are satisfied; documentation and
traceability are updated; integration/merge evidence is recorded; and no
unacknowledged blocker or debt contradicts completion.

Create `CHK` records for repeatable, objective task, work-package, or milestone
checks. Stage 5 defines Ready, Done, and checklist controls; Stage 6 records the
actual execution evidence.
