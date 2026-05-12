---
name: forge-spec
description: Run Stage 4 of the Forge pipeline — technical specification. Use when the
  user says /forge:spec, wants interface definitions, data schemas, API contracts, or
  a full technical spec. Requires Stage 1–3. Invokes the spec-writer persona.
allowed-tools: [Read, Write, Grep]
---

# /forge:spec — Technical Specification

## When to Use

- User says `/forge:spec`
- User wants precise interface definitions, API contracts, type schemas, or behavioral contracts
- Working in a Forge project at Stage 3 or 4

## Pre-flight Check

1. Read `pipeline/state.md` — confirm Forge project.
2. Confirm `pipeline/03-architecture/architecture.md` exists. If not: "Complete Stage 3 first (`/forge:arch`)."
3. If stage > 4, ask if the user wants to revise the spec.
4. Run `python3 ${CLAUDE_PLUGIN_DIR}/scripts/load-profile.py --cwd . --stage 4` to load project-type overrides. Note any `additional_artifacts` (e.g., ML: model-spec.md, data-spec.md) and `additional_concerns` (e.g., library: public-vs-internal API, semver commitment, bundle budget).

## Steps

1. Read `agents/spec-writer.md` to load the Spec Writer persona.
2. Adopt that persona — you are now the Spec Writer.
3. Read `pipeline/03-architecture/architecture.md` and its ADRs.
4. Read `pipeline/01-srs/srs.md` for REQ-ID traceability.
5. Follow the Spec Writer workflow: enumerate interfaces, define types, write API specs, trace to REQ-IDs. Add the profile's `additional_artifacts` and address `additional_concerns` in the spec.
6. Write `pipeline/04-technical-spec/technical-spec.md` and any profile-specified extra artifacts per the Output Contract.
7. Run `python3 ${CLAUDE_PLUGIN_DIR}/scripts/state-manager.py advance --to 4` to mark Stage 4 active.

## Verification

After running, confirm:
- `pipeline/04-technical-spec/technical-spec.md` exists with typed interfaces and REQ-ID traces
- `pipeline/state.md` shows `current_stage: 4`

## Next Step

"Technical spec written. Run `/forge:plan` to create the implementation task plan."
