# Architecture Validation Rules

> Loaded during validation phase (Workflow Steps 15–16).
> Architecture SHALL NOT be considered complete until all rules pass.

---

## Validation Objectives

Validate:

- Completeness
- Consistency
- Traceability
- Architectural Correctness
- Separation of Concerns
- Security Coverage
- Quality Attribute Coverage
- Operational Readiness

---

## Requirement Coverage

Every approved requirement shall map to one or more architectural elements.

Required mapping: REQ → Feature → Screen → API → Service → Deployment

Fail if:
- a requirement has no service
- a requirement has no architectural representation
- a requirement is implemented by an unidentified component

---

## Feature Coverage

Every feature shall reference one or more services, APIs, and architectural components. No feature may remain unimplemented.

---

## Screen Coverage

Every screen produced during Stage 2 shall reference supporting APIs, owning services, and authorization requirements.

Fail if a screen has no architectural support.

---

## Service Validation

Every service shall define: Identifier, Purpose, Responsibilities, Dependencies, Owned APIs, Owned Datastore, Deployment Target, Observability, Security Considerations, Quality Attributes.

Fail if any section is missing.

---

## API Validation

Every API shall define: API ID, Purpose, Method, URI, Authentication, Authorization, Provider, Consumer, Referenced Requirements/Features/Services.

Fail if:
- an API has no owner
- an API is unused
- duplicate APIs exist
- undocumented authentication exists

---

## Datastore Validation

Every datastore shall define: Purpose, Owner, Encryption, Retention, Backup, Recovery, Referenced Services, Referenced Requirements.

Fail if:
- orphan datastore
- duplicate ownership
- undefined lifecycle
- missing security

---

## Integration Validation

Every external integration shall define: Purpose, Authentication, Timeout, Retry, Monitoring, Failure Handling, Referenced Requirements, Referenced Services.

---

## Security Validation

Verify: Authentication, Authorization, RBAC, Secrets, Encryption, Audit Logging, Threat Model, Trust Boundaries, Rate Limiting, Compliance, Input Validation, Output Encoding.

Fail if any security area is undocumented.

---

## Deployment Validation

Verify: Development, Testing, Staging, Production, Disaster Recovery, Infrastructure Topology, Scaling Strategy, Availability, Networking, Monitoring.

Fail if deployment architecture is incomplete.

---

## Observability Validation

Verify: Logging, Metrics, Tracing, Health Checks, Alerting, SLIs, SLOs, Dashboards.

Fail if operational visibility is incomplete.

---

## Quality Attribute Validation

Verify architecture strategies exist for: Availability, Performance, Latency, Scalability, Reliability, Maintainability, Security, Extensibility, Portability, Interoperability, Resilience, Cost Efficiency.

---

## Traceability Validation

Every architecture artifact shall trace back to business requirements.

Required chain: REQ → EP → CAP → FEAT → US → UF → SCR → CMP → API → SRV → DB → DEP → ADR

Fail if: missing links, orphan services, orphan APIs, orphan databases, orphan deployments, orphan ADRs.

---

## Identifier Validation

Identifiers must: Be unique, Remain stable, Match naming conventions, Reference existing artifacts.

Duplicate identifiers are validation failures.

---

## Dependency Validation

Validate: No circular service dependencies, No circular container dependencies, No undefined external dependencies, No missing integrations, No dangling references.

---

## Cross-Artifact Consistency

All generated artifacts shall remain internally consistent:

- An API referenced by a service must exist
- A deployment target referenced by a container must exist
- A datastore referenced by a service must exist
- A trust boundary referenced by security architecture must exist
- A domain entity referenced by the data model must exist
- An ADR referenced by another document must exist

Broken references are considered validation failures.

---

## Architecture Quality Gates

The stage SHALL fail if any of the following occur:

| Gate | Failure Condition |
|------|-------------------|
| 1 | Missing requirement coverage |
| 2 | Missing service ownership |
| 3 | Missing API ownership |
| 4 | Missing deployment mapping |
| 5 | Incomplete security architecture |
| 6 | Incomplete observability |
| 7 | Missing ADRs |
| 8 | Duplicate identifiers |
| 9 | Broken traceability |
| 10 | Circular dependencies |
| 11 | Broken cross-document references |
| 12 | Implementation details introduced |

If implementation-specific artifacts appear, remove them. Defer them to Stage 4.

---

## Repair Strategy

When validation failures are detected, attempt automatic repair. Repairs may include:

- Adding missing references
- Correcting identifiers
- Creating missing ADRs
- Completing traceability
- Resolving dependency inconsistencies
- Repairing documentation references

If automatic repair cannot confidently resolve the issue, STOP. Report the validation failures. Do not advance the stage.
