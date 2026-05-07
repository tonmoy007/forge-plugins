# ROADMAP.md

> Milestone tracker. For full task DAG with dependencies, see `build/04-plan/task-dag.md`.

## Status Legend

- 🔲 Not started
- 🟡 In progress
- 🟢 Done
- 🔴 Blocked

---

## M1: Core Skeleton — "Pipeline works manually" 🔲

**Goal**: A user can install the plugin, run `/forge:init`, and see `/forge:status`
display the current pipeline state. No hooks yet, no agents yet — just the plumbing.

| Task | Status | Notes |
|------|--------|-------|
| T-001: Plugin scaffolding (plugin.json, dirs) | 🔲 | |
| T-002: forge-init skill (scaffold pipeline/) | 🔲 | |
| T-003: state-manager.py script | 🔲 | |
| T-004: forge-status skill | 🔲 | |
| T-005: gate-criteria.md reference (machine-readable) | 🔲 | |
| T-006: check-gate.py script | 🔲 | |

**Definition of done**: `claude plugin install --plugin-dir .` works, `/forge:init` scaffolds
a pipeline, `/forge:status` reads the state, `check-gate.py --stage 1` returns valid JSON.

---

## M2: Hook System — "Pipeline enforces itself" 🔲

**Goal**: All 7 hooks fire at the right lifecycle events. Pipeline state is automatically
loaded into context. Design system enforcement runs on file writes. Stop hook does basic
reflection + gate check.

| Task | Status | Notes |
|------|--------|-------|
| T-007: session-start.py hook | 🔲 | |
| T-008: prompt-submit.py hook | 🔲 | |
| T-009: stop-reflect.py hook | 🔲 | |
| T-010: session-end.py hook | 🔲 | |
| T-011: pre-tool-write.py hook (design system) | 🔲 | |
| T-012: post-tool-use.py hook (decision logger) | 🔲 | |
| T-013: Wire all hooks into plugin.json | 🔲 | |

**Definition of done**: opening a Claude Code session in a Forge-managed project shows the
`[Forge]` context block. Writing `color: #3b82f6` in a UI file triggers a token suggestion.
The `Stop` hook produces a reflection log entry.

---

## M3: Specialized Agents — "Each stage has a brain" 🔲

**Goal**: All 12 stage agents and 4 cross-stage agents are written and wired to skills.
Each `/forge:*` command spawns the right agent with the right tools and context.

| Task | Status | Notes |
|------|--------|-------|
| T-014: Write all 12 stage agent personas | 🔲 | Large task — split per agent |
| T-015: Write all 12 stage skills (SKILL.md) | 🔲 | Wires skill → agent |
| T-016: Write 4 cross-stage agents | 🔲 | reflector, lesson-extractor, skill-miner, gate-checker |
| T-017: context-pruner.py script | 🔲 | Stage-aware artifact selection |
| T-018: forge-resume skill | 🔲 | |

**Definition of done**: `/forge:srs` spawns the requirements analyst agent with a clean
context (no architecture/spec leakage), produces `srs.md` with REQ-IDs.

---

## M4: Memory + Lessons — "Pipeline learns from mistakes" 🔲

**Goal**: User corrections become lessons automatically. Lessons inject into relevant
sessions. Cross-project lessons graduate to `~/.forge/`.

| Task | Status | Notes |
|------|--------|-------|
| T-019: extract-lessons.py script | 🔲 | |
| T-020: Lesson injection in SessionStart | 🔲 | |
| T-021: .forge/lessons.yaml machine-readable mirror | 🔲 | |
| T-022: Tier 3 cross-project memory | 🔲 | |

**Definition of done**: a correction in one session ("Use fp16 not bf16 on T4") becomes
a lesson that shows up in the next session's context block.

---

## M5: Adaptive Workflow — "Pipeline fits the project" 🔲

**Goal**: Forge detects project type on init and adjusts stage emphasis, criteria, and
agent prompts accordingly.

| Task | Status | Notes |
|------|--------|-------|
| T-023: Project type detection in forge-init | 🔲 | |
| T-024: project-type-profiles.md reference | 🔲 | |
| T-025: Wire profiles into stage skills | 🔲 | |

**Definition of done**: `/forge:init` on an ML project skips wireframes, adds drift
detection to eval criteria, runs ML-specific spec questions.

---

## M6: Auto-Skill Creation — "Pipeline extends itself" 🔲

**Goal**: Pattern detection runs in PostToolUse. After 3+ occurrences of a pattern,
skill-miner agent generates a SKILL.md draft and proposes installation.

| Task | Status | Notes |
|------|--------|-------|
| T-026: Pattern tracker in post-tool-use.py | 🔲 | |
| T-027: mine-skills.py script | 🔲 | |
| T-028: Skill approval flow in stop-reflect.py | 🔲 | |
| T-029: forge-retro skill (cycle retrospective) | 🔲 | |

**Definition of done**: doing the same 3-tool sequence 3+ times triggers a skill proposal.
User approval installs it; rejection blacklists the pattern.

---

## M7: Polish + Documentation — "Ready for other developers" 🔲

**Goal**: A new user can install, learn, and use Forge in under 10 minutes.

| Task | Status | Notes |
|------|--------|-------|
| T-030: Comprehensive README.md | 🔲 | User-facing |
| T-031: CONTRIBUTING.md + agent authoring guide | 🔲 | |
| T-032: End-to-end test on sample project | 🔲 | tests/integration/full-pipeline.sh |
| T-033: Package and publish | 🔲 | |

**Definition of done**: full pipeline runs successfully on `examples/sample-todo-api/`,
producing all 12 stage artifacts with traceability intact.

---

## Critical Path

```
T-001 → T-002 → T-003 → T-007 → T-009 → T-013 → T-014 → T-015 → T-032
                  ↓        ↓        ↓
                T-005 → T-006     T-019 → T-020
```

Roughly 15 tasks on the critical path. Other tasks can parallelize once T-013 lands.
