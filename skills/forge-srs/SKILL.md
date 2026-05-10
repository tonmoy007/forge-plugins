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
3. Ask the user to describe their project if they haven't already. Gather:
   - What the system does
   - Who uses it
   - Key constraints (technology, timeline, compliance)
4. Follow the Requirements Analyst workflow: clarify, categorize, assign REQ-IDs, write acceptance criteria.
5. Write `pipeline/01-srs/srs.md` per the Output Contract in the persona file.
6. Run `python3 ${CLAUDE_PLUGIN_DIR}/scripts/state-manager.py advance --to 1` to mark Stage 1 active.

## Verification

After running, confirm:
- `pipeline/01-srs/srs.md` exists with REQ-IDs and acceptance criteria
- `pipeline/state.md` shows `current_stage: 1`

## Next Step

"SRS written. Run `/forge:ux` when ready to design the product experience."
