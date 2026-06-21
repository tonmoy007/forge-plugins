# Dynamic workflow engine (`scripts/_workflow.py`)

> Loaded on demand. The technical reference for the v0.4.0 dynamic-workflow engine — the DAG
> model, the `orchestration:` toggles + tunables, hybrid sub-DAG generation, git-worktree
> isolation, and the per-node fresh-session cost economics. The engine itself is **always
> available**; every capability *built on top of it* is an independent opt-in toggle, all
> default `false`, so with no `orchestration:` block Forge behaves exactly as v0.3.6
> (REQ-NF-025). For the config-loading rules see [`orchestration-config.md`](orchestration-config.md).

## What the engine is

`run_workflow` generalizes `_orchestrate.fan_out` from a flat *homogeneous* parallel map (one
shared prompt + one schema, no edges) to a topological **DAG executor** over *heterogeneous*
agent steps: each node carries its own prompt builder, optional output schema, model, and
validator; nodes declare `depends_on` edges; downstream nodes receive their upstream results
for inter-step data passing. Nodes are scheduled in dependency *waves* (Kahn's algorithm) and
each wave fans out across bounded parallel `claude -p` dispatches. Forge's own fan-outs
(`/forge:review`, `/forge:adopt`, `/forge:why`) run on it as the single-wave special case.

### The platform constraint (ADR-006)

A Python `scripts/` primitive **cannot** drive Claude's in-session Agent/Task tool. "Parallel
agents" therefore means parallel `claude -p` subprocess dispatches through the single
`hooks/_background_agent.dispatch` wrapper (cost-gated via `_cost_cap`, never-raises) — never a
subprocess invoking the Agent tool. Every node, verifier, and skeptic in this engine is a
`dispatch` call. This is why the deterministic plan lives in Python and only the leaf agent
invocations are stochastic.

## The DAG model

The data model is plain `dataclasses` in `scripts/_workflow.py`:

### `WorkflowNode`

One step in the DAG.

| Field | Type | Meaning |
|-------|------|---------|
| `id` | `str` | Unique node id; results are keyed and ordered by it. |
| `build_prompt` | `Callable[[dict], str]` | Receives `{dep_id: validated_result}` for this node's completed upstream deps and returns the prompt string — the inter-step data channel. |
| `depends_on` | `list[str]` | Upstream node ids (default `[]`). |
| `output_schema` | `Optional[dict]` | JSON schema passed to `dispatch` to constrain the reply. |
| `model` | `Optional[str]` | Per-node model override (else the dispatch default). |
| `validate` | `Optional[Callable[[dict], Any]]` | Post-parse validator; a raise → drop-with-reason, not a crash. |
| `verify` | `Optional[VerifySpec]` | Per-node fresh-session verification (below). |
| `cwd` | `Optional[str]` | Per-node working directory (T-196); `None` ⇒ inherit `run_workflow`'s scalar `cwd`, so existing single-`cwd` callers are unaffected. |
| `decompose` | `Optional[DecomposeSpec]` | Marks a sub-DAG-generating node (below); `None` ⇒ a plain node. |

### `VerifySpec`

A declarative per-node verification request: `skill: str`, `model: Optional[str]`,
`schema: Optional[dict]`. When a node carries one, an **independent fresh-session** verifier
runs after the node's own dispatch and gates its result; a clean `fail` verdict triggers one
bounded heal (re-dispatch + re-verify) before dropping. An unavailable or garbage verdict
degrades to *passed* — the verifier is an extra check and must not block (REQ-NF-013). The
shared primitives (`run_verify` / `VERIFY_SCHEMA` / `verdict_failed` / `should_heal`) live in
`scripts/_verify.py`, imported by **both** the engine and `autopilot.py`.

### `WorkflowSpec` / `WorkflowResult`

`WorkflowSpec` is just `nodes: list[WorkflowNode]`. `WorkflowResult` carries
`results: dict` (`{node_id: validated_output}`, **ordered by node id**), `completed: int`,
`dropped: int`, `total_cost_usd: float`, and `dropped_reasons: list[str]`. A dropped or
over-cap node is never silently truncated — it appears in `dropped_reasons`.

### `plan_waves(spec) -> list[list[str]]`

Groups node ids into dependency waves via Kahn's algorithm, **sorted within each wave** for
determinism. Returns `[]` when the graph has a cycle (no valid ordering). Unknown dependencies
are ignored here — they are reported by `validate_spec`.

### `validate_spec(spec) -> list[str]`

Returns structural errors (`[]` == valid), never raises:

- **duplicate node id** — two nodes share an `id`.
- **unknown dependency** — a `depends_on` names a node not in the spec.
- **cycle detected** — `plan_waves` finds no valid ordering.

`run_workflow` calls `validate_spec` **first**; an invalid spec dispatches nothing and returns
all nodes dropped with `invalid spec: …` reasons.

## Execution & determinism

`run_workflow(spec, *, forge_dir, feature, max_parallel=4, max_total=64, max_budget_usd=None,
resume=None, dispatch_fn=None, claude_bin=None, cwd=None, allow_generated_subdags=False)`:

1. **Validate** the spec (invalid ⇒ nothing dispatched).
2. **Budget-aware admission** — walk nodes in topological order (wave, then sorted id) and admit
   each while it fits *both* the count cap (`max_total`) and the spend cap (`max_budget_usd`,
   charged one fresh-session floor per node). This pass is single-threaded, so cap pressure
   drops a **fixed** set, identical across parallel and sequential runs (REQ-NF-029).
   `max_budget_usd` bounds the **admission set** (one floor per admitted node), *not* realized
   spend: a node's retry, per-node verify, or heal dispatches are not pre-charged, so actual cost
   can exceed it. Size with headroom and keep the `_cost_cap` daily cap as the hard spend gate.
3. **Run wave by wave** — each wave's ready nodes fan out across at most `max_parallel` threads;
   results pass to downstream nodes via `build_prompt`.
4. **Retry-once-then-drop** — a failed dispatch is retried once, then dropped with a reason; a
   node whose dependency dropped is skipped (no orphan dispatch).

**Determinism is split** (REQ-NF-026):

- **(a) Engine result.** `results` is id-ordered; a parallel run (`max_parallel=N`) and a
  sequential run (`max_parallel=1`) are **byte-identical** *given identical dispatch outcomes
  and no mid-run cap trip*. Enforced as a test invariant.
- **(b) Drops are deterministic.** Budget pre-allocated in topological order, not by thread race.
- **(c) Worktree file merges are out** of the byte-identical invariant (see below); they instead
  guarantee conflicts surface via git, never silent clobber, given a fixed admission + merge order.

The engine **never raises**: every failure path becomes a structured `dropped_reasons` entry.

## The `orchestration:` config block

`.forge/config.yaml` gains an opt-in `orchestration:` block, loaded fail-soft by
`scripts/_workflow_config.py:load_orchestration_config`. The toggles are **independent** — any
combination is valid; turning one on never implies another. Full coercion rules and the
fail-soft table live in [`orchestration-config.md`](orchestration-config.md); the real defaults:

| Key | Type | Default | Gates |
|-----|------|---------|-------|
| `flows_enabled` | bool | `false` | `/forge:flow` + `.forge/workflows/*.yaml` |
| `parallel_build` | bool | `false` | parallel fan-out of independent build tasks |
| `worktree_isolation` | bool | `false` | each parallel mutating node in its own git worktree |
| `allow_generated_subdags` | bool | `false` | the validated `decompose` sub-DAG node |
| `max_parallel` | int ≥1 | `4` | max concurrent dispatches per wave |
| `max_total` | int ≥1 | `64` | hard cap on total nodes admitted per run |
| `max_budget_usd` | float | `null` (no cap) | per-run **admission** ceiling (one floor/node; not realized spend — see above) |

Toggles use strict `is True` semantics: a stray `1` / `"yes"` does **not** enable a capability.
With every toggle off (the default), behavior matches v0.3.6.

## User-defined flows (`flows_enabled`)

A declarative `.forge/workflows/<name>.yaml` compiles to a `WorkflowSpec` via
`scripts/workflow_loader.py`:

```yaml
name: research-brief
description: gather sources then draft a brief
nodes:
  - id: gather
    prompt: "Research the topic and return JSON {findings: [...]}"
  - id: draft
    depends_on: [gather]
    prompt_template: "Write a draft from these findings: {{gather}}"
    schema: {type: object}      # optional → WorkflowNode.output_schema
    model: claude-haiku-4-5     # optional → WorkflowNode.model
```

A literal `prompt` compiles to a constant `build_prompt`; a `prompt_template` compiles to a
closure that substitutes `{{upstream_id}}` tokens with the matching upstream result at run time.
Interpolated upstream output is treated as **untrusted data** — it is spliced in with plain
`str()` (never `str.format`/eval), so a result containing `{`/`}` cannot hijack the prompt; it
was schema-validated at the upstream node boundary. The loader is fail-soft: a missing file,
absent PyYAML, malformed YAML, or a structurally invalid spec all yield
`LoadResult(spec=None, errors=[...])` — it never raises.

`/forge:flow` is the command surface (active only when `flows_enabled`):

- `/forge:flow` — list available workflows.
- `/forge:flow <name>` — run a workflow through `run_workflow`.
- `/forge:flow <name> --plan` — show the `plan_waves` dependency plan without dispatching.

Persisted output flows through the Proposal→Validator→Executor rails (ADR-006): nothing is
written to the project unapproved. When background is unavailable (`claude` not on PATH or
`FORGE_NO_BACKGROUND=1`), it degrades to the deterministic dry-run plan.

## Per-stage parallel build (`parallel_build`)

`scripts/parallel_build.py:run_parallel_build` maps the *ready* task-DAG nodes — those whose
`depends_on` are all done — to a `WorkflowSpec` of independent (edge-less) nodes and runs them
through the engine. With `parallel_build` on, the width is `config.max_parallel`; off, it is `1`
(sequential), preserving today's behavior. Each node gets its own `cwd` via the caller's
`cwd_for(task_id)` (T-196), which is how worktree isolation hands each node its own checkout.

## Worktree isolation + lifecycle (`worktree_isolation`)

When `worktree_isolation` is on and the target is a git work tree, each parallel file-mutating
node runs in its **own git worktree** on a **branch-per-node** (`scripts/_worktree.py`):

- **Branch naming** — every branch is namespaced under `forge/wt/<safe-node-id>`, so it can
  never be (or move) a protected branch; a node literally named `main` becomes `forge/wt/main`,
  distinct from `main`. Checkouts live under `<repo>/.forge-worktrees/<node>`.
- **Join** — sequential, deterministic id order (git cannot merge two branches into one tree
  concurrently). Each node commits in its worktree, then merges back with `--no-ff`. A
  **conflicting** merge fails loudly: it is `git merge --abort`-ed so the base ref is untouched
  (never silent last-write-wins) and the node is excluded with a reason.
- **Lifecycle** — every worktree is torn down in a `finally`, so teardown happens on success
  **and** on any drop/crash; the branch is force-deleted and the checkout removed (no orphaned
  `.git/worktrees`).
- **Degradation** — when worktrees are unavailable, it degrades to a **sequential single
  worktree** (`max_parallel=1`), never raising.

### Adversarial-verify join (`adversarial_skeptics > 0`)

Before a built node merges, `adversarial_admit` can gate it through N independent skeptics, each
prompted to **refute** the work (fresh context, schema-constrained verdict, reusing the
`_verify` primitive). Admission is by **majority of *dispatched* skeptics**: a cost-cap-dropped
skeptic (`status == "skipped"`) counts toward neither the numerator nor the denominator, so it
can never silently lower the bar. A strict majority is required (`admit_votes * 2 > dispatched`;
a tie is not a majority). If zero skeptics dispatch, the verifier is unavailable and degrades to
*admit*. Refuted nodes are excluded from the merge with reasons.

## Hybrid sub-DAG generation (`allow_generated_subdags`)

A node carrying a `DecomposeSpec` is a `decompose` node: its `build_prompt` is a cheap-model,
schema-constrained **generation** prompt whose reply is a sub-DAG (a JSON node/edge list).
Generation **never escapes a validated slot** — before *any* child dispatches, the candidate
sub-DAG is admitted by `_admit_subdag`, three pure-function gates:

1. **node-count cap** — `len(nodes) <= DecomposeSpec.max_nodes` (default `8`).
2. **token-budget proxy** — a deterministic stdlib heuristic (`len(json) // 4`, since there is
   no stdlib tokenizer) compared against `DecomposeSpec.max_chars // 4` (default `max_chars`
   `4096` ≈ 1024 tokens).
3. **`validate_spec`** — acyclicity + duplicate-id + unknown-dependency.

The first failing gate yields a reason; the whole admission is a pure function of the generated
JSON (same JSON ⇒ same accept/reject). Any violation — or garbage/failed generation — drops the
generated set with a reason and runs the **deterministic** `DecomposeSpec.fallback` sub-DAG
(`[]` ⇒ a pure no-op). Gated by `allow_generated_subdags` (**off by default**); with it off the
decompose node is inert and behaves as a plain node — no generation, no children.

## Cost economics: per-node fresh sessions

Cost is **per-node fresh-session** in v0.4.0. Heterogeneous nodes (distinct prompts/models)
defeat `--resume` session reuse, so each node pays the fresh-session cache-creation floor.
The engine charges `_workflow.FRESH_FLOOR_USD`, sourced from `_background_agent.FRESH_FLOOR_USD`
(currently **`$0.06`**; a resumed dispatch would be `RESUME_FLOOR_USD` `$0.01`) so the admission
estimate can never drift from the real cost gate.

**Sizing rule.** `FRESH_FLOOR_USD × node_count` must fit the budget. A run is bounded by three
knobs: `max_total` (node count), `max_budget_usd` (per-run spend), and the `_cost_cap` daily cap
(`DEFAULT_DAILY_USD` = `$0.50`). At the `$0.06` floor, the default daily cap admits only ~8 fresh
nodes before it trips — i.e. **only small workflows run under defaults**. Larger runs require
raising `max_budget_usd` and/or the daily cap. Admission is deterministic (topological
pre-allocation), so cap pressure always drops the *same* fixed set, never a thread-race set.

`max_budget_usd` and `resume` are threaded from `run_workflow` into every node's `dispatch`
call: the CLI enforces the per-dispatch ceiling and reuses the given session when one is passed.

## Failure & safety summary

- Every new module (engine, loader, worktree helpers, config) is **stdlib + fail-soft PyYAML**
  and **never raises** (REQ-NF-024) — every path degrades to a structured result.
- Every dispatch routes through the single `_background_agent` adapter and is `_cost_cap`-gated;
  the `FORGE_NO_BACKGROUND=1` kill switch and the capability probe are honored.
- Parallel file-mutating nodes never share a worktree; conflicts surface via git; worktrees are
  torn down on success and failure; isolation degrades to sequential when unavailable.
- With all `orchestration` toggles off (default), behavior matches v0.3.6.
