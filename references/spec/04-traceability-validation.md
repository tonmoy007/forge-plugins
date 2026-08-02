# Stage 4 Traceability and Validation

## Traceability Rules

The required append-only chain is:

```
BG → REQ → EP → CAP → FEAT → US → UF → SCR → CMP → API → SRV → DB → ADR
   → SPEC → MOD → INT → DTO → CFG → ERR → TEST
```

`TEST` is a downstream placeholder only; Stage 4 defines testable acceptance
conditions but does not create test implementation. Every `SPEC` must cite its
REQ lineage and its architectural parent(s). Every module references a service,
component, API, datastore, or ADR. Every interface references a module. Every
DTO references the interface(s) that exchange it. Every configuration belongs
to a module. Every error belongs to a contract. No Stage 4 artifact may be
orphaned or introduce an untraceable parent.

## Deterministic Validation Gates

Validation is mandatory. Fail the stage if any condition is false:

- every module references approved architecture;
- every interface belongs to a module;
- every DTO/event references one or more interfaces;
- every configuration belongs to a module;
- every validation rule resolves to an error and contract;
- every error belongs to a contract;
- every state machine and sequence has upstream lineage;
- every specification reaches a valid REQ lineage;
- no orphan specifications, invented parents, broken references, or duplicate IDs;
- no source code, implementation algorithms, or unauthorized architecture;
- all required/profile artifacts exist and cross-document references resolve.

## Quality Gates

Pass only when contracts are complete, internally consistent, unambiguous,
testable, secure, performant, operable, versioned, compatible, and traceable.
Validate public/internal boundary clarity, ownership singularity, error safety,
NFR coverage, integration failure behavior, data protection, and profile
compliance. Report warnings separately; unresolved errors block advancement.

## Repair Rules

Repair only Stage 4 omissions or broken Stage 4 references. Re-run every
validation and quality gate after each repair. Escalate upstream conflicts
instead of changing upstream artifacts. Do not repair a failure by introducing
new functionality, architecture, parents, or identifiers.
