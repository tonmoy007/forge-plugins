# Architecture Identifiers & Traceability

> Loaded during any artifact creation step.
> Defines how artifacts are identified and linked.

---

## Artifact Identifiers

Use deterministic identifiers:

| Artifact | Format |
|----------|--------|
| System | SYS-001 |
| Containers | CNT-001, CNT-002 |
| Services | SRV-001, SRV-002 |
| APIs | API-001, API-002 |
| Datastores | DB-001, DB-002 |
| External Systems | EXT-001 |
| Integrations | INT-001 |
| Deployment Units | DEP-001 |
| Security Controls | SEC-001 |
| Architecture Decisions | ADR-001 |
| Events | MSG-001 |
| Quality Attributes | QA-001 |
| Non-functional Requirements | NFR-001 |
| Architecture Risks | AR-001 |
| Trust Boundaries | TB-001 |

Never duplicate identifiers. Never reuse identifiers for different artifacts. Identifiers remain stable across revisions.

---

## Traceability Chain

Architecture continues the Forge traceability chain. Never create a separate traceability model.

```
REQ → EP → CAP → FEAT → US → UF → SCR → CMP → API → SRV → DB → DEP → ADR
```

Every architectural artifact must reference upstream artifacts. Every downstream artifact must reference its parent. No orphaned architecture is permitted.

---

## Traceability Rules

Every architecture artifact shall include:

- Identifier
- Purpose
- Parent Artifacts
- Referenced Requirements
- Referenced Features
- Referenced Screens (if applicable)
- Referenced APIs (if applicable)
- Referenced Services
- Referenced ADRs
- Referenced Deployments

Traceability shall always be bidirectional.

---

## Architecture Layers

Reason about the system using architectural layers:

1. Business Layer
2. Application Layer
3. Service Layer
4. Integration Layer
5. Data Layer
6. Infrastructure Layer
7. Operations Layer

Never mix responsibilities between layers.

---

## Architecture Documentation Rules

Architecture documents shall:

- Be implementation independent
- Avoid code, pseudo-code, language-specific constructs, framework-specific implementation
- Focus on architecture, responsibilities, interactions, ownership, and reasoning

If implementation detail is required, record it as: "Deferred to Stage 4 Technical Specification."
