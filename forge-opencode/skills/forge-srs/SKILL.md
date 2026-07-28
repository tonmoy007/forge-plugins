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
3. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 1` to load any project-type overrides for this stage. Apply the emphasis hints, skip flags, additional artifacts, concerns, and criteria when following the persona workflow below.

## Steps

1. Read `agents/requirements-analyst.md` to load the Requirements Analyst persona.
2. Adopt that persona completely — you are now the Requirements Analyst.
3. Ask the user to describe their project if they haven't already. Gather:
   - What the system does
   - Who uses it
   - Key constraints (technology, timeline, compliance)
4. **Clarify before writing (REQ-INTERACTIVE-CLARIFY-001).** If the description is vague or under-specified, ask ONE bounded clarifying-question round BEFORE writing `pipeline/01-srs/srs.md` — a single batch covering the highest-ambiguity areas (scope, users, constraints). This is a single round, not a drip; cap at one batch (max 1 round) and bundle the questions rather than trickling them out.
5. Follow the Requirements Analyst workflow: clarify, categorize, assign REQ-IDs, write acceptance criteria. Honor any profile overrides loaded in pre-flight (extra concerns, skipped steps, additional NFR categories).
6. **Record assumptions for unanswered items.** For any clarifying question the user leaves unanswered, proceed and record an explicit ASSUMPTION in the SRS (under Constraints and assumptions) instead of blocking.
7. Write `pipeline/01-srs/srs.md` per the Output Contract in the persona file.
8. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 1` to mark Stage 1 active.

## Verification

After running, confirm:
- `pipeline/01-srs/srs.md` exists with REQ-IDs and acceptance criteria
- `pipeline/state.md` shows `current_stage: 1`

## Next Step

Derive the hint from the canonical stage table — never hardcode it
(REQ-NEXTHINT-001, single source of truth). Run the helper and present its
output to the user verbatim:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 1
```
