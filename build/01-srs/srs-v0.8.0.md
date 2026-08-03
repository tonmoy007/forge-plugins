# SRS — Forge v0.8.0 (Builder Phase 1: decompose the Stage 6 monolith)

> **Status**: Ready to build (2026-08-03). Derived from `docs/builder-pro-plan-analysis.md`
> (analysis of `BUILDER_PRO-PLAN.md`, verdict: "sound vision, scope needs trimming,
> execute Phase 1 only"). This SRS formalizes only the **Recommended Execution Plan**
> from that analysis — nothing from the original 17-task / 13-sub-agent proposal beyond
> that trimmed scope.
>
> Numbering continues from v0.7.0 (`T-227..T-234`, planned but not yet built — Docker
> workflow, unrelated to this feature). This work is **T-235..T-240**, independent of
> and not blocked by v0.7.0.

---

## Problem

Stage 6 (`agents/builder.md` + `skills/forge-build/SKILL.md`) is a single monolithic
persona that does context loading, code generation, testing, linting, verification,
progress tracking, and committing all in one prompt. `docs/builder-pro-plan-analysis.md`
confirms this is a real problem (reliability, testability) but that the proposed fix
(13 sub-agents, AI-agnostic adapters, 6 builder modes, 8 enterprise artifact files) is
3-4x over-scoped for a 12-stage plugin at its current size.

## Scope (Phase 1 only)

Decompose the monolith into **3 focused sub-agents**, wired sequentially, in-session,
through the existing `forge-build` skill — no new orchestration machinery, no headless
dispatch, no new state machine.

### REQ-BUILDCTX-001 — Context Loader sub-agent

`agents/context-loader.md`: given a task ID, resolves and returns only the docs/sections
relevant to that task (task-dag entry → matching technical-spec section → referenced
architecture/interface/DTO excerpts → applicable profile `additional_criteria`) instead
of the full project context. Read-only (`Read`, `Grep`, `Glob`).

- **AC-BUILDCTX-001a**: Given a task ID, output names only files/sections tied to that
  task's declared `Files` — not the entire spec or architecture doc.
- **AC-BUILDCTX-001b**: Includes task resolution (reads the task-dag entry itself) —
  folded in per the analysis's "5-6 sub-agents max" guidance; no separate Task Resolver
  agent is created.

### REQ-BUILDGEN-001 — Code Generator sub-agent

`agents/code-generator.md`: given a context bundle (REQ-BUILDCTX-001's output) and the
task definition, writes production code and tests only. No context resolution, no
commit, no progress-tracking.

- **AC-BUILDGEN-001a**: Persona's Output Contract lists only code + test files — no
  commit step, no progress.md write, no gate-running.

### REQ-BUILDGATE-001 — Quality Gate Runner sub-agent

`agents/quality-gate-runner.md`: one agent that chains compile → lint → test → static
analysis, reusing existing project-detected commands and `load-profile.py`
`additional_criteria` — not four separate agents (Linter/Static Analyzer/Build
Runner/Doc Generator stay as shell steps inside this one persona per the analysis's
explicit correction of the original 13-agent plan).

- **AC-BUILDGATE-001a**: Persona runs all four checks and reports pass/fail per check,
  not just an aggregate boolean.

### REQ-BUILDPIPE-001 — Wire the pipeline into `forge-build`

`skills/forge-build/SKILL.md` Steps sequence: adopt Context Loader → adopt Code
Generator (consumes the bundle) → adopt Quality Gate Runner → existing commit +
progress-update steps (kept inline in the skill, not a new persona, per the analysis's
final recommendation). Replaces the current single `agents/builder.md` adoption step
for the default single-task flow.

- **AC-BUILDPIPE-001a**: SKILL.md references all three new agent files, in this order.
- **AC-BUILDPIPE-001b**: `agents/builder.md` is left in the repo, unmodified, as
  reference/fallback — not deleted in this phase (risk mitigation: "keep forge-build
  functional throughout the transition").

### REQ-BUILDCOMPAT-001 — Preserve existing contracts

Milestone batch mode (`--milestone N`, `build-batch.py`), the narration contract
(REQ-INTERACTIVE-NARRATE-001: Starting/Result/Next), pause-on-first-failure, and the
Verification/Next Step sections of `forge-build`'s SKILL.md are unchanged in behavior.

- **AC-BUILDCOMPAT-001a**: `test_build_batch.py` and existing narration tests still pass
  unmodified.

### REQ-BUILDTEST-001 — TDD each sub-agent in isolation

Each new agent file ships with a structural test (frontmatter parses, `allowed-tools`
matches its stated scope, required contract sections present) mirroring
`tests/unit/test_agent_tools.py`'s pattern. Red-first: write the failing test before the
agent file.

- **AC-BUILDTEST-001a**: `test_context_loader_agent.py`, `test_code_generator_agent.py`,
  `test_quality_gate_runner_agent.py` each exist and pass.
- **AC-BUILDTEST-001b**: A cross-file test confirms `forge-build/SKILL.md` names all
  three agents in the correct order (AC-BUILDPIPE-001a made mechanically verifiable).

## Explicitly Deferred (not in this SRS)

Per the analysis's risk assessment — do not build these until the decomposed pipeline
proves itself:

- Traceability chain / `forge explain <file>` (REQ deferred)
- Recovery/resumability state machine (progress.md + `--resume` already cover this)
- 8 enterprise artifact files (`build-log.md`, `execution-trace.md`, `coverage.md`, etc.)
- AI-agnostic adapter layer (GPT/Codex/Gemini/OpenHands/local-model adapters)
- Additional builder modes (`build module`, `work-package`, `sprint`, `project`) beyond
  the existing single-task + `--milestone N` batch
- A separate Task Resolver, Refactoring Agent, or Documentation Generator persona

## Non-Functional

- **NFR-BUILDPHASE1-001**: Zero regression — full unit suite, `validate-plugin.py`, and
  `tests/integration/full-pipeline.sh` all green after the change, same as before it.
- **NFR-BUILDPHASE1-002**: No new external dependency; sub-agents are markdown persona
  files following the existing `agents/*.md` frontmatter contract (stdlib-only tooling).
