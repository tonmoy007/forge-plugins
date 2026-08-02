# Architecture Artifact Specifications

> Loaded during artifact generation (Workflow Steps 4–14).
> Each section defines the required content for one deliverable.

---

## architecture.md

Executive architecture overview. Shall include:

- System Overview
- Architecture Summary
- Architectural Style
- Major Architectural Decisions
- Technology Overview
- High-Level Component Overview
- Deployment Summary
- Security Summary
- Quality Attribute Summary
- Architecture Constraints
- Assumptions, Known Risks

Reference supporting artifacts instead of duplicating them.

---

## context.md

C4 Level 1 System Context. Document:

- System Identifier, Name, Purpose
- Primary Users, External Actors, External Systems
- Trust Boundaries, System Boundary
- External Dependencies
- Context Diagram Description

Context Relationships — every relationship shall identify: Direction, Protocol, Purpose, Authentication, Data Classification.

---

## containers.md

C4 Level 2 Container Model. For every container define:

- Container ID, Purpose, Responsibilities
- Technology Class
- Inbound/Outbound Interfaces
- Dependencies
- Scaling Strategy, Availability Requirements
- Security Notes
- Deployment Target
- Owned Services, Owned APIs
- Referenced Requirements, Referenced Features

---

## components.md

C4 Level 3 Component Model. Each component shall include:

- Component ID, Purpose, Responsibilities
- Inputs, Outputs, Dependencies
- Owned APIs, Consumed APIs, Owned Datastore
- Failure Modes, Recovery Strategy
- Health Checks, Metrics, Logging Expectations
- Security Considerations
- Referenced Services, Requirements, Features

---

## domain-model.md

Logical domain model. Document:

- Domains, Bounded Contexts
- Entities, Aggregates, Value Objects
- Domain Services, Domain Events
- Business Rules, Ownership
- Relationships, Constraints, Cardinality

Do not include ORM implementation. Do not include persistence implementation. Remain implementation independent.

---

## data-model.md

Logical and physical data architecture. For every datastore define:

- Database ID, Purpose, Ownership
- Storage Type, Consistency Model
- Retention Policy, Encryption
- Backup/Restore/Replication Strategy
- Partition Strategy, Data Lifecycle
- Key Entities, Relationships
- Indexes, Constraints, Expected Growth

Never generate migration scripts. Never generate SQL.

---

## api-catalog.md

Complete API surface. Each API shall include:

- API ID, Purpose, Method, URI
- Authentication, Authorization
- Consumer, Provider
- Request/Response Summary
- Error Model, Versioning Strategy
- Rate Limits, Idempotency, Dependencies
- Referenced Requirements, Features, Screens, Services

Do not generate implementation code. Do not generate OpenAPI YAML.

---

## integration-catalog.md

Every external integration. Each includes:

- Integration ID, System Name, Purpose
- Direction, Protocol
- Authentication, Authorization
- Data Exchanged
- Retry/Timeout Strategy, Circuit Breaker, Fallback Behaviour
- Rate Limits, Monitoring, Failure Handling
- Dependencies, Security Notes
- Referenced Requirements

---

## event-architecture.md

Required for event-driven systems. Each event shall define:

- Message ID, Purpose
- Publisher, Subscriber
- Delivery Model, Ordering
- Schema Summary
- Retry Policy, Dead Letter Queue, Retention
- Replay Support, Monitoring
- Dependencies, Referenced Services, Requirements

If no messaging exists, explicitly document why.

---

## security-architecture.md

Complete security architecture. Include:

- Authentication, Authorization (RBAC, ABAC)
- Identity Provider, Session Strategy
- Secrets Management, Encryption, Key Rotation
- Data Classification, Threat Model
- Trust Boundaries, Network Segmentation
- Rate Limiting, Input Validation, Output Encoding
- Audit Logging, Secure Configuration
- Compliance Considerations
- Incident Response Considerations
- OWASP Mitigations

Never assume security. Document every control.

---

## deployment.md

Deployment architecture. Include:

- Development, Testing, Staging, Production
- Disaster Recovery
- Regions, Availability Zones
- Infrastructure Topology
- Networking, Ingress, Load Balancing
- Caching, Queues, Object Storage, Databases
- Monitoring, Secrets, Configuration Management
- Horizontal/Vertical Scaling
- Disaster Recovery Strategy, Recovery Objectives

Do not generate infrastructure code.

---

## observability.md

Operational visibility. Include:

- Logging Strategy, Structured Logging
- Metrics, Tracing, Correlation IDs
- Dashboards, Alerting
- Health/Readiness/Liveness Checks
- SLIs, SLOs, Error Budgets
- Capacity/Cost Monitoring
- Operational Ownership

---

## technology-selection.md

Technology decisions. Each decision shall include:

- Technology, Purpose
- Alternatives Considered
- Reasons for Selection
- Trade-offs, Risks, Known Limitations
- Future Migration Considerations
- Referenced ADR

Never choose technology without rationale.

---

## quality-attributes.md

Measurable quality attributes. For each include:

- Identifier, Target
- Architecture Strategy, Validation Strategy
- Related Requirements, Related Services

Minimum attributes: Availability, Performance, Latency, Scalability, Reliability, Maintainability, Extensibility, Security, Observability, Portability, Interoperability, Cost Efficiency.

---

## architecture-principles.md

Architectural principles governing the solution. Examples:

- Single Responsibility, Loose Coupling, High Cohesion
- Stateless Services, Defense in Depth, Secure by Default
- Least Privilege, Explicit Dependencies
- Backward Compatibility, API First
- Eventual Consistency, Idempotency, Resilience First

Every principle shall include: Description, Motivation, Implications, Exceptions.

---

## architecture-risks.md

Architecture risk register. Each risk includes:

- Risk ID, Description
- Likelihood, Impact
- Mitigation, Contingency, Owner
- Affected Components
- Related ADR, Related Requirements

---

## ADR Requirements

Create one Architecture Decision Record for every significant architectural decision. At minimum:

- Technology Stack
- Authentication Strategy
- Deployment Model
- Data Storage, Messaging, Caching
- Observability, API Strategy
- Security Strategy, Scalability Strategy

Additional ADRs should be generated whenever architectural trade-offs exist.

---

## ADR Format

Every ADR shall include:

- ADR ID, Status, Date
- Context, Problem Statement
- Decision, Alternatives Considered
- Decision Drivers, Trade-offs
- Positive/Negative Consequences
- Known Risks
- Future Reconsideration Criteria
- Referenced Requirements, Features, Services, APIs, Datastores, Deployments

No architectural decision shall exist without an ADR.

---

## Profile Extensions

After the default artifact set, apply profile-specific behavior. Only
generate profile artifacts when required by the active project profile.
Examples:

- **ML Systems:** Model Registry, Feature Store, Inference Architecture, GPU
  Topology
- **API Platforms:** API Versioning, Pagination Strategy, Idempotency, Rate
  Limiting
- **CLI Applications:** Command Tree, Plugin Architecture
- **IoT Systems:** Device Topology, Edge Components

Every profile artifact follows the same identifier, traceability, and
validation rules as the default deliverable set.
