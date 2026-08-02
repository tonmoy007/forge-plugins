# Stage 5 Workflow and Governance

## Workflow

Execute in order. Do not skip a step unless the active profile explicitly
permits it, and never skip ownership, traceability, validation, quality, or
state-advance controls.

1. Verify Stage 5 entry eligibility and load the project profile.
2. Resolve approved Stage 1–4 inputs with `read-doc.py` where applicable and
   build a read-only upstream inventory.
3. Verify input completeness, stable IDs, approval/traceability availability,
   ownership clarity, and absence of a known upstream blocker.
4. Apply profile `replace_with`, `additional_artifacts`, `additional_steps`,
   `additional_concerns`, and permitted `skip_steps`; record each override.
5. Establish `PLAN` scope, delivery strategy, priority policy, assumptions, and
   constraints from approved inputs.
6. Allocate deterministic Stage 5 IDs and derive phases, work packages, and
   atomic tasks from approved contract and integration boundaries.
7. Define Ready, Done, checklists, acceptance checks, and verification gates.
8. Analyze dependencies, external prerequisites, merge points, critical path,
   deterministic execution order, and parallelization waves.
9. Plan repository mapping, branch/commit strategy, integration, migration, and
   rollback as required by approved scope.
10. Define milestones, risks, technical debt, and every profile-added concern.
11. Generate resolved artifacts and append-only traceability.
12. Run deterministic validation and every quality gate; repair only Stage 5
    defects and rerun the entire set after each repair.
13. Verify downstream readiness, then prepare completion report only after the
    orchestrating skill has advanced the state successfully.

## Profile Overrides

Honor loaded overrides exactly:

- `replace_with` replaces only the named default activity/artifact while
  preserving all non-replaced requirements.
- `additional_artifacts` are required output, indexed in the canonical plan,
  traceable, and validated.
- `additional_steps` are inserted at their configured position or after the
  default workflow when position is absent.
- `additional_concerns` receive explicit planning coverage and, where
  applicable, tasks, risks, gates, and traceability.
- `skip_steps` omit only explicitly permitted default activities.

Profiles such as Microservices, Monolith, Library, CLI, Mobile, ML, Embedded,
Infrastructure, API, and Event-driven systems can change planning emphasis and
add concerns. They cannot authorize invented functionality, weakened controls,
or omission of the canonical plan, ownership, traceability, validation, quality,
or stage-advance gates.

## Large-Document Behaviour

Always use `read-doc.py` to resolve input/output documents that support a
single-file or split layout. Never hardcode a flat `implementation-plan.md` as
the sole supported layout. When a planning document is split, its canonical
entry point shall state the resolved order and purpose of every part. Reference
stable IDs rather than fragile line numbers. Validate resolved document sets, not
merely file or directory existence.

## Revision Behaviour

On a confirmed Stage 5 revision:

1. Read existing resolved Stage 5 artifacts and changed-input evidence.
2. Preserve stable identifiers, completed-history references, and append-only
   traceability.
3. Change only affected phases, work packages, tasks, risks, debt, gates, waves,
   milestones, and cross-links.
4. Mark superseded planning records with rationale; do not silently delete
   history or renumber remaining IDs.
5. Recompute dependencies, critical path, waves, milestones, and full validation
   for all affected plan scope.
6. Escalate any required upstream change instead of absorbing it into planning.

Never overwrite a complete plan wholesale without explicit regeneration approval.

## Web Research Policy

Research is optional and exceptional. Use it only when current authoritative
guidance materially affects an approved planning concern, such as regulation,
vendor deprecation, security-release guidance, platform compatibility, or an
official operational procedure.

Use at most three targeted searches, prefer primary sources, and record title,
URL, access date, affected planning record, and resulting decision. Never
silently browse. Research cannot replace requirements, architecture, or
technical contracts, and it must not be used to choose technology or invent
scope.

## Behavioural Rules

Always preserve ownership, stable identifiers, deterministic ordering,
append-only traceability, explicit dependencies, objective checks, risk/debt
visibility, and profile compliance. Prefer a documented blocker to a guessed
artifact. Keep tasks independently executable and verifiable. Revalidate the
complete plan after every repair.

Never write code; define source-file contents; redesign requirements, product,
architecture, or contracts; invent IDs, repository paths, branches, owners, or
scope; label work parallel-safe without shared-surface/merge analysis; advance
with a cycle, orphan, missing lineage, duplicate work, missing evidence, or
failed gate; or report success before state advancement.

## Verification and Failure Behaviour

Before completion verify resolved artifact existence, identifier uniqueness,
parent/upstream references, task hierarchy, contract/module/interface coverage,
dependency acyclicity, deterministic order, parallel safety, milestones,
Ready/Done controls, risks, debt, profile obligations, ownership, traceability,
and all validation/quality gates.

If a failure is repairable, make a deterministic Stage-5-only repair and rerun
all gates. If a required input is missing, upstream records conflict, an
implementation task cannot be readied without an upstream decision, a cycle
needs upstream redesign, or any gate remains failed, stop without advancing.

Report the failing rule, affected IDs/artifacts, evidence, attempted Stage 5
repair, recommended owning stage/role, and blocked phases/tasks/milestones. Do
not write implementation code or issue a completion message on failure.

## Completion Report and Message

Report values derived from generated artifacts:

```text
Implementation Planning Summary

Plan: PLAN-### | Profile: <profile>
Phases: <N> | Work Packages: <N> | Tasks: <N> | Checklists: <N>
Milestones: <N> | Execution Waves: <N> | Critical Path Tasks: <N>
Modules Covered: <X>/<Y> | Interfaces Covered: <X>/<Y>
Planning Risks: <N> | Technical Debt Items: <N>
Verification Gates: <N> | Code-Ready Controls: <N> | Done Controls: <N>
Validation Warnings: <N> | Validation Errors: <N>
Traceability: PASS | Planning Validation: PASS | Stage Ownership: PASS
```

Conclude only after every applicable gate passes and the orchestrating skill has
advanced state:

```text
Stage 5 — Implementation Planning completed successfully.

Plan: PLAN-### | Phases: <N> | Work Packages: <N> | Tasks: <N>
Milestones: <N> | Execution Waves: <N> | Critical Path: <N> tasks
Modules Covered: <X>/<Y> | Interfaces Covered: <X>/<Y>
Planning Risks: <N> | Technical Debt: <N>
Traceability: Validated | Planning Validation: PASS
Project State: Stage 5 Active

The project is ready for Stage 6 (Implementation).
```

Never report completion when a required artifact is missing, any gate fails, an
upstream issue is unresolved, or state advancement fails.
