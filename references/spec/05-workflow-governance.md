# Stage 4 Workflow and Governance

## Workflow

1. Verify Stage 4 entry and load the project profile.
2. Read all required Stage 1–3 context and build a read-only upstream inventory.
3. Reconcile Stage 3 APIs, services, data stores, integrations, ADRs, quality,
   security, and operational requirements with complete REQ lineage.
4. Apply profile `replace_with`, `skip_steps`, `additional_steps`,
   `additional_artifacts`, and `additional_concerns` exactly. Record each
   applied override in the technical-spec entry point.
5. Create `SPEC` records and deterministic module boundaries from approved
   architecture; do not alter those boundaries.
6. Specify contracts, DTOs/events, configuration, validation/errors, state
   machines, sequences, integrations, data, and cross-cutting contracts.
7. Produce append-only traceability and run validation gates.
8. Repair only Stage 4 omissions or broken Stage 4 references; escalate
   upstream conflicts instead of changing upstream artifacts.
9. Write all required artifacts, verify them, and report completion.

## Profile Overrides

Honor `replace_with`, `additional_artifacts`, `additional_steps`,
`additional_concerns`, and `skip_steps` exactly. A replacement may replace only
the named default work. Additional artifacts and steps are mandatory once
loaded. A skipped step must be explicitly permitted by the profile and may not
skip entry, ownership, traceability, validation, quality, or stage-advance
gates. Record every applied override in the technical-spec entry point.

## Revision Behaviour

On revision, preserve IDs and prior traceability. Change only affected Stage 4
artifacts, add compatibility/deprecation rules where public behavior changes,
and revalidate the full Stage 4 set. Never delete history, silently renumber,
or overwrite a complete specification without explicit regeneration approval.

## Web Research Policy

Web research is optional and limited to three targeted searches. Use it only
when current authoritative guidance materially affects a technical contract
(for example a protocol, security standard, or vendor integration). Prefer
primary sources. Record title, URL, date accessed, affected contract IDs, and
the resulting decision. Research never overrides approved Stage 1–3 artifacts.

## Behavioral Rules

Always preserve ownership, deterministic ordering, traceability, and explicit
contracts. Prefer a documented blocking question to a guessed behavior. Never
invent functionality, redefine upstream artifacts, write code, conceal risks,
omit failure behavior, downgrade security requirements, or advance on a failed
gate.

## Verification and Failure Behaviour

Verify artifact existence, identifier uniqueness, all references, lineage,
profile obligations, and validation/quality gate results before completion. If
repair is possible, perform a deterministic Stage 4-only repair and rerun all
gates. If an upstream inconsistency, missing input, or unrecoverable validation
failure remains, stop without advancing; report affected IDs, evidence,
remediation, and blocked downstream stages.

## Completion Report and Message

Report counts for requirements mapped, specifications, modules, interfaces,
public/internal contracts, DTOs/events, configurations, validation rules,
errors, state machines, sequences, integrations, data contracts, performance,
security, compatibility, operational contracts, TDRs, warnings, errors, and
validation status.

Conclude only after PASS:

```
Stage 4 — Technical Specification completed successfully.

Technical specification artifacts generated: <N>
Requirements mapped: <X>/<Y>
Modules: <N> | Interfaces: <N> | DTOs/Events: <N>
Configurations: <N> | Errors: <N> | State Machines: <N> | Sequences: <N>
Integrations: <N> | Security Contracts: <N> | Performance Contracts: <N>
Specification Validation: PASS
Project State: Stage 4 Active

The project is ready for Stage 5 (Implementation Planning).
```
