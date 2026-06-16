![Forge — SDLC Orchestrator for Claude Code](assets/banner.svg)

> Forge turns Claude Code from a smart coding assistant into a disciplined
> engineering partner. Memory isn't the problem Claude Code solves poorly —
> **sequencing is**. Forge enforces it: gated stages, REQ-ID traceability,
> and structured lesson capture across projects.

[![Tests](https://img.shields.io/badge/tests-1237%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![Claude Code](https://img.shields.io/badge/claude--code-%3E%3D2.1.0-blueviolet)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)]()

---

## What Forge Does

Claude Code already has memory — `CLAUDE.md`, persistent project context, subagents,
Agent Teams. Forge does not try to out-remember it. What Claude Code does *not* enforce
is **process**: that requirements come before design, design before code, and that
nothing advances until the previous stage actually passed. That is the gap Forge fills.

Forge imposes a structured 12-stage pipeline — from requirements through release — where
**every stage has a gate that must pass before the next begins**, and **every line of
work traces back to a numbered requirement** (`REQ-NNN → gate → code → test`).

**Without Forge**: a capable assistant with no enforced sequencing — requirements drift,
design is skipped under deadline pressure, and "done" means whatever the last prompt
asked for.

**With Forge**: work proceeds only through gates you can inspect and, when justified,
explicitly override (`/forge:force-advance` records *why*). Nothing advances silently,
nothing is untraceable.

What is genuinely Forge's, not Anthropic's:

- **Gated sequencing** — stages block until their criteria pass; overrides are explicit
  and audited, not silent.
- **REQ-ID traceability** — every artifact, gate, and test links back to a requirement
  ID, end to end.
- **Structured cross-project lessons** — not free-text memory: tagged, filterable,
  tied to project profiles, and promoted across repos.
- **Automatic skill mining** — recurring *successful* workflows are detected in your
  own session traces (semantic, success-gated, anti-unified) and proposed as
  reusable skills for review. See [`references/skill-mining.md`](references/skill-mining.md).

> Traceability in practice — each artifact references the requirement it satisfies:
>
> ```
> SRS            REQ-GATE-003  "force-advance override records a lesson"
>   └─ Gate      G7-001        eval asserts the requirement is met
>        └─ Code  scripts/force-advance.py
>             └─ Test  tests/unit/test_force_advance.py  (17 cases)
> ```
>
> See [`docs/gate-philosophy.md`](docs/gate-philosophy.md) for when a gate should be
> resolved versus overridden.

---

## Prerequisites

- **Claude Code** ≥ 2.1.0
- **Python** ≥ 3.11 (on PATH)
- **pyyaml**: `pip install pyyaml`

---

## Install

In Claude Code, run these two commands:

```
/plugin marketplace add tonmoy007/forge-plugins
/plugin install forge@forge-plugins
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
| `/forge:status` | Show current stage, task, blockers, Observer status, and recent history |
| `/forge:resume` | Restore context after a session restart |
| `/forge:retro` | Run a cycle-completion retrospective after Stage 12 |
| `/forge:why` | Explain a gate criterion, lesson tag, stage, or current blocker |
| `/forge:set-profile` | Set the project-type profile (api, library, cli, monorepo, …) |
| `/forge:rules` | Author project rules that steer agents (`init`/`add`/`list`/`validate`) — advisory, scope-based |
| `/forge:review` | Fan four reviewers (correctness/security/performance/conventions) over a diff and synthesize one report |
| `/forge:adopt` | Brownfield onboarding — detect type, infer SRS + architecture drafts, seed pipeline state |
| `/forge:autopilot` | Run pipeline stages hands-off (self-heal, optional verify, `--unattended`); `--resume`, `--mode` |
| `/forge:autopilot-stop` | Halt a running autopilot cleanly at the next stage boundary |
| `/forge:sprint` | Group the task DAG into bounded sprints and review them (`plan`/`review`/`list`) — opt-in |

### Background Daemons

Optional, cost-capped background agents (Milestone 2). Each reuses **one** cheap-model
session, runs within a configurable spend cap, and is **capability-gated** — a clean
no-op when background agents aren't available, so nothing breaks if the feature is off.

| Command | What it does |
|---------|-------------|
| `/forge:watch` | Start the **Observer** — periodically records findings (risky changes, missing tests, drift) to `.forge/observer-findings.jsonl`, surfaced at session start and in `/forge:status` |
| `/forge:watch-stop` | Stop the Observer, preserving its last poll output and findings |
| `/forge:dreamer-run` | Run the **Dreamer** — consolidate lessons: confidence decay, duplicate & contradiction detection (flag-only), and a daily digest |
| `/forge:health-check` | Run the **Health** daemon — hook-test + lesson-store integrity → `healthy / degraded / failing`; never silently disables anything |

Background work records actual API cost to `.forge/cost-ledger.jsonl` and stops at the
daily cap. See `references/daemon-bus.md` for the findings/poll contract.

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
| `monorepo` | Cross-package architecture + build orchestration; acyclic dependency-graph gate |
| `mobile` | UI-heavy (Flutter/RN/iOS/Android); platform UX + app-store readiness gate |
| `data-contract` | Schema-first (Protobuf/Avro/GraphQL/dbt); schema-hygiene + compatibility gate |

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

## Project Rules

Author project-specific constraints that steer Forge's agents — a scoped, Forge-native
take on Cursor's `.cursor/rules`. Rules live in `.forge/rules/*.md` (YAML frontmatter +
a markdown body) and are **advisory**: they nudge the agents and surface as context, but
never block a write.

```bash
/forge:rules init                                   # scaffold .forge/rules/ (README + example)
/forge:rules add no-bare-except --scope glob        # add a new rule from a template
/forge:rules list                                   # show active rules
/forge:rules validate                               # check frontmatter / scopes
```

Each rule's **scope** decides when it activates:

| Scope | Activates | Surfaces |
|-------|-----------|----------|
| `always` | every session | session-start context block |
| `stage` | when on a listed pipeline stage | session-start context block |
| `glob` | when writing a file matching `globs` | advisory feedback before the write |
| `manual` | never automatically | referenced by name |

Example — `.forge/rules/00-style.md`:

```markdown
---
description: House style for UI components
scope: glob
globs: ["**/*.tsx"]
---
Prefer composition over inheritance; use design tokens, not raw values.
```

Rules share the session-start token budget with lessons and degrade to a clean no-op
when `.forge/rules/` is absent. Full schema: `references/rules-format.md`.

---

## Autopilot

Hand Forge the wheel. `/forge:autopilot` runs pipeline stages back-to-back — for each
stage it runs the stage's agent, checks the gate, and **advances only on a pass**. On a
blocking gate it now **self-heals** (a bounded `/forge:resolve` fix, then re-checks)
before stopping — and never forces past a gate.

```bash
/forge:autopilot                 # run from the current stage to the end of the cycle
/forge:autopilot to stage 7      # run through a target stage
/forge:autopilot the next 3      # run a bounded number of stages
/forge:autopilot --unattended    # fully hands-free (no checkpoints; assumptions logged)
/forge:autopilot --resume        # continue after a stop (skips done stages)
/forge:autopilot-stop            # halt cleanly at the next stage boundary
```

**Complete (local) autonomy (v0.3.3):**
- **Self-heal** — a blocking gate triggers a bounded fix via `/forge:resolve`
  (`autopilot.max_heal_attempts`, default 1; `0` = classic stop-on-gate), then a re-gate.
- **Self-verify** — with `autopilot.verify: true`, a passing gate is double-checked by an
  independent fresh-context verifier; a fail routes back into the heal loop.
- **`--unattended`** — no per-stage checkpoints; interactive stages use
  `.forge/autopilot-answers.{json,yaml}` or record **explicit assumptions** (never a silent
  guess). Bounded by the full safety envelope; any bound STOPS cleanly and resumably.
- **Enforcing rules** — a `.forge/rules/*.md` glob rule with `enforce: true` hard-blocks
  writes to matching paths (e.g. lockfiles, secrets) — the guardrail that makes hands-off
  runs safe. See [Project Rules](#project-rules).

**Context-aware — checkpoint → compact → continue (v0.3.6, opt-in):** a long hands-off run
survives a context boundary without losing its place. Set `autopilot.context_window_size`
(tokens) to enable; the run then checkpoints and, in **background** mode, rotates to a fresh
session once a dispatch's context crosses `autopilot.context_threshold_percent` (default
80). **In-session**, a `PreCompact` hook writes the checkpoint before Claude Code's native
auto-compaction and `SessionStart` re-injects "resume at stage N — don't redo completed
stages" after. Off entirely until `context_window_size` is set. See
[`references/autopilot-context.md`](references/autopilot-context.md).

**Safety rails:** never forces a gate unless you opt in (`autopilot.allow_force` + a
reason); bounded by `max_stages` / `stop_before`, `max_heal_attempts`, `max_budget_usd`,
and the `_cost_cap` ledger; interruptible with `/forge:autopilot-stop` and the
`FORGE_NO_BACKGROUND=1` kill switch. Two substrates via `--mode`: **in-session** (default —
reuses the stage agents, no extra spend) or **background** (`claude -p` per stage,
cost-capped + capability-gated; a clean no-op when background agents are off).

It generalizes `/forge:force-advance` (one gated advance) and `/forge:build --milestone`
(a within-stage batch) to a cross-stage loop. Configure under `autopilot:` in
`.forge/config.yaml` — including `models` (per-stage model routing — a capable model for
hard stages, a cheap one for checks), `max_budget_usd` (per-dispatch spend ceiling),
`session_max_dispatches` (rotate a long reused session to bound context),
`max_heal_attempts`, and `verify`. Background stages also request schema-constrained
output via the CLI's `--json-schema`.

---

## Sprints

`/forge:sprint` slices your task DAG into bounded, reviewable chunks. It is a deterministic
**view over `pipeline/05-plan/task-dag.md`** (T-IDs are the identity) — the DAG and
`progress.md` stay the source of truth, and it is **fully opt-in** (a project that never
runs it sees no change).

```bash
/forge:sprint plan              # commit the next ready tasks to pipeline/05-plan/sprint-NN.md
/forge:sprint plan --size 6     # target a different sprint size (default 5)
/forge:sprint review            # report done vs. carried → pipeline/12-release/sprint-NN-review.md
/forge:sprint list              # sprints and their progress
```

`plan` selects the next ready tasks in dependency order and **carries over** anything from
the previous sprint that is not yet done — keeping each task's T-ID, so history follows the
work across sprints.

Cross-machine note: see [`docs/forge-sync.md`](docs/forge-sync.md) for syncing `~/.forge`
global lessons between machines (no server) and the opt-in, local-only skill-mining
telemetry (off by default; data never leaves your machine without an explicit export).

---

## How Hooks Work

Forge installs 7 lifecycle hooks that run silently alongside your Claude Code session:

| Hook | Fires | What it does |
|------|-------|-------------|
| `session-start.py` | Every session open | Injects current stage, task, blockers, top lessons, and active `always`/`stage` rules (≤ 2 000 tokens) |
| `prompt-submit.py` | Every user message | Detects stage intent; flags corrections for lesson extraction |
| `pre-tool-write.py` | Before Write/Edit | Checks design token compliance; surfaces matching `glob` project rules (advisory) |
| `post-tool-use.py` | After Write/Edit/Bash | Logs each tool call to `session-log.jsonl` (the semantic skill miner's source trace) |
| `stop-reflect.py` | End of Claude turn | Evaluates output against gate criteria; surfaces skill proposals |
| `subagent-stop.py` | End of subagent turn | Captures subagent reflections |
| `session-end.py` | Session close | Writes session summary to `.forge/sessions/`; syncs lessons |

Hooks never block your work unless a blocker gate fires (exit code 2).

---

## If something looks wrong

1. Run **`/forge:doctor`** — it reports environment, plugin, and current-stage
   gate health (`healthy` / `wedged` / `broken`) and usually names the exact fix.
2. Seeing a cryptic `PreToolUse` / `Stop` hook error that doesn't mention a Forge
   path? It's probably from **another plugin's hook**, not Forge — see
   [Troubleshooting third-party plugin hooks](docs/getting-feedback.md#troubleshooting-third-party-plugin-hooks).
   (Forge's only `PreToolUse` hook is `hooks/pre-tool-write.py`.)
3. Found a real Forge bug? File it with the
   [feedback issue template](.github/ISSUE_TEMPLATE/forge-feedback.md).

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
# 1237 passed
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and
[docs/agent-authoring.md](docs/agent-authoring.md) for step-by-step guides on:

- Adding a new agent persona
- Adding a pipeline stage
- Adding a project-type profile override

---

## License

MIT

## Author

Saddam · built with [Claude Code](https://claude.ai/code)
