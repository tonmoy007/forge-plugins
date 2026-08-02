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
/forge:init         # scaffold pipeline
/forge:srs          # write requirements
/forge:status       # check current stage
/forge:orchestrate  # drive the whole pipeline, stage by stage (see below)
/forge:validate     # gap analysis — malformed/misplaced/unimplemented IDs, traceability
/forge:trace-matrix # full id x stage matrix, gaps attributed to the responsible agent
```

## Full-Pipeline Orchestration

OpenCode has no transcript-based "done" signal (see Architecture below), so the
Claude Code version's automatic stage-advance never fires here. `/forge:orchestrate`
(`agents/orchestrator.md`) is the OpenCode-native replacement: it adopts a dedicated
Orchestrator persona that runs each stage's own skill in turn, checks its gate, and
— critically — explicitly advances `pipeline/state.md` and **re-reads it to confirm
the advance landed** before calling a stage done. See
`skills/forge-orchestrate/SKILL.md` for the full protocol and how it relates to
`/forge:autopilot` (self-heal / background dispatch — still the right tool for that).

## Validation & Traceability

`/forge:validate` (`scripts/validate-traceability.py`) runs a full gap analysis over
the pipeline: malformed IDs (wrong case/separator/digit-padding), misplaced ID
definitions (e.g. a `REQ-*` heading defined outside `pipeline/01-srs/srs.md`),
unimplemented/orphaned requirements (a `REQ-*`/`NFR-*` never referenced past Stage 1),
and the existing `traceability-check.py --full-chain` + gate-completeness scripts,
folded into one report. See `skills/forge-validate/SKILL.md`.

## Traceability Matrix & Gap Attribution

`/forge:trace-matrix` (`scripts/trace-matrix.py`, `agents/traceability-matrix.md`)
generates the full id x stage traceability matrix — every id found under `pipeline/`
as a row, every stage with activity on it as a column, defined vs merely referenced
— plus the same four gap categories `/forge:validate` checks, each one **attributed
to the specific stage agent responsible for it** (e.g. an unimplemented `REQ-*` is
attributed to the earliest downstream stage that should have referenced it, not the
stage that defined it). It writes `.forge/traceability-gaps.jsonl` — a fresh
snapshot each run — which `hooks/session-start.py` reads to advise the responsible
agent only when their stage is currently active (informational, never blocking). See
`skills/forge-trace-matrix/SKILL.md`.

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
