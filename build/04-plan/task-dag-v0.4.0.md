# Task DAG — Forge v0.4.0 (dynamic workflow engine)

> **Status**: **Ready to build** (2026-06-21). Derived from `build/01-srs/srs-v0.4.0.md`.
> Numbering continues from v0.3.6 (T-185..T-190); this is **T-191..T-199**.
>
> Format: `T-NNN [size] title` — Size: S (~30min), M (~2hr), L (~half-day).
>
> | Milestone | Tag | Gate |
> |-----------|-----|------|
> | M1 Core engine | — | build first (spike landed in 7f61ba1) |
> | M2 Mode 1 (general engine, default) | — | M1 landed |
> | M3 Mode 2 (user-defined flows) | — | M1 landed |
> | M4 Mode 3 (parallel build + isolation) | — | M1 landed |
> | M5 Hybrid generation | — | M1 landed |
> | M6 Docs + release | v0.4.0 | M1–M5 landed |
>
> **Invariants** (every task): stdlib + PyYAML fail-soft; **never-raises**; **opt-in** — zero
> behavior change when `orchestration` is unset / `mode 1` with isolation+generation off;
> **determinism** parallel==sequential byte-identical (REQ-NF-009/026), enforced as a test;
> every dispatch routes through `_cost_cap` via the single `_background_agent` adapter
> (ADR-005); `max_parallel`/`max_total`/`max_budget_usd` enforced + kill switch honored;
> parallel file-mutating nodes never share a worktree (ADR-006: scripts never drive the Agent
> tool); persisted outputs go through Proposal→Validator→Executor (human-in-the-loop);
> `.forge/`-only atomic writes; TDD red-first; full suite + `validate-plugin.py` 0 +
> `full-pipeline.sh` 12/12 green per task. Reuses `scripts/_workflow.py` (spike),
> `_background_agent.dispatch`, `_orchestrate` (single-wave special case), `_cost_cap`,
> `autopilot` verify/heal, `_stage_table`.

---

## Milestone 1: Core engine

### T-191 [M] Production-harden the engine + per-node verify/heal
- **Description**: Finalize the spiked `scripts/_workflow.py` API (`WorkflowNode`/`WorkflowSpec`/
  `WorkflowResult`, `validate_spec`, `plan_waves`, `run_workflow`). Lift `run_verify`/
  `VERIFY_SCHEMA` + the self-heal decision out of `scripts/autopilot.py` into engine hooks that
  operate on **arbitrary** nodes: when `node.verify` is set, a fresh-context schema-constrained
  pass/fail verdict gates the result (fail ⇒ drop-with-reason or one heal attempt). Reuse the
  autopilot lenient verdict parse. Spike tests already cover the executor core (7f61ba1).
- **Files**: `scripts/_workflow.py`, `tests/unit/test_workflow.py`
- **Done when**: AC-WF-001/002 — spike invariants retained; a `verify` node gets a verdict,
  failing ⇒ drop/heal, never raises on garbage verdict output.
- **Depends on**: none (spike landed)
- **REQ-IDs**: REQ-WF-001, 002, NF-024, NF-026

### T-192 [S] `orchestration:` config block
- **Description**: Add the opt-in `orchestration:` block to the config loader —
  `mode` (default 1), `max_parallel` (4), `max_total` (64), `max_budget_usd`,
  `worktree_isolation` (false), `allow_generated_subdags` (false). Fail-soft coercion,
  invalid ignored, mirroring `autopilot.load_config`. Thread into `run_workflow` call sites.
- **Files**: `scripts/_workflow.py` (or a small `scripts/_workflow_config.py`),
  `tests/unit/test_workflow.py`, `references/` (knob list)
- **Done when**: AC-WF-003 — block round-trips fail-soft; defaults correct; invalid ignored.
- **Depends on**: T-191
- **REQ-IDs**: REQ-WF-003, NF-027

---

## Milestone 2: Mode 1 — general engine (default)

### T-193 [M] Run Forge fan-outs on the engine (behavior-preserving)
- **Description**: Make `_orchestrate.fan_out` the single-wave special case of `run_workflow`
  (flat independent nodes), and route `/forge:review` (`review_synthesize.py`) and
  `/forge:adopt` (`adopt.py`) through the engine **without behavior change**. Their existing
  determinism + synthesis tests must stay green unchanged.
- **Files**: `scripts/_orchestrate.py`, `scripts/review_synthesize.py`, `scripts/adopt.py`,
  `tests/unit/test_orchestrate.py` (+ touched-consumer tests)
- **Done when**: AC-WF-004 — `/forge:review` + `/forge:adopt` tests pass unchanged; `fan_out`
  single-wave output equals pre-retrofit output.
- **Depends on**: T-191
- **REQ-IDs**: REQ-WF-004, NF-025, NF-026

---

## Milestone 3: Mode 2 — user-defined flows

### T-194 [M] `.forge/workflows/*.yaml` loader + `/forge:flow` skill
- **Description**: `scripts/workflow_loader.py` — parse a declarative workflow
  (`name`, `description`, `nodes:[{id, prompt|prompt_template, depends_on, schema?, model?}]`)
  → `WorkflowSpec`, run `validate_spec`, fail-soft on missing/malformed. `prompt_template`
  `{{upstream_id}}` interpolation compiles to a `build_prompt`. New `skills/forge-flow/SKILL.md`
  (+ `agents/` persona if needed): list workflows, show `plan_waves`, run via `run_workflow`;
  persisted output flows through Proposal→Validator→Executor; degrades to a dry-run plan when
  background unavailable.
- **Files**: `scripts/workflow_loader.py`, `skills/forge-flow/SKILL.md`,
  `tests/unit/test_workflow_loader.py`, `.claude-plugin/*` (skill registration if required)
- **Done when**: AC-WF-005 — sample YAML loads/validates/runs; malformed fails soft;
  `/forge:flow` lists + runs by name.
- **Depends on**: T-191
- **REQ-IDs**: REQ-WF-005, 006, NF-024

---

## Milestone 4: Mode 3 — per-stage parallel build

### T-195 [L] Parallel build fan-out + git-worktree isolation
- **Description**: When `mode = 3`, map ready (no-unmet-dep) task-DAG nodes to a `WorkflowSpec`
  and run them in parallel through the engine. With `worktree_isolation` on, each
  file-mutating node runs in its own git worktree; results merge at a join where git surfaces
  conflicts (never silent clobber). Capability-gated; **degrades to sequential single-worktree**
  when worktrees are unavailable. Never raises.
- **Files**: `scripts/parallel_build.py` (or extend `autopilot.py`), `scripts/_workflow.py`
  (worktree-aware node runner), build skill wiring, `tests/unit/test_parallel_build.py`
- **Done when**: AC-WF-006 — N independent nodes fan out; isolation gives each its own
  worktree; conflicts surface at merge; degrades to sequential without raising.
- **Depends on**: T-191
- **REQ-IDs**: REQ-WF-007, 008, NF-028

### T-196 [M] Adversarial-verify join
- **Description**: Before merging parallel build outputs, gate each node through an N-skeptic
  verification (each prompted to *refute*); admit only on majority survival, reusing the
  per-node verify primitive (T-191). Refuted nodes are dropped with reasons, not merged.
- **Files**: `scripts/parallel_build.py`, `scripts/_workflow.py`, `tests/unit/test_parallel_build.py`
- **Done when**: AC-WF-007 — admission only on majority survival; refuted nodes excluded with reasons.
- **Depends on**: T-195
- **REQ-IDs**: REQ-WF-009

---

## Milestone 5: Hybrid generation

### T-197 [M] Validated sub-DAG generation (`decompose` node)
- **Description**: Add a `decompose` node type whose dispatch is a cheap-model, budgeted,
  schema-constrained LLM call emitting a sub-DAG (JSON node/edge list). The sub-DAG is run
  through `validate_spec` **plus** node-count + token-budget checks **before any child
  dispatch**; any violation ⇒ drop-with-reason + deterministic fallback. Gated by
  `allow_generated_subdags` (**off by default**); generation never escapes the validated slot.
- **Files**: `scripts/_workflow.py`, `tests/unit/test_workflow.py`
- **Done when**: AC-WF-008 — a cyclic/over-budget generated sub-DAG is rejected before any
  child dispatch; off by default.
- **Depends on**: T-191
- **REQ-IDs**: REQ-WF-010, NF-027

---

## Milestone 6: Docs + release

### T-198 [S] Reference doc + README
- **Description**: `references/workflow-engine.md` (DAG model, the three modes + config knobs,
  hybrid generation, worktree isolation, the "scripts can't drive the Agent tool" constraint).
  README section on dynamic workflows + `/forge:flow`.
- **Files**: `references/workflow-engine.md`, `README.md`
- **Done when**: doc explains the engine + all three modes + config; README updated; suite green.
- **Depends on**: T-193, T-194, T-196, T-197
- **REQ-IDs**: REQ-WF-009

### T-199 [S] Release v0.4.0
- **Description**: `bump-version.py 0.4.0`; CHANGELOG `[0.4.0]`; ROADMAP + progress rows;
  refresh banner stats + **re-render `social-preview.png`** (coupled pair). Pre-release green;
  PR→develop→main→tag `v0.4.0`→mirror both remotes→GitHub releases→delete branch.
- **Files**: `.claude-plugin/*`, `CHANGELOG.md`, `ROADMAP.md`,
  `build/05-implementation/progress.md`, `README.md`, `assets/banner.svg`, `social-preview.png`
- **Done when**: suite green, validate 0, full-pipeline 12/12, manifests 0.4.0, tags on both remotes.
- **Depends on**: T-191, T-192, T-193, T-194, T-195, T-196, T-197, T-198
- **REQ-IDs**: (release)

---

## Critical path

```
T-191 → T-192 ─┬─→ T-193 (mode 1) ───────────────┐
               ├─→ T-194 (mode 2) ───────────────┤
               ├─→ T-195 (mode 3) → T-196 (verify)┤→ T-198 → T-199 (v0.4.0)
               └─→ T-197 (generation) ────────────┘
```

T-191 (engine + per-node verify, spiked) is the foundation; T-192 (config) gates the modes.
T-193/T-194/T-195/T-197 are independent and parallelizable once T-192 lands; T-196 follows
T-195. T-198 docs, T-199 ships.

---

## Out of scope (future, v0.4.1+)

- Full *top-level* LLM-generated workflows (only validated *sub*-DAGs inside a node).
- Replacing the 12-stage pipeline (it may later *run as* a `WorkflowSpec` — stretch, not required).
- A resident orchestrator / supervisor process (ADR-005 keeps dispatch detached one-shot).
- Cross-project workflow sharing via `~/.forge`; embedding/vector retrieval of workflows.
