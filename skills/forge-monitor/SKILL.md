---
name: forge-monitor
description: Run Stage 9 of the Forge pipeline — observability and monitoring. Use when
  the user says /forge:monitor, wants SLOs defined, health checks, or a system health
  report. Requires Stage 8 deployment. Invokes the observer persona.
allowed-tools: [Read, Write, Bash]
---

# /forge:monitor — Monitoring & Observability

## When to Use

- User says `/forge:monitor`
- User wants to set up observability, define SLOs, check system health, or review metrics
- Working in a Forge project at Stage 8 or 9

## Pre-flight Check

1. Read `pipeline/state.md` — confirm Forge project.
2. Confirm `pipeline/08-deployment/deployment-plan.md` exists (or `package-spec.md` for CLI/library projects). If neither: "Complete Stage 8 first (`/forge:deploy`)."
3. If stage > 9, ask if the user wants to update the health report.
4. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 9` to load project-type overrides. **If the profile sets `skip: true` (library), skip this stage and report that monitoring is N/A for the project type.** Otherwise, treat each `additional_criteria` (e.g., API: 4xx/5xx alerts, p99 latency; ML: model drift, data quality, inference latency) as required SLI/SLO/alert entries.

## Steps

1. Read `agents/observer.md` to load the Observer persona.
2. Adopt that persona — you are now the Observer.
3. Read `pipeline/08-deployment/deployment-plan.md` and `pipeline/01-srs/srs.md` NFR section.
4. Follow the Observer workflow: derive SLIs/SLOs from NFRs, check available signals, assess health. Add every profile criterion as a tracked signal with threshold and alert.
5. Write `pipeline/09-monitoring/slo-definition.md` and `pipeline/09-monitoring/health-report.md`.
6. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 9` to mark Stage 9 active.

## Verification

After running, confirm:
- `pipeline/09-monitoring/slo-definition.md` exists with SLIs, SLOs, and alert thresholds
- `pipeline/09-monitoring/health-report.md` exists with current status
- `pipeline/state.md` shows `current_stage: 9`

## Next Step

"Monitoring set up. Run `/forge:feedback` when you have user feedback or issues to triage."
