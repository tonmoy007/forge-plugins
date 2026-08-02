# Stage 1 Requirement Elicitation

*Loaded before extracting and categorizing requirements.*

## Business Goals

Before defining requirements, identify the measurable business objectives. Every Business Goal shall include: Goal ID, Name, Description, Business Value, Success Metrics, Priority, Stakeholders.

Example: `BG-001: Enable customers to purchase products online.`

Requirements exist to satisfy Business Goals. A requirement without a Business Goal is invalid.

---

## Requirement Categories

| Category | Pattern | Notes |
|----------|---------|-------|
| Functional | `REQ-F-###` | Observable behavior |
| Non-functional | `REQ-NF-###` | Measurable quality attributes |
| Business Rules | `REQ-RULE-###` | Policy, not functionality |
| Constraints | `CON-###` | Limitations on solution |
| Assumptions | `ASM-###` | Explicit beliefs |
| Dependencies | `DEP-###` | Internal/external/third-party |
| Risks | `RISK-###` | Must include mitigation |
| Open Questions | `Q-###` | Unresolved issues |

Do not mix categories.

---

## Requirement Rules

Every requirement shall: describe exactly one observable capability, have exactly one business purpose, avoid implementation details, avoid technology choices unless explicitly required, describe externally observable behavior, define measurable outcomes, be independently testable, support at least one Business Goal, avoid duplication, be implementation independent.

**Reject requirements containing vague terms** (Fast, Easy, User-friendly, Secure, Optimized, Flexible, Modern, Efficient, Scalable) unless objectively measurable.

---

## Functional Requirements

Every Functional Requirement shall contain: Requirement ID, Name, Description, Business Goal References, Priority, Business Value, Dependencies, Assumptions, Preconditions, Postconditions, Acceptance Conditions, Risks, Notes (optional).

**Example:**
```
REQ-F-014: Users shall be able to reset their password using a verified email address.
Supports: BG-002 | Priority: High | Dependencies: DEP-003
Acceptance Conditions:
• Reset email sent • Token expires after configured duration • Invalid token rejected
```

---

## Clarification Strategy

### REQ-INTERACTIVE-CLARIFY-001

When project information is incomplete, conduct exactly ONE clarification round. Prioritize questions about:

1. Business goals · 2. Scope · 3. Users · 4. Constraints · 5. External integrations · 6. Compliance · 7. Success metrics

Never conduct multiple clarification rounds. If unanswered, continue using documented assumptions. Never block SRS generation.
