---
name: forge-arch
description: Run Stage 3 of the Forge pipeline — system architecture. Use when the
  user says /forge:architecture or /forge:arch, wants a C4 diagram, data model, API
  design, or tech stack decisions. Requires Stage 1–2 to exist. Invokes system-architect.
allowed-tools: [Read, Write, WebSearch, WebFetch, Grep]
---

# /forge:arch — System Architecture

## When to Use

- User says `/forge:architecture` or `/forge:arch`
- User wants system design, C4 diagrams, data model, API contracts, or ADRs
- Working in a Forge project at Stage 2 or 3

## Pre-flight Check

**Entry gate (REQ-GATE-ENTRY-001)** — before adopting the persona, verify the
prior stage's artifact exists:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py preflight --stage 3
```

If it exits non-zero, **STOP**: present its message verbatim and do not proceed —
the prior stage must be completed first (or use `/forge:force-advance` to skip
intentionally).

1. Read `pipeline/state.md` — confirm Forge project.
2. Confirm `pipeline/01-srs/srs.md` exists. If not: "Complete Stage 1 first (`/forge:srs`)."
3. Confirm `pipeline/02-product-ux/prd.md` exists (warn if missing but don't block).
4. If stage > 3, ask if the user wants to revise architecture.
5. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 3` to load project-type overrides. Note any `additional_concerns` (e.g., ML: training/inference path, checkpoint format; fullstack: SSR/SSG strategy, BFF boundary; API: versioning, pagination, idempotency) and `additional_artifacts` (e.g., openapi-spec.yaml, route-manifest.md).

## Steps

1. Read `agents/system-architect.md` to load the System Architect persona.
2. Adopt that persona — you are now the System Architect.
3. Read `pipeline/01-srs/srs.md` and `pipeline/02-product-ux/prd.md`.
4. Follow the System Architect workflow: C4 diagrams, data model, API surface, security model, ADRs. Address every `additional_concerns` item from the profile in the architecture doc, and produce any `additional_artifacts` listed.
5. Write `pipeline/03-architecture/architecture.md`, ADR files, and any profile-specified extra artifacts per the Output Contract.
6. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 3` to mark Stage 3 active.

## Verification

After running, confirm:
- `pipeline/03-architecture/architecture.md` exists with C4 diagrams and data model
- At least one ADR exists in `pipeline/03-architecture/adr/`
- `pipeline/state.md` shows `current_stage: 3`

## Next Step

Derive the hint from the canonical stage table — never hardcode it
(REQ-NEXTHINT-001, single source of truth). Run the helper and present its
output to the user verbatim:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 3
```
