# Stage 3 Workflow and Governance

## Workflow

Execute sequentially. Each step has clear inputs and outputs.

| Step | Action |
|------|--------|
| 1 | Read project state, Stage 1 artifacts, Stage 2 artifacts. Determine project profile. |
| 2 | Build Architecture Requirement Inventory. Classify: Functional Requirements, Non-functional Requirements, Business Constraints, Technical Constraints, Compliance Requirements, Integration Requirements, Operational Requirements. |
| 3 | Identify: Actors, External Systems, Trust Boundaries, Business Domains, Bounded Contexts. |
| 4 | Define: System Context, System Boundary, External Relationships (C4 Level 1). |
| 5 | Design: Containers, Communication Paths, Responsibilities (C4 Level 2). |
| 6 | Design: Components, Responsibilities, Interactions, Ownership (C4 Level 3). |
| 7 | Design: Logical Domain Model, Business Entities, Relationships, Aggregates, Domain Events. |
| 8 | Design: Physical Data Architecture, Datastores, Persistence Strategy, Retention, Backup, Recovery. |
| 9 | Design: API Catalog, Integration Catalog, Event Architecture, Communication Patterns. |
| 10 | Design: Security Architecture, Threat Model, Trust Boundaries, Identity, Authorization, Secrets, Encryption. |
| 11 | Design: Deployment Architecture, Infrastructure Topology, Scaling, Availability, Disaster Recovery. |
| 12 | Design: Observability, Monitoring, Logging, Tracing, Operational Metrics. |
| 13 | Evaluate: Technology Choices, Trade-offs, Alternatives. Create ADRs. |
| 14 | Evaluate: Quality Attributes — Performance, Availability, Reliability, Maintainability, Scalability, Security. |
| 15 | Generate Architecture Traceability Matrix. Verify every architectural artifact maps to business intent. |
| 16 | Run complete validation. Repair issues where possible. Repeat until PASS or Unrecoverable Failure. |
| 17 | Write architecture artifacts. Write ADRs. |
| 18 | Report validation summary. |

### Step Groups

| Group | Steps | Focus |
|-------|-------|-------|
| Intake | 1–2 | Read inputs, classify requirements |
| Discovery | 3 | Identify actors, systems, boundaries, contexts |
| C4 Design | 4–6 | Context → Containers → Components |
| Domain Design | 7–8 | Domain model → Data architecture |
| Integration | 9 | APIs, integrations, events |
| Cross-cutting | 10–12 | Security, deployment, observability |
| Evaluation | 13–14 | Technology decisions, quality attributes |
| Validation | 15–16 | Traceability, validation, repair |
| Output | 17–18 | Write artifacts, report summary |

---

## Discovery Detail (Steps 1–3)

**Step 1 — Requirements Analysis.** Analyze the Software Requirements
Specification. Extract Functional Requirements, Non-functional Requirements,
Business Rules, Constraints, Assumptions, Risks, and External Systems. Verify
every requirement has a stable identifier.

**Step 2 — Product Design Analysis.** Analyze Product Design artifacts.
Extract Personas, User Stories, User Flows, Screens, Navigation, Components,
and Design Decisions. Validate consistency between the SRS and PRD; report
conflicts before continuing.

**Step 3 — Architecture Inventory.** Construct the Architecture Inventory:
Actors, Systems, Features, Domains, External Integrations, Data Sources,
Compliance Constraints, Security Requirements, Operational Requirements. This
inventory becomes the foundation of Stage 3.

---

## Web Research Policy

Web research is optional. Use WebSearch only when current architectural
guidance materially improves the design — for example: cloud-native best
practices, modern security recommendations, industry standards,
vendor-neutral architectural patterns, technology comparison, or performance
recommendations.

Limit research to a maximum of three searches. If research influences the
architecture, document Source Title, Source URL, and Affected Section. Never
silently browse. Never rely on undocumented external guidance.

---

## Revision Behavior

If revisiting Stage 3 after completion, perform incremental refinement rather
than complete regeneration whenever possible.

Rules: Preserve stable identifiers. Preserve existing ADR history. Update
only affected artifacts. Revalidate the entire architecture. Maintain
backward traceability. If an artifact already exists during a revision,
update it instead of replacing it wholesale unless the user explicitly
requests regeneration.

Never discard existing architecture without explicit user approval.

---

## Failure Behavior

If unrecoverable validation failures remain: STOP.

Report: validation errors, affected artifacts, recommended remediation, and
blocked downstream stages. Do not advance the project state.

---

## Final Review Checklist

Before completion verify:

- All approved requirements are represented
- All features have architectural ownership
- Every screen maps to APIs
- Every API maps to a service
- Every service owns its datastore
- Every deployment target is defined
- Security architecture is complete
- Deployment architecture is complete
- Observability strategy is complete
- Quality attributes are documented
- Architecture decisions have ADRs
- Traceability is complete
- No duplicate identifiers exist
- No broken references exist
- No implementation details remain
- All validation rules pass

---

## Downstream Readiness Assessment

Determine whether the architecture is suitable for implementation planning.
Confirm:

- Functional completeness
- Non-functional completeness
- Security readiness
- Operational readiness
- Deployment readiness
- Integration readiness
- Traceability completeness
- Architecture governance satisfied

If any assessment fails, report deficiencies and stop.

---

## Next Stage Readiness

Before leaving Stage 3, verify that every artifact in the Required
Deliverables list (`references/architect/01-foundation.md`) exists, passes
validation, and is fully cross-referenced. If any required handoff artifact
is missing, report it and block progression to Stage 4.

---

## Completion Report

Report values derived from generated artifacts:

```text
Architecture Summary

Requirements Processed: <N>
Functional Requirements: <N>
Non-functional Requirements: <N>
Features: <N>
Containers: <N>
Components: <N>
Services: <N>
APIs: <N>
External Integrations: <N>
Events: <N>
Datastores: <N>
Deployment Targets: <N>
Security Controls: <N>
Architecture Decisions: <N>
ADRs: <N>
Architecture Risks: <N>
Validation Warnings: <N>
Validation Errors: <N>
Architecture Validation: PASS
```

This report summarizes the architecture but does not replace the generated
artifacts.

---

## Completion Criteria

Stage 3 is complete only when:

- Every approved requirement has architectural representation
- Every architectural decision is documented with a corresponding ADR
- Every architecture artifact has a deterministic identifier and
  participates in the traceability chain
- Every required document in the Required Deliverables list has been
  generated
- Every quality gate passes and the validation result is PASS
- Project state has advanced successfully

---

## Final Confirmation

Conclude only after every applicable gate passes and the orchestrating skill
has advanced state:

```text
Stage 3 — Enterprise Architecture completed successfully.

Architecture artifacts generated: <N>
Requirements mapped: <X>/<Y>
Services: <N>
Containers: <N>
Components: <N>
APIs: <N>
Datastores: <N>
External Integrations: <N>
Architecture Decisions: <N>
ADRs: <N>
Architecture Validation: PASS
Project State: Stage 3 Active

The project is now ready for Stage 4 (Technical Specification).
```

The completion message should be concise, factual, and derived from the
generated artifacts. Never report success if any validation gate has failed
or state advancement has not succeeded.
