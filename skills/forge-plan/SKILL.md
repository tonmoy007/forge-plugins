---
name: forge-plan
description: Run Stage 5 of the Forge pipeline — implementation planning. Use when the
  user says /forge:plan, wants a task breakdown, task DAG, effort estimates, or a risk
  register. Requires Stage 1–4. Invokes the planner persona.
allowed-tools: [Read, Write, Grep]
---

# /forge:plan — Implementation Planning

## When to Use

- User says `/forge:plan`
- User wants a task breakdown, DAG, effort estimates, milestones, or risk register
- Working in a Forge project at Stage 4 or 5

## Pre-flight Check

**Entry gate (REQ-GATE-ENTRY-001)** — before adopting the persona, verify the
prior stage's artifact exists:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py preflight --stage 5
```

If it exits non-zero, **STOP**: present its message verbatim and do not proceed —
the prior stage must be completed first (or use `/forge:force-advance` to skip
intentionally).

1. Read `pipeline/state.md` — confirm Forge project.
2. Confirm `pipeline/04-spec/technical-spec.md` exists. If not: "Complete Stage 4 first (`/forge:spec`)."
3. If stage > 5, ask if the user wants to revise the plan.
4. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 5` to load project-type overrides and the `stage_emphasis` hints — use the emphasis to weight effort estimates (e.g., ML projects emphasize spec/eval/monitor, so reserve more tasks there).

## Steps

1. Read `agents/planner.md` to load the Planner persona.
2. Adopt that persona — you are now the Planner.
3. Read `pipeline/04-spec/technical-spec.md` and `pipeline/03-architecture/architecture.md`.
4. Follow the Planner workflow: decompose into tasks, map dependencies, identify critical path, enumerate risks. Apply the profile's emphasis: under-emphasized stages get lighter task budgets, over-emphasized stages get explicit milestones.
5. Write `pipeline/05-plan/task-dag.md` and `pipeline/05-plan/risk-register.md` per the Output Contract.
6. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 5` to mark Stage 5 active.

## Verification

After running, confirm:
- `pipeline/05-plan/task-dag.md` exists with T-IDs, dependencies, and effort estimates
- `pipeline/05-plan/risk-register.md` exists with R-IDs and mitigations
- `pipeline/state.md` shows `current_stage: 5`

## Next Step

Derive the hint from the canonical stage table — never hardcode it
(REQ-NEXTHINT-001, single source of truth). Run the helper and present its
output to the user verbatim:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 5
```
