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

**Entry gate (REQ-GATE-ENTRY-001)** — before adopting the persona, verify the
prior stage's artifact exists:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py preflight --stage 8
```

If it exits non-zero, **STOP**: present its message verbatim and do not proceed —
the prior stage must be completed first (or use `/forge:force-advance` to skip
intentionally).

1. Read `pipeline/state.md` — confirm Forge project.
2. Confirm `pipeline/07-evaluation/eval-report.md` exists and shows overall pass.
   If eval-report is missing or shows failures: "Stage 7 evaluation must pass before deploying."
3. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-gate.py --stage 7` to check gate status.
4. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 8` to load project-type overrides. **If the profile sets `skip: true` (CLI, library) the conventional service-deploy is replaced by `package-publish` — produce a package-spec artifact instead of a deployment runbook.**
5. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check_docker_readiness.py --cwd .`
   **unconditionally** — every project gets this, regardless of profile (it
   self-no-ops with no Docker artifacts). This is **advisory only**: it exits 0
   even with findings, and any `WARN:` lines it prints must be relayed to the
   user as advisory notes — it never blocks and does not gate this stage.

## Steps

1. Read `agents/devops.md` to load the DevOps persona.
2. Adopt that persona — you are now the DevOps Engineer.
3. Read `pipeline/03-architecture/architecture.md` for topology and `pipeline/04-spec/technical-spec.md` for config needs.
4. Follow the DevOps workflow: pre-deployment checklist, ordered steps, health checks, rollback plan. If the profile specifies `replace_with: package-publish`, follow that flow instead (build artifacts, registry credentials, version verification, publish, post-publish smoke).
5. Write `pipeline/08-deploy/deploy-plan.md` and `pipeline/08-deploy/runbook.md` — or `pipeline/08-deploy/package-spec.md` when `replace_with: package-publish`.
6. Execute deployment (or publish) steps (with user confirmation for destructive operations),
   recording what happened in `pipeline/08-deploy/deploy-log.md`.
7. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 8` after successful deploy/publish.

## Verification

After running, confirm:
- `pipeline/08-deploy/deploy-plan.md` exists with rollback procedure
- `pipeline/08-deploy/deploy-log.md` records the deployment outcome
- `pipeline/08-deploy/runbook.md` exists
- Health checks pass post-deployment
- `pipeline/state.md` shows `current_stage: 8`

## Next Step

Derive the hint from the canonical stage table — never hardcode it
(REQ-NEXTHINT-001, single source of truth). Run the helper and present its
output to the user verbatim:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 8
```
