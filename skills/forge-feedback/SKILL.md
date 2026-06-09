---
name: forge-feedback
description: Run Stage 10 of the Forge pipeline — feedback triage. Use when the user
  says /forge:feedback, has user feedback to process, wants bugs classified, or needs
  a prioritized backlog. Requires Stage 9. Invokes the triage persona.
allowed-tools: [Read, Write, Grep]
---

# /forge:feedback — Feedback Triage

## When to Use

- User says `/forge:feedback`
- User has user feedback, bug reports, or feature requests to process
- User wants a prioritized action list from incoming signals
- Working in a Forge project at Stage 9 or 10

## Pre-flight Check

1. Read `pipeline/state.md` — confirm Forge project.
2. Ask the user to provide feedback items if none are present in the conversation.
3. Check `pipeline/09-monitor/health-report.md` for any system signals to include.
4. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 10` to surface any project-type triage overrides (e.g., classes of feedback specific to the project type — UX regressions for fullstack, API contract breaks for API, regressions in train→serve parity for ML).

## Steps

1. Read `agents/triage.md` to load the Triage Specialist persona.
2. Adopt that persona — you are now the Triage Specialist.
3. Read all available feedback: user input, monitoring signals, `pipeline/10-feedback/` if it exists.
4. Follow the Triage workflow: classify, assign severity, recommend action, prioritize. Use any profile-specific categories from pre-flight to tag items.
5. Write `pipeline/10-feedback/feedback-log.md` (every incoming item, verbatim) and
   `pipeline/10-feedback/triage.md` (classified + prioritized) per the Output Contract.
6. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 10` to mark Stage 10 active.

## Verification

After running, confirm:
- `pipeline/10-feedback/feedback-log.md` exists with all incoming feedback items
- `pipeline/10-feedback/triage.md` exists with FB-IDs, classifications, and severities
- Critical and high items have specific remediation steps
- `pipeline/state.md` shows `current_stage: 10`

## Next Step

Derive the hint from the canonical stage table — never hardcode it
(REQ-NEXTHINT-001, single source of truth). Run the helper and present its
output to the user verbatim:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 10
```
