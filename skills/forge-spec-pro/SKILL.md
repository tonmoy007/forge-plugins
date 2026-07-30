---
name: forge-spec-pro
description: >
  Run Stage 4 of the Forge SDLC pipeline — Technical Specification. Converts
  approved Stage 1–3 artifacts into deterministic, traceable implementation-
  ready technical contracts by invoking the Spec Writer Pro persona.
allowed-tools:
  - Read
  - Write
  - WebSearch
  - WebFetch
  - Grep
---

# /forge:spec-pro

## Aliases

- `/forge:spec-pro`
- `/forge:technical-spec`

---

## Purpose

Stage 4 turns the approved enterprise architecture into implementation-ready
technical contracts. It defines **how approved architectural components
behave**; it does not redefine business requirements, product design, or
architecture, and it does not write implementation code.

The output is the canonical input to Stage 5 (Implementation Planning).

---

## Stage Ownership

- **Stage:** 04 — Technical Specification
- **Consumes:** Stage 1 Requirements, Stage 2 Product Design, Stage 3
  Enterprise Architecture
- **Produces:** `pipeline/04-spec/` technical contract artifacts

The stage owns module/interface/service/repository/adapter/integration
contracts, public and internal contracts, DTOs/events, configuration,
validation, errors, state machines, sequence specifications, data/file
contracts, versioning/compatibility, performance/security/operational
contracts, technical decision records where needed, and specification
traceability.

---

## Pre-flight Check

### 1. Entry Gate (REQ-GATE-ENTRY-001)

Before reading the persona or generating artifacts, execute:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py preflight --stage 4
```

If the command exits non-zero: STOP. Display its returned message verbatim.
Do not continue. The user must complete prior stages or deliberately use
`/forge:force-advance`.

### 2. Forge Project Verification

Read `pipeline/state.md`. Verify that Forge is initialized, state exists, the
current stage is valid, and a project profile is available. If verification
fails: STOP and report the failed condition.

### 3. Previous Stage Verification

Verify the canonical Stage 1–3 handoff exists:

```
pipeline/01-srs/srs.md
pipeline/02-product-ux/prd.md
pipeline/02-product-ux/user-stories.md
pipeline/02-product-ux/user-flows.md
pipeline/02-product-ux/screen-specifications.md
pipeline/02-product-ux/components.md
pipeline/02-product-ux/traceability.md
pipeline/03-architecture/architecture.md
pipeline/03-architecture/components.md
pipeline/03-architecture/domain-model.md
pipeline/03-architecture/data-model.md
pipeline/03-architecture/api-catalog.md
pipeline/03-architecture/integration-catalog.md
pipeline/03-architecture/security-architecture.md
pipeline/03-architecture/quality-attributes.md
pipeline/03-architecture/observability.md
pipeline/03-architecture/traceability.md
pipeline/03-architecture/adr/
```

If any required artifact is missing: STOP. List all missing artifacts. Do not infer or regenerate upstream architecture.

### 4. Stage Progress Check

If `current_stage > 4`, inform the user that Stage 4 appears complete and ask
whether to Review, Validate, Revise, or Regenerate. Never overwrite existing
Stage 4 artifacts without explicit confirmation.

### 5. Load Project Profile

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 4
```

Honor all loaded overrides exactly. At minimum support:

- `replace_with`
- `additional_artifacts`
- `additional_steps`
- `additional_concerns`
- `skip_steps`

Also honor supported templates, validation rules, quality gates, compliance,
security, performance, integration, and technology constraints. `skip_steps`
may skip only a default Stage 4 activity when the profile explicitly permits
it; it cannot bypass traceability, ownership, entry, validation, quality, or
stage-advance gates. Record every applied override in the output.

---

## Load Spec Writer Pro

Read `agents/spec-writer-pro.md` and adopt the persona completely. The persona
is the source of truth for Stage 4 business rules, artifact semantics,
identifier rules, validation, quality gates, and failure behavior. This skill
orchestrates; it does not duplicate or reinterpret persona logic.

---

## Load Context

Read, in order:

1. `pipeline/state.md`
2. Stage 1 SRS and requirements traceability
3. canonical Stage 2 product artifacts and traceability
4. canonical Stage 3 architecture artifacts, traceability, and ADRs
5. existing `pipeline/04-spec/` artifacts only for a confirmed revision

Use `read-doc.py` where the repository’s large-document layout applies, so
single-file and split-document layouts resolve consistently. Never use source
code, Stage 5 planning, or Stage 6 implementation as the authority for a new
technical contract.

---

## Specification Readiness Assessment

Before persona execution, create a read-only Specification Input Inventory:

- business goals, functional/non-functional requirements, rules, constraints
- epics, capabilities, features, stories, flows, screens, components
- APIs, services, components, datastores, integrations, events, deployment
- ADRs, technology decisions, security, quality, performance, operations
- upstream traceability identifiers and project-profile obligations

Verify: required inputs are complete; IDs resolve; Stage 3 traceability is
available; architectural ownership is explicit; profile is loaded; no known
upstream validation failure makes contract definition impossible.

If any check fails, STOP with a readiness report. Do not ask the persona to
invent missing artifacts.

---

## Execution Workflow

Execute sequentially. Each step completes before the next unless an active
profile explicitly supplies a replacement, addition, or permitted skip.

| Step | Orchestrate | Expected result |
|---|---|---|
| 1 | Establish `SPEC` scope from approved architecture | every scope has upstream lineage |
| 2 | Specify modules | `MOD` ownership and behavior contracts |
| 3 | Specify public/internal interfaces | `INT` and `CONTRACT` boundaries |
| 4 | Specify DTOs and events | `DTO` schemas and exchange semantics |
| 5 | Specify configuration | `CFG` ownership, validation, and operations |
| 6 | Specify validations and error catalog | `VAL` and `ERR` behavior |
| 7 | Specify state machines and sequences | `FSM` and `SEQ` behavior |
| 8 | Specify service/repository/adapter/integration/data contracts | boundary and failure semantics |
| 9 | Specify performance, security, operations | `PERF` and `SEC` cross-cutting contracts |
| 10 | Specify versioning and compatibility | `COMP` and deprecation/migration rules |
| 11 | Produce traceability and profile artifacts | complete append-only lineage |
| 12 | Validate, repair, verify, and report | PASS only before advancement |

For each profile `additional_step`, insert it at the stated position (or after
the default workflow if no position is given). For each `additional_concern`,
ensure a named artifact section and traceability coverage. For `replace_with`,
use the replacement while preserving all non-replaced required behavior.

The persona determines the document contents and writes the output contract.
Do not add implementation code, source file structure, or unapproved
architecture during orchestration.

---

## Artifact Verification

After persona execution, verify the Stage 4 entry point and all persona-required
artifacts exist, including profile additions and non-skipped defaults. At
minimum verify:

```
pipeline/04-spec/technical-spec.md
pipeline/04-spec/module-specifications.md
pipeline/04-spec/interface-specifications.md
pipeline/04-spec/dto-event-definitions.md
pipeline/04-spec/configuration-specifications.md
pipeline/04-spec/validation-rules.md
pipeline/04-spec/error-catalog.md
pipeline/04-spec/state-machines.md
pipeline/04-spec/sequence-specifications.md
pipeline/04-spec/integration-contracts.md
pipeline/04-spec/data-contracts.md
pipeline/04-spec/versioning-compatibility.md
pipeline/04-spec/performance-contracts.md
pipeline/04-spec/security-contracts.md
pipeline/04-spec/operational-contracts.md
pipeline/04-spec/traceability.md
```

When the large-document layout is used, verify the canonical entry point and
its manifest-resolved documents rather than assuming a flat layout. Verify
`tdr/` only when a technical decision record is required.

---

## Traceability and Ownership Verification

Verify the append-only chain without inventing parents:

```
BG → REQ → EP → CAP → FEAT → US → UF → SCR → CMP → API → SRV → DB → ADR
   → SPEC → MOD → INT → DTO → CFG → ERR → TEST
```

Confirm every Stage 4 artifact has valid REQ lineage and approved Stage 3
ownership. Confirm every module references architecture, every interface is
owned by a module, every DTO/event belongs to interfaces, every configuration
belongs to a module, every error belongs to a contract, and no `SPEC`, `MOD`,
`INT`, `DTO`, `CFG`, `ERR`, `FSM`, `SEQ`, `PERF`, `SEC`, or `COMP` is orphaned.

Reject duplicate IDs, unresolved references, cycles that violate architecture,
invented artifacts, redefined Stage 1–3 artifacts, and implementation code.

---

## Validation and Repair Loop

Run every deterministic validation and quality gate defined by
`agents/spec-writer-pro.md`, plus profile-supplied validation rules. Validate
contract completeness, schema/DTO integrity, error safety, state/sequence
consistency, integration failure semantics, security, performance,
compatibility, operations, cross-document consistency, identifier integrity,
traceability, ownership, and profile compliance.

If validation fails, repair only missing or inconsistent Stage 4 artifacts and
references. Re-run the complete validation set after every repair. Never repair
by changing or silently redefining Stage 1–3 artifacts. If an upstream conflict
or unrecoverable failure remains: STOP; report evidence, affected IDs,
recommended remediation, and blocked downstream stages.

---

## Stage Advancement

Advance only when all required artifacts exist, traceability and ownership
verification pass, all quality gates pass, and no unresolved error remains.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 4
```

If the command fails: STOP and display the returned error. Do not claim success.

---

## Completion Report

Present the persona’s structured completion report with counts for requirements
mapped, specifications, modules, interfaces, public/internal contracts,
DTOs/events, configurations, validations, errors, state machines, sequences,
integrations, data, performance, security, compatibility, operational
contracts, technical decision records, warnings, errors, and PASS/FAIL result.

Also confirm `pipeline/state.md` now reports `current_stage: 4`.

---

## Next Stage

Only after successful advancement, derive the next-step guidance from the
canonical stage table:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 4
```

Present the helper output verbatim.

---

## Behavioral Rules

Always run preflight first, load the profile, read `agents/spec-writer-pro.md`,
preserve upstream ownership, execute the persona, verify artifacts,
traceability, and ownership, advance only after PASS, and present the canonical
next hint.

Never duplicate persona business logic in this skill; redefine upstream
artifacts; invent functionality or parent IDs; bypass a required gate; advance
on validation failure; write implementation code; or claim completion before
state advancement succeeds.
