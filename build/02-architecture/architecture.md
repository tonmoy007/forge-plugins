# Architecture — Forge Plugin

> System architecture for the Forge Claude Code plugin.
> References: `01-srs/srs.md` for requirements.
> **v0.2 delta**: see `architecture-v0.2.md` (daemons, orchestration, brownfield,
> sprint) — it composes with this base and resolves OQ-001…OQ-008.

---

## 1. Component Map

```
┌──────────────────────────────────────────────────────────────────────┐
│                           Claude Code Session                         │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                  Forge Plugin Components                      │    │
│  │                                                               │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────────────┐ │    │
│  │  │ Hooks   │  │ Skills  │  │ Agents  │  │ Scripts/Refs   │ │    │
│  │  │ (7)     │  │ (16)    │  │ (16)    │  │ (helpers)      │ │    │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────────┬───────┘ │    │
│  │       │            │            │                 │         │    │
│  │       └────────────┴────────────┴─────────────────┘         │    │
│  │                          │                                   │    │
│  │                          ▼                                   │    │
│  │           ┌──────────────────────────────┐                  │    │
│  │           │   State + Memory Subsystem    │                  │    │
│  │           │  (state.md, lessons.yaml,    │                  │    │
│  │           │   patterns.jsonl)            │                  │    │
│  │           └──────────────────────────────┘                  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              Project Filesystem (Tier 2)                      │    │
│  │                                                               │    │
│  │  pipeline/state.md          tasks/lessons.md                  │    │
│  │  pipeline/01-srs/...        tasks/todo.md                     │    │
│  │  pipeline/02-product-ux/    .forge/patterns.jsonl             │    │
│  │  pipeline/.../              .forge/lessons.yaml               │    │
│  │                             .forge/sessions/                  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│                              ▲                                       │
│                              │                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │             User Filesystem (~/.forge/) — Tier 3             │    │
│  │                                                               │    │
│  │  ~/.forge/global-lessons.md                                   │    │
│  │  ~/.forge/project-profiles.md                                 │    │
│  │  ~/.forge/skill-library/                                      │    │
│  │  ~/.forge/config.yaml                                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Boundaries

### 2.1 Hooks (`hooks/`)
**Responsibility**: React to Claude Code lifecycle events. Read state, inject context,
enforce gates, log activity.

**Boundary rules**:
- stdlib only (latency budget)
- No filesystem writes outside `pipeline/`, `tasks/`, `.forge/`
- Never modifies user source code
- Exit code 2 only when explicitly blocking (Stop with unmet gates)

### 2.2 Skills (`skills/`)
**Responsibility**: User-facing slash commands. One folder per command, each with SKILL.md.

**Boundary rules**:
- No code execution in SKILL.md (it's instructions, not Python)
- Each skill invokes one or more agents
- Helper scripts called by skills go in `scripts/`

### 2.3 Agents (`agents/`)
**Responsibility**: Specialized personas with role, goal, allowed tools, context scope, output contract.

**Boundary rules**:
- One agent per file
- Frontmatter declares `allowed-tools`, `model` (optional), `context-scope`
- Body contains persona, instructions, examples
- Agents communicate only via filesystem (write to artifacts, read from prior artifacts)

### 2.4 Scripts (`scripts/`)
**Responsibility**: Deterministic helpers callable from skills, hooks, or CLI.

**Boundary rules**:
- Can use third-party deps (declared in `requirements.txt`)
- Each script is self-contained, takes JSON or args, returns JSON or exit code
- Each script has a corresponding test in `tests/unit/`

### 2.5 References (`references/`)
**Responsibility**: Reference docs loaded on-demand by skills.

**Boundary rules**:
- Markdown only
- No code, no instructions to execute — informational
- Loaded by skills via explicit `Read` calls when relevant

---

## 3. Data Flow

### 3.1 Session Start

```
SessionStart event
    │
    ▼
session-start.py hook reads:
    ├── pipeline/state.md (current stage, task)
    ├── tasks/lessons.md (filtered by stage relevance)
    ├── ~/.forge/global-lessons.md (filtered)
    └── pipeline/02-product-ux/design-system.md (summary if Stage 6+)
    │
    ▼
Compose < 2000-token context block
    │
    ▼
stdout → injected into Claude's session context
```

### 3.2 User Invokes /forge:build

```
User types "/forge:build"
    │
    ▼
UserPromptSubmit hook:
    ├── Detects stage 6 intent
    └── Returns additionalContext: stage 6 instructions
    │
    ▼
Claude loads skills/forge-build/SKILL.md
    │
    ▼
SKILL.md instructs Claude to spawn 'builder' agent
    │
    ▼
Builder agent (separate context) reads:
    ├── pipeline/04-plan/task-dag.md
    ├── pipeline/03-spec/technical-spec.md
    ├── pipeline/02-product-ux/design-system.md
    └── tasks/lessons.md (Stage 6 tagged)
    │
    ▼
Builder works through DAG: Read → Edit → test
    │
    ▼
PreToolUse[Write|Edit] for each UI file:
    └── Token audit, returns feedback if violations
    │
    ▼
PostToolUse for each tool call:
    └── Log to session-log.jsonl, update progress.md
    │
    ▼
Builder finishes (SubagentStop)
    │
    ▼
Stop hook pipeline runs:
    ├── 1. Reflector: assess against gate criteria
    ├── 2. Lesson extractor: detect corrections
    ├── 3. Gate checker: pass/warn/block
    └── 4. Skill miner: pattern frequency check
```

### 3.3 Session End

```
SessionEnd event
    │
    ▼
session-end.py hook:
    ├── Final pipeline/state.md persist
    ├── Write .forge/sessions/<timestamp>.md
    └── Update .forge/patterns.jsonl
```

---

## 4. State + Memory Architecture

### 4.1 Three-Tier Layout

| Tier | Location | Lifetime | Purpose |
|------|----------|----------|---------|
| 1 | Session context (in-memory) | Until session ends | Active working knowledge |
| 2 | Project files | Until project deleted | Per-project state, lessons, decisions |
| 3 | `~/.forge/` | Permanent | Cross-project knowledge |

### 4.2 State File Format (`pipeline/state.md`)

Markdown with YAML frontmatter for machine reading:

```markdown
---
schema_version: 1
project_type: ml-pipeline
cycle: 1
current_stage: 6
current_task: T-007
current_milestone: 2
total_tasks: 23
last_updated: 2026-05-05T14:32:00Z
blockers: []
---

# Pipeline State

## Stage History
| Stage | Started | Completed | Gate | Notes |
|-------|---------|-----------|------|-------|
| 1 | 2026-04-28 | 2026-04-28 | passed | |
...

## Last Reflection
*(written by reflector agent on each Stop)*
```

### 4.3 Lesson File Format

Human-readable: `tasks/lessons.md` (markdown)
Machine-readable mirror: `.forge/lessons.yaml` (regenerated on session start)

```yaml
# .forge/lessons.yaml
lessons:
  - id: L-001
    stage: [6]
    project_types: [ml-pipeline]
    trigger: "Fine-tuning on T4 GPU"
    rule: "T4 lacks bf16 support — use fp16 with manual cast after 4-bit load"
    why: "Wasted session on silent dtype mismatch"
    frequency: 3
    last_used: 2026-05-01
    tags: [gpu, dtype]
```

### 4.4 Pattern File Format (`.forge/patterns.jsonl`)

Append-only JSONL, one event per line:

```json
{"ts": "2026-05-05T14:32:00Z", "session": "abc", "kind": "tool_seq", "tools": ["Read", "Edit", "Bash"], "context": "fixing test"}
{"ts": "2026-05-05T14:35:00Z", "session": "abc", "kind": "instruction", "text": "always run pytest -x after editing tests/"}
```

Aggregation runs in `mine-skills.py` to produce skill candidates.

---

## 5. Hook Interaction Model

### 5.1 Hook Registry

| Event | Matcher | Hook | Async | Timeout |
|-------|---------|------|-------|---------|
| SessionStart | "" | session-start.py | no | 5s |
| UserPromptSubmit | "" | prompt-submit.py | no | 3s |
| PreToolUse | Write\|Edit\|MultiEdit | pre-tool-write.py | no | 3s |
| PostToolUse | Write\|Edit\|MultiEdit\|Bash | post-tool-use.py | yes | 5s |
| Stop | "" | stop-reflect.py | no | 15s |
| SubagentStop | "" | subagent-stop.py | no | 5s |
| SessionEnd | "" | session-end.py | yes | 10s |

### 5.2 Hook I/O Contract

**Input** (stdin, JSON):
```json
{
  "session_id": "...",
  "hook_event_name": "Stop",
  "transcript_path": "/path/to/transcript",
  ...
}
```

**Output** (stdout):
- Plain text → injected into Claude's context (SessionStart, UserPromptSubmit)
- JSON with `hookSpecificOutput` → structured response (PreToolUse, Stop)
- Empty → no-op

**Exit codes**:
- 0: success
- 2: blocking signal (PreToolUse: deny tool; Stop: prevent stop)
- Other: log warning to user, continue

---

## 6. Agent Architecture

### 6.1 Agent Definition

Each agent is a Markdown file with frontmatter:

```markdown
---
name: requirements-analyst
description: Stage 1 agent. Extracts complete, testable requirements from vague input.
allowed-tools: [Read, Write, WebSearch, Grep]
model: claude-sonnet-4-6  # optional override
---

# Requirements Analyst

## Role
Senior business analyst / product strategist with 15+ years of...

## Goal
Extract a complete SRS with REQ-IDs from user input...

## Context Scope
You read ONLY:
- User's input describing the project
- (No prior pipeline artifacts — this is Stage 1, fresh start)

## Output Contract
You MUST produce:
- pipeline/01-srs/srs.md with all REQ-IDs and acceptance criteria
- pipeline/01-srs/stakeholder-map.md if stakeholder info is provided

## Workflow
1. Ask one bounded round of clarifying questions on ambiguity (a single batch, not a drip), then proceed and record assumptions for anything unanswered (REQ-INTERACTIVE-CLARIFY-001)
2. Categorize requirements: functional, non-functional, constraints
3. Assign IDs (REQ-001, REQ-002, ...)
4. Write acceptance criteria (testable, measurable)
5. List open questions explicitly
```

### 6.2 Agent Spawning

Skills spawn agents via Claude's subagent mechanism. Example skill:

```markdown
# /forge:srs

[Read references/agent-personas.md to load the requirements-analyst persona]

Adopt the requirements-analyst persona. Your task: produce pipeline/01-srs/srs.md from the user's project description.

User input follows.
```

The skill loads the persona, the agent runs in its scoped context, output lands in
`pipeline/01-srs/`. The Stop hook then validates against Stage 1 gate criteria.

---

## 7. Failure Modes

| Failure | Detection | Response |
|---------|-----------|----------|
| Hook script crashes | Non-zero exit, stderr | Log to `.forge/errors.log`, continue session |
| State.md corrupted | YAML parse error in session-start | Restore from last `.forge/sessions/<latest>` snapshot |
| Lessons.yaml out of sync | Hash mismatch with lessons.md | Regenerate from markdown |
| Gate check ambiguous | Agent can't determine pass/fail | Default to "warn" (not block); log for human review |
| Pattern miner misfires | User rejects 3 proposed skills | Increase threshold for that pattern type, blacklist signature |
| Cross-project lesson conflicts with project lesson | Different rules same trigger | Project lesson wins; log conflict |
| Plugin reload mid-session | `/reload-plugins` called | All hooks re-register; in-flight state preserved |

---

## 8. Security Considerations

- **Hook scripts run in user context** — they have full filesystem access
- **No remote calls in hooks** by default (except WebSearch by agents, which is opt-in via tool restriction)
- **No credentials stored** in any Forge-managed files
- **Pattern logging** captures tool names + file paths but never file contents
- **Lesson extraction** stores user's own corrections — no external transmission

---

## 9. Versioning

| File | Schema versioned? | Migration strategy |
|------|-------------------|--------------------|
| pipeline/state.md | Yes (`schema_version`) | Migration scripts in `scripts/migrate/` |
| .forge/lessons.yaml | Yes | Regenerated from .md on schema change |
| .forge/patterns.jsonl | No | Append-only; old entries ignored if format changes |
| ~/.forge/* | Yes | User prompted on schema change |

Plugin version (in `plugin.json`) follows semver:
- Patch: bug fixes, no schema change
- Minor: new features, backward-compatible schema
- Major: breaking schema change, requires migration

---

## 10. Architecture Decision Records

ADRs live in `02-architecture/adr/`. Initial decisions:

- ADR-001: Hooks are Python (not Bash) — see `adr/001-python-hooks.md`
- ADR-002: Lessons stored as both Markdown and YAML — see `adr/002-dual-lesson-format.md`
- ADR-003: Cross-stage agents are hook-triggered, not user-invoked — see `adr/003-cross-stage-agents.md`
- ADR-004: Stop hook does sequential pipeline (not parallel) — see `adr/004-stop-hook-sequential.md`

**v0.2 additions** (see the delta `architecture-v0.2.md`):

- ADR-005: Daemons are detached one-shot dispatches, not resident processes — see `adr/005-daemon-execution-model.md`
- ADR-006: Orchestration primitive wraps in-session subagents with a structured contract — see `adr/006-orchestration-primitive.md`
- ADR-007: Cost cap is a hard prerequisite gate on a two-phase ledger — see `adr/007-cost-cap-hard-gate.md`

---

## 11. Traceability

Every component traces back to a REQ-ID:

| Component | Maps to |
|-----------|---------|
| State machine | REQ-001, REQ-002, REQ-003, REQ-004, REQ-005 |
| Slash commands | REQ-010, REQ-011, REQ-012, REQ-013 |
| Stage agents | REQ-020, REQ-022, REQ-023, REQ-024 |
| Cross-stage agents | REQ-021 |
| Hook scripts | REQ-030 to REQ-038 |
| Memory tiers | REQ-040 to REQ-045 |
| Reflector agent | REQ-050 to REQ-054 |
| Project profiles | REQ-060 to REQ-064 |
| Skill miner | REQ-070 to REQ-074 |
| pre-tool-write.py | REQ-080 to REQ-083 |
| traceability-check.py | REQ-090 to REQ-092 |
