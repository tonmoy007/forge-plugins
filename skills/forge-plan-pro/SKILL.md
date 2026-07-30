---
name: forge-plan-pro
description: >
  Run Stage 5 of the Forge pipeline — Implementation Planning. Orchestrates
  Planner Pro to convert approved Stage 1–4 artifacts into a deterministic,
  traceable execution plan.
allowed-tools:
  - Read
  - Write
  - WebSearch
  - WebFetch
  - Grep
---

# /forge:plan-pro

## Aliases

- `/forge:plan-pro`
- `/forge:implementation-plan`

## Purpose

This skill orchestrates Stage 5 — Implementation Planning. It performs stage
gating, profile loading, persona/reference loading, context verification,
artifact/traceability/ownership verification, state advancement, and canonical
next-stage guidance.

This skill does not perform implementation planning. `agents/planner-pro.md`
and its mandatory `references/plan/` documents are the sole authority for
planning logic, artifacts, identifiers, task decomposition, validation, quality
gates, revisions, failures, and completion behavior.

## Stage Ownership

| Component | Owns |
|---|---|
| This skill | Stage orchestration only |
| Planner Pro + `references/plan/` | Stage 5 planning knowledge and rules |
| State Manager | Pipeline entry and progression |
| Document resolver | Single-file/split-document resolution |

Do not duplicate or reinterpret persona/reference logic in this skill.

## Pre-flight Check

### Entry Gate

Before reading the persona, references, or planning artifacts, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py preflight --stage 5
```

If it exits non-zero, STOP. Display the returned message verbatim. Do not adopt
Planner Pro, generate artifacts, or bypass the prerequisite. The user must
complete the prior stage or use the repository’s approved force-advance flow.

### Forge Project and Progress Verification

Read `pipeline/state.md`. Verify Forge is initialized, state exists, the current
stage is valid, and a project profile is available. If any condition fails, STOP
and report it.

If `current_stage > 5`, tell the user that Stage 5 appears complete and offer
Review, Validate, Revise, or Regenerate. Never overwrite existing Stage 5
artifacts without explicit confirmation. If `current_stage == 5`, continue only
as confirmed refinement work.

### Upstream Handoff Verification

Verify the canonical Stage 1–4 handoff required by Planner Pro exists or
resolves with `read-doc.py`. This includes the Stage 1 SRS/traceability, required
Stage 2 product/traceability artifacts, required Stage 3 architecture/
traceability/ADRs, and every Stage 4 contract required by the Planner Pro
foundation and workflow references.

If any required input is missing or cannot resolve, STOP. List every missing
artifact. Do not infer, regenerate, or replace upstream work.

## Load Project Profile

Run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 5
```

Load and pass its result unchanged to Planner Pro. The persona’s governance
reference controls handling of `replace_with`, `additional_artifacts`,
`additional_steps`, `additional_concerns`, and `skip_steps`. Never let a profile
bypass entry, ownership, traceability, validation, quality, or advancement gates.

## Load Planner Pro and References

Read `agents/planner-pro.md`, adopt Planner Pro, and follow its Reference Loading
Protocol exactly. The following files are mandatory agent instructions:

```text
references/plan/01-foundation.md
references/plan/02-execution-planning.md
references/plan/03-delivery-governance.md
references/plan/04-traceability-validation.md
references/plan/05-workflow-governance.md
```

Load each reference when the agent requires it and load all five before final
validation or completion. Do not omit, summarize away, substitute, or weaken a
reference instruction.

## Execute Stage

Provide Planner Pro only the context authorized by its foundation and workflow
references. Use:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/read-doc.py <document-base-path>
```

for every canonical document that can have a single-file or split layout. Do not
assume a flat planning or specification document exists, and do not use source
code or later-stage output as authority for a new Stage 5 plan.

Execute the persona sequentially, apply loaded profile overrides exactly, and
allow it to generate only the Stage 5 artifacts governed by its references.

## Verification

Before advancement, verify through the document resolver that the canonical
implementation-plan entry point and every required, profile-added, and
non-skipped Stage 5 artifact resolve successfully.

Verify that Planner Pro reports PASS for all applicable planning-completeness,
traceability, ownership, deterministic dependency/order, validation, and quality
gates. Confirm every planning artifact has valid upstream lineage, no Stage 1–4
artifact was redefined, no implementation code was generated, and no unresolved
validation error remains.

If verification fails, report the failures and affected artifacts. Do not
advance. Let Planner Pro perform only the deterministic Stage 5 repair permitted
by its references; stop and report upstream conflicts or unrecoverable failures.

## Advance Pipeline State

Advance only after successful verification:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 5
```

If advancement fails, display the returned message verbatim and stop. Do not
claim completion.

## Completion Report

Present the Planner Pro report derived from generated artifacts, then verify
`pipeline/state.md` reports `current_stage: 5`. Do not summarize the full plan
unless requested.

## Next Stage

Only after successful advancement, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 5
```

Present the helper output verbatim.

## Orchestration Rules

This skill SHALL run preflight first; load the profile; read Planner Pro and its
mandatory references; use the document resolver; preserve upstream ownership;
execute the persona; verify resolved artifacts, planning completeness,
traceability, dependencies, determinism, and stage ownership; advance only after
PASS; and present the canonical next hint.

This skill SHALL NOT duplicate planning logic; redefine upstream work; invent
functionality, IDs, repository paths, owners, or dependencies; bypass a gate;
advance on failure; write implementation code; overwrite confirmed existing
planning artifacts without approval; or claim completion before advancement.
