# Forge — SDLC Orchestrator for Claude Code

> A Claude Code plugin that turns Claude into a full-lifecycle software development engine
> with specialized agents, persistent memory, auto-reflection, and adaptive workflows.

**Status**: 🚧 Active development — M1–M3 complete, M4 (Memory + Lessons) in progress.

---

## What This Repository Is

This is **the development repository for the Forge plugin**, not the plugin itself.

The plugin is being built by Claude Code, following the same 12-stage pipeline that Forge itself
will eventually orchestrate. We're eating our own dogfood: this repo contains a `build/` directory
with SRS, architecture, spec, and task DAG that drives Claude's work, just like a Forge-managed
project would.

## What Forge Does (When Built)

When installed in Claude Code, Forge:

1. **Orchestrates** a 12-stage SDLC pipeline (SRS → Product → Architecture → Spec → Plan → Build → Eval → Deploy → Monitor → Feedback → Resolve → Release)
2. **Specializes** 16 agents — 12 stage-specific personas + 4 cross-stage helpers (reflector, lesson-extractor, skill-miner, gate-checker)
3. **Remembers** across sessions via 3-tier memory (session context → project files → cross-project)
4. **Reflects** on every `Stop` event — evaluates output against gate criteria, extracts lessons
5. **Adapts** to project type (API, full-stack, ML, CLI, library) with custom workflow profiles
6. **Creates skills** automatically when it detects patterns repeated 3+ times
7. **Enforces gates** via hooks — design system tokens, traceability, exit criteria
8. **Documents** every decision automatically — no silent edits, no lost context

## Repository Structure

```
forge/
├── README.md                  # this file
├── CLAUDE.md                  # instructions for Claude when working in this repo
├── DEVELOPMENT.md             # how to develop the plugin (workflows for humans)
├── ROADMAP.md                 # milestone tracker
│
├── .claude-plugin/            # ← THE PLUGIN (output)
│   └── plugin.json
├── skills/                    # ← /forge:* slash commands
├── agents/                    # ← specialized subagents
├── hooks/                     # ← lifecycle hook scripts
├── scripts/                   # ← deterministic helpers
├── references/                # ← on-demand docs for skills
├── assets/                    # ← banners, templates
│
├── build/                     # ← the build pipeline ARTIFACTS
│   ├── 01-srs/                # what the plugin must do
│   ├── 02-architecture/       # how it fits together
│   ├── 03-spec/               # implementation-ready specs
│   ├── 04-plan/               # task DAG + risk register
│   ├── 05-implementation/     # progress tracker, decisions log
│   └── 06-evaluation/         # eval reports, test results
│
├── prompts/                   # ← prompts to give Claude for development
│   ├── development/           #    one prompt per task in the DAG
│   ├── agents/                #    prompts for working on agent personas
│   └── sessions/              #    session bootstrap prompts
│
├── tests/                     # ← test the plugin itself
├── examples/                  # ← sample projects to test the plugin against
└── docs/                      # ← user-facing documentation (when ready)
```

## Quickstart for Developers (Humans)

### Option A: Develop with Claude Code

```bash
git clone <repo-url> forge
cd forge
claude              # start a Claude Code session in this dir
```

Then either:

- **Ask Claude to start work**: `Read CLAUDE.md, then read build/04-plan/task-dag.md and start the first unblocked task.`
- **Use a specific prompt**: paste contents of `prompts/development/T-001-scaffold.md` into Claude.

### Option B: Develop manually

Work through `build/04-plan/task-dag.md` task by task. Each task has a corresponding
prompt file in `prompts/development/` showing how Claude should approach it.

## How Claude Works in This Repo

When Claude reads `CLAUDE.md` (which it does automatically), it learns:

1. **Where it is in the build** (read `build/05-implementation/progress.md`)
2. **What's next** (read `build/04-plan/task-dag.md` for the first unblocked task)
3. **Lessons from prior sessions** (read `tasks/lessons.md`)
4. **Plugin development conventions** (read `DEVELOPMENT.md`)

Then it picks up the work — exactly the experience the finished plugin will provide for end users.

## Current Phase

| Milestone | Status | Tasks | Description |
|-----------|--------|-------|-------------|
| M1: Core Skeleton | 🟢 Done | T-001–006 | Plugin scaffold + state manager + status command |
| M2: Hook System | 🟢 Done | T-007–013 | 7 hooks across 6 lifecycle events |
| M3: Specialized Agents | 🟢 Done | T-014–018 | 12 stage + 4 cross-stage agents; context-pruner; forge-resume |
| M4: Memory + Lessons | 🟡 In progress | T-019–022 | Lesson extraction done; injection + cross-project memory pending |
| M5: Adaptive Workflow | 🔲 Not started | T-023–025 | Project type detection + profiles |
| M6: Auto-Skill Creation | 🔲 Not started | T-026–029 | Pattern mining → skill generation |
| M7: Polish + Docs | 🔲 Not started | T-030–033 | README, contribution guide, e2e test |

**Tests passing**: 338 &nbsp;·&nbsp; **Tasks complete**: 19 / 33

See `ROADMAP.md` for the full task list with dependencies.

## License

MIT (TBD — verify before publishing).

## Author

Saddam · built with Claude Code
