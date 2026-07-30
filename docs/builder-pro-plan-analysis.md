# Builder Pro-Plan Analysis

> **Date**: 2026-07-30
> **Source**: `BUILDER_PRO-PLAN.md` + `skills/forge-build/SKILL.md` + project structure
> **Status**: Analysis only — no files written or modified in the project

---

## Summary

The BUILDER_PRO-PLAN.md proposes a **major redesign of Stage 6 (Builder)** — transforming it from a single monolithic coding agent into a full **Execution Orchestrator** with specialized sub-agents, deterministic pipelines, quality gates, traceability, and recovery. The current `forge-build` skill and `builder.md` agent are the MVP. The plan proposes evolving that MVP into a production-grade execution engine.

---

## Current State of Stage 6 (Builder)

The current implementation is **minimal and monolithic**:

| Component | File | What it does |
|-----------|------|-------------|
| Skill definition | `skills/forge-build/SKILL.md` | Pre-flight gate check → load builder persona → implement → test → commit → narrate |
| Agent persona | `agents/builder.md` | Single monolithic persona: reads context, writes code, writes tests, updates progress, commits |
| Workflow | Inline in SKILL.md | Linear: read task → read spec → implement → test → lint → commit → update progress |

The builder is essentially a **single prompt** that does everything — context loading, code generation, testing, verification, committing, progress tracking — all in one agent with no decomposition.

---

## BUILDER_PRO-PLAN.md Vision

The plan proposes transforming Stage 6 from a "coding agent" into an **Execution Orchestrator** with:

### 1. Specialized Sub-Agents

```
Execution Orchestrator
├── Context Loader
├── Task Resolver
├── Code Generator
├── Refactoring Agent
├── Test Generator
├── Documentation Generator
├── Linter
├── Static Analyzer
├── Build Runner
├── Verification Agent
├── Commit Generator
├── Progress Updater
└── Recovery Agent
```

### 2. Deterministic Pipeline Per Task

```
Load Context → Verify Inputs → Generate Code → Compile → Run Tests → Lint → Static Analysis → Verify Spec → Update Progress → Commit
```

### 3. Builder Modes

`build task`, `build module`, `build work-package`, `build milestone`, `build sprint`, `build project` — all use the same engine, only the scope changes.

### 4. Traceability

Every generated file traces back: `REQ → SPEC → ADR → MOD → TASK`. A `forge explain <file>` command returns the full provenance chain.

### 5. Quality Gates (10 gates, all must pass)

Compile → Tests → Lint → Formatting → Static Analysis → Architecture Validation → Spec Validation → Requirement Validation → Coverage → Security Scan

### 6. Recovery/Resumability

Failed tasks can be resumed from the point of failure without recomputation. Task state tracked: not started / in progress / completed / failed.

### 7. AI-Agnostic Adapter Layer

Execution Kernel → Claude Adapter, GPT Adapter, Codex Adapter, Gemini Adapter, OpenHands Adapter, Local Model Adapter.

### 8. Enterprise Artifacts

`build-log.md`, `execution-trace.md`, `verification.md`, `coverage.md`, `dependency-report.md`, `quality-report.md`, `security-report.md`, `implementation-decisions.md`

### 9. Context Resolution

Load only relevant docs per task (module → interfaces → DTO → requirements) instead of the whole project. Token usage becomes tiny.

---

## Gap Assessment

The gap between current and proposed is **massive**:

| Dimension | Current | Proposed |
|-----------|---------|----------|
| Architecture | Single agent, single skill | 13 specialized sub-agents + orchestrator |
| Workflow | Inline linear steps | Deterministic pipeline with quality gates |
| Traceability | None | Full REQ → SPEC → ADR → TASK provenance |
| Recovery | None | Resumable from failure point |
| Quality gates | Implicit (test + commit) | 10 explicit gates, none skipped |
| AI-agnostic | Claude-only | Adapter layer for any LLM |
| Artifacts | `progress.md` only | 8 enterprise artifact files |
| Context loading | Loads all context files | Resolves only relevant docs per task |
| Builder modes | Single mode | 6 scope modes (task → project) |

---

## Proposed Plan

### Phase 1: Foundation — Decompose the Monolith

| # | Task | Description |
|---|------|-------------|
| 1 | Extract Context Loader | Split context-loading logic from builder.md into a dedicated sub-agent that resolves only relevant docs per task |
| 2 | Extract Task Resolver | Split task resolution (reading DAG, finding spec sections, finding interfaces) into a dedicated sub-agent |
| 3 | Extract Code Generator | Split code generation into a dedicated sub-agent with deterministic generation pipeline |
| 4 | Extract Test Generator | Split test generation into a dedicated sub-agent |
| 5 | Extract Verification Agent | Split verification (compile, test, lint, static analysis, spec comparison) into a dedicated sub-agent |
| 6 | Extract Commit Generator | Split commit creation into a dedicated sub-agent |
| 7 | Extract Progress Updater | Split progress.md updates into a dedicated sub-agent |

### Phase 2: Orchestration & Quality Gates

| # | Task | Description |
|---|------|-------------|
| 8 | Build Execution Orchestrator | Create the orchestrator that chains sub-agents in the deterministic pipeline |
| 9 | Implement Quality Gates | Enforce all 10 quality gates — no gate passes, no commit |
| 10 | Implement Builder Modes | Add support for build task, module, work-package, milestone, sprint, project scopes |
| 11 | Implement Context Resolution | Load only relevant docs per task (module → interfaces → DTO → requirements) |

### Phase 3: Traceability & Recovery

| # | Task | Description |
|---|------|-------------|
| 12 | Implement Traceability | Every generated file gets metadata tracing back to TASK → MOD → SPEC → ADR → REQ. Add `forge explain <file>` command |
| 13 | Implement Recovery | Failed tasks can be resumed from the point of failure without recomputation |
| 14 | Generate Enterprise Artifacts | Produce build-log.md, execution-trace.md, verification.md, coverage.md, dependency-report.md, quality-report.md, security-report.md, implementation-decisions.md |

### Phase 4: AI-Agnostic & Advanced

| # | Task | Description |
|---|------|-------------|
| 15 | Implement AI-Agnostic Adapter Layer | Abstract the execution kernel from the LLM adapter |
| 16 | Incremental Build Support | Never regenerate — patch current code + task, verify, commit |
| 17 | Integration with Existing Pipeline | Wire the new orchestrator into the existing `forge-build` skill and `state-manager.py` advance flow |

---

## Key Risks

### 1. Scope Creep

The plan is extremely ambitious. Without strict scoping, it could consume months of work. **Recommendation**: start with Phase 1 (decomposition) and measure value before continuing.

### 2. Over-Engineering

The current single-agent approach works for a plugin with 12 stages. The orchestrator adds complexity that may not be justified until the project scales significantly. **Recommendation**: validate that the monolith is actually a bottleneck before investing in decomposition.

### 3. Integration Fragility

The new orchestrator must integrate with existing hooks (`session-start.py`, `state-manager.py`, `check-gate.py`) without breaking the current pipeline. **Recommendation**: keep the existing skill functional throughout the transition; the orchestrator replaces it, not coexists with it.

### 4. Testing Burden

13 new sub-agents + orchestrator = massive test surface. Each sub-agent needs unit tests, and the orchestrator needs integration tests. **Recommendation**: TDD red-first on each sub-agent; don't batch tests.

### 5. AI-Agnostic Abstraction May Be Premature

The current project is Claude-only. Adding GPT/Codex/Gemini adapters before there's demand adds unnecessary complexity. **Recommendation**: defer Phase 4 until there's a concrete need.

---

## Recommended Approach

The BUILDER_PRO-PLAN.md is a **long-term vision**, not a sprint plan. The recommended path:

1. **Start with Phase 1** — decompose the monolithic builder into sub-agents. This is the highest-value, lowest-risk change.
2. **Build the orchestrator** (Phase 2, items 8-9) — this is the core value proposition of the plan.
3. **Defer Phases 3-4** until there's proven demand — traceability, recovery, enterprise artifacts, and AI-agnostic adapters are nice-to-haves that can be added incrementally.

The current `forge-build` skill and `builder.md` agent should remain functional throughout the transition — the orchestrator should replace them, not coexist with them.

---

## Related Documents

- `BUILDER_PRO-PLAN.md` — the original vision document
- `skills/forge-build/SKILL.md` — current Stage 6 skill definition
- `agents/builder.md` — current Builder agent persona
- `build/02-architecture/architecture.md` — project architecture
- `build/03-spec/technical-spec.md` — technical specification
- `build/04-plan/task-dag.md` — task dependency graph
- `build/05-implementation/progress.md` — implementation progress tracker

---

## Verdict (appended 2026-07-30)

### Overall Assessment: **Sound vision, but scope needs trimming. Execute Phase 1 only.**

The BUILDER_PRO-PLAN correctly identifies the core problem — the builder is a monolith that does everything in one prompt — and the decomposition into specialized sub-agents is the right architectural move. However, the plan overshoots by 3–4x on scope. Here's the breakdown:

### What's Right

1. **Decomposition is justified.** The current `builder.md` agent handles context loading, code generation, testing, verification, progress tracking, and committing in a single persona. Splitting these into focused sub-agents (Context Loader, Code Generator, Test Generator, Verification Agent) will improve reliability and make each component independently testable.

2. **The orchestration primitive already exists.** ADR-006 established `scripts/_orchestrate.py` as the deterministic fan-out adapter with Pydantic schemas, index-ordered results, and bounded parallelism. The workflow engine (`scripts/_workflow.py`) supports arbitrary DAG execution. The BUILDER_PRO-PLAN doesn't need to build an orchestrator from scratch — it should layer the builder's sub-agent pipeline on top of this existing infrastructure.

3. **Context resolution is high-value.** Loading only relevant docs per task (module → interfaces → DTO → requirements) instead of the full project context is a genuine token savings and accuracy improvement. This should be prioritized.

4. **Quality gates are overdue.** The current skill only runs tests and commits. Adding compile check, lint, static analysis, and spec validation as explicit gates before commit is a real quality improvement.

### What's Wrong

1. **13 sub-agents is too many.** The plan lists Context Loader, Task Resolver, Code Generator, Refactoring Agent, Test Generator, Documentation Generator, Linter, Static Analyzer, Build Runner, Verification Agent, Commit Generator, Progress Updater, and Recovery Agent. Most of these are thin wrappers around shell commands. A practical decomposition is 5–6 sub-agents max:
   - Context Loader (resolves relevant docs)
   - Task Resolver (reads DAG, finds spec section)
   - Code Generator (writes code + tests)
   - Quality Gate Runner (compile, lint, test, static analysis — one agent, not four)
   - Commit + Progress Updater (single agent, since both are sequential bookkeeping)
   
   The Linter, Static Analyzer, Build Runner, and Documentation Generator don't need their own personas — they're shell commands called by the Quality Gate Runner.

2. **Recovery/Resumability is over-engineered.** The current `--milestone N --resume` pattern already handles resumption by skipping tasks marked done in progress.md. Building a separate state machine with `not started / in progress / completed / failed` per task is duplicating what progress.md already does.

3. **Enterprise artifacts are noise.** `build-log.md`, `execution-trace.md`, `verification.md`, `coverage.md`, `dependency-report.md`, `quality-report.md`, `security-report.md`, `implementation-decisions.md` — eight new files per task? The existing `progress.md` + `reflection.md` + gate output is sufficient. These artifacts add maintenance burden without proportional value.

4. **AI-Agnostic Adapter Layer is premature.** The project is Claude-only. Adding GPT/Codex/Gemini/OpenHands/Local Model adapters before there's a single user asking for it is textbook premature abstraction. Defer indefinitely.

5. **6 builder modes is scope creep.** `build task`, `build module`, `build work-package`, `build milestone`, `build sprint`, `build project` — the current single-mode + `--milestone N` batch covers 95% of use cases. The additional modes add branching complexity in the orchestrator for marginal UX gain.

### Existing Infrastructure the Plan Ignores

The plan proposes building several things that already exist:

| Proposed | Already Exists |
|----------|---------------|
| Execution Orchestrator | `agents/orchestrator.md` + `skills/forge-orchestrate/SKILL.md` — drives full pipeline with verified state.md advances |
| Deterministic pipeline | `scripts/_orchestrate.py` — index-ordered, deterministic fan-out with Pydantic schemas |
| DAG execution | `scripts/_workflow.py` — arbitrary DAG with parallel fan-out, worktree isolation, session reuse |
| Quality gates | `scripts/check-gate.py` — per-stage gate checking with severity levels |
| Context resolution | Could extend `scripts/load-profile.py` pattern (already loads per-stage, per-profile context) |

The BUILDER_PRO-PLAN should **extend** these, not replace them.

### Recommended Execution Plan

**Phase 1 only — Decompose the Monolith (4–6 tasks, not 17):**

1. Extract Context Loader — resolve relevant docs per task from the spec/architecture
2. Extract Code Generator — focused code + test generation sub-agent
3. Build Quality Gate Runner — single sub-agent that chains compile → lint → test → static analysis
4. Wire orchestrator — use existing `_orchestrate.py` to chain Context Loader → Code Generator → Quality Gate Runner → Commit
5. Update `forge-build` skill to use the new sub-agent pipeline instead of the monolithic builder persona
6. TDD each sub-agent in isolation

**Defer everything else.** Traceability, recovery, enterprise artifacts, AI-agnostic adapters, and additional builder modes are all deferrable until the decomposed pipeline proves itself.

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Plan scope consumes months | High | Execute Phase 1 only, measure value |
| 13 sub-agents = untestable surface | High | Reduce to 5–6, TDD each |
| Integration breaks existing pipeline | Medium | Keep `forge-build` functional during transition |
| Over-engineering recovery/artifacts | Medium | Defer, use existing progress.md |
| AI-agnostic abstraction wasted effort | Low | Defer indefinitely |

### Bottom Line

The BUILDER_PRO-PLAN is a **architecture astronaut** document — it describes a beautiful system that's 4x too complex for the current project size. The kernel of truth is: decompose the builder monolith into focused sub-agents and chain them through the existing orchestration primitive. Do that, measure the improvement, then decide if traceability/enterprise-artifacts/recovery are actually needed. Don't build the spaceship when a truck will move the freight.
