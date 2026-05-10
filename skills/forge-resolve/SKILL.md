---
name: forge-resolve
description: Run Stage 11 of the Forge pipeline — issue resolution and hotfixes. Use
  when the user says /forge:resolve, wants to fix bugs from triage, or needs a hotfix.
  Requires Stage 10 triage report. Invokes the resolver persona.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# /forge:resolve — Resolution & Hotfix

## When to Use

- User says `/forge:resolve`
- User wants to fix bugs, apply hotfixes, or address triage items
- Working in a Forge project at Stage 10 or 11

## Pre-flight Check

1. Read `pipeline/state.md` — confirm Forge project.
2. Confirm `pipeline/10-feedback/triage-report.md` exists. If not: "Complete Stage 10 first (`/forge:feedback`)."
3. Read the triage report and surface the critical/high items to the user before starting.

## Steps

1. Read `agents/resolver.md` to load the Resolver persona.
2. Adopt that persona — you are now the Resolver.
3. Read `pipeline/10-feedback/triage-report.md`. Start with the highest severity item.
4. Follow the Resolver workflow: reproduce → root cause → targeted fix → regression test → commit.
5. Update `pipeline/11-resolution/resolution-log.md` with each resolved item.
6. Run `python3 ${CLAUDE_PLUGIN_DIR}/scripts/state-manager.py advance --to 11` after first resolution.

## Verification

After each resolution, confirm:
- Root cause documented in resolution-log.md
- Regression test added and passing
- Full test suite passing
- Commit uses `fix(FB-XXX):` format

## Next Step

"All critical/high items resolved. Run `/forge:release` to cut a versioned release."
