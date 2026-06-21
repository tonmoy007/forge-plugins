# SRS — Forge v0.4.0 (dynamic workflow engine: custom harness + parallel agents)

> **Status**: **Draft — ready for build** (2026-06-21, rev. 2 after independent critic review).
> Opens the v0.4 program. Adds a general **dynamic-workflow engine** — an arbitrary DAG of
> heterogeneous agent steps with parallel fan-out, inter-step data passing, and per-node
> verification — exposed through **independently-toggleable** capabilities, with a **hybrid**
> dynamism model (the LLM may generate only *bounded, pre-validated* sub-DAGs).
>
> **Grounding**: derived from a 2026-06-21 research review of Claude Code's own Dynamic
> Workflows + Agent SDK, durable/graph orchestration (LangGraph `Send`, Temporal), and the
> automatic-workflow-generation literature (AFlow ICLR'25, ADAS, a 2026 survey of workflow
> optimization for LLM agents, DSPy). Field consensus is **hybrid**: a curated DAG backbone
> with generation confined to validated slots; pure generation fails via cascading
> hallucination, cost blow-ups, and non-reproducibility — which conflict with Forge's
> traceability + gate model. Key citations in §6.
>
> **Spike landed**: `scripts/_workflow.py` + `tests/unit/test_workflow.py` (commit 7f61ba1)
> prove the executor core (REQ-WF-001); this SRS hardens it and builds the capabilities on top.
>
> **Rev. 2 changes** (from the adversarial review): config is **independent toggles**, not a
> single `mode` enum; `max_budget_usd`/`resume` are explicitly plumbed and **fresh-per-node**
> session economics are stated with deterministic budget-aware admission; the determinism
> invariant is split (engine-result vs worktree-merge); the `_orchestrate.fan_out` retrofit
> now names **all three** consumers (incl. `why.py`); per-node `cwd`, worktree lifecycle, and
> the `decompose` token-budget proxy are specified.

---

## 1. Overview

### 1.1 Problem

Forge orchestration is two disjoint, hardcoded layers: `scripts/_orchestrate.py::fan_out`
(a flat *homogeneous* parallel **map** — one shared prompt + one schema, no edges, no
data-passing) and `scripts/autopilot.py` (a linear `range(start,end+1)` **sequencer** over
the fixed 12-stage table). Neither can express an arbitrary **graph** of heterogeneous agent
steps. There is no DAG model, no dependency scheduling, no step-to-step data flow, and no
place to run parallel agents on independent work. Users want flexibility — compose custom
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
through **independently-configurable** capabilities (the engine is always on; each capability
is its own opt-in toggle, all default off):

- **Engine** (always on) — the reusable core; Forge's own fan-outs run on it.
- **User-defined flows** (`flows_enabled`) — `.forge/workflows/*.yaml` + a `/forge:flow <name>` command.
- **Per-stage parallel build** (`parallel_build`) — the build stage fans out independent
  task-DAG nodes in parallel, optionally with git-worktree isolation + an adversarial-verify join.

These are not mutually exclusive: a user may enable flows and parallel build together.

**Hybrid dynamism**: an optional `decompose` node lets the LLM generate a *sub-DAG*, which is
validated (acyclicity + schema + node/token budget) **before** any child dispatch — generation
never escapes the validated slot.

### 1.3 Scope

**In scope** — production-harden the spiked engine (incl. `max_budget_usd`/`resume` plumbing
and deterministic budget-aware admission); extract per-node verify/heal out of autopilot into
a shared module; the opt-in `orchestration:` config block (independent toggles); the
behavior-preserving retrofit of **all three** `fan_out` consumers (`/forge:review`,
`/forge:adopt`, `/forge:why`); the `.forge/workflows/*.yaml` loader + `/forge:flow` skill; the
parallel-build fan-out (per-node `cwd`) + git-worktree isolation/lifecycle + adversarial-verify
join; the hybrid validated sub-DAG `decompose` node; docs.

Reuses: `scripts/_workflow.py` (spike); `hooks/_background_agent.dispatch` (per-node executor,
unchanged); `scripts/_orchestrate.py` (its ThreadPool bounding + index-order + retry/drop
become the single-wave special case); `hooks/_cost_cap.py` + `FORGE_NO_BACKGROUND`;
`scripts/autopilot.py` verify/heal logic (extracted to a shared module); `scripts/_stage_table.py`;
the Proposal→Validator→Executor rails (ADR-006) for human-in-the-loop outputs.

**Out of scope (future)** — full *top-level* LLM-generated workflows (only validated *sub*-DAGs
inside a node); **replacing** the 12-stage pipeline (it may later *run as* a `WorkflowSpec` —
a stretch, never required); a resident orchestrator / supervisor process (ADR-005 — dispatch
stays detached one-shot); cross-project workflow sharing via `~/.forge`; embedding/vector
retrieval of workflows; **session reuse across heterogeneous DAG nodes** (see §1.4 — nodes are
intentionally fresh-session in v0.4.0); any subprocess driving Claude's in-session Agent tool.

### 1.4 Design principles (from the research)

- **Deterministic orchestration code; LLM nondeterminism at the leaves.** The plan lives in
  Python that shells to `claude -p`; only the agent invocations are stochastic.
- **Curated backbone; generation in validated slots only.** Hybrid beats both pure-fixed and
  pure-generated. Validate before execute.
- **Validate before dispatch.** Acyclicity + schema + node/token budget on every spec —
  authored *or* generated — before a single agent runs.
- **Opt-in, zero-change default.** All capability toggles default off; with them off, behavior
  matches v0.3.6 (the engine-retrofit of existing consumers is behavior-preserving).
- **Cost is per-node fresh-session in v0.4.0.** Heterogeneous nodes (distinct prompts/models)
  defeat `--resume` reuse, so each node pays the fresh-session floor (~$0.05; `_cost_cap`
  `FRESH_FLOOR_USD`). **Sizing rule:** `floor × node_count` must fit the cap; `max_total` and
  `max_budget_usd` bound a run. The default daily cap ($0.50) admits only small workflows —
  larger runs require raising the cap/budget. Admission is **deterministic**: budget is
  pre-allocated in topological order (as `max_total` already is in the spike), so cap pressure
  drops a *fixed* set, never a thread-race set.
- **Determinism is split.** The engine's *result* is byte-identical parallel-vs-sequential;
  worktree *file merges* are not (see REQ-NF-026).
- **Isolate parallel file writers.** Git worktrees per mutating node, branch-per-node (never on
  `main`/`develop`); conflicts surface at the merge/join (git detects), never silent
  last-write-wins; worktrees are torn down on success **and** on drop/crash.

---

## 2. Functional Requirements

### 2.1 Core engine

- **REQ-WF-001 — Workflow DAG model + executor (harden the spike).** Finalize
  `scripts/_workflow.py`: `WorkflowNode` (id, `build_prompt(upstream)`, `depends_on`,
  `output_schema`, `model`, `validate`, **`verify: Optional[VerifySpec]`** — skill/model/schema,
  not a bare bool), `WorkflowSpec`, `WorkflowResult`; `validate_spec` (dup-id/unknown-dep/cycle),
  `plan_waves` (Kahn, sorted within wave), `run_workflow` (validate-first; topological waves;
  bounded parallel per wave; data passing via `build_prompt`; retry-once-then-drop; id-ordered,
  byte-identical parallel/sequential; never-raises). **Add `max_budget_usd` and `resume`
  parameters** and thread them into each node's `dispatch` call. **Budget-aware admission**:
  pre-allocate `max_total` *and* `max_budget_usd` in topological order so cap pressure drops a
  deterministic set. Each node dispatches through `_background_agent.dispatch` (cost-gated).
  *Spiked in 7f61ba1; T-191 production-hardens.*
- **REQ-WF-002 — Per-node verification + heal (shared module).** Extract `run_verify`/
  `VERIFY_SCHEMA`/`verdict_failed` + the self-heal decision out of `autopilot.py` into a
  shared module (`scripts/_verify.py`) that **both** autopilot and the engine import (autopilot
  behavior unchanged — its tests stay green). When `node.verify` is set, a **fresh-session**,
  schema-constrained pass/fail verdict gates the node's result (`verdict_failed` ⇒
  drop-with-reason or one heal attempt). Lenient parse; never raises.

### 2.2 Configuration

- **REQ-WF-003 — `orchestration:` config block (independent toggles).** `.forge/config.yaml`
  gains `orchestration:` with **independent** capability toggles, **all default `false`**:
  `flows_enabled`, `parallel_build`, `worktree_isolation`, `allow_generated_subdags`; plus
  tunables `max_parallel` (default 4), `max_total` (default 64), `max_budget_usd`. The engine
  itself is always available (no toggle). Fail-soft load + coercion (invalid ignored), mirroring
  `autopilot.load_config`. Closes the documented config gap (concurrency is currently code-only).
  With all toggles off, behavior matches v0.3.6.

### 2.3 Engine consumers (default plumbing)

- **REQ-WF-004 — Forge fan-outs run on the engine.** `_orchestrate.fan_out` becomes the
  single-wave special case of `run_workflow` (a flat list of independent nodes). **All three**
  current consumers run on the engine with **behavior preserved** — their existing tests stay
  green: `/forge:review` (`review_synthesize.py`, 4 dimensions), `/forge:adopt` (`adopt.py`,
  brownfield aspects), and `/forge:why` (`why.py`, single-item fallback). Pipeline retrofit
  stays out of scope.

### 2.4 User-defined flows (`flows_enabled`)

- **REQ-WF-005 — `.forge/workflows/*.yaml` schema + loader.** A declarative workflow file:
  `name`, `description`, `nodes: [{id, prompt | prompt_template, depends_on, schema?, model?}]`.
  A loader (`scripts/workflow_loader.py`) parses YAML → `WorkflowSpec`, runs `validate_spec`,
  fail-soft (missing/malformed ⇒ reported, never raises). `prompt_template` supports
  `{{upstream_id}}` interpolation compiled to a `build_prompt`; interpolated upstream output is
  treated as untrusted data (it is schema-validated at the upstream boundary).
- **REQ-WF-006 — `/forge:flow <name>` skill.** Lists available workflows, shows `plan_waves`
  for a chosen one, and runs it via `run_workflow`. Registered in `.claude-plugin/plugin.json`
  like other skills. Persisted output flows through the Proposal→Validator→Executor rails
  (human-in-the-loop, ADR-006); nothing is written unapproved. Capability/cost-gated; degrades
  to a deterministic dry-run plan when background is unavailable. Active only when `flows_enabled`.

### 2.5 Per-stage parallel build (`parallel_build`)

- **REQ-WF-007 — Parallel build fan-out + per-node `cwd`.** When `parallel_build` is on, the
  build stage maps independent, ready task-DAG nodes (no unmet `depends_on`) to a `WorkflowSpec`
  and runs them in parallel through the engine. This requires a **per-node `cwd`** in the engine
  (today `run_workflow` takes one scalar `cwd`); add per-node `cwd` so each node can run in its
  own directory/worktree.
- **REQ-WF-008 — Worktree isolation + lifecycle.** When `worktree_isolation` is on, each
  parallel file-mutating node runs in its **own git worktree** on a **branch-per-node** (never
  `main`/`develop`, per the repo branch rules) created from a clean committed base; the node
  commits its work; results merge at a join step where git surfaces conflicts (never silent
  last-write-wins). **Lifecycle**: worktrees are removed after a successful merge **and** on any
  drop/crash (no orphaned `.git/worktrees`). Capability-gated; **degrades to sequential
  single-worktree** when worktrees are unavailable. Never raises.
- **REQ-WF-009 — Adversarial-verify join.** Before parallel build outputs are merged, an
  N-skeptic verification stage (each prompted to *refute*) gates admission by **majority of
  dispatched skeptics** (the denominator is the skeptics actually dispatched, not a fixed N, so
  a cost-cap drop can't silently lower the bar). Reuses the per-node verify primitive
  (REQ-WF-002). Refuted/failed nodes are excluded from the merge with reasons.

### 2.6 Hybrid dynamism (`allow_generated_subdags`)

- **REQ-WF-010 — Validated sub-DAG generation (`decompose` node).** An optional node type whose
  dispatch is a cheap-model, budgeted, **schema-constrained** LLM call that emits a sub-DAG
  (JSON node/edge list). The emitted sub-DAG is run through `validate_spec` **plus** a
  node-count cap and a **token-budget proxy** (a deterministic stdlib heuristic — character
  count / `len(json) // 4` — since there is no stdlib tokenizer) **before any child node
  dispatches**; any violation ⇒ drop-with-reason + deterministic fallback. Gated by
  `allow_generated_subdags` (**off by default**). Generation never escapes this validated slot.

---

## 3. Non-Functional Requirements

- **REQ-NF-024 — Stdlib + PyYAML fail-soft; never-raises.** All new code (engine, loader,
  worktree helpers, skill helpers, config) is stdlib + fail-soft PyYAML; every path degrades to
  a structured result, never an exception.
- **REQ-NF-025 — Opt-in / zero-change default.** With all `orchestration` toggles off (default),
  behavior matches v0.3.6; the engine-consumer retrofit is behavior-preserving (verified by the
  unchanged `/forge:review` + `/forge:adopt` + `/forge:why` tests).
- **REQ-NF-026 — Determinism (split).** (a) **Engine result**: `WorkflowResult.results` is
  id-ordered; parallel (`max_parallel=N`) and sequential (`max_parallel=1`) runs are
  **byte-identical *given identical dispatch outcomes and no mid-run cap trip*** (REQ-NF-009
  lineage), enforced as a test invariant. (b) Cap/failure **drops are themselves deterministic**
  (budget pre-allocated in topological order, not by thread race — REQ-NF-029). (c) Worktree
  **file merges** (`parallel_build`) are **explicitly out** of the byte-identical invariant; they
  instead guarantee: conflicts surface via git, never silent clobber, given a fixed admission
  set + merge order.
- **REQ-NF-027 — Bounded & cost-gated; budget actually plumbed.** Every dispatch routes through
  `_cost_cap` via the single adapter; `max_parallel` / `max_total` / **`max_budget_usd` are
  enforced (the param is threaded from `run_workflow` into each `dispatch`)**; the
  `FORGE_NO_BACKGROUND` kill switch and capability probe are honored; overflow/over-budget drops
  are logged. Per-node fresh-session economics are documented (§1.4); sizing is the user's
  responsibility via `max_total`/`max_budget_usd`/cap.
- **REQ-NF-028 — Isolation safety.** Parallel file-mutating nodes never share a worktree;
  conflicts surface at merge via git, never silent clobbering; worktrees are torn down on success
  and on failure; isolation is capability-gated and degrades to sequential.
- **REQ-NF-029 — Deterministic admission + ledger safety.** Budget-aware admission pre-allocates
  `max_total`/`max_budget_usd` in topological order so cap pressure drops a fixed set independent
  of thread scheduling. Cost-ledger appends remain atomic single-line writes, safe under parallel
  fan-out.
- Inherited: single dispatch adapter (one host-binary touch, ADR-005); human-in-the-loop for any
  persisted state (ADR-006); ≤2000-token session-start budget; `.forge/`-only atomic writes;
  two-remote parity; `python3`; TDD red-first.

---

## 4. Acceptance Criteria

- **AC-WF-001** — Engine core: a diamond DAG (`A→B,C→D`) passes data along every edge; parallel
  and sequential runs are byte-identical; a cycle and an unknown dependency are rejected with
  **zero** dispatches; a failed node drops its dependents while independent branches survive;
  `max_total` overflow is dropped with a logged reason. (Spike tests retained.)
- **AC-WF-002** — Budget plumbed + deterministic admission: `max_budget_usd` and `resume` reach
  `dispatch` (asserted via a spy dispatch_fn); a run that exhausts the budget mid-fan-out drops a
  **deterministic** set (pre-allocated topo order), identical across repeated runs.
- **AC-WF-003** — Per-node verify: a `verify` node gets a fresh-session schema-constrained
  verdict; a failing verdict drops-or-heals the node; never raises on garbage verdict output;
  autopilot's own verify tests still pass after the extraction.
- **AC-WF-004** — Config: the `orchestration` block round-trips fail-soft; all toggles default
  `false`; invalid values ignored.
- **AC-WF-005** — Engine consumers: `/forge:review`, `/forge:adopt`, **and `/forge:why`**
  existing tests pass unchanged on the engine; `fan_out` single-wave output equals the
  pre-retrofit output.
- **AC-WF-006** — Flows: a sample `.forge/workflows/*.yaml` loads, validates, and runs; malformed
  YAML fails soft (reported, no raise); `/forge:flow` lists and runs by name; no-op when
  `flows_enabled` is false.
- **AC-WF-007** — Parallel build: with `parallel_build` on, N independent task nodes fan out with
  per-node `cwd`; off ⇒ today's sequential behavior.
- **AC-WF-008** — Worktree isolation: each mutating node gets its own worktree + branch;
  conflicting writes surface at merge (never silent clobber); worktrees are removed on success
  **and** on a dropped/failed node; with worktrees unavailable it degrades to sequential without
  raising.
- **AC-WF-009** — Adversarial-verify join admits a node only on majority of *dispatched* skeptics;
  refuted nodes are excluded from the merge with reasons; a cap-dropped skeptic does not lower the
  denominator silently.
- **AC-WF-010** — Generation: a generated sub-DAG containing a cycle, or exceeding the node-count
  or token-proxy budget, is rejected **before** any child dispatch; `allow_generated_subdags`
  defaults off.
- **AC-WF-011** — Full suite green, `validate-plugin.py` 0, `full-pipeline.sh` 12/12 — with every
  toggle both off (default) and on.

---

## 5. Traceability

| REQ-ID | Task |
|--------|------|
| REQ-WF-001 | T-191 |
| REQ-WF-002 | T-192 |
| REQ-WF-003 | T-193 |
| REQ-WF-004 | T-194 |
| REQ-WF-005, 006 | T-195 |
| REQ-WF-007 | T-196 |
| REQ-WF-008 | T-197 |
| REQ-WF-009 | T-198 (impl) / T-200 (docs) |
| REQ-WF-010 | T-199 |
| REQ-NF-024 | T-191, T-192, T-195 |
| REQ-NF-025 | T-194 |
| REQ-NF-026 | T-191, T-194 |
| REQ-NF-027 | T-191, T-193 |
| REQ-NF-028 | T-196, T-197 |
| REQ-NF-029 | T-191 |
| (release) | T-201 |

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
  (arXiv 2510.06711); a 2026 survey of workflow optimization for LLM agents (static templates →
  search-optimized → dynamic runtime graphs; verdict: **hybrid, context-decides** — arXiv ID to
  confirm at build); DSPy (compile prompts within a fixed pipeline, arXiv 2310.03714).
- **Internal contracts** — ADR-005 (single dispatch adapter / no resident process), ADR-006
  (orchestration primitive; scripts cannot drive the Agent tool; Proposal→Validator→Executor),
  ADR-007 (cost-cap hard gate); REQ-NF-009 (parallel==sequential determinism).
