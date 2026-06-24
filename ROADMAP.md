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
| **v0.2.3** | 🟢 released | **Background daemons (M2)** — Observer (`/forge:watch`), Dreamer (`/forge:dreamer-run`), Health (`/forge:health-check`) + async skill-miner production path + size-bounded log rotation. All capability-gated, cheap-model + session-reused, never-raises. T-142–T-147. |
| ~~sprint~~ | ⚪ shipped as v0.3.4 | The v0.2 M4 backlog — deferred from v0.2.3, delivered as v0.3.4 below. T-153–T-155. |
| **v0.3.0** | 🟢 released | **Rules (governance)** — user-authored `.forge/rules/*.md` that steer agents (scopes: always / stage / glob / manual); `/forge:rules` (init/add/list/validate); session-start + pre-tool-write injection. Advisory, fail-soft, no-op when absent. Tag `v0.3.0`, both remotes. T-157–T-161. |
| **v0.3.1** | 🟢 released | **Autopilot (autonomy)** — cross-stage hands-off execution (bounded, stop-on-gate), dual in-session/background substrate (`--mode`), `/forge:autopilot` + `/forge:autopilot-stop`, resume. Tag `v0.3.1`, both remotes. T-162–T-166. |
| ~~v0.3.2~~ | ⚪ folded | **Modernized harness** (structured outputs, per-dispatch budget, model routing, session rotation) — built as T-167–T-170 but **folded into the v0.3.3 release** rather than tagged separately. |
| **v0.3.3** | 🟢 released | **Complete (local) autonomy + modernized harness** — self-heal loop (blocker → `/forge:resolve` → re-gate), independent verifier subagents, `--unattended` mode, and enforcing rules guardrail, on a harness rebuilt onto current Claude Code primitives (`--json-schema`, `--max-budget-usd`, per-stage `autopilot.models`, session rotation). Each verified against the live CLI, degrades gracefully. Tag `v0.3.3`, both remotes. T-167–T-176. |
| **v0.3.4** | 🟢 released | **Sprint planning + cross-machine guidance (M4)** — `/forge:sprint` plan/review (a view over the task DAG; closes EF-011), `~/.forge` sync guidance + opt-in local-only telemetry, and a cross-platform hook-timeout fix (Windows degrades, never crashes). Closes the long-deferred v0.2 M4 backlog. Tag `v0.3.4`, both remotes. T-153–T-155. |
| **v0.3.5** | 🟢 released | **Semantic skill mining + skill-creator** — replaced the tool-name-n-gram miner with a semantic, success-gated, **anti-unification**-based miner that proposes genuine reusable *workflows*, authors them via a new `/forge:skill-creator` (agentskills.io `SKILL.md`), verifies by replay, and curates the library (ExpeL voting + `/dream`-style maintenance). Human-approved throughout. Tag `v0.3.5`, both remotes. SRS `build/01-srs/srs-v0.3.5.md`, DAG `build/04-plan/task-dag-v0.3.5.md` (T-177–T-184). |
| **v0.3.6** | 🟢 released | **Context-aware autopilot** — when an autopilot run crosses a configurable context threshold, it automatically **checkpoints → compacts → continues**. Background dispatches rotate the session on a real token-pressure signal (`usage.input_tokens`); in-session runs ride native auto-compaction via a new **PreCompact** checkpoint + **SessionStart(`compact`)** resume injection, with a shared schema-versioned checkpoint and run-log idempotency. Opt-in (default 80%). Tag `v0.3.6`, both remotes. SRS `build/01-srs/srs-v0.3.6.md`, DAG `build/04-plan/task-dag-v0.3.6.md` (T-185–T-190). |
| **v0.4.0** | 🟢 released | **Dynamic workflow engine** — generalizes Forge's orchestration into a topological **DAG executor** (`scripts/_workflow.py`): heterogeneous agent steps, `depends_on` waves, bounded parallel fan-out, inter-step data passing, per-node verify, budget/resume-plumbed, deterministic + never-raises. Capabilities are **independent opt-in toggles** (`orchestration:` block, all default off): user-defined flows (`.forge/workflows/*.yaml` + `/forge:flow`), per-stage parallel build + git-worktree isolation + adversarial-verify join, and hybrid validated sub-DAG generation (`decompose`). Forge's own `/forge:review`/`/forge:adopt`/`/forge:why` fan-outs now run on the engine (behavior-preserving). Adversarially verified (SHIP-WITH-NOTES, both notes closed). Tag `v0.4.0`, both remotes. SRS `build/01-srs/srs-v0.4.0.md`, DAG `build/04-plan/task-dag-v0.4.0.md` (T-191–T-201). |
| **v0.4.1** | 🟢 released | **Operable engine** (hardening, **zero semantic change**) — make the shipped v0.4.0 engine observable + cost-predictable: live `[Forge]` **stderr narration** (stdout byte-identical), one structured **`.forge/events.jsonl`** audit line per run, a **pure cost pre-flight estimator** over the existing deterministic admission set (surfaced in `/forge:flow` before dispatch, loud at a runtime drop), and a dogfood **`.forge/workflows/doc-review.yaml`** + a parallel-build integration test. Tag `v0.4.1`, origin. SRS `build/01-srs/srs-v0.4.1.md`, DAG `build/04-plan/task-dag-v0.4.1.md` (T-202–T-206). |
| **v0.5.0** | 🟢 released | **Unified `~/.forge` graduation layer** — generalizes the T-022 lesson promoter into one tier-agnostic core (`scripts/_graduation.py`: registry · atomic IO · 30-day TTL · idempotent keyed merge · `Tier` protocol · fail-soft `graduate()` driver), then adds **skills** and **workflows** tiers behind **per-tier gates** (breadth for lessons; approved + ExpeL `weight>0` + `use≥2` for skills; validates-clean + ≥2 successful `workflow_run` records for workflows). **Project-wins** recall in every tier; skill recall = **symlink** (ADR-009), workflows recall via the loader search path. Automatic, silent, fail-soft at session-start (`FORGE_NO_GRADUATE=1` escape); new `/forge:graduate` (dry-run / list / scan). Behavior-preserving for lessons. ADR-008 + ADR-009. Tag `v0.5.0`, both remotes. SRS `build/01-srs/srs-v0.5.0.md`, DAG `build/04-plan/task-dag-v0.5.0.md` (T-207–T-213). |
| **v0.6.0** | 🟢 released | **Engine made real I — per-node session reuse** (cost-reduction, **zero default behavior change**). Drives the already-built-but-unused `_background_agent.dispatch(resume=...)` path from the v0.4.0 DAG engine: capture each node's first-attempt `session_id` and `--resume` it into **that same node's** retry/heal re-dispatches (same prompt + model), lowering their realized floor from `FRESH_FLOOR_USD` `$0.06` to `RESUME_FLOOR_USD` `$0.01`. **Within-node only**; the independent verifier is **never** reused (REQ-WF-002); admission stays on `FRESH_FLOOR_USD` so the estimator/admitted-set split is identical on vs off (AC-WF-014); a stale session **falls back to fresh** within the attempt budget. Opt-in `orchestration.session_reuse` (strict `is True`, default off ⇒ byte-identical to v0.4.x). ADR-010. **Deferred follow-ups**: per-branch/cross-node reuse (trio item 1's other half, measurement-gated), trio items 2–3 (top-level generation · pipeline-as-WorkflowSpec), and **caveman mode** (orthogonal prompt-compression, candidate v0.6.1). ADR-010. Tag `v0.6.0`, both remotes. SRS `build/01-srs/srs-v0.6.0.md`, DAG `build/04-plan/task-dag-v0.6.0.md` (T-214–T-219). |
| **v0.6.1** | 🟢 released | **Caveman mode — measured and rejected; static prompt tightening only** (**zero default behavior change**). Investigated the `caveman` token-reduction approach: the one stdlib-legal lever (a terse-output preamble at the dispatch chokepoint) was built behind a default-off `orchestration.caveman_mode` toggle and **measured** against the `_cost_cap` output-token ledger — a real before/after on the Dreamer free-prose prompt (`haiku`, N=5/arm) showed **mean −52.9%**, no saving, well under the REQ-CM-005 ≥10% gate (Forge's free-prose prompts are already length-bounded). Per the gate the **runtime toggle was dropped** (config + `_caveman.py` + wiring reverted; dispatch byte-identical to v0.6.0); v0.6.1 ships only the **deterministic static tightening** of verbose non-verdict prompt constants (`dreamer`/`autopilot`/`parallel_build`) — verify/skeptic/gate/observer untouched. The measurement gate worked as designed. ADR-011. Tag `v0.6.1`, both remotes. SRS `build/01-srs/srs-v0.6.1.md`, DAG `build/04-plan/task-dag-v0.6.1.md` (T-220–T-226). |

---

## Consolidated roadmap & standing non-goals (program-wide)

> Source: `build/01-srs/srs-v0.4.1.md` §5. Supersedes the scattered per-version
> "future / out-of-scope" sections for engine-adjacent work — deferred items were
> restated across 12 SRS + 9 DAG docs (e.g. `~/.forge` cross-project sharing was
> deferred *three* times). Decided once, on the record. **Nothing here is built yet.**

> **Re-sequencing note (2026-06-22).** The unified `~/.forge` graduation layer was pulled
> ahead of the "engine made real" trio and shipped as **v0.5.0** (released) — lower-risk,
> generalizes built machinery, high cross-project leverage. The engine trio below is the
> subsequent engine work; its first slice ships as **v0.6.0**. See srs-v0.5.0 §6 / srs-v0.6.0 §6.

### v0.5.0 — Unified `~/.forge` graduation layer (released) 🟢

Generalize the T-022 lesson promoter into one tier-agnostic core + skills and workflows
tiers behind per-tier gates, recalled with project-wins. See the v0.5.0 row above and
[`references/graduation-layer.md`](references/graduation-layer.md) ·
ADR-008 / ADR-009.

### Engine "made real" trio (v0.6.x)

1. **Session reuse across heterogeneous DAG nodes.** ✅ **within-node** half **shipped as
   v0.6.0** — a node's own retry/heal re-dispatch `--resume`s its first-attempt session
   (cost-only; admission stays on the fresh floor; verifier never reused; fallback-to-fresh;
   default-off). ADR-010. **Deferred**: **per-branch / cross-node** reuse — resuming a
   *dependency's* session for a *dependent* node defeats `--resume` on heterogeneous
   prompts/models and has a weaker correctness argument; a future, **measurement-gated**
   follow-up with its own SRS + ADR (srs-v0.6.0 §6). M–L.
2. **Top-level LLM-generated workflows** — extend the validated-slot model
   (`allow_generated_subdags`) from a sub-DAG-in-a-node to a whole generated top-level
   `WorkflowSpec`, behind the same validate-before-dispatch rails. L; higher risk. Deferred.
3. **Pipeline-as-WorkflowSpec** — express the 12-stage SDLC as a `WorkflowSpec` on the
   engine, unifying `autopilot.py`'s sequencer with `run_workflow`. "Stretch, never
   required" — only if it simplifies. L; architecturally significant. Deferred.

### Caveman mode — prompt-compression (v0.6.1: measured, runtime toggle rejected)

Investigated separately from session reuse. The one stdlib lever that ported under REQ-NF-024 — a
terse-output preamble at the single dispatch chokepoint (`hooks/_background_agent.dispatch`) — was
**built behind a default-off `orchestration.caveman_mode` toggle and measured**: a real before/after on
the Dreamer free-prose prompt (`haiku`, N=5/arm, actual `usage.output_tokens`) showed **mean −52.9%** —
no saving, well under the REQ-CM-005 ≥10% bar, because Forge's free-prose prompts are already
length-bounded ("3-5 sentences, terse, no bullet lists"). Per the gate the **runtime toggle was
dropped**; v0.6.1 ships only the **deterministic static tightening** of verbose non-verdict prompt
constants. The `caveman-compress` / `caveman-shrink` levers were rejected at research time (model call +
`pip` / Node-MCP proxy — stdlib violation). The measurement-gated discipline worked as designed: it
stopped a token-reduction feature that didn't reduce tokens. See
`build/02-architecture/adr/011-caveman-mode.md` and `build/06-evaluation/v0.6.1-caveman-measurement.md`.

### Separate programs / parked

- **Hosted autonomy — Managed Agents (`--mode managed`)** — Anthropic-run loop + container,
  gate-derived Outcome rubric, scheduled deployments. The largest unbuilt milestone; its own
  program (≥ v0.6), independent of the workflow engine. Deferred on a deliberate "local-only
  autonomy first" decision.
- **In-session configurable-% context trigger — BLOCKED UPSTREAM.** Needs a Claude Code
  `ContextThreshold` hook event (issues #46695 / #25689). Parked until upstream ships it;
  v0.3.6 already delivers the token-pressure-rotation approximation.

### Standing non-goals (decided; do not re-add as backlog)

- **Embedding / vector retrieval of skills or workflows** — Claude's description-matching
  already covers invocation, and it breaks the stdlib-only / no-`pip install` rule. Non-goal.
- **A subprocess driving Claude's in-session Agent/Task tool** — impossible by design (ADR-006);
  the engine delegates to `claude -p`. Non-goal.
- **A resident orchestrator / supervisor process** — ADR-005 keeps dispatch detached one-shot;
  reversing it needs a superseding ADR first. Non-goal absent that ADR.
- **Repackaging Forge as a Python package / standalone CLI / ACP / multi-tenant / channel
  adapters / third-party integrations** — Forge is a Claude Code plugin. Non-goal.
- **Full policy DSL / blocking rule engine** — rules are advisory (the `enforce: true` guardrail
  shipped in v0.3.3 T-175; the full DSL stays out). Non-goal.
- **RL / weight-level self-improvement; fully unattended skill installation; Web/Streamlit status
  UI; anonymous telemetry beyond opt-in local-only** — firm, long-standing non-goals.

---

## Critical Path

```
T-001 → T-002 → T-003 → T-007 → T-009 → T-013 → T-014 → T-015 → T-032
                  ↓        ↓        ↓
                T-005 → T-006     T-019 → T-020
```

Roughly 15 tasks on the critical path. Other tasks can parallelize once T-013 lands.
