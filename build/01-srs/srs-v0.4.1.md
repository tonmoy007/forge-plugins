# SRS — Forge v0.4.1 (operable engine: workflow observability, cost pre-flight, dogfood) + consolidated roadmap

> **Status**: **Draft — ready for build** (2026-06-21). A **hardening** release for the v0.4.0
> dynamic-workflow engine. v0.4.0 shipped a correct, never-raising DAG executor (`scripts/_workflow.py`)
> + parallel-build/worktree/adversarial-join (`scripts/parallel_build.py`) behind independent,
> default-off toggles. The engine is *correct* but **opaque to operate**: runs are silent, leave no
> audit trail, hit a silent cost cliff, and Forge does not dogfood its own flow/parallel-build
> features. This release makes the shipped engine **observable and safe to run with zero change to its
> semantics** — the byte-identical result invariant (REQ-NF-026a) is untouched.
>
> **Not** new engine capability. No new *capability* toggle, no new node type, no change to
> scheduling, admission, verify, or merge logic. Only observability (stderr narration + `events.jsonl`),
> a pure pre-flight estimator over the *existing* deterministic admission set, and a dogfood example +
> integration test. (The single added config key — `orchestration.narrate`, default **on** — is an
> observability control that gates no engine behavior; it is not a capability toggle, see REQ-WF-011.)
>
> **Second purpose**: consolidate the deferred backlog. Today "future / out-of-scope" items are
> scattered across 12 SRS + 9 task-DAG docs, and several recur verbatim across subsystems (e.g.
> `~/.forge` cross-project sharing is deferred *three* times). §5 folds them into one program-wide
> roadmap + a single standing-non-goals list, with provenance, so they stop resurfacing piecemeal.
>
> **Grounding**: the v0.1.6 NARRATE precedent (REQ-INTERACTIVE-NARRATE-001 — `[Forge]` progress on
> stderr, stdout contract preserved); the v0.2.3 audit-log + rotation machinery (T-146
> `_error_log.append_jsonl`); the cost-cap fresh-session economics (ADR-007, `_cost_cap.FRESH_FLOOR_USD`);
> the deterministic topological admission set already computed by `run_workflow` (REQ-NF-029).

---

## 1. Overview

### 1.1 Problem

The v0.4.0 engine is correct but **dark to operate**:

- **Silent runs.** `run_workflow` / `parallel_build` use a module `logging` logger and record
  failures into a `dropped_reasons` list *on the return value*. There is **no user-facing
  narration** (`rg stderr|[Forge]|narrat scripts/_workflow.py scripts/parallel_build.py` → nothing).
  A multi-node DAG runs with no live signal; if cap pressure drops half the nodes, the reasons are
  buried in an object the user never sees. This regresses the operability bar set by `/forge:build`,
  which narrates per task (REQ-INTERACTIVE-NARRATE-001).
- **No audit trail.** Neither engine file writes to `.forge/events.jsonl`. Every other Forge
  subsystem — cost-cap, observer, health, skill-miner — leaves a structured record; a workflow run
  leaves none (no record of which nodes ran/dropped, cost, or verdicts).
- **Silent cost cliff.** Nodes are fresh-session (~$0.05 floor each, §1.4 of srs-v0.4.0); the default
  daily cap ($0.50) admits only small workflows. Over-budget runs drop a *deterministic* set
  (correct) — but there is **no pre-flight estimate** and the drop is not surfaced loudly, so a user
  runs a 20-node flow, silently gets ~9 nodes, and must dig into a return value to learn why.
- **Not dogfooded.** There is **no repo-local `.forge/workflows/`** — Forge ships `/forge:flow` + a
  YAML schema it never uses itself. `parallel_build` *is* wired into `autopilot.py`'s build stage
  (REQ-WF-007) but is exercised **only by unit tests**; no integration test runs it end-to-end against
  `examples/sample-todo-api/` with the toggle on.

Separately, the **deferred backlog is fragmented**: "future / out-of-scope" sections live in every
SRS and DAG, and identical items are restated per version (see §5 provenance). There is no single
place that says what is coming, what is a standing non-goal, and why.

### 1.2 Objective

Make the v0.4.0 engine **operable** — visible while it runs, auditable after, and predictable about
cost — **without changing what it computes**, and prove it by dogfooding. Concretely:

- **See it run** — `[Forge]`-style stderr narration of waves, per-node start/complete/drop+reason,
  and running cost (REQ-WF-011).
- **Audit it** — one structured, versioned `events.jsonl` record per run (REQ-WF-012).
- **Predict its cost** — a pure pre-flight estimator over the *existing* deterministic admission set,
  surfaced before dispatch and loudly at an actual drop (REQ-WF-013).
- **Prove it** — a real in-repo example workflow + an integration test of the parallel-build path,
  closing the docs gap on flow YAML / toggles / cost-sizing (REQ-WF-014).
- **Consolidate the roadmap** — one program-wide future/non-goals section (§5).

### 1.3 Scope

**In scope** — REQ-WF-011..015 (narration, `events.jsonl` audit, cost pre-flight + loud drops,
dogfood example + integration test, release) and the §5 roadmap consolidation. All observability is
**additive and side-channel** (stderr + a `.forge/` append); the engine's stdout result is unchanged.

**Reuses** (no new dependencies, no new architecture): `scripts/_workflow.py` `run_workflow` +
its topological admission set (REQ-NF-029); `scripts/parallel_build.py`; `hooks/_error_log.py`
(`append_jsonl` + rotation, T-146); `hooks/_cost_cap.py` (`FRESH_FLOOR_USD`, daily/monthly headroom,
`_spend`); `scripts/workflow_loader.py` + the `/forge:flow` dry-run plan; the v0.1.6 stderr-narration
idiom (stdout reserved for the structured contract).

**Out of scope** — every item in §5.1–§5.3 (the v0.5.0 engine-made-real trio; the unified `~/.forge`
graduation layer; the Managed-Agents track; the blocked-upstream context trigger) and §5.4 (standing
non-goals). No new engine *capability* of any kind ships in v0.4.1.

### 1.4 Design principles

- **Side channel, not the contract.** Narration goes to **stderr only**; stdout keeps the structured
  result / id-list contract byte-for-byte (the T-128 / REQ-INTERACTIVE-NARRATE-001 rule). Turning
  narration on or off must not change a single stdout byte.
- **Live is best-effort; the audit is the deterministic truth.** Per-node lines from parallel threads
  **interleave by wall-clock — accepted, informational.** The *testable, deterministic* artifacts are
  (a) an id-ordered end-of-run **summary block** on stderr and (b) the `events.jsonl` record — both
  ordered by id/wave, independent of thread scheduling.
- **Estimate is a pure function.** The pre-flight estimator is a pure function of `(spec, cap-state)`;
  it performs **zero dispatch** and reproduces exactly the admitted/dropped split the run then takes
  (it reads the same topological pre-allocation, REQ-NF-029). Same inputs ⇒ same estimate.
- **Zero semantic change.** No change to scheduling, admission, verify, heal, adversarial join, or
  merge. v0.4.1 with narration/audit off is byte-identical to v0.4.0.
- **Stdlib + fail-soft + never-raises** (REQ-NF-024 lineage): narration, the audit write, and the
  estimator each degrade to a no-op on any error (unwritable `.forge`, missing cap state) and never
  raise into the engine's never-raises guarantee.

---

## 2. Functional Requirements

### 2.1 Observability

- **REQ-WF-011 — Live run narration.** `run_workflow` and `parallel_build` emit `[Forge]`-style
  progress to **stderr**: at each wave, `workflow '<name>': wave k/N — M node(s)`; per node, a
  `start` line, then `done` / `dropped: <reason>` with the node's cost; and a final **id-ordered
  summary block** (`completed: [...]`, `dropped: [{id, reason}]`, `total $X.XXXX`). Default **on**;
  silenced by config `orchestration.narrate: false` or env `FORGE_WF_QUIET=1` (fail-soft coercion,
  mirroring `load_config`). Narration is stderr-only and never touches stdout. Never raises; a
  narration failure degrades to silence, not an engine error. *Live per-node lines may interleave
  under parallelism (accepted); the summary block is deterministic, id-ordered.*

- **REQ-WF-012 — `events.jsonl` audit record.** On every `run_workflow` / `parallel_build`
  completion, append **exactly one** structured JSON line to `.forge/events.jsonl` via
  `_error_log.append_jsonl` (rotation + atomic single-line write, T-146 / REQ-NF-029 ledger-safety):
  fields `schema_version`, `ts` (injectable; defaults to wall clock), `event: "workflow_run"`,
  `name`, `nodes`, `waves`, `completed: [id...]`, `dropped: [{id, reason}]`, `total_cost_usd`,
  `verdicts` (per-node verify / adversarial outcomes when present), `admitted` (the admission set).
  PII-free and versioned (REQ-SESSIONLOG-001 discipline). Fail-soft: an unwritable `.forge` degrades
  silently; an over-cap or invalid-spec run still writes a record carrying its drops. Never raises.

### 2.2 Cost predictability

- **REQ-WF-013 — Cost pre-flight + loud drops.** A **pure** estimator exposed by the engine computes,
  for a `WorkflowSpec` against current cap state, `estimate ≈ admissible_node_count ×
  _cost_cap.FRESH_FLOOR_USD`, compares it to remaining daily/monthly cap headroom and
  `max_budget_usd` / `max_total`, and returns the **deterministic admitted-vs-pre-dropped split** —
  the *same* topological pre-allocation `run_workflow` uses (REQ-NF-029), no dispatch. `/forge:flow`
  surfaces this in its existing dry-run plan (estimate, cap headroom, which nodes will run vs drop)
  **before** any run. At runtime, an actual admission drop fires a loud narration line (REQ-WF-011)
  and is captured in the audit record (REQ-WF-012). Pure function of `(spec, cap-state)`; never raises.

### 2.3 Dogfood + docs

- **REQ-WF-014 — Dogfood example + integration test.** Ship a real, genuinely-useful
  `.forge/workflows/<example>.yaml` in-repo (a small validated diamond — e.g. a doc/triage fan-out)
  that loads + validates clean (`validate_spec` ok) and becomes the **worked example** in README /
  `references/`. Add a `tests/integration/` test that drives the `parallel_build` path against
  `examples/sample-todo-api/` with `parallel_build` **on**, using an **injected fake `dispatch_fn`**
  (no real spend, deterministic) to assert fan-out → adversarial-verify join → merge → worktree
  teardown. Fold in the docs gap: the `.forge/workflows/*.yaml` schema, the four `orchestration:`
  toggles, and the per-node fresh-session **cost-sizing rule** (§1.4 of srs-v0.4.0) all documented in
  README / `references/`, anchored by the dogfood example.

### 2.4 Release

- **REQ-WF-015 — Release v0.4.1.** Bump `0.4.1`; CHANGELOG `[0.4.1]`; README + ROADMAP updates;
  refresh `assets/banner.svg` + `social-preview.png` per the standing release rule; tag `v0.4.1` on
  `origin` + `polygon`; publish GitHub releases; manifests (`plugin.json` + `marketplace.json`) at
  `0.4.1`. Pre-release green required (see AC-WF-016).

---

## 3. Non-Functional Requirements

- **REQ-NF-030 — Zero behavior change; stdout invariant preserved.** With narration off, v0.4.1 is
  byte-identical to v0.4.0. With narration on, the engine's **stdout** result (and `_orchestrate`
  / `/forge:review`,`/forge:adopt`,`/forge:why` outputs) is byte-identical to narration-off — all
  added output is stderr or a `.forge/` append. The REQ-NF-026 determinism split is unchanged.
- **REQ-NF-031 — Stdlib, fail-soft, never-raises.** All new code (narration, audit write, estimator,
  loader/skill helpers) is stdlib + fail-soft PyYAML; every path degrades to a no-op structured result
  on error and never raises into `run_workflow` / `parallel_build` (REQ-NF-024 lineage).
- **REQ-NF-032 — Audit-write safety under parallel fan-out.** The `events.jsonl` append is a single
  atomic line via the existing rotation-aware writer; concurrent workflow runs cannot interleave a
  partial record (REQ-NF-029 ledger-safety lineage). The audit record is **deterministic** (id-ordered
  fields), independent of thread scheduling.
- **REQ-NF-033 — Estimator fidelity.** The pre-flight admitted/dropped split equals, node-for-node,
  the set `run_workflow` actually admits/drops for the same `(spec, cap-state)`; any divergence is a
  defect. The estimator performs zero dispatch and reads `FRESH_FLOOR_USD` / cap headroom from the
  single cost-cap source (no second cost model).
- Inherited: single dispatch adapter (ADR-005); human-in-the-loop for persisted state (ADR-006);
  ≤2000-token session-start budget; `.forge/`-only atomic writes; two-remote parity; `python3`;
  TDD red-first.

---

## 4. Acceptance Criteria

- **AC-WF-012** — Narration: a multi-node run prints per-node `start` / `done` / `dropped: <reason>`
  lines and a final id-ordered summary on **stderr**; the summary block is identical across repeated
  runs (deterministic); **stdout is byte-identical with narration on vs off**; `orchestration.narrate:
  false` / `FORGE_WF_QUIET=1` silences it; a forced narration error degrades to silence, no raise.
- **AC-WF-013** — Audit: after any run, **exactly one** well-formed JSON line is appended to
  `.forge/events.jsonl` with `completed` / `dropped` / `total_cost_usd` / `verdicts` / `admitted`;
  an over-cap run and an invalid-spec run each still write a record (carrying their drops); an
  unwritable `.forge` degrades silently; the line is schema-versioned and PII-free.
- **AC-WF-014** — Pre-flight: for a spec whose `node_count × FRESH_FLOOR_USD` exceeds the cap, the
  estimator reports an admitted/dropped split **identical** to what the subsequent run drops;
  `/forge:flow` surfaces the estimate + cap headroom **before** running; the estimator is a pure
  function (same `(spec, cap-state)` ⇒ same result, zero dispatch); an actual runtime drop emits a
  loud narration line.
- **AC-WF-015** — Dogfood: the in-repo `.forge/workflows/<example>.yaml` validates clean and is
  referenced as the worked example in README; the integration test exercises `parallel_build` against
  `examples/sample-todo-api/` end-to-end with a fake dispatcher (fan-out + adversarial join + merge +
  worktree teardown all asserted); README / `references/` document the YAML schema, the four toggles,
  and the cost-sizing rule.
- **AC-WF-016** — Release green: full unit suite passes; `validate-plugin.py` returns 0;
  `full-pipeline.sh` 12/12 with every `orchestration` toggle both **off** (default) and **on**;
  `v0.4.1` tagged on `origin` + `polygon` with GitHub releases; manifests at `0.4.1`; two-remote parity.

---

## 5. Consolidated roadmap & standing non-goals (program-wide)

> Supersedes the scattered per-version "future / out-of-scope" sections for engine-adjacent work.
> Provenance in §7.2. Nothing here is built in v0.4.1; it exists so deferred work stops resurfacing
> piecemeal and so non-goals are decided once, on the record.

### 5.1 v0.5.0 — "Engine made real" (next minor)

Each item is its own SRS section + ADR when built; not a v0.4.1 line item.

1. **Session reuse across heterogeneous DAG nodes** — v0.4.0 is intentionally fresh-session per node
   (heterogeneous prompts/models defeat `--resume`); design a reuse strategy (per-branch / within-retry)
   that lowers the per-node floor without breaking deterministic admission. M–L.
2. **Top-level LLM-generated workflows** — extend the validated-slot model (`allow_generated_subdags`)
   from a sub-DAG inside a node to a whole generated top-level `WorkflowSpec`, behind the same
   validate-before-dispatch rails (acyclicity + schema + node/token budget). L; higher risk.
3. **Pipeline-as-WorkflowSpec** — express the 12-stage SDLC as a `WorkflowSpec` run on the engine,
   unifying `autopilot.py`'s sequencer with `run_workflow`. Explicitly tagged "stretch, never required"
   in srs-v0.4.0; only if it simplifies, never as a forced migration. L; architecturally significant.

### 5.2 Unified `~/.forge` graduation layer (candidate, post-v0.5.0)

Cross-project sharing via `~/.forge` is deferred **three times** for three memory tiers — lessons
(**already built**: `promote-lessons.py`, T-022), skills (srs-v0.3.5), and workflows (srs-v0.4.0).
Rather than three bespoke promoters, generalize the existing lesson-promotion mechanism into **one
`~/.forge` graduation layer** serving lessons + skills + workflows (frequency/quality-gated promotion,
project-lesson-wins conflict rule already established). Sequenced after flows are dogfooded (REQ-WF-014).

### 5.3 Separate future programs / parked

- **Hosted autonomy — Managed Agents (`--mode managed`)** — Anthropic-run loop + container,
  gate-derived Outcome rubric, scheduled deployments. Deferred since v0.3.3 on a deliberate "local-only
  autonomy first" decision. The **largest unbuilt milestone**; its own program (≥ v0.6), independent of
  the workflow engine.
- **In-session configurable-% context trigger — BLOCKED UPSTREAM.** Needs a Claude Code
  `ContextThreshold` hook event (issues #46695 / #25689); programmatic API-level compaction
  (`context_management: compact_20260112`) is not injectable via `claude -p`. Parked until upstream
  ships the hook; not actionable now. (v0.3.6 already delivers the token-pressure-rotation approximation.)

### 5.4 Standing non-goals (decided; do not re-add as backlog)

- **Embedding / vector retrieval of skills or workflows** — deferred for both subsystems and rejected
  on two grounds: Claude's description-matching already covers invocation, and it breaks the
  stdlib-only / no-`pip install` rule (REQ-NF-024 + the `frontmatter` lesson). Non-goal.
- **A subprocess driving Claude's in-session Agent/Task tool** — impossible by design; ADR-006. The
  engine delegates to `claude -p`; this constraint is why. Non-goal.
- **A resident orchestrator / supervisor process** — ADR-005 keeps dispatch detached one-shot.
  Reversing it requires a superseding ADR first, not a feature task. Non-goal absent that ADR.
- **Repackaging Forge as a Python package / standalone CLI / ACP / multi-tenant / channel adapters /
  third-party integrations** — repeated v0.2→v0.3 identity decision: Forge is a Claude Code plugin.
  Non-goal.
- **Full policy DSL / blocking rule engine** — rules are advisory by design (the enforcing
  `enforce: true` guardrail already shipped in v0.3.3 T-175; the *full DSL* stays out). Non-goal.
- **RL / weight-level self-improvement (MiMo-style); fully unattended skill installation; Web/Streamlit
  status UI; anonymous telemetry beyond opt-in local-only** — firm, long-standing non-goals.

---

## 6. Traceability

| REQ-ID | Task |
|--------|------|
| REQ-WF-011 | T-202 |
| REQ-WF-012 | T-203 |
| REQ-WF-013 | T-204 |
| REQ-WF-014 | T-205 |
| REQ-WF-015 | T-206 |
| REQ-NF-030 | T-202, T-205 |
| REQ-NF-031 | T-202, T-203, T-204 |
| REQ-NF-032 | T-203 |
| REQ-NF-033 | T-204 |
| §5 roadmap | T-205 (docs) / this SRS |
| (release) | T-206 |

---

## 7. References & provenance

### 7.1 Internal contracts reused

- **REQ-INTERACTIVE-NARRATE-001** (v0.1.6, T-128) — `[Forge]` progress on stderr; stdout reserved for
  the structured contract. The narration precedent REQ-WF-011 follows.
- **T-146** (v0.2.3) — `hooks/_error_log.py` `append_jsonl` + byte-ceiling rotation; the audit writer.
- **ADR-007 / `_cost_cap`** — `FRESH_FLOOR_USD`, daily/monthly headroom, `_spend`; the single cost model
  the estimator reads.
- **REQ-NF-026 / REQ-NF-029** (v0.4.0) — split determinism invariant + deterministic topological
  admission; the estimator and the byte-identical-stdout guarantee build on these.
- **ADR-005 / ADR-006** — single detached dispatch adapter; scripts cannot drive the in-session Agent
  tool. Cited by the §5.4 non-goals.

### 7.2 Deferred-backlog provenance (sources consolidated into §5)

- `build/04-plan/task-dag-v0.4.0.md:220-228`, `build/01-srs/srs-v0.4.0.md:83-88` — engine-made-real
  trio; `~/.forge` workflow sharing; embeddings; resident process; in-session Agent driving.
- `build/01-srs/srs-v0.3.5.md:55-57`, `build/04-plan/task-dag-v0.3.5.md:146-150` — `~/.forge` skill
  graduation "analogous to lesson promotion"; embedding/vector skill retrieval; RL self-improvement;
  unattended skill install.
- `build/01-srs/srs.md:184` (Q-002) — `~/.forge` sync-across-machines (lessons; since built, T-022).
- `build/04-plan/task-dag-v0.3.3.md:154-158`, `build/01-srs/srs-v0.3.3.md:40,57` — Managed Agents
  (`--mode managed`), deferred v0.3.4+, "local-only autonomy first".
- `build/04-plan/task-dag-v0.3.6.md:124-130`, `build/01-srs/srs-v0.3.6.md:67-72` — in-session
  configurable-% trigger blocked upstream (#46695 / #25689); programmatic API compaction.
- `build/01-srs/srs-v0.3.md:44`, `build/01-srs/srs-v0.2.md:48` — Python package extraction / standalone
  CLI / multi-tenant / channel adapters / full policy DSL (identity non-goals).
