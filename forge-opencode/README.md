# Forge — SDLC Orchestrator for OpenCode

Port of [Forge](https://github.com/tonmoy007/forge-plugins) (Claude Code plugin) to OpenCode.

Gated 12-stage pipeline with learning, auto-reflection, and adaptive workflows.

## Install

Copy `forge-opencode/` to `~/.config/opencode/plugin/forge-opencode/` or `.opencode/plugin/forge-opencode/` in your project.

## Pipeline

| Stage | Command | Output |
|-------|---------|--------|
| 1 — Requirements | `/forge:srs` | SRS with REQ-IDs |
| 2 — Product & UX | `/forge:product` | PRD, design system, user flows |
| 3 — Architecture | `/forge:arch` | Architecture doc, ADRs, data model |
| 4 — Technical Spec | `/forge:spec` | Tech spec, interface contracts |
| 5 — Planning | `/forge:plan` | Task DAG, milestones |
| 6 — Implementation | `/forge:build` | Code, progress tracker |
| 7 — Evaluation | `/forge:eval` | Test results, eval report |
| 8 — Deployment | `/forge:deploy` | Deploy plan, runbook |
| 9 — Monitoring | `/forge:monitor` | Observability config |
| 10 — Feedback | `/forge:feedback` | Triage report |
| 11 — Resolution | `/forge:resolve` | Hotfixes, regression tests |
| 12 — Release | `/forge:release` | Changelog, release notes |

## Usage

```
/forge:init      # scaffold pipeline
/forge:srs       # write requirements
/forge:status    # check current stage
```

## Architecture

OpenCode plugin routes lifecycle events to Python hook scripts:

| OpenCode Event | Hook Script | Purpose |
|---|---|---|
| `session.created` | `session-start.py` | State injection |
| `message.send.before` | `prompt-submit.py` | Intent detection |
| `tool.execute.before` | `pre-tool-write.py` | Design system enforcement |
| `tool.execute.after` | `post-tool-use.py` | Logging + pattern tracking |
| `session.idle` | `stop-reflect.py` | Reflection + lesson extraction |
| `session.compacted` | `pre-compact.py` | Autopilot checkpoint |
| `session.deleted` | `session-end.py` | Session summary |

## License

MIT
