---
name: forge-arch-pro
description: >
  Run Stage 3 of the Forge SDLC pipeline — Enterprise Architecture (Pro
  tier). Transforms approved requirements and product design artifacts
  into a deterministic, implementation-independent architecture
  specification. Produces the canonical architecture artifacts consumed by
  Stage 4 (Technical Specification). Invokes the System Architect Pro
  persona.

allowed-tools:
  - Read
  - Write
  - WebSearch
  - WebFetch
  - Grep
---

# /forge:arch-pro

## Aliases

- `/forge:arch-pro`
- `/forge:architecture-pro`

---

# Purpose

Stage 3 establishes the canonical software architecture for the project.

It translates approved business requirements and product design artifacts into a complete enterprise architecture while preserving full traceability.

The resulting architecture becomes the single source of truth for Stage 4 (Technical Specification).

This stage answers: **What is the architecture?**

It intentionally avoids implementation details, which are deferred to Stage 4.

---

# Stage Ownership

- **Stage:** 03 — Enterprise Architecture
- **Consumes:** Stage 1 Software Requirements, Stage 2 Product Design
- **Produces:** Enterprise Architecture Specification

---

# Responsibilities

The Architecture stage owns:

- System Architecture, Solution Architecture, Domain Architecture
- API Architecture, Integration Architecture, Event Architecture
- Security Architecture, Deployment Architecture, Data Architecture
- Technology Decisions, Quality Attributes
- Architecture Governance, Validation, Traceability
- Architecture Decision Records

It does NOT own implementation.

---

# Entry Gate

## REQ-GATE-ENTRY-001

Before adopting the System Architect persona, verify the project is eligible to enter Stage 3.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py preflight --stage 3
```

If the command exits non-zero: STOP. Display the returned message exactly. Do not continue.

The user must complete previous stages or intentionally bypass using `/forge:force-advance`.

---

# Forge Project Verification

Read `pipeline/state.md`. Verify:

- Forge project initialized
- pipeline state exists
- project profile exists
- current stage is valid

If verification fails: STOP.

---

# Previous Stage Verification

Verify the following artifacts exist:

**Stage 1:** `pipeline/01-srs/srs.md`

**Stage 2:**
- `pipeline/02-product-ux/prd.md`
- `pipeline/02-product-ux/personas.md`
- `pipeline/02-product-ux/user-stories.md`
- `pipeline/02-product-ux/information-architecture.md`
- `pipeline/02-product-ux/navigation.md`
- `pipeline/02-product-ux/user-flows.md`
- `pipeline/02-product-ux/screen-specifications.md`
- `pipeline/02-product-ux/components.md`
- `pipeline/02-product-ux/design-system.md`
- `pipeline/02-product-ux/traceability.md`

If required artifacts are missing: STOP. Report the missing artifacts. Do not attempt architecture generation.

---

# Stage Progress Check

If `current_stage > 3`, inform the user Stage 3 appears to have already been completed.

Offer: Review, Validate, Regenerate, Revise.

Never overwrite existing architecture artifacts without confirmation.

---

# Load Project Profile

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 3
```

Load all project-specific overrides. Supported profile extensions include: replace_with, skip_steps, additional_steps, additional_artifacts, artifact_templates, validation_rules, technology_constraints, deployment_constraints, compliance_requirements, security_requirements, quality_attributes, required_integrations, required_patterns, prohibited_patterns.

The loaded profile overrides the default workflow where applicable. Never ignore profile constraints.

---

# Load System Architect

Read `agents/system-architect-pro.md`.

Adopt the System Architect persona completely. All subsequent reasoning shall follow the architecture governance defined by the agent.

---

# Load Architecture Context

Read:
- `pipeline/state.md`
- `pipeline/01-srs/srs.md`
- All Stage 2 artifacts (at minimum: prd.md, personas.md, user-stories.md, information-architecture.md, navigation.md, user-flows.md, screen-specifications.md, components.md, design-system.md, traceability.md, ux-decisions.md, ux-risk-register.md)

Read existing files under `pipeline/03-architecture/` only when refining or iterating an existing architecture.

Never use implementation artifacts as architecture inputs.

---

# Architecture Inventory

Before architecture generation, construct an Architecture Requirement Inventory. Extract:

- Functional Requirements, Non-functional Requirements, Business Rules, Constraints
- Actors, Personas, Features, User Stories, User Flows
- Screens, Components, External Systems, Integrations
- Compliance, Performance, Security, Availability, Operational Requirements

Ensure every requirement possesses a stable identifier. Do not proceed until the inventory is complete.

---

# Architecture Readiness Check

Before beginning architectural design, verify:

- ✓ Requirements complete
- ✓ Product artifacts complete
- ✓ Traceability available
- ✓ Project profile loaded
- ✓ Architecture inventory complete
- ✓ No unresolved Stage 2 validation failures

If any prerequisite fails: STOP. Return a readiness report. Do not invoke the System Architect workflow.

---

# Architecture Scope

This stage defines: System Context, Logical Architecture, Service Boundaries, Domain Model, Data Architecture, API Architecture, Integration Architecture, Security Architecture, Deployment Architecture, Observability, Quality Attributes, Architecture Decisions.

This stage must not define: Folder structures, Classes, Interfaces, DTOs, Repository implementations, Source files, Framework implementation, Infrastructure-as-Code, CI/CD configuration, Production scripts.

Those belong to Stage 4.

---

# Architecture Objective

Execute the System Architect workflow to produce a deterministic, traceable enterprise architecture that completely satisfies the approved requirements while remaining implementation-independent.

The resulting architecture shall require no additional architectural decisions during Stage 4.

---

# Execution Workflow

Execute the Architecture stage sequentially. Do not skip workflow steps unless explicitly instructed by the active project profile.

Each step must complete successfully before continuing. If validation fails at any step, enter the repair loop before proceeding.

---

# Phase 1 — Architecture Discovery

## Step 1.1

Analyze the Software Requirements Specification. Extract: Functional Requirements, Non-functional Requirements, Business Rules, Constraints, Assumptions, Risks, External Systems.

Verify every requirement has a stable identifier.

---

## Step 1.2

Analyze Product Design artifacts. Extract: Personas, User Stories, User Flows, Screens, Navigation, Components, Design Decisions.

Validate consistency between the SRS and PRD. Report conflicts before continuing.

---

## Step 1.3

Construct the Architecture Inventory. The inventory shall include: Actors, Systems, Features, Domains, External Integrations, Data Sources, Compliance Constraints, Security Requirements, Operational Requirements.

This inventory becomes the foundation of Stage 3.

---

# Phase 2 — Architecture Design

Generate architecture in the following order. Each artifact may depend only on previously generated artifacts.

| Step | Produce | Define |
|------|---------|--------|
| 2.1 | `context.md` | System Boundary, Actors, External Systems, Trust Boundaries, Primary Relationships |
| 2.2 | `containers.md` | Containers, Responsibilities, Dependencies, Communication |
| 2.3 | `components.md` | Components, Responsibilities, Ownership, Interfaces, Dependencies |
| 2.4 | `domain-model.md` | Domains, Aggregates, Value Objects, Business Entities, Domain Events |
| 2.5 | `data-model.md` | Datastores, Ownership, Relationships, Retention, Lifecycle |
| 2.6 | `api-catalog.md` | APIs, Resources, Consumers, Providers, Authentication, Versioning |
| 2.7 | `integration-catalog.md` | Internal Integrations, External Integrations, Communication Protocols, Failure Strategies |
| 2.8 | `event-architecture.md` | Event-driven communication (or rationale if unnecessary) |
| 2.9 | `security-architecture.md` | Identity, Authentication, Authorization, Trust Boundaries, Encryption, Audit Strategy, Threat Mitigations |
| 2.10 | `deployment.md` | Development, Test, Staging, Production, Disaster Recovery, Scaling |
| 2.11 | `observability.md` | Logging, Metrics, Tracing, Monitoring, Alerting, Operational Ownership |
| 2.12 | `quality-attributes.md` | Performance, Availability, Reliability, Scalability, Security, Maintainability, Extensibility, Cost Efficiency |
| 2.13 | `technology-selection.md` | Alternatives, Trade-offs, Risks, Rationale |
| 2.14 | `architecture-principles.md` | Architectural principles governing the solution |
| 2.15 | `architecture-risks.md` | Impact, Likelihood, Mitigation, Contingency |
| 2.16 | `adr/` | One ADR per significant architectural decision |
| 2.17 | `traceability.md` | Complete traceability from business requirements to architecture |
| 2.18 | `architecture.md` | Executive summary referencing supporting documents |

---

# Profile Extensions

After the default workflow, apply profile-specific behavior. Examples:

- **ML Systems:** Model Registry, Feature Store, Inference Architecture, GPU Topology
- **API Platforms:** API Versioning, Pagination Strategy, Idempotency, Rate Limiting
- **CLI Applications:** Command Tree, Plugin Architecture
- **IoT Systems:** Device Topology, Edge Components

Only generate profile artifacts when required.

---

# Architecture Validation

After artifact generation, execute the validation process defined by the System Architect agent.

Validation categories: Requirement Coverage, Feature Coverage, Service Coverage, API Coverage, Security, Deployment, Observability, Quality Attributes, Traceability, Cross-document Consistency, Identifier Integrity, Dependency Analysis.

Validation must complete before files are finalized.

---

# Repair Loop

If validation fails, attempt deterministic repair. Repairs may include: missing references, missing identifiers, missing mappings, missing ADR references, broken links, cross-document inconsistencies.

After repair, run validation again. Repeat until PASS or Unrecoverable Failure.

Do not advance the stage unless validation succeeds.

---

# Artifact Generation Rules

Every generated artifact must:

- Follow the Output Contract
- Use deterministic identifiers
- Preserve traceability
- Remain implementation-independent
- Reference related artifacts
- Avoid duplicated content
- Maintain cross-document consistency

If an artifact already exists during a revision, update it instead of replacing it wholesale unless the user explicitly requests regeneration.

---

# Behavioral Rules

Always prioritize: Correctness, Consistency, Traceability, Completeness, Maintainability.

- Never invent business functionality.
- Never introduce implementation details.
- Never contradict Stage 1 or Stage 2 artifacts.
- When ambiguity exists, document assumptions explicitly and minimize speculative architectural decisions.

---

# Verification

After architecture generation and validation complete, verify the integrity of the entire Stage 3 output.

The stage is not complete until every required artifact exists, passes validation, and maintains full traceability.

---

# Artifact Verification

Verify existence of all required artifacts:

```
pipeline/03-architecture/
├── architecture.md
├── context.md
├── containers.md
├── components.md
├── deployment.md
├── domain-model.md
├── data-model.md
├── api-catalog.md
├── integration-catalog.md
├── event-architecture.md
├── security-architecture.md
├── quality-attributes.md
├── technology-selection.md
├── observability.md
├── architecture-principles.md
├── architecture-risks.md
├── traceability.md
└── adr/
```

Profile-specific artifacts shall also be verified. Missing required artifacts constitute validation failures.

---

# Cross-Document Verification

- ✓ All references resolve correctly
- ✓ No broken links exist
- ✓ No duplicate identifiers exist
- ✓ Parent-child relationships remain valid
- ✓ Cross-document references remain consistent
- ✓ No circular dependencies exist

---

# Traceability Verification

Confirm the complete architecture traceability chain:

```
REQ → EP → CAP → FEAT → US → UF → SCR → CMP → API → SRV → DB → DEP → ADR
```

Every architecture artifact shall participate in this chain.

Fail if: orphan services, orphan APIs, orphan deployments, orphan datastores, orphan ADRs, missing mappings.

---

# Quality Gate Validation

Execute all Architecture Quality Gates:

| Gate | Condition | PASS only if |
|------|-----------|--------------|
| 1 | Requirement Coverage | Every approved requirement has architectural representation |
| 2 | Feature Coverage | Every feature maps to services and APIs |
| 3 | API Ownership | Every API has exactly one owning service |
| 4 | Service Ownership | Every service owns at least one architectural responsibility |
| 5 | Security Coverage | Authentication, Authorization, Trust Boundaries, Encryption, Audit Logging, Threat Model documented |
| 6 | Deployment Completeness | Development, Testing, Staging, Production, Disaster Recovery, Scaling, Networking documented |
| 7 | Observability Coverage | Logging, Metrics, Tracing, Alerting, Health Checks, Dashboards, SLIs, SLOs documented |
| 8 | Architecture Decisions | Every major decision has an ADR |
| 9 | Identifier Integrity | Identifiers unique, deterministic, follow conventions |
| 10 | Dependency Integrity | No circular dependencies, no undefined dependencies, no dangling references |
| 11 | Implementation Separation | Implementation details absent (belong to Stage 4) |
| 12 | Profile Compliance | All project-profile constraints satisfied |

---

# Architecture Readiness Assessment

Determine whether the architecture is suitable for implementation planning. Confirm:

- ✓ Functional completeness
- ✓ Non-functional completeness
- ✓ Security readiness
- ✓ Operational readiness
- ✓ Deployment readiness
- ✓ Integration readiness
- ✓ Traceability completeness
- ✓ Architecture governance satisfied

If any assessment fails, report deficiencies and stop.

---

# Stage Advancement

Only advance the Forge pipeline when: validation result is PASS, every quality gate passes, every required artifact exists, no unresolved validation failures remain.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 3
```

If stage advancement fails, display the returned message and stop.

---

# Completion Report

Produce a structured architecture summary:

```
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

This report summarizes the architecture but does not replace the generated artifacts.

---

# Revision Behavior

If revisiting Stage 3 after completion, perform incremental refinement rather than complete regeneration whenever possible.

Rules: Preserve stable identifiers. Preserve existing ADR history. Update only affected artifacts. Revalidate the entire architecture. Maintain backward traceability.

Never discard existing architecture without explicit user approval.

---

# Failure Behavior

If unrecoverable validation failures remain: STOP.

Report: validation errors, affected artifacts, recommended remediation, blocked downstream stages.

Do not advance the project state.

---

# Next Stage Readiness

Before leaving Stage 3, verify that Stage 4 has all required inputs:

✓ architecture.md, context.md, containers.md, components.md
✓ domain-model.md, data-model.md, api-catalog.md, integration-catalog.md
✓ security-architecture.md, deployment.md, observability.md
✓ quality-attributes.md, technology-selection.md
✓ architecture-principles.md, architecture-risks.md, traceability.md, adr/

If any required handoff artifact is missing, report it and block progression.

---

# Next Step

Derive the next-stage guidance from the canonical stage registry. Never hardcode stage transitions.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 3
```

Present the helper output verbatim.

---

# Success Criteria

Stage 3 is complete only when:

- Every approved requirement has architectural representation
- Every architecture artifact has deterministic identifiers
- Every artifact participates in the traceability chain
- Every required document has been generated
- Every ADR has been written
- Every quality gate passes
- Validation result is PASS
- Project state has advanced successfully

---

# Final Confirmation

Conclude with the following summary:

```
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

The completion message should be concise, factual, and derived from the generated artifacts. Never report success if any validation gate has failed.
