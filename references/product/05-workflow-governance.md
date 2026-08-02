# Stage 2 Workflow and Governance

## Workflow

Execute in order. Do not skip a step unless the active profile explicitly permits it, and never skip ownership, traceability, validation, quality, or stage-advance controls.

1. Verify Stage 2 entry eligibility and load the project profile.
2. Read `pipeline/01-srs/srs.md` and build a complete requirement inventory.
3. Verify all requirements have stable REQ-IDs and upstream traceability from Stage 1.
4. Apply profile `replace_with`, `additional_artifacts`, `additional_steps`, `additional_concerns`, and permitted `skip_steps`; record each override.
5. Categorize requirements: Functional, Non-functional, Business Rules, Constraints, UX Requirements, External Dependencies.
6. Create personas (PER-###) based on requirement analysis and user segments.
7. Group requirements into Epics (EP-###), Capabilities (CAP-###), and Features (FEAT-###).
8. Generate User Stories (US-###) with Acceptance Criteria (AC-###) for each feature.
9. Design Information Architecture with logical hierarchy and content grouping.
10. Create Navigation Model documenting all navigation patterns and user movement.
11. Generate User Flows (UF-###) with clear pre/post conditions and screen references.
12. Define Screen Specifications (SCR-###) with states, permissions, responsive behaviour, and accessibility.
13. Generate text-based wireframes describing layouts without images.
14. Define Component Inventory (CMP-###) with variants, states, and accessibility.
15. Create comprehensive Design System with tokens, typography, spacing, and motion.
16. Generate UX Design Decisions (DDR-###) documenting major choices and tradeoffs.
17. Generate UX Risk Register (UXR-###) documenting identified risks and mitigations.
18. Generate traceability matrix mapping all REQ → downstream artifacts.
19. Run deterministic validation against all rules; repair only Stage 2 defects and rerun.
20. Verify downstream readiness, then prepare completion report only after orchestrating skill has advanced state successfully.

## Profile Overrides

Honor loaded overrides exactly:

- `replace_with` replaces only the named default activity/artifact while preserving all non-replaced requirements.
- `additional_artifacts` are required output, indexed in the canonical PRD, traceable, and validated.
- `additional_steps` are inserted at their configured position or after default workflow when position is absent.
- `additional_concerns` receive explicit coverage in personas, features, screens, or risk register.
- `skip_steps` omit only explicitly permitted default activities.

Profile-driven variations cannot authorize invented functionality, weakened validation, or omission of ownership, traceability, quality, or stage-advance gates.

## Web Research (REQ-WEBSEARCH-001)

Web research is optional and exceptional. Use it ONLY when:

- Current UX guidance is beneficial for design decisions
- Accessibility guidance is needed for WCAG compliance
- Platform conventions matter (web, mobile, desktop)
- Modern UX patterns affect design
- Component library best practices are relevant

**Limit:** Maximum 3 targeted searches.

Use primary sources. Record: Title, URL, Access Date, Affected Design Artifact, Resulting Decision.

Never silently browse. Research cannot replace requirements or invent scope, and it must not be used to choose platforms, architecture, or technology.

## Behavioral Rules

**Always:** Preserve complete traceability, produce deterministic identifiers, never invent functionality, keep design implementation-independent, prioritize clarity over creativity, prefer explicit documentation over assumptions, fail validation rather than producing ambiguous artifacts, ensure every artifact references its parent.

**Never:** Design APIs, design databases, write implementation code, define infrastructure, skip accessibility, skip responsive behavior, skip validation, break traceability, advance with orphaned artifacts, redefine requirements, or report success when validation fails.

## Verification and Failure Behaviour

Before completion verify:
- Resolved artifact existence under `pipeline/02-product-ux/`
- Identifier uniqueness within each type
- Parent/upstream references (every ID links to a parent or REQ)
- Feature/story/flow/screen/component hierarchy
- Requirement coverage (every REQ has at least one downstream mapping)
- No invented functionality
- Dependency acyclicity
- Traceability matrix completeness
- Accessibility documentation on all screens and components
- Responsive behaviour documented for all breakpoints
- All validation/quality gates

If a failure is repairable, make a deterministic Stage-2-only repair and rerun all gates. If a required input is missing, upstream records conflict, or any gate remains failed, stop without advancing.

Report the failing rule, affected IDs/artifacts, evidence, attempted Stage 2 repair, and blocked stages/features. Do not write implementation code or issue a completion message on failure.

## Completion Report and Message

Report metrics derived from generated artifacts:

```text
Product Design Summary

Personas: <N> | Epics: <N> | Capabilities: <N>
Features: <N> | User Stories: <N> | User Flows: <N>
Screens: <N> | Components: <N> | Design Decisions: <N>
UX Risks: <N> | Acceptance Criteria: <N>
Requirements Mapped: <X>/<Y> | Validation: <status>
Traceability: PASS | Accessibility: PASS | Responsive Design: PASS
```

Conclude only after every applicable gate passes and the orchestrating skill has advanced state:

```text
Stage 2 — Product Design & UX completed successfully.

Personas: <N> | Features: <N> | User Stories: <N>
User Flows: <N> | Screens: <N> | Components: <N>
Design Decisions: <N> | UX Risks: <N>
Requirements Mapped: <X>/<Y> | Traceability: Validated
Validation: PASS | Accessibility: PASS
Project State: Stage 2 Active

The project is ready for Stage 3 (Architecture Design).
```

Never report completion when a required artifact is missing, any gate fails, an upstream issue is unresolved, or state advancement fails.
