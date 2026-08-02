# Architecture Workflow Steps

> Execute sequentially. Each step has clear inputs and outputs.

---

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

---

## Step Groups

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
