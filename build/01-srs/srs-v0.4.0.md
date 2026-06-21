# SRS — Forge v0.4.0 (dynamic workflow engine: custom harness + parallel agents)

> **Status**: **Draft — ready for build** (2026-06-21). Opens the v0.4 program.
> Adds a general **dynamic-workflow engine** — an arbitrary DAG of heterogeneous agent
> steps with parallel fan-out, inter-step data passing, and per-node verification — exposed
> through three **user-configurable** modes, with a **hybrid** dynamism model (the LLM may
> generate only *bounded, pre-validated* sub-DAGs).
>
> **Grounding**: derived from a 2026-06-21 research review of Claude Code's own Dynamic
> Workflows + Agent SDK, durable/graph orchestration (LangGraph `Send`, Temporal), and the
> automatic-workflow-generation literature (AFlow ICLR'25, ADAS, survey "From Static
> Templates to Dynamic Runtime Graphs" arXiv 2603.22386, DSPy). The field consensus is
> **hybrid**: a curated DAG backbone with generation confined to validated slots; pure
> generation fails via cascading hallucination, cost blow-ups, and non-reproducibility —
> which conflict with Forge's traceability + gate model. Key citations in §6.
>
> **Spike landed**: `scripts/_workflow.py` + `tests/unit/test_workflow.py` (commit 7f61ba1)
> already prove the executor core (REQ-WF-001); this SRS hardens it and builds the modes on top.

---

## 1. Overview

### 1.1 Problem

Forge orchestration is two disjoint, hardcoded layers: `scripts/_orchestrate.py::fan_out`
(a flat *homogeneous* parallel **map** — one shared prompt + one schema, no edges, no
data-passing) and `scripts/autopilot.py` (a linear `range(start,end+1)` **sequencer** over
the fixed 12-stage table). Neither can express an arbitrary **graph** of heterogeneous
agent steps. There is no DAG model, no dependency scheduling, no step-to-step data flow, and
no place to run parallel agents on independent work. Users want flexibility — compose custom
multi-agent workflows and parallelize independent build tasks — not only the fixed pipeline.

A platform constraint shapes what is buildable: **a Python `scripts/` primitive cannot drive
Claude's in-session Agent/Task tool** (ADR-006). "Parallel agents" therefore means parallel
`claude -p` dispatches via the single `hooks/_background_agent.dispatch` wrapper, or an
in-session skill that itself spawns subagents — never a subprocess calling the Agent tool.

### 1.2 Objective

Deliver a general **dynamic-workflow engine** (`scripts/_workflow.py`) that generalizes
`fan_out` from a flat map to a topological **DAG executor** — per-node prompt/schema/model,
`depends_on` edges, dependency-wave scheduling, bounded parallel fan-out per wave, inter-step
data passing, per-node verification, deterministic + never-raising — built **on** the mature
single-step `dispatch` executor (cost-gated, structured outputs, model routing). Expose it
through three modes the **user selects via config** (`orchestration.mode`, default `1`):

1. **General engine** (default) — the reusable core; Forge's own fan-outs run on it.
2. **User-defined flows** — `.forge/workflows/*.yaml` + a `/forge:flow <name>` command.
3. **Per-stage parallel build** — the build stage fans out independent task-DAG nodes in
   parallel with git-worktree isolation + an adversarial-verify join.

**Hybrid dynamism**: an optional `decompose` node lets the LLM generate a *sub-DAG*, which is
validated (acyclicity + schema + budget) **before** any child dispatch — generation never
escapes the validated slot.

### 1.3 Scope

**In scope** — production-harden the spiked engine; lift per-node verify/heal out of
autopilot so it operates on arbitrary nodes; the opt-in `orchestration:` config block; the
mode-1 behavior-preserving retrofit of `fan_out`/`/forge:review`/`/forge:adopt`; the mode-2
YAML loader + `/forge:flow` skill; the mode-3 parallel-build fan-out + worktree isolation +
adversarial-verify join; the hybrid validated sub-DAG `decompose` node; docs.

Reuses: `scripts/_workflow.py` (spike); `hooks/_background_agent.dispatch` (per-node executor,
unchanged); `scripts/_orchestrate.py` (its ThreadPool bounding + index-order + retry/drop
become the single-wave special case); `hooks/_cost_cap.py` + `FORGE_NO_BACKGROUND`;
`scripts/autopilot.py` verify/heal/checkpoint behavior; `scripts/_stage_table.py`; the
Proposal→Validator→Executor rails (ADR-006) for human-in-the-loop outputs.

**Out of scope (future)** — full *top-level* LLM-generated workflows (only validated *sub*-DAGs
inside a node); **replacing** the 12-stage pipeline (it may later *run as* a `WorkflowSpec` —
a stretch, never required); a resident orchestrator / supervisor process (ADR-005 — dispatch
stays detached one-shot); cross-project workflow sharing via `~/.forge`; embedding/vector
retrieval of workflows; any subprocess driving Claude's in-session Agent tool (ADR-006).

### 1.4 Design principles (from the research)

- **Deterministic orchestration code; LLM nondeterminism at the leaves.** The plan lives in
  Python that shells to `claude -p`; only the agent invocations are stochastic (Claude
  Workflows, LangGraph, Temporal all converge here).
- **Curated backbone; generation in validated slots only.** Hybrid beats both pure-fixed and
  pure-generated (survey 2603.22386, AFlow, ADAS). Validate before execute.
- **Validate before dispatch.** Acyclicity + schema + node/token budget on every spec —
  authored *or* generated — before a single agent runs.
- **Opt-in, zero-change default.** Mode 1 changes internal plumbing behavior-preservingly;
  modes 2/3, worktree isolation, and sub-DAG generation are **off by default**.
- **Bounded, cost-gated, never-raises; determinism as a test invariant.** Parallel output ==
  sequential output, byte-identical (results id-ordered); retry-once-then-drop, never silent.
- **Isolate parallel file writers.** Git worktrees per mutating node; conflicts surface at the
  merge/join (git detects), never silent last-write-wins.

---

## 2. Functional Requirements

### 2.1 Core engine

- **REQ-WF-001 — Workflow DAG model + executor (harden the spike).** Finalize
  `scripts/_workflow.py`: `WorkflowNode` (id, `build_prompt(upstream)`, `depends_on`,
  `output_schema`, `model`, `validate`, `verify`), `WorkflowSpec`, `WorkflowResult`;
  `validate_spec` (dup-id / unknown-dep / cycle), `plan_waves` (Kahn, sorted within wave),
  `run_workflow` (validate-first; topological waves; bounded parallel per wave via
  `ThreadPoolExecutor`; inter-step data passing through `build_prompt`; retry-once-then-drop;
  id-ordered, byte-identical parallel/sequential; never-raises). Each node dispatches through
  `_background_agent.dispatch` (cost-gated). *Spiked in 7f61ba1; T-191 production-hardens.*
- **REQ-WF-002 — Per-node verification + heal.** Lift `run_verify`/`VERIFY_SCHEMA` and the
  self-heal decision out of `autopilot.py` into engine hooks that operate on **arbitrary**
  nodes: when `node.verify` is set, a fresh-context, schema-constrained pass/fail verdict
  gates the node's result (`verdict_failed` ⇒ drop-with-reason or one heal attempt). Reuses
  the autopilot verify schema + lenient parse; never raises.

### 2.2 Configuration

- **REQ-WF-003 — `orchestration:` config block (opt-in).** `.forge/config.yaml` gains
  `orchestration:` with `mode` (default `1`), `max_parallel` (default 4), `max_total`
  (default 64), `max_budget_usd`, `worktree_isolation` (default `false`),
  `allow_generated_subdags` (default `false`). Fail-soft load + coercion (invalid ignored),
  mirroring `autopilot.load_config`. Closes the documented config gap (concurrency is
  currently code-only). With defaults, behavior matches v0.3.6.

### 2.3 Mode 1 — general engine (default)

- **REQ-WF-004 — Forge fan-outs run on the engine.** `_orchestrate.fan_out` becomes the
  single-wave special case of `run_workflow` (a flat list of independent nodes). `/forge:review`
  (4 review dimensions) and `/forge:adopt` (brownfield aspects) run on the engine with
  **behavior preserved** — their existing determinism tests stay green. Pipeline retrofit
  stays out of scope.

### 2.4 Mode 2 — user-defined flows

- **REQ-WF-005 — `.forge/workflows/*.yaml` schema + loader.** A declarative workflow file:
  `name`, `description`, and `nodes: [{id, prompt | prompt_template, depends_on, schema?,
  model?}]`. A loader (`scripts/workflow_loader.py`) parses YAML → `WorkflowSpec`, runs
  `validate_spec`, and is fail-soft (missing/malformed ⇒ reported, never raises). `prompt_template`
  supports `{{upstream_id}}` interpolation compiled to a `build_prompt`.
- **REQ-WF-006 — `/forge:flow <name>` skill.** Lists available workflows, shows `plan_waves`
  for a chosen one, and runs it via `run_workflow`. Any persisted output flows through the
  Proposal→Validator→Executor rails (human-in-the-loop, ADR-006); nothing is written
  unapproved. Capability/cost-gated; degrades to a deterministic dry-run plan when background
  is unavailable.

### 2.5 Mode 3 — per-stage parallel build

- **REQ-WF-007 — Parallel build fan-out.** When `mode = 3`, the build stage maps independent,
  ready task-DAG nodes (no unmet `depends_on`) to a `WorkflowSpec` and runs them in parallel
  through the engine instead of strictly one-at-a-time.
- **REQ-WF-008 — Worktree isolation.** When `worktree_isolation` is on, each parallel
  file-mutating node runs in its **own git worktree**; results are merged at a join step where
  git surfaces conflicts (never silent last-write-wins). Capability-gated; **degrades to
  sequential, single-worktree** execution when worktrees are unavailable. Never raises.
- **REQ-WF-009 — Adversarial-verify join.** Before parallel build outputs are merged, an
  N-skeptic verification stage (each prompted to *refute*) gates admission by majority
  survival — reusing the per-node verify primitive (REQ-WF-002). Failing nodes are dropped
  with reasons, not merged.

### 2.6 Hybrid dynamism

- **REQ-WF-010 — Validated sub-DAG generation (`decompose` node).** An optional node type
  whose dispatch is a cheap-model, budgeted, **schema-constrained** LLM call that emits a
  sub-DAG (JSON node/edge list). The emitted sub-DAG is run through `validate_spec` **plus** a
  node-count and token budget check **before any child node dispatches**; on any violation the
  decompose node is dropped with a reason and the engine falls back to its deterministic path.
  Gated by `allow_generated_subdags` (**off by default**). Generation never escapes this
  validated slot.

---

## 3. Non-Functional Requirements

- **REQ-NF-024 — Stdlib + PyYAML fail-soft; never-raises.** All new code (engine, loader,
  skill helpers, config) is stdlib + fail-soft PyYAML; every path degrades to a structured
  result, never an exception.
- **REQ-NF-025 — Opt-in / zero-change default.** With `orchestration` unset (or `mode: 1`,
  isolation off, generation off), behavior matches v0.3.6; the mode-1 retrofit is
  behavior-preserving (verified by the unchanged `/forge:review` + `/forge:adopt` tests).
- **REQ-NF-026 — Determinism invariant.** `run_workflow` results are id-ordered; parallel
  (`max_parallel=N`) and sequential (`max_parallel=1`) runs are **byte-identical**, enforced
  as a test invariant (REQ-NF-009 lineage), not asserted in prose.
- **REQ-NF-027 — Bounded & cost-gated.** Every dispatch routes through `_cost_cap` via the
  single adapter; `max_parallel` / `max_total` / `max_budget_usd` are enforced; the
  `FORGE_NO_BACKGROUND` kill switch and capability probe are honored; overflow drops are logged.
- **REQ-NF-028 — Isolation safety.** Parallel file-mutating nodes never share a worktree;
  conflicts surface at the merge/join via git, never as silent clobbering; isolation is
  capability-gated and degrades to sequential.
- Inherited: single dispatch adapter (one host-binary touch, ADR-005); human-in-the-loop for
  any persisted state (ADR-006); ≤2000-token session-start budget; `.forge/`-only atomic
  writes; two-remote parity; `python3`; TDD red-first.

---

## 4. Acceptance Criteria

- **AC-WF-001** — Engine: a diamond DAG (`A→B,C→D`) passes data along every edge; parallel
  and sequential runs are byte-identical; a cycle and an unknown dependency are rejected with
  **zero** dispatches; a failed node drops its dependents while independent branches survive;
  `max_total` overflow is dropped with a logged reason. (Spike tests retained + extended.)
- **AC-WF-002** — Per-node verify: a `verify` node gets a schema-constrained verdict; a
  failing verdict drops-or-heals the node; never raises on garbage verdict output.
- **AC-WF-003** — Config: the `orchestration` block round-trips fail-soft; defaults are
  `mode 1`, isolation off, generation off; invalid values are ignored.
- **AC-WF-004** — Mode 1: the existing `/forge:review` and `/forge:adopt` determinism tests
  pass unchanged on the engine; `fan_out` single-wave output equals the pre-retrofit output.
- **AC-WF-005** — Mode 2: a sample `.forge/workflows/*.yaml` loads, validates, and runs;
  malformed YAML fails soft (reported, no raise); `/forge:flow` lists and runs by name.
- **AC-WF-006** — Mode 3: parallel build fans out N independent task nodes; with isolation on
  each runs in its own worktree and conflicting writes surface at merge; with worktrees
  unavailable it degrades to sequential without raising.
- **AC-WF-007** — Adversarial-verify join admits a node only on majority survival; refuted
  nodes are excluded from the merge with reasons.
- **AC-WF-008** — Generation: a generated sub-DAG containing a cycle or exceeding the node/
  token budget is rejected **before** any child dispatch; `allow_generated_subdags` defaults off.
- **AC-WF-009** — Full suite green, `validate-plugin.py` 0, `full-pipeline.sh` 12/12 — with
  every mode both off (default) and on.

---

## 5. Traceability

| REQ-ID | Task |
|--------|------|
| REQ-WF-001, 002 | T-191 |
| REQ-WF-003 | T-192 |
| REQ-WF-004, NF-025 | T-193 |
| REQ-WF-005, 006 | T-194 |
| REQ-WF-007, 008, NF-028 | T-195 |
| REQ-WF-009 | T-196 |
| REQ-WF-010 | T-197 |
| REQ-WF-009 (docs) | T-198 |
| (release) | T-199 |

---

## 6. Key citations (research, 2026-06-21)

- **Claude Code Dynamic Workflows + Agent SDK** — deterministic JS orchestration
  (`agent`/`parallel`/`pipeline`), journaled-resume, schema outputs, 16-concurrent/1000-total
  caps, worktree isolation, stage=workflow for gates: code.claude.com/docs/en/workflows;
  code.claude.com/docs/en/agent-sdk/overview; code.claude.com/docs/en/worktrees.
- **Graph / durable orchestration** — LangGraph `Send` API (runtime map-reduce fan-out) +
  checkpointers; Temporal durable execution (deterministic replay; nondeterminism in
  activities): langchain-ai/langgraph control-flow primitives; temporal.io AI agents.
- **Automatic workflow generation** — AFlow (MCTS over code workflows, ICLR'25, arXiv
  2410.10762); ADAS / Meta Agent Search (arXiv 2408.08435) + "Inefficiencies of Meta Agents"
  (2510.06711); survey "From Static Templates to Dynamic Runtime Graphs" (arXiv 2603.22386,
  verdict: **hybrid, context-decides**); DSPy (compile prompts within a fixed pipeline, arXiv
  2310.03714).
- **Internal contracts** — ADR-005 (single dispatch adapter / no resident process), ADR-006
  (orchestration primitive; scripts cannot drive the Agent tool; Proposal→Validator→Executor),
  ADR-007 (cost-cap hard gate); REQ-NF-009 (parallel==sequential determinism).
