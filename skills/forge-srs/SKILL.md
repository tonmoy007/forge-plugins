---
name: forge-srs
description: Run Stage 1 of the Forge pipeline — requirements analysis. Use when the
  user says /forge:srs, wants to write requirements, define what to build, produce an
  SRS, or start a new project with Forge. Invokes the requirements-analyst persona.
allowed-tools: [Read, Write, WebSearch, WebFetch, Grep]
---

# /forge:srs — Requirements Analysis

## When to Use

- User says `/forge:srs`
- User wants to define requirements, write an SRS, or describe what to build
- Working in a Forge project at Stage 0 or 1

## Pre-flight Check

1. Read `pipeline/state.md` to confirm this is a Forge project.
2. Note the current stage. If stage > 1, inform the user this stage appears done and ask if they want to revise it.

## Steps

1. Read `agents/requirements-analyst.md` to load the Requirements Analyst persona.
2. Adopt that persona completely — you are now the Requirements Analyst.
3. Ask the user to describe their project if they haven't already. Gather: what the system does, who uses it, key constraints (technology, timeline, compliance).
4. Follow the Requirements Analyst workflow: clarify, categorize, assign REQ-IDs, write acceptance criteria.
<<<<<<< HEAD
5. Write `pipeline/01-srs/srs.md` per the Output Contract in the persona file.
6. Run `python3 ${CLAUDE_PLUGIN_DIR}/scripts/state-manager.py advance --to 1` to mark Stage 1 active.
=======
5. Conduct a single bounded round of clarification questions (REQ-INTERACTIVE-CLARIFY-001) before writing `pipeline/01-srs/srs.md` — one batch, not a drip. Unanswered questions become documented assumptions in the SRS.
6. Write `pipeline/01-srs/srs.md` per the Output Contract in the persona file.
7. Run `python3 ${CLAUDE_PLUGIN_DIR}/scripts/state-manager.py advance --to 1` to mark Stage 1 active.
>>>>>>> 5a2d054873ab85c3b8590120b883ff3fcfc97f3a

## Verification

After running, confirm:
- `pipeline/01-srs/srs.md` exists with REQ-IDs and acceptance criteria
- `pipeline/state.md` shows `current_stage: 1`

## Next Step

Derive the hint from the canonical stage table — never hardcode it (REQ-NEXTHINT-001, single source of truth). Run the helper and present its output to the user verbatim:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 1
```
