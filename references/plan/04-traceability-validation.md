# Stage 5 Traceability and Validation

## Traceability Rules

Maintain complete, append-only planning lineage:

```text
BG → REQ → EP → CAP → FEAT → US → UF → SCR → CMP → API → SRV → DB → ADR
   → SPEC → MOD → INT → DTO → CFG → ERR → PLAN → PHASE → WP → TASK → CHK → CODE
```

Preserve every available upstream link. A planning record may cite the nearest
valid parent and its applicable `SPEC`/`MOD`/`INT` records, but it must never
invent a missing link. Every `PLAN` references approved scope; every `PHASE`
references its plan; every `WP` references its phase and approved module scope;
every `TASK` references its work package and valid Stage 4 contract; and every
`CHK`, `CODE-READY`, `DONE`, `MILE`, `RISK-PLAN`, `TD`, assumption, constraint,
and `VG` references the planning records it governs or affects.

The traceability matrix shall cover Stage 5 records and resolve all parent and
upstream IDs. No Stage 5 artifact may become an orphan or an invented upstream
parent.

## Deterministic Validation

Validation is mandatory after artifact generation and after every repair. Fail
the stage if any applicable condition is false:

1. Required, profile-added, and non-skipped artifacts resolve using `read-doc.py`.
2. Every identifier is syntactically valid, unique, stable, and type-correct.
3. Every planning artifact has a valid parent or valid upstream lineage.
4. Every task references at least one approved `SPEC` or applicable technical
   contract.
5. Every applicable module has one or more tasks or an explicit, approved
   non-implementation rationale.
6. Every applicable interface has one or more implementation/integration tasks.
7. Every task belongs to exactly one `WP`, every `WP` to one `PHASE`, and every
   `PHASE` to one `PLAN`.
8. Every work package references approved module scope.
9. Every milestone references work packages and has measurable exit criteria.
10. Every task has owner, effort, dependencies, outputs, acceptance checks,
    Ready controls, Done controls, and verification evidence.
11. Every dependency edge resolves, has valid direction, and introduces no
    self-edge, undefined node, invalid boundary crossing, or cycle.
12. Topological execution and wave ordering are reproducible from dependencies,
    priority, and ID tie-breaks; parallel work has governed shared surfaces.
13. Every risk, debt, assumption, constraint, Ready/Done control, checklist, and
    verification gate has required fields and valid affected references.
14. Repository, branch, integration, migration, rollback, risk, debt, and
    governance planning exist when approved scope makes them applicable.
15. No production code, source-file contents, implementation algorithm,
    unapproved architecture, upstream redefinition, duplicate work, or
    contradictory task order appears.
16. All profile obligations are represented and validated.

## Quality Gates

Pass Stage 5 only when every applicable gate passes:

| Gate | Required condition |
|---|---|
| Planning scope | All work derives from approved Stage 1–4 scope; no invented scope exists. |
| Artifact existence | Required and profile artifacts resolve through the document resolver. |
| Module coverage | Every applicable `MOD` has planning coverage or approved rationale. |
| Interface coverage | Every applicable `INT` has implementation/integration coverage. |
| Contract coverage | Every task references valid specification/contract lineage. |
| Hierarchy integrity | Task → WP → Phase → Plan relationships resolve exactly once. |
| Milestone integrity | Milestones cite work packages and measurable evidence-based exit criteria. |
| Dependency integrity | No orphan nodes, undefined references, self-edges, or cycles. |
| Deterministic order | Execution/wave order is reproducible and graph-valid. |
| Parallel safety | Shared surfaces, concurrency, merge order, and integration gates are governed. |
| Verification completeness | Task/work-package/milestone Ready, Done, acceptance, and evidence controls exist. |
| Ownership separation | No Stage 1–4 redefinition and no implementation code is present. |
| Duplication control | No duplicated deliverable, acceptance check, or conflicting task scope exists. |
| Profile compliance | Valid profile additions, replacements, concerns, and skips are recorded and satisfied. |
| Downstream readiness | Stage 6 can execute ready tasks without reopening Stage 5 planning. |

Report warnings separately. Unresolved errors always block advancement.

## Repair Rules

Repair only Stage 5 omissions or broken Stage 5 references: missing cross-links,
incomplete planning fields, malformed IDs, duplicate Stage 5 IDs, invalid task
hierarchy, or an incorrect planning dependency that can be corrected without
changing upstream intent.

After each repair, rerun the complete validation and quality-gate set. Never
repair by changing Stage 1–4 artifacts, inventing functionality, removing
required work, weakening a gate, fabricating a parent, or breaking a real
dependency. Escalate upstream conflicts and unrecoverable failures through the
workflow-governance rules.
