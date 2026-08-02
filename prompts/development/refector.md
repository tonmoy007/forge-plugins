You are refactoring an existing Forge SDLC agent specification.

DO NOT rewrite it from scratch.

Instead, preserve its existing philosophy, style, frontmatter, and compatibility while upgrading it into an enterprise-grade architecture agent suitable for large-scale software engineering organizations.

==========================
OBJECTIVE
==========================

Upgrade `agents/system-architect.md` to become the authoritative Stage 3 Architecture Agent in the Forge pipeline.

The resulting agent must produce deterministic architecture artifacts that become the canonical input for Stage 4 (Technical Specification).

Stage 3 defines WHAT the system architecture is.

Stage 4 defines HOW it is implemented.

Never blur these responsibilities.

==========================
PIPELINE CONTEXT
==========================

Stage 1
Requirements (SRS)

↓

Stage 2
Product Design
(PRD, Personas, User Flows, Screens, Design System)

↓

Stage 3
Architecture   ← THIS AGENT

↓

Stage 4
Technical Specification

↓

Stage 5+
Implementation

Architecture must stop before implementation details.

Do NOT generate

- source code
- package hierarchy
- folder structure
- classes
- interfaces
- DTOs
- repositories
- migrations
- CI/CD
- file names
- implementation sequence
- OpenAPI YAML
- ORM definitions

Those belong to Stage 4.

==========================
PRIMARY RESPONSIBILITIES
==========================

Expand the agent so it owns:

• Enterprise Architecture
• Solution Architecture
• Logical Architecture
• Technology Strategy
• System Boundaries
• Domain Modeling
• API Architecture
• Event Architecture
• Security Architecture
• Deployment Architecture
• Observability Architecture
• Architecture Governance
• Architecture Validation
• Architecture Traceability
• Architecture Decision Records

==========================
ARCHITECTURE PRINCIPLES
==========================

The upgraded agent should explicitly follow principles inspired by

- ISO/IEC/IEEE 42010
- ISO/IEC/IEEE 29148
- C4 Model
- Arc42
- TOGAF
- OWASP ASVS
- OWASP Top 10
- Twelve-Factor App
- Cloud Native principles

Do NOT quote standards.

Apply their concepts.

==========================
TRACEABILITY
==========================

Architecture must continue the Forge traceability chain.

The agent must never start a new chain.

Use

REQ

↓

EP

↓

CAP

↓

FEAT

↓

US

↓

UF

↓

SCR

↓

CMP

↓

API

↓

SRV

↓

DB

↓

DEP

↓

ADR

Every architectural artifact must reference upstream artifacts.

Generate a complete Architecture Traceability Matrix.

Fail validation if any mapping is missing.

==========================
ARTIFACT IDS
==========================

Introduce deterministic IDs.

Examples

SYS-001

CNT-001

SRV-001

API-001

DB-001

MSG-001

DEP-001

SEC-001

INT-001

ADR-001

QA-001

NFR-001

Never allow duplicate IDs.

==========================
OUTPUT CONTRACT
==========================

Expand the output contract significantly.

Instead of only

architecture.md

generate modular architecture artifacts.

Recommended artifacts

architecture.md

context.md

containers.md

components.md

deployment.md

domain-model.md

data-model.md

api-catalog.md

integration-catalog.md

security-architecture.md

quality-attributes.md

technology-selection.md

observability.md

architecture-principles.md

architecture-risks.md

traceability.md

adr/

Each artifact must have a clearly defined responsibility.

==========================
C4 MODEL
==========================

Expand C4 support.

Include

Level 1

System Context

Level 2

Containers

Level 3

Components

Do NOT generate Level 4.

==========================
API CATALOG
==========================

Expand API documentation.

Each API should define

API ID

Purpose

Method

URI

Authentication

Consumer

Provider

Request Summary

Response Summary

Error Model

Rate Limits

Version

Dependencies

Referenced Requirements

Referenced Features

==========================
SERVICE SPECIFICATIONS
==========================

Each service should include

Service ID

Purpose

Responsibilities

Inputs

Outputs

Dependencies

Scaling Strategy

Failure Modes

Health Checks

Observability

Security Considerations

Owned APIs

Owned Data Stores

Referenced Requirements

==========================
DATA MODEL
==========================

Separate

Logical Domain Model

Physical Data Model

Define

Entities

Relationships

Cardinality

Aggregates

Value Objects

Constraints

Retention

Lifecycle

==========================
EVENT ARCHITECTURE
==========================

Support event-driven systems.

Each event should define

Message ID

Publisher

Subscriber

Schema Summary

Delivery Guarantee

Retry Policy

Dead Letter Queue

Ordering

Retention

==========================
SECURITY
==========================

Expand the Security Architecture.

Include

Authentication

Authorization

RBAC

Secrets

Encryption

Threat Model

Trust Boundaries

Data Classification

Rate Limiting

Audit Logging

Key Rotation

Session Management

Compliance Considerations

OWASP mitigations

==========================
DEPLOYMENT
==========================

Document

Development

Testing

Staging

Production

Disaster Recovery

Infrastructure Topology

Networking

Ingress

Load Balancing

Storage

Scaling

==========================
OBSERVABILITY
==========================

Document

Logging

Metrics

Tracing

Alerting

Dashboards

SLIs

SLOs

Error Budgets

==========================
QUALITY ATTRIBUTES
==========================

Generate measurable quality attribute scenarios.

Availability

Performance

Latency

Scalability

Reliability

Maintainability

Extensibility

Security

Resilience

Portability

Interoperability

==========================
ADR
==========================

Upgrade ADR requirements.

Each ADR should include

Status

Context

Decision

Alternatives

Tradeoffs

Consequences

Risks

Related Requirements

Related APIs

Related Services

Related Datastores

==========================
VALIDATION
==========================

Introduce deterministic validation.

The stage must fail if

A requirement has no service.

A feature has no API.

A screen has no supporting service.

A service owns no API.

An API owns no service.

A service owns no deployment.

Security architecture is incomplete.

No ADR exists.

Duplicate IDs exist.

Circular service dependencies exist.

Missing traceability exists.

==========================
WORKFLOW
==========================

Expand the workflow.

Recommended flow

1 Read SRS

2 Read Product Artifacts

3 Build Requirement Inventory

4 Extract NFRs

5 Identify Actors

6 Identify External Systems

7 Build System Context

8 Build Containers

9 Build Components

10 Build Domain Model

11 Build Data Model

12 Build API Catalog

13 Build Integration Catalog

14 Build Event Architecture

15 Build Security Architecture

16 Build Deployment Architecture

17 Build Observability

18 Build Quality Attributes

19 Generate ADRs

20 Generate Traceability Matrix

21 Run Validation

22 Repair Validation Failures

23 Write Artifacts

==========================
COMPLETION
==========================

Replace the existing completion message with a validation summary.

Report

Requirements Mapped

Features Covered

Services

APIs

Containers

Components

Domain Entities

Data Stores

External Integrations

ADRs

Architecture Risks

Validation Result

PASS or FAIL

==========================
IMPORTANT
==========================

Preserve

- existing YAML frontmatter
- Forge conventions
- Markdown style
- existing role definition where still applicable
- compatibility with forge-arch skill
- Stage 3 responsibilities

Do not modify Stage 4 responsibilities.

Produce a polished enterprise-grade `agents/system-architect.md` suitable for deterministic SDLC orchestration.
