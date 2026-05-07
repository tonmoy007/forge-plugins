# Quick Start

> 5-minute orientation for a new contributor.

## Goal of This Repo

Build a Claude Code plugin called **Forge** that orchestrates a 12-stage SDLC pipeline.

The plugin is being built **using Claude Code itself** — meta. The repo contains both:
- The eventual plugin code (`hooks/`, `skills/`, `agents/`, etc.)
- The build artifacts that drive Claude's work (`build/`)

## What's Already Done

- ✅ Full SRS, architecture, spec, task DAG written (`build/01-srs/` through `build/04-plan/`)
- ✅ Claude operating manual (`CLAUDE.md`)
- ✅ Reference docs (hooks, skills, agents, gates, profiles, stages)
- ✅ Detailed prompts for first 3 + 1 critical task (T-001, T-002, T-003, T-009)
- ✅ Sample example for e2e testing (`examples/sample-todo-api/`)
- ✅ Test fixtures (`tests/fixtures/`)

## What's Pending

All 33 tasks in `build/04-plan/task-dag.md`. Status in `build/05-implementation/progress.md`.

## How to Start

### Option 1: Have Claude Do It

```bash
# Open Claude Code in this repo
claude

# Paste this into Claude:
```

> Read `prompts/sessions/bootstrap.md` and follow it.

### Option 2: Pick a Specific Task

```bash
cat prompts/development/T-001-scaffold.md
# Read it, then paste it to Claude:
claude
# > [paste contents of T-001-scaffold.md]
```

### Option 3: Read First, Decide Later

Read these in order:
1. `README.md` — repo overview
2. `CLAUDE.md` — Claude's operating manual
3. `build/01-srs/srs.md` — what the plugin does
4. `build/02-architecture/architecture.md` — how it fits together
5. `build/04-plan/task-dag.md` — the 33-task plan

## File Map

| Want to know... | Read |
|-----------------|------|
| Repo overview | `README.md` |
| Claude's instructions | `CLAUDE.md` |
| Human dev workflow | `DEVELOPMENT.md` |
| Milestone status | `ROADMAP.md` |
| Plugin requirements | `build/01-srs/srs.md` |
| Plugin architecture | `build/02-architecture/architecture.md` |
| Detailed specs | `build/03-spec/technical-spec.md` |
| Task list | `build/04-plan/task-dag.md` |
| Build progress | `build/05-implementation/progress.md` |
| What we've learned | `tasks/lessons.md` |
| Hooks API reference | `references/claude-code-hooks.md` |
| Skill format | `references/skill-format.md` |
| Agent format | `references/agent-format.md` |
| Gate criteria | `references/gate-criteria.md` |
| Stage definitions | `references/pipeline-stages.md` |
| Project profiles | `references/project-type-profiles.md` |
| ADRs | `build/02-architecture/adr/` |

## Commit Style

```
<type>(T-XXX): <subject>

<body>

Ref: T-XXX
REQ: REQ-NNN, REQ-MMM
```

## Got Stuck?

1. Read `tasks/lessons.md` — someone may have hit this before
2. Search `build/05-implementation/decisions.md` — may explain why something is the way it is
3. Re-read the task's prompt in `prompts/development/T-XXX-*.md`
4. If still stuck, file in lessons.md as an open question and move on
