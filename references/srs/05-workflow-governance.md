# Stage 1 Workflow and Governance

*Loaded at execution start and again for profiles, revisions, research, failures, and completion.*

## Workflow

Execute sequentially:

1. Read project description
2. Analyze business problem
3. Identify Business Goals
4. Identify stakeholders
5. Define project scope
6. Conduct one clarification round if required
7. Record assumptions
8. Extract Functional Requirements
9. Extract Non-functional Requirements
10. Identify Business Rules
11. Identify Constraints
12. Identify Dependencies
13. Identify Risks
14. Prioritize requirements
15. Define measurable acceptance conditions
16. Generate requirements traceability matrix
17. Validate requirements
18. Repair validation failures where possible
19. Generate artifacts
20. Prepare completion report

Never skip validation. Never generate artifacts before successful validation.

---

## Stage Advancement

Advance Stage 1 only after every validation gate passes.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 1
```

If advancement fails, display the returned message and stop.

---

## Completion Report

Generate a structured summary:

```
Requirements Summary
Business Goals: 5 | Functional Requirements: 38 | Non-functional Requirements: 14
Business Rules: 11 | Constraints: 8 | Assumptions: 6
Dependencies: 9 | Risks: 7 | Open Questions: 3 | Stakeholders: 4
Validation Warnings: 0 | Validation Errors: 0 | Requirements Validation: PASS
```

The summary shall reflect the generated artifacts.

---

## Revision Behavior

When revisiting Stage 1, perform incremental refinement.

**Rules:** Preserve Business Goal IDs. Preserve Requirement IDs. Preserve Requirement ordering where possible. Update only affected sections. Revalidate the entire SRS. Preserve downstream stability.

Never renumber existing identifiers unless explicitly requested.

---

## Failure Behavior

If unrecoverable validation failures remain, STOP. Report validation failures, affected sections, recommended remediation, and blocked downstream stages.

Never advance the project state when validation fails.

---

## Next Stage Readiness

Before leaving Stage 1, verify that Stage 2 has every required input.

**Required handoff artifacts:** ✓ srs.md, ✓ requirements-traceability.md

**Optional supporting artifacts:** stakeholder-map.md, glossary.md, domain-model.md

If required artifacts are missing, report them and block progression.

---

## Next Step

Derive the next-stage guidance from the canonical stage registry. Never hardcode stage transitions.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 1
```

Present the helper output verbatim.

---

## Success Criteria

Stage 1 is complete only when:

- Business Goals are defined
- Project scope is complete
- Stakeholders are identified
- Functional Requirements are complete
- Non-functional Requirements are measurable
- Business Rules, Constraints, Assumptions documented
- Dependencies identified
- Risks include mitigation
- Requirements traceability complete
- Every quality gate passes
- Validation result is PASS
- Project state advances successfully

---

## Behavioral Rules

**Always:** think from the business perspective first, resolve ambiguity before specification, prefer explicit documentation over assumptions, document uncertainty rather than hiding it, preserve deterministic identifiers, maintain implementation independence.

**Never:** design user interfaces, define APIs, define databases, choose technologies, recommend architectures, write source code, speculate beyond available evidence.

If business information is missing, document assumptions instead of inventing facts.

---

## Web Research

### REQ-WEBSEARCH-001

Use `WebSearch` only when authoritative external guidance materially improves the SRS (ISO standards, OWASP ASVS, WCAG, GDPR, HIPAA, PCI DSS, government regulations, industry compliance requirements).

**Rules:** Maximum three searches. Prefer primary sources. Cite every external source used. Never replace user requirements with web research. Never silently browse.

---

## Final Confirmation

Conclude with a concise completion summary:

```
Stage 1 — Requirements Engineering completed successfully.
Business Goals: 5 | Functional Requirements: 38 | Non-functional Requirements: 14
Business Rules: 11 | Constraints: 8 | Dependencies: 9 | Risks: 7
Requirements Traceability: Validated | Requirements Validation: PASS
Project State: Stage 1 Active
The project is now ready for Stage 2 (Product Design & UX).
```

The completion report must always be derived from the generated artifacts. Never report success if validation has failed.
