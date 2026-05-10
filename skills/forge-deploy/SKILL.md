---
name: forge-deploy
description: Run Stage 8 of the Forge pipeline — deployment. Use when the user says
  /forge:deploy, wants to ship to an environment, or needs a deployment plan and runbook.
  Requires Stage 7 eval to pass. Invokes the devops persona.
allowed-tools: [Read, Write, Bash]
---

# /forge:deploy — Deployment

## When to Use

- User says `/forge:deploy`
- User wants to deploy to staging or production, write a deployment plan, or create a runbook
- Working in a Forge project at Stage 7 or 8

## Pre-flight Check

1. Read `pipeline/state.md` — confirm Forge project.
2. Confirm `pipeline/07-evaluation/eval-report.md` exists and shows overall pass.
   If eval-report is missing or shows failures: "Stage 7 evaluation must pass before deploying."
3. Run `python3 ${CLAUDE_PLUGIN_DIR}/scripts/check-gate.py --stage 7` to check gate status.

## Steps

1. Read `agents/devops.md` to load the DevOps persona.
2. Adopt that persona — you are now the DevOps Engineer.
3. Read `pipeline/03-architecture/architecture.md` for topology and `pipeline/04-technical-spec/technical-spec.md` for config needs.
4. Follow the DevOps workflow: pre-deployment checklist, ordered steps, health checks, rollback plan.
5. Write `pipeline/08-deployment/deployment-plan.md` and `pipeline/08-deployment/runbook.md`.
6. Execute deployment steps (with user confirmation for destructive operations).
7. Run `python3 ${CLAUDE_PLUGIN_DIR}/scripts/state-manager.py advance --to 8` after successful deploy.

## Verification

After running, confirm:
- `pipeline/08-deployment/deployment-plan.md` exists with rollback procedure
- `pipeline/08-deployment/runbook.md` exists
- Health checks pass post-deployment
- `pipeline/state.md` shows `current_stage: 8`

## Next Step

"Deployed. Run `/forge:monitor` to set up observability and track system health."
