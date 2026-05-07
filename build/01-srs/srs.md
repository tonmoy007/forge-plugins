# SRS — Forge Plugin

> Software Requirements Specification.
> The complete, testable list of what the Forge plugin must do.
> Every requirement has an ID. Every task in the DAG references one or more REQ-IDs.

---

## 1. Overview

### 1.1 Purpose
Forge is a Claude Code plugin that orchestrates a 12-stage SDLC pipeline through specialized
agents, persistent memory, automatic reflection, and adaptive workflows.

### 1.2 Scope
**In scope**: Plugin code, hooks, skills, agents, scripts, references, and tests for delivery
as a Claude Code plugin (v2.1+).

**Out of scope** (for v0.1.0):
- Web UI / dashboard outside the CLI
- Cloud-hosted memory (everything is local files)
- Non-Claude-Code platforms (Cursor, Copilot, etc.)
- IDE plugins (VS Code, JetBrains) — those use Claude Code CLI internally
- Multi-user collaboration features (single developer initially)

### 1.3 Stakeholders
- **Primary user**: Software developer using Claude Code daily, wanting structured workflow
  with memory and learning
- **Secondary**: Teams adopting Forge for shared conventions across a project
- **Maintainer**: This repo's owner

---

## 2. Functional Requirements

### 2.1 Pipeline State Machine

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| REQ-001 | Pipeline has 12 ordered stages | Stages 1–12: SRS, Product, Architecture, Spec, Plan, Build, Eval, Deploy, Monitor, Feedback, Resolve, Release |
| REQ-002 | Pipeline state persisted | `pipeline/state.md` updated after every stage transition; survives session restarts |
| REQ-003 | Stage transitions gated | Cannot advance without exit criteria met (or explicit user override with logged justification) |
| REQ-004 | Resumable from any stage | `state.md` + artifacts on disk are sufficient to continue work in a new session |
| REQ-005 | Cycle types supported | New feature (1→12), iteration (5→12), hotfix (6→9), tech debt (3→8) |

### 2.2 Slash Commands

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| REQ-010 | One command per stage | `/forge:srs`, `/forge:product`, `/forge:arch`, `/forge:spec`, `/forge:plan`, `/forge:build`, `/forge:eval`, `/forge:deploy`, `/forge:monitor`, `/forge:feedback`, `/forge:resolve`, `/forge:release` |
| REQ-011 | Pipeline management commands | `/forge:init`, `/forge:status`, `/forge:resume`, `/forge:retro` |
| REQ-012 | Each command is a Skill | Has SKILL.md with frontmatter, lives in `skills/` |
| REQ-013 | Commands invoke specialized agents | Each `/forge:<stage>` spawns the corresponding agent with scoped context |

### 2.3 Specialized Agents

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| REQ-020 | 12 stage agents | One persona file per stage in `agents/` with role, goal, tools, context scope, output contract |
| REQ-021 | 4 cross-stage agents | Reflector, lesson-extractor, skill-miner, gate-checker |
| REQ-022 | Agent tool restrictions | Each agent has `allowed-tools` in frontmatter limiting what it can do (e.g., SRS agent has no Bash) |
| REQ-023 | Agent context scoping | Each agent reads only the artifacts it needs (no full pipeline dump) |
| REQ-024 | Agent output contracts | Each agent's persona specifies what files/sections it must produce |

### 2.4 Lifecycle Hooks

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| REQ-030 | SessionStart hook | Loads pipeline state, lessons, design system summary into context (< 2000 tokens) |
| REQ-031 | UserPromptSubmit hook | Detects stage intent, prunes context, flags corrections for lesson extraction |
| REQ-032 | PreToolUse hook (Write/Edit) | Audits UI files for raw values vs design tokens; returns feedback as additionalContext |
| REQ-033 | PostToolUse hook | Async-logs tool calls, tracks task progress, counts patterns |
| REQ-034 | Stop hook | Runs 4-step pipeline: reflect → extract lessons → check gates → mine skills |
| REQ-035 | SubagentStop hook | Captures subagent output, updates state.md |
| REQ-036 | SessionEnd hook | Persists final state, writes session summary |
| REQ-037 | Hook latency budget | Total hook overhead < 200ms per event |
| REQ-038 | Hook failure isolation | A failing hook never breaks the session; logs error, continues |

### 2.5 Memory System

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| REQ-040 | Tier 1: Session memory | Injected by SessionStart hook into context (< 2000 tokens budget) |
| REQ-041 | Tier 2: Project memory | Files in `pipeline/`, `tasks/`, `.forge/` within the project |
| REQ-042 | Tier 3: Cross-project memory | Files in `~/.forge/` shared across all Forge-managed projects |
| REQ-043 | Lesson promotion | Lesson used in 3+ projects → graduates to Tier 3 |
| REQ-044 | Lesson injection by relevance | SessionStart filters lessons by current stage tags + project type |
| REQ-045 | Machine-readable lessons | `.forge/lessons.yaml` mirrors `tasks/lessons.md` for hook parsing |

### 2.6 Auto-Reflection

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| REQ-050 | Reflection on every Stop | Every Stop event produces a 1-line reflection in pipeline/state.md |
| REQ-051 | Gate-aware reflection | Compares output to current stage's gate criteria, lists gaps |
| REQ-052 | Correction-triggered deep reflection | User corrections trigger root-cause analysis + lesson proposal |
| REQ-053 | Stage-completion retrospective | When a stage gate passes, a full retro is written to that stage's folder |
| REQ-054 | Cycle-completion retrospective | `/forge:retro` after Stage 12 produces full cycle review |

### 2.7 Adaptive Workflow

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| REQ-060 | Project type detection | `forge-init` detects from file structure: api, fullstack, ml-pipeline, cli, library |
| REQ-061 | Type-specific stage emphasis | ML projects skip wireframes, API projects simplify design system, etc. |
| REQ-062 | Type-specific gate criteria | Each profile adds/removes criteria from base set (defined in `references/project-type-profiles.md`) |
| REQ-063 | Profile override by user | User can manually set profile via `/forge:init --type=<type>` |
| REQ-064 | Per-project learned preferences | Conventions used 3+ times become project profile entries in `~/.forge/project-profiles.md` |

### 2.8 Auto-Skill Creation

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| REQ-070 | Pattern tracking | PostToolUse logs tool sequences to `.forge/patterns.jsonl` |
| REQ-071 | Frequency threshold | Patterns proposed as skills only after ≥3 occurrences |
| REQ-072 | Skill draft generation | Skill-miner agent produces SKILL.md draft from pattern |
| REQ-073 | User approval required | Generated skills are not auto-installed; user approves/modifies/rejects |
| REQ-074 | Rejected pattern blacklist | Rejected patterns don't get re-proposed |

### 2.9 Design System Enforcement

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| REQ-080 | Token audit on UI writes | PreToolUse on `.tsx/.jsx/.vue/.svelte/.css/.html` scans for raw values |
| REQ-081 | Detected violations | Hex colors, raw px values, raw font families, ad-hoc z-index, `!important` |
| REQ-082 | Feedback-only enforcement | Hook returns additionalContext suggesting tokens; doesn't block |
| REQ-083 | Stage-aware activation | Only runs in Stage 6 (Build) and after; skipped in pre-build stages |

### 2.10 Traceability

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| REQ-090 | ID chain enforced | REQ-XXX → FEAT-XXX → Component → T-XXX → commit → test |
| REQ-091 | Trace verification command | Script that reads all artifacts and verifies chain integrity |
| REQ-092 | Broken-trace alerts | Reflector flags requirements without tasks, tasks without tests |

---

## 3. Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Performance | Hook latency overhead | < 200ms per event total |
| NFR-002 | Performance | Plugin install time | < 30 seconds from `claude plugin install` |
| NFR-003 | Performance | Context overhead from SessionStart | < 2000 tokens |
| NFR-004 | Reliability | Offline operation | All core features work without network |
| NFR-005 | Compatibility | Claude Code version | v2.1.0+ (hooks v2, skills, custom agents) |
| NFR-006 | Safety | Source code modification | Never without explicit user approval |
| NFR-007 | Reliability | Hook idempotency | Re-running any hook produces the same result |
| NFR-008 | Reliability | Graceful hook failure | Failed hook logs error, doesn't break session |
| NFR-009 | Maintainability | Python version | 3.11+ |
| NFR-010 | Maintainability | Hook dependencies | stdlib only (heavy deps go in scripts/) |
| NFR-011 | Maintainability | Test coverage | > 80% on hooks/ and scripts/ |
| NFR-012 | Usability | Time to first stage | < 5 minutes from install to `/forge:srs` working |
| NFR-013 | Privacy | No telemetry | Zero data leaves the user's machine without explicit action |

---

## 4. Constraints

- **Platform**: Claude Code v2.1+ only (uses hooks v2, plugins API, custom agents)
- **Language**: Python 3.11+ for hooks/scripts; Markdown for skills/agents
- **License**: MIT (TBD)
- **Distribution**: Plugin marketplace (when ready), manual `--plugin-dir` for now

---

## 5. Assumptions

- Users have Python 3.11+ available on PATH
- Users are working on local filesystems (not cloud-only environments)
- Users will accept that lessons and patterns are stored as plain text
- Claude Code's hooks API is stable enough through v2.1 lifecycle

---

## 6. Open Questions

> Track these here. Each must be resolved or explicitly deferred before final release.

| Q | Question | Status | Owner |
|---|----------|--------|-------|
| Q-001 | How to handle lessons that conflict across projects? | Open | TBD |
| Q-002 | Should `~/.forge/` be sync-able across machines? | Deferred to v0.2 | — |
| Q-003 | Marketplace publication path? | Open | Pending Claude Code marketplace launch |
| Q-004 | Telemetry for skill mining (anonymized) — opt-in? | Deferred to v0.2 | — |

---

## 7. Glossary

- **Stage**: One of 12 discrete phases in the pipeline (e.g., SRS, Architecture)
- **Gate**: Set of exit criteria that must pass before advancing to the next stage
- **Agent**: A specialized Claude subagent with a tuned persona and scoped tools
- **Hook**: Shell command or script run by Claude Code at a lifecycle event
- **Skill**: A folder with SKILL.md that creates a slash command and/or auto-invocable behavior
- **Pattern**: A repeated sequence of tool calls or instructions, candidate for skill mining
- **Lesson**: An actionable rule extracted from user corrections, stored in lessons.md
- **Profile**: A project-type-specific override of stage emphasis and criteria
- **Tier 1/2/3**: Memory layers — session context / project files / cross-project files
