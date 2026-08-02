# Recommended Traceability Rules

## Every artifact should have a stable identifier and explicit parent references:

| Artifact             | ID Pattern | Parent                     |
| -------------------- | ---------- | -------------------------- |
| Requirement          | REQ-001    | Business Objective         |
| Persona              | PER-001    | —                          |
| Epic                 | EP-001     | Requirement(s)             |
| Capability           | CAP-001    | Epic                       |
| Feature              | FEAT-001   | Requirement(s), Capability |
| User Story           | US-001     | Feature                    |
| User Flow            | UF-001     | Feature, User Story        |
| Screen               | SCR-001    | User Flow                  |
| Component            | CMP-001    | Screen                     |
| Design Decision      | DDL-001    | Related Requirement(s)     |
| Acceptance Criterion | AC-001     | Requirement, User Story    |


# Enforce the following invariants:

- Every REQ-* must map to at least one FEAT-*.
- Every FEAT-* must map to at least one UF-*.
- Every UF-* must reference one or more SCR-*.
- Every SCR-* must list its CMP-*.
- No feature, flow, screen, or component may exist without an upstream requirement unless explicitly marked as DERIVED with a documented rationale.
- All relationships should be bidirectional where practical (e.g., screens list parent flows, flows list referenced screens).
