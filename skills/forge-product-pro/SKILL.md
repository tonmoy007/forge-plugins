---
name: forge-product-pro
description: >
  Run Stage 2 of the Forge pipeline — Product Design & UX (Pro tier).
  Transforms the approved Stage 1 SRS into complete, traceable product
  design artifacts including the PRD, user stories, personas, information
  architecture, navigation model, user flows, screen specifications,
  wireframes, component inventory, design system, UX decisions, and
  traceability matrix. Invokes the Product Designer Pro persona.

allowed-tools:
  - Read
  - Write
  - WebSearch
  - WebFetch
---

# /forge:product-pro

## Aliases

- `/forge:product-pro`
- `/forge:ux-pro` (informal alias some users may type)

## Purpose

This skill orchestrates Stage 2 — Product Design & UX. It performs stage
gating, profile loading, persona/reference loading, context verification,
artifact/traceability verification, state advancement, and canonical
next-stage guidance.

This skill does not perform product design. `agents/product-designer-pro.md`
and its mandatory `references/product/` documents are the sole authority for
design logic, artifacts, identifiers, flow decomposition, validation, quality
gates, revisions, failures, and completion behavior.

## Stage Ownership

| Component | Owns |
|---|---|
| This skill | Stage orchestration only |
| Product Designer Pro + `references/product/` | Stage 2 design knowledge and rules |
| State Manager | Pipeline entry and progression |

Do not duplicate or reinterpret persona/reference logic in this skill.

## Pre-flight Check

### Entry Gate (REQ-GATE-ENTRY-001)

Before reading the persona, references, or design artifacts, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py preflight --stage 2
```

If it exits non-zero, STOP. Display the returned message verbatim. Do not adopt
Product Designer Pro, generate artifacts, or bypass the prerequisite. The user
must complete Stage 1 or use the repository's approved force-advance flow.

### Forge Project and Progress Verification

Read `pipeline/state.md`. Verify Forge is initialized, state exists, the current
stage is valid, and a project profile is available. If any condition fails, STOP
and report it.

If `current_stage > 2`, tell the user that Stage 2 appears complete and offer
Review, Validate, Revise, or Regenerate. Never overwrite existing Stage 2
artifacts without explicit confirmation. If `current_stage == 2`, continue only
as confirmed refinement work.

### SRS Verification

Verify `pipeline/01-srs/srs.md` exists and is readable. If missing or invalid,
return "Stage 1 (SRS) must be completed before Product Design. Run `/forge:srs`."
Do not continue.

### Load Project Profile

Run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 2
```

Load and pass its result unchanged to Product Designer Pro. The persona's
governance reference controls handling of `replace_with`, `additional_artifacts`,
`additional_steps`, `additional_concerns`, and `skip_steps`. Never let a profile
bypass entry, ownership, traceability, validation, quality, or advancement gates.

## Load Product Designer and References

Read `agents/product-designer-pro.md`, adopt Product Designer Pro, and follow
its Reference Loading Protocol exactly. The following files are mandatory agent
instructions:

```text
references/product/01-foundation.md
references/product/02-information-architecture-flows.md
references/product/03-design-system-components.md
references/product/04-traceability-validation.md
references/product/05-workflow-governance.md
```

Load each reference when the agent requires it and load all five before final
validation or completion. Do not omit, summarize away, substitute, or weaken a
reference instruction.

## Read Context

- Read `pipeline/state.md`
- Read `pipeline/01-srs/srs.md`
- Read existing `pipeline/02-product-ux/` files (for iteration/refinement only)

Never use architecture, implementation, API, or source code as design inputs.

## Execute Stage

Provide Product Designer Pro only the context authorized by its foundation and
workflow references. Execute the persona sequentially, apply loaded profile
overrides exactly, and allow it to generate only the Stage 2 artifacts governed
by its references.

## Verification

Before advancement, verify through the document resolver that the canonical PRD
entry point and every required, profile-added, and non-skipped Stage 2 artifact
resolve successfully.

Verify that Product Designer Pro reports PASS for all applicable design-
completeness, traceability, ownership, validation, and quality gates. Confirm
every design artifact has valid upstream lineage (traces to REQ-IDs), no Stage 1
requirement was redefined, no implementation code was generated, and no
unresolved validation error remains.

If verification fails, report the failures and affected artifacts. Do not
advance. Let Product Designer Pro perform only the deterministic Stage-2-only
repair permitted by its references; stop and report upstream conflicts or
unrecoverable failures.

## Advance Pipeline State

Advance only after successful verification:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 2
```

If advancement fails, display the returned message verbatim and stop. Do not
claim completion.

## Completion Report

Present the Product Designer Pro report derived from generated artifacts, then
verify `pipeline/state.md` reports `current_stage: 2`. Do not summarize the full
design unless requested.

## Next Stage

Only after successful advancement, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 2
```

Present the helper output verbatim.

## Orchestration Rules

This skill SHALL run preflight first; load the profile; read Product Designer
Pro and its mandatory references; preserve upstream ownership; execute the
persona; verify resolved artifacts, design completeness, traceability, and
stage ownership; advance only after PASS; and present the canonical next hint.

This skill SHALL NOT duplicate design logic; redefine upstream work; invent
functionality, IDs, features, or scope; bypass a gate; advance on failure; write
implementation code; overwrite confirmed existing design artifacts without
approval; or claim completion before advancement.

## Success Criteria

Stage 2 complete only when:
- Every approved requirement is represented in downstream design artifacts.
- All generated artifacts pass validation.
- All documents are written successfully.
- Stage state is advanced to 2.
- Next stage hint has been displayed.

The Product Design specification MUST be complete enough that an architect can
begin Stage 3 without additional stakeholder clarification.
