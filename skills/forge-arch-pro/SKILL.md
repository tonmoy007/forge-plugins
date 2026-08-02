---
name: forge-arch-pro
description: >
  Run Stage 3 of the Forge SDLC pipeline — Enterprise Architecture (Pro
  tier). Transforms approved requirements and product design artifacts
  into a deterministic, implementation-independent architecture
  specification. Produces the canonical architecture artifacts consumed by
  Stage 4 (Technical Specification). Invokes the System Architect Pro
  persona.

allowed-tools:
  - Read
  - Write
  - WebSearch
  - WebFetch
  - Grep
---

# /forge:arch-pro

## Aliases

- `/forge:arch-pro`
- `/forge:architecture-pro`

## Purpose

This skill orchestrates Stage 3 — Enterprise Architecture. It performs stage
gating, profile loading, persona/reference loading, context verification,
artifact/traceability verification, state advancement, and canonical
next-stage guidance.

This skill does not perform architecture design. `agents/system-architect-pro.md`
and its mandatory `references/architect/` documents are the sole authority for
architecture logic, artifacts, identifiers, validation, quality gates,
revisions, failures, and completion behavior.

## Stage Ownership

| Component | Owns |
|---|---|
| This skill | Stage orchestration only |
| System Architect Pro + `references/architect/` | Stage 3 architecture knowledge and rules |
| State Manager | Pipeline entry and progression |

Do not duplicate or reinterpret persona/reference logic in this skill.

## Pre-flight Check

### Entry Gate

Before adopting the System Architect persona, references, or architecture
artifacts, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py preflight --stage 3
```

If it exits non-zero, STOP. Display the returned message verbatim. Do not
continue. The user must complete the prior stage or use the repository's
approved `/forge:force-advance` flow.

### Forge Project Verification

Read `pipeline/state.md`. Verify Forge is initialized, state exists, the
current stage is valid, and a project profile is available. If any condition
fails, STOP and report it.

### Previous Stage Verification

Verify the following artifacts exist:

**Stage 1:** `pipeline/01-srs/srs.md`

**Stage 2:**
- `pipeline/02-product-ux/prd.md`
- `pipeline/02-product-ux/personas.md`
- `pipeline/02-product-ux/user-stories.md`
- `pipeline/02-product-ux/information-architecture.md`
- `pipeline/02-product-ux/navigation.md`
- `pipeline/02-product-ux/user-flows.md`
- `pipeline/02-product-ux/screen-specifications.md`
- `pipeline/02-product-ux/components.md`
- `pipeline/02-product-ux/design-system.md`
- `pipeline/02-product-ux/traceability.md`

If any required artifact is missing, STOP. Report the missing artifacts. Do
not attempt architecture generation.

### Stage Progress Check

If `current_stage > 3`, inform the user Stage 3 appears to have already been
completed. Offer Review, Validate, Revise, or Regenerate. Never overwrite
existing Stage 3 artifacts without explicit confirmation. If `current_stage ==
3`, continue only as confirmed refinement work.

### Load Project Profile

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 3
```

Load and pass its result unchanged to System Architect Pro. Supported profile
extensions include `replace_with`, `skip_steps`, `additional_steps`,
`additional_artifacts`, `artifact_templates`, `validation_rules`,
`technology_constraints`, `deployment_constraints`, `compliance_requirements`,
`security_requirements`, `quality_attributes`, `required_integrations`,
`required_patterns`, and `prohibited_patterns`. The persona's governance
reference controls how these apply. Never let a profile bypass entry,
ownership, traceability, validation, quality, or advancement gates.

## Load System Architect and References

Read `agents/system-architect-pro.md`, adopt System Architect Pro, and follow
its Reference Loading Protocol exactly. The following files are mandatory
agent instructions:

```text
references/architect/01-foundation.md
references/architect/02-artifact-specs.md
references/architect/03-identifiers-traceability.md
references/architect/04-validation-rules.md
references/architect/05-workflow-governance.md
```

Load each reference when the agent requires it and load all five before final
validation or completion. Do not omit, summarize away, substitute, or weaken a
reference instruction.

## Execute Stage

Provide System Architect Pro only the context authorized by its foundation and
workflow references: `pipeline/state.md`, `pipeline/01-srs/srs.md`, and every
Stage 2 artifact listed above. Read existing files under
`pipeline/03-architecture/` only when refining or iterating an existing
architecture. Never use implementation artifacts, source code, or later-stage
output as authority for a new architecture.

Execute the persona sequentially through its 18-step workflow, apply loaded
profile overrides exactly, and allow it to generate only the Stage 3 artifacts
governed by its references.

## Verification

Before advancement, verify that every required artifact under
`pipeline/03-architecture/` (and every profile-added artifact) exists:

```text
pipeline/03-architecture/
├── architecture.md
├── context.md
├── containers.md
├── components.md
├── deployment.md
├── domain-model.md
├── data-model.md
├── api-catalog.md
├── integration-catalog.md
├── event-architecture.md
├── security-architecture.md
├── quality-attributes.md
├── technology-selection.md
├── observability.md
├── architecture-principles.md
├── architecture-risks.md
├── traceability.md
└── adr/
```

Verify that System Architect Pro reports PASS for all applicable quality gates
defined in `references/architect/04-validation-rules.md`, including
requirement coverage, service/API ownership, security and deployment
completeness, ADR coverage, identifier integrity, dependency integrity,
implementation separation, and profile compliance. Confirm every architecture
artifact has valid upstream lineage and that no Stage 1–2 artifact was
redefined.

If verification fails, report the failures and affected artifacts. Do not
advance. Let System Architect Pro perform only the deterministic repair
permitted by its references; stop and report upstream conflicts or
unrecoverable failures.

## Advance Pipeline State

Advance only after successful verification:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 3
```

If advancement fails, display the returned message verbatim and stop. Do not
claim completion.

## Completion Report

Present the System Architect Pro report derived from generated artifacts,
then verify `pipeline/state.md` reports `current_stage: 3`. Do not summarize
the full architecture unless requested.

## Next Stage

Only after successful advancement, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 3
```

Present the helper output verbatim.

## Orchestration Rules

This skill SHALL run preflight first; verify the Forge project and previous
stage artifacts; load the profile; read System Architect Pro and its mandatory
references; preserve upstream ownership; execute the persona; verify resolved
artifacts, quality gates, dependencies, and stage ownership; advance only
after PASS; and present the canonical next hint.

This skill SHALL NOT duplicate architecture logic; redefine upstream work;
invent functionality, IDs, services, or architectural decisions; introduce
implementation details owned by Stage 4; bypass a gate; advance on failure;
overwrite confirmed existing architecture artifacts without approval; or claim
completion before advancement.
