# ROADMAP.md

> Milestone tracker. For full task DAG with dependencies, see `build/04-plan/task-dag.md`.

## Status Legend

- 🔲 Not started
- 🟡 In progress
- 🟢 Done
- 🔴 Blocked

---

## M1: Core Skeleton — "Pipeline works manually" 🟢

**Goal**: A user can install the plugin, run `/forge:init`, and see `/forge:status`
display the current pipeline state. No hooks yet, no agents yet — just the plumbing.

| Task | Status | Notes |
|------|--------|-------|
| T-001: Plugin scaffolding (plugin.json, dirs) | 🟢 | commit 86a0b03 |
| T-002: forge-init skill (scaffold pipeline/) | 🟢 | commit 80e4f1f; 14 tests |
| T-003: state-manager.py script | 🟢 | _state_lib.py + CLI; 36 tests |
| T-004: forge-status skill | 🟢 | SKILL.md; gate section gracefully optional |
| T-005: gate-criteria.md reference (machine-readable) | 🟢 | 12 stages, 60 criteria |
| T-006: check-gate.py script | 🟢 | 4 check types; 14 tests |

**Definition of done**: `claude plugin install --plugin-dir .` works, `/forge:init` scaffolds
a pipeline, `/forge:status` reads the state, `check-gate.py --stage 1` returns valid JSON.

---

## M2: Hook System — "Pipeline enforces itself" 🟢

**Goal**: All 7 hooks fire at the right lifecycle events. Pipeline state is automatically
loaded into context. Design system enforcement runs on file writes. Stop hook does basic
reflection + gate check.

| Task | Status | Notes |
|------|--------|-------|
| T-007: session-start.py hook | 🟢 | token-budget context injection; 17 tests |
| T-008: prompt-submit.py hook | 🟢 | stage intent + correction flagging; 16 tests |
| T-009: stop-reflect.py hook | 🟢 | v4.1 Proposal/Validator/Executor pipeline; 48 tests |
| T-010: session-end.py hook | 🟢 | session summary to .forge/sessions/; 18 tests |
| T-011: pre-tool-write.py hook (design system) | 🟢 | 5 violation types; 35 tests |
| T-012: post-tool-use.py hook (decision logger) | 🟢 | session-log + patterns.jsonl; 18 tests |
| T-013: Wire all hooks into plugin.json | 🟢 | pre-wired in T-001; validate-plugin.py confirms |

**Definition of done**: opening a Claude Code session in a Forge-managed project shows the
`[Forge]` context block. Writing `color: #3b82f6` in a UI file triggers a token suggestion.
The `Stop` hook produces a reflection log entry.

---

## M3: Specialized Agents — "Each stage has a brain" 🟢

**Goal**: All 12 stage agents and 4 cross-stage agents are written and wired to skills.
Each `/forge:*` command spawns the right agent with the right tools and context.

| Task | Status | Notes |
|------|--------|-------|
| T-014: Write all 12 stage agent personas | 🟢 | Role/Goal/Scope/Output/Workflow per spec |
| T-015: Write all 12 stage skills (SKILL.md) | 🟢 | + "product" and "arch" prompt-submit aliases |
| T-016: Write 4 cross-stage agents | 🟢 | reflector, lesson-extractor, skill-miner, gate-checker |
| T-017: context-pruner.py script | 🟢 | Stage-aware artifact selection; 35 tests |
| T-018: forge-resume skill | 🟢 | Uses context-pruner + state-manager |

**Definition of done**: `/forge:srs` spawns the requirements analyst agent with a clean
context (no architecture/spec leakage), produces `srs.md` with REQ-IDs.

---

## M4: Memory + Lessons — "Pipeline learns from mistakes" 🟢

**Goal**: User corrections become lessons automatically. Lessons inject into relevant
sessions. Cross-project lessons graduate to `~/.forge/`.

| Task | Status | Notes |
|------|--------|-------|
| T-019: extract-lessons.py script | 🟢 | Rule-based extraction + dedup + atomic write; 43 tests |
| T-020: Lesson injection in SessionStart | 🟢 | Filter by stage tags + project type; sorted by frequency; capped at 5 |
| T-021: .forge/lessons.yaml machine-readable mirror | 🟢 | sync-lessons.py; session-start auto-syncs on stale md; 37 tests |
| T-022: Tier 3 cross-project memory | 🟢 | promote-lessons.py; ~/.forge/ scaffold; auto-registers+promotes; 39 tests |

**Definition of done**: a correction in one session ("Use fp16 not bf16 on T4") becomes
a lesson that shows up in the next session's context block. ✅

---

## M5: Adaptive Workflow — "Pipeline fits the project" 🟢

**Goal**: Forge detects project type on init and adjusts stage emphasis, criteria, and
agent prompts accordingly.

| Task | Status | Notes |
|------|--------|-------|
| T-023: Project type detection in forge-init | 🟢 | train.py + ML libs + notebooks + API types; 10 tests |
| T-024: project-type-profiles.md reference | 🟢 | 5 profiles, ≥3 stage overrides each; YAML valid |
| T-025: Wire profiles into stage skills | 🟢 | load-profile.py + 24 tests; all 12 skills profile-aware |

**Definition of done**: `/forge:init` on an ML project skips wireframes, adds drift
detection to eval criteria, runs ML-specific spec questions. ✅

---

## M6: Auto-Skill Creation — "Pipeline extends itself" 🟢

**Goal**: Pattern detection runs in PostToolUse. After 3+ occurrences of a pattern,
skill-miner agent generates a SKILL.md draft and proposes installation.

| Task | Status | Notes |
|------|--------|-------|
| T-026: Pattern tracker in post-tool-use.py | 🟢 | Sliding 3-tool window; SHA-1 signature stability; 22 tests |
| T-027: mine-skills.py script | 🟢 | freq≥3 → SKILL.md draft; blacklist + collision filters; 33 tests |
| T-028: Skill approval flow in stop-reflect.py | 🟢 | list/approve/modify/reject; end-to-end cycle verified; 22 tests |
| T-029: forge-retro skill (cycle retrospective) | 🟢 | writes to pipeline/12-release/retro.md; 16 structural tests |

**Definition of done**: doing the same 3-tool sequence 3+ times triggers a skill proposal.
User approval installs it; rejection blacklists the pattern. ✅

---

## M7: Polish + Documentation — "Ready for other developers" 🟢

**Goal**: A new user can install, learn, and use Forge in under 10 minutes.

| Task | Status | Notes |
|------|--------|-------|
| T-030: Comprehensive README.md | 🟢 | User-facing; install, quickstart, 12-stage reference, hooks, config |
| T-031: CONTRIBUTING.md + agent authoring guide | 🟢 | docs/agent-authoring.md; walkthroughs for agent/stage/profile |
| T-032: End-to-end test on sample project | 🟢 | 29 fixtures; 12/12 gates; traceability chain intact; 532/532 tests |
| T-033: Package and publish | 🟢 | CHANGELOG.md; v0.1.0 tag |

**Definition of done**: full pipeline runs successfully on `examples/sample-todo-api/`,
producing all 12 stage artifacts with traceability intact. ✅

---

## Post-1.0 Point Releases

> M1–M7 above delivered v0.1.0. Subsequent point releases sand off dogfood
> findings and add capability. CHANGELOG.md is the source of truth for per-release
> detail; per-release scope lives in `build/01-srs/srs-vX.Y.Z.md` +
> `build/04-plan/task-dag-vX.Y.Z.md`.

| Release | Status | Theme |
|---------|--------|-------|
| v0.1.1 – v0.1.3.1 | 🟢 released | signal-quality patches, profile wiring, `python-frontmatter` drop |
| v0.1.5 + v0.1.5.1 | 🟢 released | kill surface-healthy/substance-inert antipatterns (T-101–T-125); PyYAML fail-soft hotfix |
| release-infra | 🟢 merged | hard CI gates w/ subprocess coverage (~72%), `scripts/bump-version.py` |
| v0.1.6 | 🟢 released | Make Forge interactive — CLARIFY (clarify before scoping), CONFIRM (outline+pause before spec/plan), NARRATE (per-task build narration). T-126–T-130. |
| v0.1.7 | 🟢 released | **Three more project-type profiles** — monorepo (dep-graph gate), mobile (store-readiness gate), data-contract (schema-hygiene gate). Each profile + detection + a real gate. T-131–T-135. |
| **v0.2.0** | 🟢 released | **v0.2 foundation (P0)** — cost cap + ledger, background-agent dispatch (`claude -p`, session reuse), capability probe wiring, background skill-miner instrumentation, `/forge:set-profile`. Spike PASS; O-2 completion-rate accruing. T-136–T-141. |
| **v0.2.1** | 🟢 released | **Orchestration + brownfield (M3)** — deterministic bounded fan-out primitive (`_orchestrate.py`), `/forge:review` (parallel reviewers), `/forge:adopt` (brownfield onboarding, closes EF-014), `/forge:why` LLM fallback. Not spike-gated. T-148–T-152. |
| **v0.2.2** | 🟢 released | **Skill-miner cost fix — clears the spike's O-2 gate.** Background skill-miner pins a cheap model (`haiku`), cutting an unpinned ~$1.07/run (Opus-class default) to ~$0.022/run; six live dispatches 6/6. + date-robust over-cap test, README hero banner. **Unblocks the M2 daemons.** |
| daemons (M2) | 🟡 unblocked — building | Observer / Dreamer / Health + async skill-miner + log rotation. O-2 gate cleared by v0.2.2; building on the proven adapter (cheap model + session reuse). Ships as **v0.2.3**. T-142–T-147. |
| sprint | ⚪ planned | Sprint plan/review over the DAG (M4, closes EF-011) + `~/.forge` sync, telemetry, Windows spike. T-153–T-156. |

---

## Critical Path

```
T-001 → T-002 → T-003 → T-007 → T-009 → T-013 → T-014 → T-015 → T-032
                  ↓        ↓        ↓
                T-005 → T-006     T-019 → T-020
```

Roughly 15 tasks on the critical path. Other tasks can parallelize once T-013 lands.
