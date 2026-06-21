# Task DAG — Forge v0.4.0 (dynamic workflow engine)

> **Status**: **Ready to build** (2026-06-21, rev. 2 after independent critic review).
> Derived from `build/01-srs/srs-v0.4.0.md`. Numbering continues from v0.3.6 (T-185..T-190);
> this is **T-191..T-201**.
>
> Format: `T-NNN [size] title` — Size: S (~30min), M (~2hr), L (~half-day).
>
> | Milestone | Tag | Gate |
> |-----------|-----|------|
> | M1 Core engine + config | — | build first (spike landed in 7f61ba1) |
> | M2 Engine consumers (default) | — | M1 landed |
> | M3 User-defined flows | — | M1 landed |
> | M4 Per-stage parallel build | — | M1 landed |
> | M5 Hybrid generation | — | M1 landed |
> | M6 Docs + release | v0.4.0 | M1–M5 landed |
>
> **Invariants** (every task): stdlib + PyYAML fail-soft; **never-raises**; **opt-in** — zero
> behavior change when all `orchestration` toggles are off; **engine-result determinism**
> parallel==sequential byte-identical *given identical dispatch outcomes + no mid-run cap trip*
> (REQ-NF-026/009), with cap/failure drops themselves deterministic (topo pre-allocation);
> worktree file-merges are out of that invariant; every dispatch routes through `_cost_cap` via
> the single `_background_agent` adapter (ADR-005) and threads `max_budget_usd`/`resume`;
> parallel agents are `claude -p` dispatches, never the in-session Agent tool (ADR-006);
> parallel file-mutating nodes never share a worktree, branch-per-node off `main`/`develop`,
> torn down on success and on failure; persisted outputs go through Proposal→Validator→Executor
> (human-in-the-loop); `.forge/`-only atomic writes; TDD red-first; full suite +
> `validate-plugin.py` 0 + `full-pipeline.sh` 12/12 green per task. Reuses `scripts/_workflow.py`
> (spike), `_background_agent.dispatch`, `_orchestrate` (single-wave special case), `_cost_cap`,
> `autopilot` verify/heal (extracted to `scripts/_verify.py`), `_stage_table`.

---

## Milestone 1: Core engine + config

### T-191 [M] Harden engine — budget/resume plumbing, deterministic admission, verify field
- **Description**: Finalize the spiked `scripts/_workflow.py` API. **Add `max_budget_usd` and
  `resume` parameters** to `run_workflow` and thread them into each node's `dispatch` kwargs
  (today absent — `_workflow.py:165,238`). Make admission **deterministic & budget-aware**:
  pre-allocate `max_budget_usd` in topological order alongside the existing `max_total`
  pre-allocation, so a near-cap run drops a fixed set independent of thread scheduling. Change
  `WorkflowNode.verify` from a bare `bool` to `Optional[VerifySpec]` (skill/model/schema). Spike
  tests already cover the executor core (7f61ba1).
- **Files**: `scripts/_workflow.py`, `tests/unit/test_workflow.py`
- **Done when**: AC-WF-001/002 — spike invariants retained; `max_budget_usd`+`resume` reach
  `dispatch` (spy); budget-exhausted fan-out drops a deterministic set across repeated runs.
- **Depends on**: none (spike landed)
- **REQ-IDs**: REQ-WF-001, NF-024, NF-026, NF-027, NF-029

### T-192 [M] Extract per-node verify/heal to a shared module
- **Description**: Extract `run_verify` / `VERIFY_SCHEMA` / `verdict_failed` + the self-heal
  decision out of `scripts/autopilot.py` into `scripts/_verify.py`, imported by **both**
  autopilot (behavior unchanged) and the engine. Wire the engine so a node with `verify` set
  gets a **fresh-session** schema-constrained verdict (fail ⇒ drop-with-reason or one heal
  attempt). Lenient parse; never raises.
- **Files**: `scripts/_verify.py` (new), `scripts/autopilot.py`, `scripts/_workflow.py`,
  `tests/unit/test_autopilot.py`, `tests/unit/test_workflow.py`, `tests/unit/test_verify.py` (new)
- **Done when**: AC-WF-003 — engine verify node gets a verdict, fail ⇒ drop/heal, never raises;
  **autopilot's existing verify tests pass unchanged** after the extraction.
- **Depends on**: T-191
- **REQ-IDs**: REQ-WF-002, NF-024

### T-193 [S] `orchestration:` config block (independent toggles)
- **Description**: Add the opt-in `orchestration:` block — independent toggles
  `flows_enabled`, `parallel_build`, `worktree_isolation`, `allow_generated_subdags` (**all
  default false**) + tunables `max_parallel` (4), `max_total` (64), `max_budget_usd`. Fail-soft
  coercion (invalid ignored), mirroring `autopilot.load_config`. Thread into `run_workflow`
  call sites.
- **Files**: `scripts/_workflow_config.py` (new) or `scripts/_workflow.py`,
  `tests/unit/test_workflow.py` (or `test_workflow_config.py`), `references/` (knob list)
- **Done when**: AC-WF-004 — block round-trips fail-soft; all toggles default false; invalid ignored.
- **Depends on**: T-191
- **REQ-IDs**: REQ-WF-003, NF-027

---

## Milestone 2: Engine consumers (default plumbing)

### T-194 [M] Run all three Forge fan-outs on the engine (behavior-preserving)
- **Description**: Make `_orchestrate.fan_out` the single-wave special case of `run_workflow`
  (flat independent nodes), and route **all three** current consumers through the engine without
  behavior change: `/forge:review` (`review_synthesize.py`), `/forge:adopt` (`adopt.py`), and
  **`/forge:why` (`why.py:403`, single-item fallback)** — the third consumer the rev-1 draft
  omitted. Their existing tests must stay green unchanged.
- **Files**: `scripts/_orchestrate.py`, `scripts/review_synthesize.py`, `scripts/adopt.py`,
  `scripts/why.py`, `tests/unit/test_orchestrate.py`, `tests/unit/test_why.py`
  (+ any other touched-consumer tests)
- **Done when**: AC-WF-005 — `/forge:review` + `/forge:adopt` + `/forge:why` tests pass
  unchanged; `fan_out` single-wave output equals pre-retrofit output.
- **Depends on**: T-193
- **REQ-IDs**: REQ-WF-004, NF-025, NF-026

---

## Milestone 3: User-defined flows (`flows_enabled`)

### T-195 [M] `.forge/workflows/*.yaml` loader + `/forge:flow` skill
- **Description**: `scripts/workflow_loader.py` — parse a declarative workflow
  (`name`, `description`, `nodes:[{id, prompt|prompt_template, depends_on, schema?, model?}]`)
  → `WorkflowSpec`, run `validate_spec`, fail-soft on missing/malformed. `prompt_template`
  `{{upstream_id}}` interpolation compiles to a `build_prompt` (upstream output is untrusted,
  schema-validated). New `skills/forge-flow/SKILL.md` (+ persona if needed) **registered in
  `.claude-plugin/plugin.json`**: list workflows, show `plan_waves`, run via `run_workflow`;
  persisted output → Proposal→Validator→Executor; dry-run plan when background unavailable;
  no-op when `flows_enabled` is false.
- **Files**: `scripts/workflow_loader.py` (new), `skills/forge-flow/SKILL.md` (new),
  `.claude-plugin/plugin.json`, `tests/unit/test_workflow_loader.py` (new)
- **Done when**: AC-WF-006 — sample YAML loads/validates/runs; malformed fails soft;
  `/forge:flow` lists + runs by name; no-op when toggle off. `validate-plugin.py` 0 with the
  new skill registered.
- **Depends on**: T-193
- **REQ-IDs**: REQ-WF-005, 006, NF-024

---

## Milestone 4: Per-stage parallel build (`parallel_build`)

### T-196 [M] Parallel build fan-out + per-node `cwd`
- **Description**: Add a **per-node `cwd`** to the engine (`run_workflow` currently takes one
  scalar `cwd` — `_workflow.py:165`). When `parallel_build` is on, map ready (no-unmet-dep)
  task-DAG nodes to a `WorkflowSpec` and run them in parallel through the engine; off ⇒ today's
  sequential build.
- **Files**: `scripts/_workflow.py` (per-node `cwd`), `scripts/parallel_build.py` (new) or
  extend `autopilot.py`, build skill wiring, `tests/unit/test_parallel_build.py` (new),
  `tests/unit/test_workflow.py`
- **Done when**: AC-WF-007 — N ready nodes fan out with per-node `cwd`; off ⇒ sequential.
- **Depends on**: T-193
- **REQ-IDs**: REQ-WF-007, NF-028

### T-197 [L] Worktree isolation + lifecycle + merge/join
- **Description**: When `worktree_isolation` is on, run each file-mutating node in its **own git
  worktree** on a **branch-per-node** (off `main`/`develop`, per repo rules) from a clean
  committed base; the node commits; merge at a join where git surfaces conflicts (never silent
  clobber). **Lifecycle**: remove worktrees after a successful merge **and** on any drop/crash
  (no orphaned `.git/worktrees`). Capability-gated; **degrades to sequential single-worktree**
  when worktrees are unavailable. Never raises. New `scripts/_worktree.py` (add/commit/merge/
  remove helpers, all fail-soft).
- **Files**: `scripts/_worktree.py` (new), `scripts/parallel_build.py`,
  `tests/unit/test_parallel_build.py`, `tests/unit/test_worktree.py` (new)
- **Done when**: AC-WF-008 — each node gets its own worktree+branch; conflicts surface at merge;
  worktrees removed on success **and** on failure; degrades to sequential without raising.
- **Depends on**: T-196
- **REQ-IDs**: REQ-WF-008, NF-028

### T-198 [M] Adversarial-verify join
- **Description**: Before merging parallel build outputs, gate each node through an N-skeptic
  verification (each prompted to *refute*); admit only on **majority of dispatched skeptics**
  (denominator = skeptics actually dispatched, so a cost-cap drop can't silently lower the bar),
  reusing the `scripts/_verify.py` primitive (T-192). Refuted/failed nodes excluded from the
  merge with reasons.
- **Files**: `scripts/parallel_build.py`, `scripts/_verify.py`, `tests/unit/test_parallel_build.py`
- **Done when**: AC-WF-009 — admission only on majority of dispatched skeptics; refuted excluded
  with reasons; a cap-dropped skeptic does not lower the denominator.
- **Depends on**: T-197
- **REQ-IDs**: REQ-WF-009

---

## Milestone 5: Hybrid generation (`allow_generated_subdags`)

### T-199 [M] Validated sub-DAG generation (`decompose` node)
- **Description**: Add a `decompose` node type whose dispatch is a cheap-model, budgeted,
  schema-constrained LLM call emitting a sub-DAG (JSON node/edge list). The sub-DAG is run
  through `validate_spec` **plus** a node-count cap and a **token-budget proxy** (deterministic
  stdlib heuristic — char count / `len(json)//4`, no stdlib tokenizer) **before any child
  dispatch**; any violation ⇒ drop-with-reason + deterministic fallback. Gated by
  `allow_generated_subdags` (**off by default**); generation never escapes the validated slot.
- **Files**: `scripts/_workflow.py`, `tests/unit/test_workflow.py`
- **Done when**: AC-WF-010 — a cyclic / over-node-count / over-token-proxy generated sub-DAG is
  rejected before any child dispatch; off by default.
- **Depends on**: T-193 (reads the `allow_generated_subdags` toggle; engine core from T-191)
- **REQ-IDs**: REQ-WF-010, NF-027

---

## Milestone 6: Docs + release

### T-200 [S] Reference doc + README
- **Description**: `references/workflow-engine.md` (DAG model, the toggles + tunables, hybrid
  generation, worktree isolation/lifecycle, per-node fresh-session cost economics + sizing
  against the cap, the "scripts can't drive the Agent tool" constraint). README section on
  dynamic workflows + `/forge:flow`.
- **Files**: `references/workflow-engine.md` (new), `README.md`
- **Done when**: doc explains the engine + all toggles + config + cost sizing; README updated; suite green.
- **Depends on**: T-194, T-195, T-198, T-199
- **REQ-IDs**: REQ-WF-009

### T-201 [S] Release v0.4.0
- **Description**: `bump-version.py 0.4.0`; CHANGELOG `[0.4.0]`; ROADMAP + progress rows;
  refresh banner stats + **re-render `social-preview.png`** (coupled pair). Pre-release green;
  PR→develop→main→tag `v0.4.0`→mirror both remotes→GitHub releases→delete branch.
- **Files**: `.claude-plugin/*`, `CHANGELOG.md`, `ROADMAP.md`,
  `build/05-implementation/progress.md`, `README.md`, `assets/banner.svg`, `social-preview.png`
- **Done when**: AC-WF-011 — suite green, validate 0, full-pipeline 12/12 (toggles off and on),
  manifests 0.4.0, tags on both remotes.
- **Depends on**: T-191, T-192, T-193, T-194, T-195, T-196, T-197, T-198, T-199, T-200
- **REQ-IDs**: (release)

---

## Critical path

```
T-191 → T-192 ─┐
       → T-193 ┼─→ T-194 (consumers) ───────────────────────┐
               ├─→ T-195 (flows) ──────────────────────────┤
               ├─→ T-196 (parallel) → T-197 (worktree) → T-198 (verify-join)
               └─→ T-199 (generation) ────────────────────┘
                                                              └─→ T-200 → T-201 (v0.4.0)
```

T-191 (engine hardening, spiked) is the foundation; T-192 (shared verify) and T-193 (config)
build on it. **Every capability task depends on T-193** (it reads the toggles/tunables) —
corrected from rev. 1, where the per-task fields said `T-191` while the prose said `T-192`.
T-194/T-195/T-196/T-199 parallelize once T-193 lands; T-197 follows T-196; T-198 follows T-197.
T-200 docs, T-201 ships.

---

## Out of scope (future, v0.4.1+)

- Full *top-level* LLM-generated workflows (only validated *sub*-DAGs inside a node).
- **Session reuse across heterogeneous DAG nodes** — v0.4.0 is intentionally fresh-session
  per node; a reuse strategy (per-branch / within-retry) is deferred.
- Replacing the 12-stage pipeline (it may later *run as* a `WorkflowSpec` — stretch, not required).
- A resident orchestrator / supervisor process (ADR-005 keeps dispatch detached one-shot).
- Cross-project workflow sharing via `~/.forge`; embedding/vector retrieval of workflows.
