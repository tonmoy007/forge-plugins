---
name: forge-srs-pro
description: >
  Run Stage 1 of the Forge pipeline — Requirements Engineering (Pro tier).
  Use when the user invokes /forge:srs-pro, wants the enterprise-grade
  requirements workflow, create or refine an SRS, or begin a new Forge
  project with the Pro persona set. Orchestrates the Requirements Analyst
  Pro persona.

allowed-tools:
  - Read
  - Write
  - WebSearch
  - WebFetch
  - Grep
---

# /forge:srs-pro — Requirements Engineering (Pro)

## Aliases

- `/forge:srs-pro`
- `/forge:requirements-pro` (informal alias some users may type)

## Purpose

This skill orchestrates **Stage 1** of the Forge SDLC pipeline.

It is responsible only for: Pipeline validation, Stage gating, Project profile loading, Persona loading, Persona execution, Artifact verification, Pipeline state progression, Next-stage guidance.

This skill **does not perform requirements analysis itself**. All business analysis, requirement elicitation, clarification, validation, traceability, prioritization, and SRS generation are owned exclusively by `agents/requirements-analyst-pro.md`.

---

## When to Use

Invoke this skill when:

- The user enters `/forge:srs-pro`
- The user wants to define software requirements, refine an SRS, or describe what should be built
- The user is starting a new Forge project
- The current project is at Stage 0 or Stage 1

---

## Stage Responsibilities

| Component | Owns |
|-----------|------|
| This skill | Orchestration |
| Requirements Analyst | Business knowledge |
| Verifier | Artifact validation |
| State Manager | Pipeline progression |

Do not duplicate responsibilities across these components.

---

# Pre-flight Check

## Entry Gate

Before loading the persona, verify that Stage 1 may execute:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py preflight --stage 1
```

If the command exits non-zero, display the returned message verbatim, stop execution, and do not adopt the persona.

---

## Existing Stage Handling

If the current project is already beyond Stage 1, inform the user that Stage 1 has already been completed. Ask whether they want to revise, regenerate, or leave unchanged.

Never overwrite existing Stage 1 artifacts without confirmation.

If the project is already in Stage 1, continue in refinement mode.

---

## Load Project Profile

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 1
```

Load any project-type overrides (additional requirement categories, validation rules, artifacts, skipped sections, domain-specific concerns, compliance requirements).

These overrides extend the Requirements Analyst. They never replace it.

---

# Execute Stage

## Load Persona

Read `agents/requirements-analyst-pro.md`. Adopt the Requirements Analyst persona completely.

---

## Execute Persona

Execute the persona exactly as written. The persona is the authoritative definition of clarification, business analysis, requirement extraction, validation, prioritization, traceability, artifact generation, and web research.

Apply any project profile overrides loaded during pre-flight.

If an existing SRS exists, perform an incremental refinement unless the user explicitly requested complete regeneration.

---

# Verification

Before advancing the pipeline, verify the generated artifacts.

## Required Artifacts

Verify `pipeline/01-srs/srs.md` and `pipeline/01-srs/requirements-traceability.md` exist.

## Optional Artifacts

If generated, verify `stakeholder-map.md`, `glossary.md`, `domain-model.md`.

## Artifact Validation

Verify the generated SRS satisfies the Output Contract defined by the Requirements Analyst. At minimum verify: Business Goals, Functional Requirements, Non-functional Requirements, Business Rules, Constraints, Assumptions, Dependencies, Risks, Success Criteria, Open Questions, Requirement Priorities, Requirements Traceability Summary.

---

## Identifier Validation

Verify unique identifiers exist for: BG, REQ-F, REQ-NF, REQ-RULE, CON, ASM, DEP, RISK, Q.

Identifiers shall be unique, sequential, and deterministic.

---

## Traceability Validation

Verify every Business Goal owns one or more Requirements. Every Requirement references one or more Business Goals.

Verify `pipeline/01-srs/requirements-traceability.md` exists.

Fail verification if orphan Business Goals exist, orphan Requirements exist, duplicate mappings exist, or invalid mappings exist.

---

## Stage Ownership Validation

Verify Stage 1 contains only business artifacts.

**Stage 1 SHALL NOT generate:** user stories, epics, capabilities, features, user flows, screens, components, APIs, database schemas, architectures, technical specifications, source code.

If implementation artifacts are detected, fail verification.

---

## Validation Result

If verification fails: report the failures, identify affected artifacts, do not advance the pipeline, request additional user input only if required.

---

# Advance Pipeline State

Advance only after successful verification:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 1
```

If advancement fails, display the returned message verbatim and stop execution.

---

# Final Validation

Verify `pipeline/01-srs/srs.md` exists. Verify `pipeline/01-srs/requirements-traceability.md` exists. Verify `pipeline/state.md` shows `current_stage: 1`.

---

# Completion Report

Provide a concise completion report including: Business Goals, Functional Requirements, Non-functional Requirements, Business Rules, Constraints, Assumptions, Dependencies, Risks, Open Questions, Validation Result, Traceability Result, Optional Artifacts Generated.

Do not summarize the SRS unless requested.

---

# Next Stage Readiness

Before leaving Stage 1, verify that Stage 2 has every required input.

**Required:** `pipeline/01-srs/srs.md`, `pipeline/01-srs/requirements-traceability.md`

**Optional:** `stakeholder-map.md`, `glossary.md`, `domain-model.md`

If required artifacts are missing, block progression.

---

# Next Step

Never hardcode stage transitions.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 1
```

Present the command output verbatim.

---

# Orchestration Rules

**This skill SHALL:** orchestrate Stage 1 only, use the Requirements Analyst as the single source of truth, honor project profile overrides, preserve existing identifiers during refinement, verify artifact ownership, verify traceability, verify required artifacts, block progression on validation failure, preserve incremental updates where possible.

**This skill SHALL NOT:** redefine business requirements, duplicate the Requirements Analyst workflow, invent requirements, bypass validation, advance the pipeline on failure, overwrite existing artifacts without confirmation, generate implementation artifacts.

The Requirements Analyst remains the authoritative definition of Requirements Engineering. This skill exists solely to orchestrate its execution.
