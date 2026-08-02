# Stage 2 Traceability and Validation

## Traceability Matrix

Generate `pipeline/02-product-ux/traceability.md` mapping all artifacts:

```
Requirement → Epic → Capability → Feature → User Story → User Flow → Screen → Component → Acceptance Criteria
```

Every REQ-ID from Stage 1 must appear at least once in the matrix. No orphaned artifacts (artifacts without a parent or reference path) are permitted. Every downstream ID must link to at least one upstream ID.

The traceability matrix is mandatory and must be 100% complete before advancing to Stage 3.

## Validation Rules

Fail the stage if any of these conditions are true:

- A requirement has no feature (orphaned REQ)
- A feature has no user flow (no UF references FEAT)
- A flow has no screen (no SCR references UF)
- A screen has no component (no CMP references SCR)
- A user story has no acceptance criteria (orphaned US)
- A screen lacks responsive behaviour documentation
- A screen lacks accessibility notes
- An artifact lacks a stable ID
- Duplicate IDs exist
- Invented features exist (features not traced to any REQ)
- A feature references a non-existent REQ
- A screen references a non-existent UF
- A component references a non-existent SCR

If any validation failure is found, make a deterministic Stage-2-only repair and rerun all gates. Only stop if repair is impossible (e.g., a missing upstream requirement).

## Quality Checklist

Before completion verify all items:

- ✓ Every requirement is mapped to at least one downstream artifact
- ✓ No invented functionality (all features trace to REQ-IDs)
- ✓ Every feature is traceable to at least one user story
- ✓ Every user story has acceptance criteria
- ✓ Every flow references at least two screens
- ✓ Every screen references at least one component
- ✓ Every screen includes responsive behaviour documentation
- ✓ Every screen includes accessibility notes (WCAG AA)
- ✓ Accessibility documented on all interactive elements
- ✓ Responsive behaviour documented for all breakpoints
- ✓ Acceptance criteria are measurable and objective
- ✓ All design tokens documented (colors, typography, spacing)
- ✓ Navigation model complete and consistent
- ✓ Information architecture hierarchical and logical
- ✓ IDs deterministic and unique within each type
- ✓ Traceability matrix 100% complete with no orphaned artifacts
- ✓ All validation gates passed
