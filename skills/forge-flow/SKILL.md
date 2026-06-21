---
name: flow
description: Run a user-defined Forge workflow from `.forge/workflows/*.yaml` — a declarative
  DAG of agent steps with per-node prompts, `depends_on` edges, and `{{upstream}}` data
  passing. Use when the user runs /forge:flow, says "run my workflow", "run the <name> flow",
  "list my workflows", "show the flow plan", or references a `.forge/workflows/*.yaml` file.
  Lists available flows, shows the dependency-wave plan, and runs the chosen one through the
  bounded, deterministic workflow engine. Only active when `orchestration.flows_enabled` is
  true; otherwise it is a clean no-op that points the user at how to enable it.
allowed-tools: [Read, Bash, Edit, Write, Task]
---

# forge-flow — user-defined workflow DAGs

`/forge:flow` runs a workflow the user authored in `.forge/workflows/<name>.yaml`: a
declarative DAG where each node carries its own prompt (or a `{{upstream_id}}`-interpolating
template), `depends_on` edges, and optional `schema`/`model`. The loader
(`scripts/workflow_loader.py`) parses the file into a `WorkflowSpec`; the engine
(`scripts/_workflow.py` → `run_workflow`) schedules nodes in dependency *waves* and fans each
wave out in bounded parallel. It is the user-facing front end to the same deterministic,
never-raises engine `/forge:review` is built on.

A Python script cannot drive Claude's in-session Agent tool (ADR-006), so node dispatch goes
through the single `_background_agent.dispatch` wrapper — which is cost-gated through
`_cost_cap` on every node.

## When to Use

- `/forge:flow` (lists available workflows) or `/forge:flow <name>` (runs one).
- The user wants to run a `.forge/workflows/*.yaml` they wrote.
- The user asks to see a flow's plan before running it (`/forge:flow <name> --plan`).

## When NOT to Use

- A single ad-hoc prompt → just ask Claude directly; a flow is for a *repeatable multi-step DAG*.
- The 12-stage pipeline → that's `/forge:build`, `/forge:autopilot`, etc., not a user flow.

## Pre-flight: the toggle gate (no-op when off)

User-defined flows are **opt-in** and **off by default** (REQ-NF-025). Read the toggle first:

```bash
python3 - <<'PY'
import sys; from pathlib import Path
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
import _workflow_config as c
cfg = c.load_orchestration_config(Path(".forge"))
print("flows_enabled", cfg.flows_enabled)
PY
```

If `flows_enabled` is **false**, this skill is a **clean no-op**: do not load, plan, or run
anything. Tell the user it is disabled and how to turn it on, then stop:

> User-defined flows are off. Enable them by adding to `.forge/config.yaml`:
> ```yaml
> orchestration:
>   flows_enabled: true
> ```

## Steps

1. **Gate.** Run the toggle check above. If `flows_enabled` is false → no-op (stop, as above).
2. **List.** Enumerate available flows and, for a chosen one, load + validate it and print its
   wave plan:

   ```bash
   python3 - "$ARGUMENTS" <<'PY'
   import sys; from pathlib import Path
   sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
   import workflow_loader as wl, _workflow as wf
   wf_dir = Path(".forge/workflows")
   arg = (sys.argv[1] or "").strip().split()
   name = arg[0] if arg else ""
   files = wl.list_workflows(wf_dir)
   if not name:
       print("Available workflows:")
       for p in files:
           r = wl.load_workflow_file(p)
           tag = r.name or p.stem
           desc = (r.description or "").splitlines()[0] if r.description else ""
           print(f"  - {p.stem}: {tag} — {desc}" if desc else f"  - {p.stem}: {tag}")
       if not files:
           print("  (none — add a file to .forge/workflows/<name>.yaml)")
       sys.exit(0)
   path = wf_dir / f"{name}.yaml"
   if not path.exists():
       path = wf_dir / f"{name}.yml"
   res = wl.load_workflow_file(path)
   if not res.ok:
       print("Could not load workflow:")
       for e in res.errors:
           print(f"  - {e}")
       sys.exit(0)
   print(f"Workflow: {res.name or name}")
   if res.description:
       print(res.description.splitlines()[0])
   for i, wave in enumerate(wf.plan_waves(res.spec), 1):
       print(f"  wave {i}: {', '.join(wave)}")
   PY
   ```

   With no name, this lists flows and stops. With a name, it prints the wave plan. If the user
   passed `--plan` (or background is unavailable — see below), **stop here**: this is the
   deterministic dry-run plan; relay it and do not dispatch.

3. **Run.** When the user picked a flow and wants it executed, run it through the engine. The
   engine reads `orchestration.max_parallel` / `max_total` / `max_budget_usd` and is cost-gated
   per node; a per-node dispatch over the cap is skipped and reported (never silently truncated):

   ```bash
   python3 - "$ARGUMENTS" <<'PY'
   import sys, json; from pathlib import Path
   sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
   import workflow_loader as wl, _workflow as wf, _workflow_config as c
   cfg = c.load_orchestration_config(Path(".forge"))
   name = ((sys.argv[1] or "").strip().split() or [""])[0]
   path = Path(".forge/workflows") / f"{name}.yaml"
   if not path.exists():
       path = Path(".forge/workflows") / f"{name}.yml"
   res = wl.load_workflow_file(path)
   if not res.ok:
       print(json.dumps({"errors": res.errors})); sys.exit(0)
   out = wf.run_workflow(
       res.spec, forge_dir=Path(".forge"), feature=f"flow:{name}",
       max_parallel=cfg.max_parallel, max_total=cfg.max_total,
       max_budget_usd=cfg.max_budget_usd,
   )
   print(json.dumps({
       "completed": out.completed, "dropped": out.dropped,
       "total_cost_usd": out.total_cost_usd,
       "dropped_reasons": out.dropped_reasons,
       "results": out.results,
   }, indent=2, sort_keys=True))
   PY
   ```

4. **Propose, don't apply.** The run produces **proposed** outputs. Following the
   Proposal→Validator→Executor rails (ADR-006), present the results to the user for review —
   **nothing is written to the project unapproved**. Only after the user approves do you apply
   any file changes (the Executor step). If any node was dropped, say so explicitly rather than
   implying the whole flow completed.

## Degraded mode (background unavailable)

If `claude` is not on PATH or `FORGE_NO_BACKGROUND=1` is set, node dispatch cannot run. Do not
fail — **degrade to the deterministic dry-run plan** from step 2 (load + validate + `plan_waves`)
and tell the user the flow was planned but not executed because background dispatch is
unavailable.

## Verification

After running, these should hold:

- With `flows_enabled` false → the skill did nothing and explained how to enable it.
- `.forge/workflows/<name>.yaml` that loads → a wave plan is shown; a malformed/missing file →
  the loader's structured errors are surfaced (no crash).
- A run reports `completed` / `dropped` counts with reasons; dropped nodes are never hidden.
- No project files are written without the user approving the proposed output.

## Examples

**User**: "/forge:flow"

**Claude**: [gate passes, lists]
"Available workflows:
  - research-brief: research-brief — gather sources then draft a brief

Run one with `/forge:flow research-brief`, or `/forge:flow research-brief --plan` to preview
the wave plan first."

**User**: "/forge:flow research-brief --plan"

**Claude**:
"Workflow: research-brief
  wave 1: gather
  wave 2: draft

This is the plan only — nothing dispatched. Run `/forge:flow research-brief` to execute."
