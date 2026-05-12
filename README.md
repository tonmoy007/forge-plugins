# Forge — SDLC Orchestrator for Claude Code

> Turn Claude Code into a full-lifecycle software development engine: 12-stage pipeline,
> specialized agents, persistent memory, auto-reflection, and adaptive workflows.

[![Tests](https://img.shields.io/badge/tests-532%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![Claude Code](https://img.shields.io/badge/claude--code-%3E%3D2.1.0-blueviolet)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)]()

---

## What Forge Does

Forge gives Claude Code a structured 12-stage pipeline — from requirements through release —
with gate enforcement, specialized agents per stage, and a memory system that learns from every
session.

**Without Forge**: Claude is a smart assistant that forgets everything between sessions.

**With Forge**: Claude becomes a disciplined engineering partner that remembers decisions,
enforces quality gates, surfaces lessons from past mistakes, and adapts its workflow to your
project type.

---

## Prerequisites

- **Claude Code** ≥ 2.1.0
- **Python** ≥ 3.11 (on PATH)
- **pyyaml**: `pip install pyyaml`

---

## Install

```bash
claude plugin install https://github.com/<user>/forge
```

That's it. Forge activates automatically in any project where you've run `/forge:init`.

---

## Quickstart (< 5 minutes)

### 1. Initialize Forge in your project

```
/forge:init
```

Forge detects your project type (API, full-stack, ML pipeline, CLI, library), scaffolds
`pipeline/` in your project root, and writes `pipeline/state.md` — the single source of
truth for where you are in the pipeline.

### 2. Describe your project to get requirements

```
/forge:srs
```

Claude interviews you about your project and produces a requirements document
(`pipeline/01-srs/srs.md`) with REQ-IDs you'll trace through every subsequent stage.

### 3. Continue through the pipeline

Each `/forge:*` command runs the next stage. You never need to remember where you are —
Forge tells you at every session start.

---

## The 12-Stage Pipeline

| Command | Stage | Output |
|---------|-------|--------|
| `/forge:srs` | 1 — Requirements | SRS with REQ-IDs |
| `/forge:product` | 2 — Product & UX | PRD, design system, user flows |
| `/forge:arch` | 3 — Architecture | Architecture doc, ADRs, data model |
| `/forge:spec` | 4 — Technical Spec | Tech spec, interface spec, test strategy |
| `/forge:plan` | 5 — Planning | Task DAG, milestones, risk register |
| `/forge:build` | 6 — Implementation | Code, decisions log, progress tracker |
| `/forge:eval` | 7 — Evaluation | Test results, security review, eval report |
| `/forge:deploy` | 8 — Deployment | Deploy plan, deploy log |
| `/forge:monitor` | 9 — Monitoring | Observability config, incident log |
| `/forge:feedback` | 10 — Feedback | Feedback log, triage |
| `/forge:resolve` | 11 — Resolution | Hotfixes, backlog updates |
| `/forge:release` | 12 — Release | Release notes, release checklist |

### Utility Commands

| Command | What it does |
|---------|-------------|
| `/forge:status` | Show current stage, task, blockers, and recent history |
| `/forge:resume` | Restore context after a session restart |
| `/forge:retro` | Run a cycle-completion retrospective after Stage 12 |

---

## Gate Enforcement

Every stage has **exit criteria**. Forge will not let you advance until gates pass:

- Stage 1 requires REQ-IDs in the SRS and an "Open Questions" section
- Stage 2 requires design tokens (`--color-`, `--font-`, `--space-` CSS variables) and WCAG accessibility notes
- Stage 3 requires at least one ADR in `pipeline/03-architecture/adr/`
- Stage 6 checks that all tasks are done before calling the build complete
- ...and so on through Stage 12

Gates are defined in `references/gate-criteria.md` and enforced by `scripts/check-gate.py`.
Blockers stop advancement; warnings are surfaced but don't block.

---

## Adaptive Project Profiles

Forge detects your project type at init and customizes the pipeline:

| Type | How it adapts |
|------|--------------|
| `api` | Adds OpenAPI spec step; emphasizes auth and rate-limiting gates |
| `fullstack` | Adds design system enforcement; CSS token gate in Stage 2 |
| `ml-pipeline` | Adds data contract step; GPU memory and drift detection lessons |
| `cli` | Skips UX flows; emphasizes help text and exit-code documentation |
| `library` | Emphasizes API stability and semver constraints |

Run `/forge:init` — Forge detects the type automatically, or you can override it.

---

## Memory and Lessons

Forge maintains three tiers of memory:

1. **Session context** — injected at every `SessionStart` via the hook; current stage, active task, blockers, relevant lessons
2. **Project memory** — `pipeline/` files accumulate decisions, reflections, and stage history across sessions
3. **Cross-project lessons** — `~/.forge/global-lessons.yaml` promotes high-frequency patterns across all your Forge projects

Lessons are extracted automatically after each stage completion. When a pattern appears
3+ times, Forge proposes a new skill you can approve, modify, or reject.

---

## How Hooks Work

Forge installs 7 lifecycle hooks that run silently alongside your Claude Code session:

| Hook | Fires | What it does |
|------|-------|-------------|
| `session-start.py` | Every session open | Injects current stage, task, blockers, top lessons (≤ 2 000 tokens) |
| `prompt-submit.py` | Every user message | Detects stage intent; flags corrections for lesson extraction |
| `pre-tool-write.py` | Before Write/Edit | Checks design token compliance, traceability, naming conventions |
| `post-tool-use.py` | After Write/Edit/Bash | Logs tool use; appends to `patterns.jsonl` for skill mining |
| `stop-reflect.py` | End of Claude turn | Evaluates output against gate criteria; surfaces skill proposals |
| `subagent-stop.py` | End of subagent turn | Captures subagent reflections |
| `session-end.py` | Session close | Writes session summary to `.forge/sessions/`; syncs lessons |

Hooks never block your work unless a blocker gate fires (exit code 2).

---

## Project Structure (After Init)

```
your-project/
├── pipeline/
│   ├── state.md              ← single source of truth (stage, task, blockers)
│   ├── 01-srs/               ← requirements
│   ├── 02-product-ux/        ← PRD, design system
│   ├── 03-architecture/      ← architecture docs, ADRs
│   ├── 04-spec/              ← technical and interface specs
│   ├── 05-plan/              ← task DAG, milestones
│   ├── 06-implementation/    ← progress tracker, decisions log
│   ├── 07-evaluation/        ← test results, eval report
│   ├── 08-deploy/            ← deploy plan and log
│   ├── 09-monitor/           ← observability config, incident log
│   ├── 10-feedback/          ← feedback log, triage
│   ├── 11-resolve/           ← hotfixes, backlog updates
│   └── 12-release/           ← release notes, checklist, retrospective
└── .forge/
    └── lessons.yaml          ← project-local lessons
```

---

## Configuration

No config file needed for basic use. Advanced options via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `FORGE_PROJECT_TYPE` | auto-detected | Override project type detection |
| `FORGE_MAX_LESSON_TOKENS` | `500` | Max tokens for lesson injection |
| `FORGE_LESSON_CAP` | `5` | Max lessons shown at session start |

---

## Testing Forge

The integration test runs the full pipeline against a sample Todo API project:

```bash
bash tests/integration/full-pipeline.sh
# PASS: full-pipeline integration test
#   29 artifacts present
#   12/12 stage gate checks passed
#   traceability chain intact (REQ → spec, FEAT → arch, T-IDs in plan)
```

Unit tests:

```bash
python3 -m pytest tests/ -q
# 532 passed
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and
[docs/agent-authoring.md](docs/agent-authoring.md) for step-by-step guides on:

- Adding a new agent persona
- Adding a pipeline stage
- Adding a project-type profile override

---

## Milestones

| Milestone | Status | Description |
|-----------|--------|-------------|
| M1: Core Skeleton | 🟢 Done | Plugin scaffold, state manager, `/forge:status` |
| M2: Hook System | 🟢 Done | 7 hooks across 6 lifecycle events |
| M3: Specialized Agents | 🟢 Done | 12 stage + 4 cross-stage agents |
| M4: Memory + Lessons | 🟢 Done | Lesson extraction, injection, cross-project memory |
| M5: Adaptive Workflow | 🟢 Done | Project type detection + 5 profiles |
| M6: Auto-Skill Creation | 🟢 Done | Pattern mining → skill proposals → approval flow |
| M7: Polish + Docs | 🟡 In progress | README, e2e test, packaging |

---

## License

MIT

## Author

Saddam · built with [Claude Code](https://claude.ai/code)
