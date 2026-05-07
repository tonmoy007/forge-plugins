# Task DAG — Forge Plugin Build

> 33 tasks across 7 milestones, with dependencies. Work them in topological order.
> The first unblocked task is the next one to start.
>
> Format: `T-NNN [size] title — description`
> Size: S (small, ~30min), M (medium, ~2hr), L (large, ~half-day)

---

## Milestone 1: Core Skeleton

### T-001 [S] Plugin scaffolding
- **Description**: Create `.claude-plugin/plugin.json` with metadata and empty hook stubs. Verify plugin loads.
- **Files**: `.claude-plugin/plugin.json`, `scripts/validate-plugin.py`
- **Done when**: `python scripts/validate-plugin.py` returns success; `claude plugin install --plugin-dir .` doesn't error
- **Depends on**: none
- **REQ-IDs**: REQ-010, REQ-011, REQ-012

### T-002 [M] forge-init skill
- **Description**: Skill that scaffolds `pipeline/`, `tasks/`, `.forge/` in a target project. Detects project type. Writes initial `state.md`.
- **Files**: `skills/forge-init/SKILL.md`, `scripts/init-pipeline.sh`
- **Done when**: `/forge:init` in a fresh dir creates the full structure with state.md
- **Depends on**: T-001
- **REQ-IDs**: REQ-001, REQ-002, REQ-060

### T-003 [S] state-manager.py script
- **Description**: CLI for read/write of `pipeline/state.md` with atomic operations.
- **Files**: `scripts/state-manager.py`, `tests/unit/test_state_manager.py`
- **Done when**: All CLI subcommands (read, advance, set-task, reflect) pass tests
- **Depends on**: T-001
- **REQ-IDs**: REQ-002, REQ-003, REQ-004

### T-004 [S] forge-status skill
- **Description**: `/forge:status` reads state, displays progress, blockers, gate status.
- **Files**: `skills/forge-status/SKILL.md`
- **Done when**: `/forge:status` shows formatted dashboard for any pipeline state
- **Depends on**: T-003
- **REQ-IDs**: REQ-011

### T-005 [M] gate-criteria.md (machine-readable)
- **Description**: All 12 stages' exit criteria in YAML, parseable by check-gate.py.
- **Files**: `references/gate-criteria.md`
- **Done when**: YAML validates; covers all 12 stages from PIPELINE.md
- **Depends on**: T-001
- **REQ-IDs**: REQ-003, REQ-090

### T-006 [M] check-gate.py script
- **Description**: Evaluates gate criteria for a given stage, returns JSON pass/fail.
- **Files**: `scripts/check-gate.py`, `tests/unit/test_check_gate.py`
- **Done when**: `check-gate.py --stage 1` returns valid JSON; tests pass
- **Depends on**: T-005
- **REQ-IDs**: REQ-003, REQ-090, REQ-091

---

## Milestone 2: Hook System

### T-007 [M] session-start.py hook
- **Description**: Loads pipeline state + filtered lessons + design summary into context (< 2000 tokens).
- **Files**: `hooks/session-start.py`, `tests/unit/test_session_start.py`
- **Done when**: Hook outputs valid context block; under token budget; handles non-Forge dirs silently
- **Depends on**: T-003
- **REQ-IDs**: REQ-030, REQ-040, REQ-044, NFR-001, NFR-003

### T-008 [M] prompt-submit.py hook
- **Description**: Detects stage intent, prunes context, flags corrections.
- **Files**: `hooks/prompt-submit.py`, `tests/unit/test_prompt_submit.py`
- **Done when**: Detects "/forge:build" → returns Stage 6 context; corrections flagged to file
- **Depends on**: T-003
- **REQ-IDs**: REQ-031

### T-009 [L] stop-reflect.py hook (the big one)
- **Description**: 4-step pipeline — reflect, extract lessons, check gate, mine skills.
- **Files**: `hooks/stop-reflect.py`, `tests/unit/test_stop_reflect.py`
- **Done when**: All 4 steps run sequentially; gate failure with explicit "done" → exit 2; lessons appear in lessons.md after corrections
- **Depends on**: T-006, T-019 (lesson extractor)
- **REQ-IDs**: REQ-034, REQ-050, REQ-051, REQ-052

### T-010 [S] session-end.py hook
- **Description**: Final state persist, session summary write.
- **Files**: `hooks/session-end.py`, `tests/unit/test_session_end.py`
- **Done when**: `.forge/sessions/<ts>.md` written with duration, tasks, lessons, files
- **Depends on**: T-003
- **REQ-IDs**: REQ-036

### T-011 [M] pre-tool-write.py hook (design system)
- **Description**: Scans UI files for raw values, returns feedback as additionalContext.
- **Files**: `hooks/pre-tool-write.py`, `tests/unit/test_pre_tool_write.py`
- **Done when**: Hex colors, raw px, raw fonts trigger feedback; non-UI files skipped; only fires after Stage 6
- **Depends on**: T-003
- **REQ-IDs**: REQ-032, REQ-080, REQ-081, REQ-082, REQ-083

### T-012 [S] post-tool-use.py hook
- **Description**: Async logging, progress tracking, pattern counting.
- **Files**: `hooks/post-tool-use.py`, `tests/unit/test_post_tool_use.py`
- **Done when**: session-log.jsonl appends; progress.md updates in Stage 6; patterns.jsonl tracks tool sequences
- **Depends on**: T-003
- **REQ-IDs**: REQ-033, REQ-070

### T-013 [S] Wire hooks into plugin.json
- **Description**: Register all 7 hooks with correct matchers, types, timeouts.
- **Files**: `.claude-plugin/plugin.json`
- **Done when**: `/hooks` command in Claude Code shows all Forge hooks; basic invocation works
- **Depends on**: T-007 through T-012
- **REQ-IDs**: REQ-030 to REQ-038

---

## Milestone 3: Specialized Agents

### T-014 [L] Stage agent personas (12 files)
- **Description**: Write all 12 stage agent persona files in `agents/`. Each: role, goal, tools, scope, output contract, workflow, examples.
- **Files**: `agents/{requirements-analyst,product-designer,system-architect,spec-writer,planner,builder,evaluator,devops,observer,triage,resolver,release-manager}.md`
- **Done when**: All 12 files exist, follow schema, validated by `scripts/validate-skill.py` (or equivalent for agents)
- **Depends on**: T-001
- **REQ-IDs**: REQ-020, REQ-022, REQ-023, REQ-024
- **Note**: This is the largest task — split per agent if needed. Consider 12 sub-tasks.

### T-015 [L] Stage skill files (12 files)
- **Description**: SKILL.md for `/forge:srs` through `/forge:release`. Each invokes its agent.
- **Files**: `skills/forge-{srs,product,arch,spec,plan,build,eval,deploy,monitor,feedback,resolve,release}/SKILL.md`
- **Done when**: All slash commands work in Claude Code; each invokes the right agent
- **Depends on**: T-014
- **REQ-IDs**: REQ-010, REQ-013

### T-016 [M] Cross-stage agent personas (4 files)
- **Description**: Reflector, lesson-extractor, skill-miner, gate-checker personas.
- **Files**: `agents/{reflector,lesson-extractor,skill-miner,gate-checker}.md`
- **Done when**: All 4 files exist, callable by hooks
- **Depends on**: T-014
- **REQ-IDs**: REQ-021

### T-017 [M] context-pruner.py script
- **Description**: Given a stage, returns prioritized list of artifacts to inject (within token budget).
- **Files**: `scripts/context-pruner.py`, `tests/unit/test_context_pruner.py`
- **Done when**: Stage 6 returns task-dag + spec sections + design system, NOT full SRS or architecture
- **Depends on**: T-005
- **REQ-IDs**: REQ-023, NFR-003

### T-018 [S] forge-resume skill
- **Description**: `/forge:resume` reads state, injects full context for current task, continues work.
- **Files**: `skills/forge-resume/SKILL.md`
- **Done when**: After session restart, `/forge:resume` picks up exactly where last session ended
- **Depends on**: T-003, T-017
- **REQ-IDs**: REQ-004, REQ-011

---

## Milestone 4: Memory + Lessons

### T-019 [M] extract-lessons.py script
- **Description**: Parse conversation transcript for corrections → structured lessons (Trigger/Rule/Why).
- **Files**: `scripts/extract-lessons.py`, `tests/unit/test_extract_lessons.py`
- **Done when**: Sample correction → valid YAML lesson; offline mode works (rule-based fallback)
- **Depends on**: T-001
- **REQ-IDs**: REQ-052

### T-020 [S] Lesson injection in SessionStart
- **Description**: SessionStart filters lessons by stage tags + project type, includes top N relevant.
- **Files**: `hooks/session-start.py` (update)
- **Done when**: Stage 6 ML project session shows GPU lessons, not docs lessons
- **Depends on**: T-007, T-019
- **REQ-IDs**: REQ-044

### T-021 [S] .forge/lessons.yaml mirror
- **Description**: Sync `tasks/lessons.md` ↔ `.forge/lessons.yaml` automatically.
- **Files**: `scripts/sync-lessons.py`
- **Done when**: Edit lessons.md → next session-start regenerates lessons.yaml
- **Depends on**: T-019
- **REQ-IDs**: REQ-045

### T-022 [M] Tier 3 cross-project memory
- **Description**: `~/.forge/global-lessons.md` + promotion logic (3+ projects → global).
- **Files**: `scripts/promote-lessons.py`, `~/.forge/` template structure
- **Done when**: Lesson used in 3 projects shows up in 4th project's session-start
- **Depends on**: T-019, T-021
- **REQ-IDs**: REQ-042, REQ-043

---

## Milestone 5: Adaptive Workflow

### T-023 [M] Project type detection in forge-init
- **Description**: Detect API/fullstack/ML/CLI/library from file structure + user input.
- **Files**: `scripts/detect-project-type.py`, `skills/forge-init/SKILL.md` (update)
- **Done when**: ML project (has `train.py`, `requirements.txt` with torch) → "ml-pipeline" profile assigned
- **Depends on**: T-002
- **REQ-IDs**: REQ-060

### T-024 [M] project-type-profiles.md
- **Description**: Per-type stage emphasis, criteria additions, prompt overrides.
- **Files**: `references/project-type-profiles.md`
- **Done when**: All 5 profiles defined with concrete overrides for at least 3 stages each
- **Depends on**: T-005
- **REQ-IDs**: REQ-061, REQ-062

### T-025 [S] Wire profiles into stage skills
- **Description**: Each stage skill reads project profile, adjusts instructions.
- **Files**: All 12 `skills/forge-*/SKILL.md` files (update)
- **Done when**: `/forge:eval` on ML project includes drift detection criterion in eval matrix
- **Depends on**: T-015, T-024
- **REQ-IDs**: REQ-061, REQ-062

---

## Milestone 6: Auto-Skill Creation

### T-026 [M] Pattern tracker in post-tool-use.py
- **Description**: Detect repeated tool sequences, log to patterns.jsonl with signature.
- **Files**: `hooks/post-tool-use.py` (update), `tests/unit/test_post_tool_use.py` (update)
- **Done when**: Same 3-tool sequence 3 times → 3 entries with same signature
- **Depends on**: T-012
- **REQ-IDs**: REQ-070

### T-027 [M] mine-skills.py script
- **Description**: Aggregate patterns, filter by frequency, generate SKILL.md drafts.
- **Files**: `scripts/mine-skills.py`, `tests/unit/test_mine_skills.py`
- **Done when**: Pattern with frequency=3 produces SKILL.md draft with name, description, steps
- **Depends on**: T-026, T-016 (skill-miner agent)
- **REQ-IDs**: REQ-071, REQ-072

### T-028 [S] Skill approval flow
- **Description**: stop-reflect.py shows proposed skills, handles approve/modify/reject.
- **Files**: `hooks/stop-reflect.py` (update)
- **Done when**: User can install proposed skill, modifications are persisted, rejections blacklist pattern
- **Depends on**: T-027
- **REQ-IDs**: REQ-073, REQ-074

### T-029 [S] forge-retro skill
- **Description**: `/forge:retro` after Stage 12 produces full retrospective + skill mining.
- **Files**: `skills/forge-retro/SKILL.md`
- **Done when**: Retro covers what went well, what didn't, lessons captured, skills proposed
- **Depends on**: T-027
- **REQ-IDs**: REQ-054

---

## Milestone 7: Polish + Documentation

### T-030 [M] User-facing README.md
- **Description**: Comprehensive README with install, quickstart, all commands, configuration.
- **Files**: `README.md` (overwrite the dev-focused one), `docs/` content
- **Done when**: New user can install and run `/forge:init` → `/forge:srs` from README alone in < 10 min
- **Depends on**: T-032 (so we have proof it works)
- **REQ-IDs**: NFR-012

### T-031 [S] CONTRIBUTING.md + agent authoring guide
- **Description**: How to add new agents, stages, profiles.
- **Files**: `CONTRIBUTING.md`, `docs/agent-authoring.md`
- **Done when**: Someone can add a new stage by following the guide
- **Depends on**: T-014
- **REQ-IDs**: —

### T-032 [M] End-to-end test
- **Description**: Full pipeline run on `examples/sample-todo-api/`. All 12 stages produce artifacts.
- **Files**: `tests/integration/full-pipeline.sh`, `examples/sample-todo-api/` setup
- **Done when**: Script exits 0 with all artifacts present and traceability chain holds
- **Depends on**: All previous tasks
- **REQ-IDs**: NFR-011, NFR-012

### T-033 [S] Package and publish
- **Description**: Tag v0.1.0, publish to marketplace (when available), GitHub release.
- **Files**: `.claude-plugin/plugin.json` (version bump), `CHANGELOG.md`
- **Done when**: Tag exists; release notes published; install from tag works
- **Depends on**: T-032
- **REQ-IDs**: —

---

## Critical Path

```
T-001 ─┬─→ T-002 ─→ T-023 ─→ T-024 ─→ T-025
       │
       ├─→ T-003 ─┬─→ T-004
       │           ├─→ T-007 ─→ T-020 ─→ T-022
       │           ├─→ T-008
       │           ├─→ T-010
       │           ├─→ T-011
       │           └─→ T-012 ─→ T-026 ─→ T-027 ─→ T-028 ─→ T-029
       │
       ├─→ T-005 ─→ T-006 ─→ T-009 ─→ T-013
       │              │
       │              └─→ T-017 ─→ T-018
       │
       └─→ T-014 ─┬─→ T-015 ─→ T-025
                   ├─→ T-016
                   └─→ T-031

T-019 ─→ T-020 ─→ T-022
   │
   └─→ T-021

T-013 + T-015 + T-022 + T-025 + T-029 ─→ T-032 ─→ T-030 ─→ T-033
```

**Critical path length**: ~15 tasks
**Parallelizable after T-013**: T-014 (split into 12 sub-tasks), T-019, T-026

---

## Risk Register

| ID | Risk | Impact | Likelihood | Mitigation |
|----|------|--------|------------|------------|
| R-1 | Hook latency exceeds 200ms | M | M | Profile early in T-013, async hooks where possible |
| R-2 | Context injection > 2000 tokens | H | M | Aggressive pruning in T-017, measure on real projects |
| R-3 | Lesson extraction hallucinates | M | H | User confirmation required, conservative thresholds |
| R-4 | Skill miner proposes junk | L | H | Frequency ≥ 3 + user approval, blacklist |
| R-5 | Gate checker false-passes | H | M | Conservative defaults, explicit checks before each gate type |
| R-6 | Plugin breaks on Claude Code update | H | L | Pin to v2.1 schema, e2e test on each CC release |
| R-7 | Cross-project lessons conflict | M | M | Project lesson wins; log conflict for review |
| R-8 | Filesystem permissions on ~/.forge/ | L | L | Document; create dirs with `mkdir -p` |
