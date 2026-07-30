# Stage 5 Delivery Governance Rules

## Repository Planning

Map approved modules and contracts to intended repository areas only after
inspecting repository structure available to the project. For every map entry,
state the approved module/contract, intended area, evidence, and whether the
location is existing, follows a documented repository convention, or requires
repository discovery during Stage 6.

Never invent folders, packages, filenames, or source paths. When repository
convention is unavailable, create a bounded discovery task with an objective
outcome. If actual repository structure conflicts with approved Stage 4
contracts, record the affected IDs and escalate; do not select a new
architecture.

## Branching and Commit Strategy

Follow existing repository branch governance. Define the smallest reviewable
branch scope consistent with one task or tightly coupled, independently
verifiable work-package slice. Where repository policy permits, preserve task
IDs in branch names.

The branch strategy shall define:

- branch creation prerequisites and base branch;
- task/work-package association and branch lifetime;
- required checks, reviewer/approval guidance, and risk-based review depth;
- merge order, conflict owner, and shared-surface coordination;
- release/stabilization branch behavior when applicable; and
- abandoned-branch and rollback coordination.

For every task or tightly coupled reviewable delivery slice, plan commit
granularity and message conventions that retain the relevant `TASK` ID, separate
unrelated changes, and permit deterministic review and rollback. Follow the
repository’s existing commit policy. Never prescribe production code or bypass
protected branches, checks, reviews, or repository policy.

## Implementation and Integration Order

Derive build order from the validated dependency graph. A foundation → shared
abstractions → independent module realization → adapters/integrations →
migrations → cross-module behavior → hardening → release-readiness sequence may
be used only when approved contracts support it.

Every execution-order item shall reference `TASK` IDs and say whether it is
sequential, wave-parallel, a merge point, or a verification gate. Do not impose
a template over a different contract-driven order.

For each integration boundary, state provider, consumer, contract, prerequisite,
compatibility requirement, verification evidence, failure-behavior reference,
merge owner, and rollback implication. Integrate stable contracts before
dependent product slices where possible. If parallel providers and consumers
need contract-first work, create a bounded contract-validation task rather than
relying on informal coordination.

## Migration and Rollback Planning

Create a migration plan whenever approved Stage 4 contracts include data,
configuration, API compatibility, event format, deployment, identity, or another
state-transition concern. Each planned migration step shall identify its upstream
contract, preconditions, owner role, ordering, compatibility window, validation,
monitoring, rollback condition, and recovery action.

Do not invent migrations merely because a project has data. Do not ignore an
approved migration concern because implementation detail is unknown; create a
bounded planning/discovery task or escalate the missing contract.

For each change with material operational, data, security, or compatibility
risk, plan rollback with trigger, decision authority, safe rollback point, data
integrity constraints, compatibility implication, evidence, communication owner,
and post-rollback verification. Never propose unsafe data destruction, security
bypass, or an unapproved architecture change. If safe rollback is impossible,
record irreversibility and require a stronger verification gate.

## Planning Risks

Identify risks only from input evidence, task uncertainty, known dependencies,
or documented assumptions. Use a declared likelihood and impact scale. Every
`RISK-PLAN` record shall include title, description, upstream references,
affected planning artifacts, category, likelihood, impact, exposure, trigger,
early-warning signal, mitigation, contingency, owner role, review point, and
status.

Use applicable categories: delivery, dependency, integration, security,
performance, migration, operational, capacity, quality, or governance. Review
risks at phase starts, before critical integration waves, before migrations, and
at milestone readiness. A risk without owner, trigger, mitigation, or contingency
is incomplete.

## Technical Debt, Assumptions, and Constraints

Record intentional, approved delivery trade-offs as `TD` items. Each shall state
description, reason for incurrence, linked upstream contract, affected task/work
package, impact, interest/risk, repayment trigger, proposed remediation, owner
role, priority, and status.

Never disguise a missing requirement, security defect, architecture
contradiction, unresolved validation failure, or unapproved scope cut as debt.
Those conditions block or escalate upstream.

Planning assumptions (`ASM-PLAN`) and constraints (`CON-PLAN`) refine execution
context only. They shall be explicit, owned, traceable, dated/validated, and
state impact if false and affected tasks/phases. They must never contradict or
replace Stage 1 assumptions/constraints; escalate any contradiction to the
upstream owner.

## Verification Gates

Define reusable `VG` records for meaningful delivery boundaries. Each gate shall
state ID, purpose, applicable tasks/work packages, input evidence, objective pass
conditions, verifier role, failure response, and downstream work blocked by a
failure.

Use gates as applicable for contract conformance, build/static quality,
integration, migration rehearsal, security, performance, observability,
documentation, release readiness, and profile-specific concerns. A narrative
assertion alone never passes a gate.
