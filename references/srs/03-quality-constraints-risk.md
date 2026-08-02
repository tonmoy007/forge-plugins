# Stage 1 Quality Attributes, Constraints, and Risk

*Loaded before extracting non-functional requirements, business rules, constraints, assumptions, dependencies, and risks.*

## Non-functional Requirements

Every NFR shall be measurable. Categories: Performance, Reliability, Availability, Scalability, Security, Privacy, Accessibility, Localization, Compliance, Maintainability, Observability, Disaster Recovery.

✓ Good: `P95 response time < 250 ms` · `Availability ≥ 99.95%` · `Support 25,000 concurrent users`
✗ Bad: `System should be fast.`

---

## Business Rules

Business Rules define policy rather than functionality. Each shall include: Rule ID, Description, Business Justification, Related Requirements, Exceptions.

---

## Constraints

Document all constraints: Regulatory, Legal, Budget, Schedule, Operational, Infrastructure, Organizational.

Constraints restrict solutions. They are not requirements.

---

## Assumptions

Document every assumption explicitly. Never hide assumptions inside requirements. Every assumption shall contain: Assumption ID, Description, Reason, Impact if false.

---

## Dependencies

Document: Internal, External, Third-party, Infrastructure, Operational, Data.

Every dependency shall include: Dependency ID, Type, Owner, Impact, Failure consequences.

---

## Risks

Every identified risk shall contain: Risk ID, Description, Likelihood, Impact, Mitigation, Contingency.

Never list risks without mitigation.

---

## Requirement Prioritization

Prioritize requirements using one of: MoSCoW, Business Criticality, Kano, Product Profile Override.

Document the chosen approach. Every requirement must receive a priority.

---

## Success Criteria

Business Goals require measurable success metrics. Examples: Increase conversion by 20%, Reduce processing time below 5 minutes, Achieve 99.9% uptime, Reduce manual work by 40%.

Avoid subjective success statements.
