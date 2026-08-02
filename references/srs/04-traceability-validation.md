# Stage 1 Traceability and Validation

*Loaded before creating traceability and before any validation or repair.*

## Requirements Traceability

Generate `pipeline/01-srs/requirements-traceability.md`.

The traceability matrix shall map `Business Goal → Requirement`. Every requirement shall reference one or more Business Goals. Every Business Goal shall own at least one Requirement.

**Example:**
| BG | Requirement |
|----|-------------|
| BG-001 | REQ-F-001 |
| BG-001 | REQ-F-002 |
| BG-002 | REQ-NF-001 |

No orphan Business Goals. No orphan Requirements.

---

## Validation Rules

Validation is mandatory before writing output.

**Fail validation if:**
- Business Goal has no Requirement
- Requirement has no Business Goal
- Duplicate identifiers exist
- Duplicate requirements exist
- Requirement is ambiguous
- Requirement contains implementation details
- Requirement is not measurable or testable
- Requirement lacks acceptance conditions, priority, or business value
- Requirement conflicts with another requirement
- Constraint documented as requirement
- Business Rule documented as requirement
- Risk lacks mitigation
- Dependency lacks owner
- Open question undocumented

Attempt deterministic repair before reporting failure.

---

## Quality Gates

Execute the following gates. Proceed only if all quality gates PASS.

| Gate | Criterion |
|------|-----------|
| 1 | Business Goals complete |
| 2 | Scope defined |
| 3 | Stakeholders identified |
| 4 | Requirements categorized |
| 5 | Requirements prioritized |
| 6 | Acceptance conditions documented |
| 7 | Business Rules identified |
| 8 | Constraints documented |
| 9 | Dependencies documented |
| 10 | Risks documented |
| 11 | Requirements Traceability complete |
| 12 | No implementation details detected |

---

## Verification

Before completing Stage 1, verify that every required artifact has been generated, validated, and internally consistent.

Stage 1 establishes the canonical business truth for the entire Forge pipeline. No downstream stage may compensate for incomplete requirements.

---

## Artifact Verification

Verify the existence of: `pipeline/01-srs/srs.md`, `pipeline/01-srs/requirements-traceability.md`.

If generated, also verify: `stakeholder-map.md`, `glossary.md`, `domain-model.md`.

Missing mandatory artifacts constitute validation failures.

---

## Requirements Consistency Validation

Verify:
- ✓ Every Business Goal has supporting requirements
- ✓ Every Requirement supports at least one Business Goal
- ✓ No duplicate Business Goals, Requirements, Business Rules, Constraints, Assumptions, Risks, Dependencies
- ✓ No conflicting Requirement IDs or Goal IDs

---

## Business Validation

Verify:
- ✓ Problem statement clearly defined
- ✓ Scope clearly defined
- ✓ Out-of-scope documented
- ✓ Stakeholders identified
- ✓ Business objectives measurable
- ✓ Success criteria measurable
- ✓ Business terminology consistent

---

## Requirement Quality Validation

Every requirement shall satisfy: Necessary, Atomic, Complete, Correct, Consistent, Feasible, Testable, Measurable, Prioritized, Unambiguous, Implementation Independent.

Reject requirements violating any quality attribute.

---

## Acceptance Condition Validation

Every Functional Requirement shall contain measurable acceptance conditions.

Verify: Observable behavior, Objective evaluation, Business outcome, No implementation details, No technology assumptions.

Acceptance conditions remain business-oriented. UX acceptance criteria belong to Stage 2.

---

## Requirement Traceability Validation

Validate `Business Goal → Requirement` mapping.

**Requirements Traceability Rules:**
- Every Business Goal owns one or more Requirements
- Every Requirement references one or more Business Goals

**Fail if:** orphan Business Goals exist, orphan Requirements exist, duplicate mappings exist, broken mappings exist.

---

## Scope Validation

Verify: Everything inside scope is represented. Everything outside scope is excluded. No hidden scope. No undocumented assumptions expanding scope.

---

## Risk Validation

Every identified risk shall contain: ✓ Likelihood, ✓ Impact, ✓ Mitigation, ✓ Contingency.

No incomplete risks allowed.

---

## Dependency Validation

Every dependency shall contain: ✓ Owner, ✓ Type, ✓ Impact, ✓ Failure consequence.

---

## Constraint Validation

Every constraint shall be measurable where applicable, justified, categorized, and distinguishable from requirements. Constraints are not functionality.

---

## Assumption Validation

Every assumption shall be explicit, reviewable, explain why it exists, and describe its impact. Never hide assumptions inside requirements.

---

## Open Question Validation

Every unresolved issue shall appear as an Open Question. Never silently ignore uncertainty.

---

## SRS Readiness Assessment

Determine whether the SRS is ready for Product Design. Confirm:

✓ Business goals complete · ✓ Stakeholders complete · ✓ Scope complete · ✓ Requirements complete
✓ Priorities assigned · ✓ Risks documented · ✓ Dependencies documented · ✓ Constraints documented
✓ Assumptions documented · ✓ Traceability complete · ✓ Validation passed

If any assessment fails, STOP. Report deficiencies. Do not advance the pipeline.
