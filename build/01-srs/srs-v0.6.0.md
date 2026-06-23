# SRS — Forge v0.6.0 (engine made real I: per-node session reuse)

> **Status**: **Draft — ready for build** (2026-06-23). The first item of the "engine made real"
> trio (srs-v0.4.1 §5.1, re-sequenced to follow the v0.5.0 graduation layer). A **cost-reduction**
> minor release with **zero default behavior change**: it lowers the realized per-node spend floor of
> the v0.4.0 workflow engine by reusing a node's own `claude -p` session across its retry and heal
> re-dispatches, **without touching deterministic admission**. Scoped deliberately to **within-node
> reuse only** — the safe, provably-identical case — per the 2026-06-23 decision to ship the
> "tightest, most shippable" slice of the trio. The other two trio items (top-level generation,
> pipeline-as-WorkflowSpec) and the orthogonal **caveman mode** prompt-compression feature are each
> their own later release (§6).
>
> **Grounding** (verified against the shipped code, 2026-06-23):
> - `hooks/_background_agent.py` — the single `claude -p` wrapper. `dispatch(..., resume=None, ...)`
>   **already** supports session reuse: `resume=<session_id>` adds `--resume <id>` to the CLI command
>   (`:197`) and charges `RESUME_FLOOR_USD = 0.01` instead of `FRESH_FLOOR_USD = 0.06` (`:42-43`,
>   `:188-189`); `DispatchResult` returns the `session_id` (`:149`). A bad `--resume` yields a
>   structured `status="error"`, never an exception (REQ-F-003).
> - `scripts/_workflow.py` — `_attempt` (`:319`) does one dispatch but **discards `res.session_id`**;
>   `_run_node` (`:387`) re-dispatches the retry (`:393`) and verify-heal (`:411`) with the *same fresh
>   kwargs*; `_run_verify`/`_verify_prompt` (`:350-384`) are a **deliberately fresh, independent**
>   critique (REQ-WF-002). `_preallocate` (`:545`) and `estimate_admission` (`:592`) both charge
>   `FRESH_FLOOR_USD` per node; `run_workflow`'s existing `resume=` param (`:649`) is a **coarse**
>   run-level knob that threads one given session into every node uniformly — not per-node chaining.
> - The v0.4.1 invariants this release must keep: REQ-NF-026 determinism split (parallel ≡ sequential),
>   the T-128 stdout contract, the T-204 estimator-equals-run-drops check (AC-WF-014), the T-203
>   `events.jsonl` one-line audit, REQ-NF-024 stdlib-only / fail-soft / never-raises.

---

## 1. Overview

### 1.1 Problem

The v0.4.0 DAG engine dispatches **every node as a fresh `claude -p` session**. A fresh session pays
the ~42k-token cache-creation tax (~$0.05–0.06, the `FRESH_FLOOR_USD` floor); a `--resume` of an
existing session is a cache read (~$0.005–0.01, `RESUME_FLOOR_USD`). The wrapper
(`_background_agent.dispatch`) was **built for reuse** — it takes `resume=<session_id>`, emits
`--resume`, charges the cheaper floor, and returns each run's `session_id` — yet the engine never uses
it for node-to-node reuse:

- `_attempt` (`scripts/_workflow.py:319`) throws away the `session_id` it gets back.
- A node that **fails and retries** (`_run_node:393`) re-dispatches **fresh**, paying a second full
  floor — even though the retry is the *same node, same prompt, same model* and could `--resume` the
  first attempt's session.
- A node that **fails verification and heals** (`_run_node:411`) re-dispatches **fresh** for the same
  reason.

So a node that takes 2–3 production dispatches (first + retry, or first + heal) pays 2–3× the fresh
floor where the 2nd/3rd are provably resumable. The existing `run_workflow(resume=...)` param does not
help: it is a blunt run-level knob that threads **one** caller-supplied session into **every** node's
dispatch identically (used to resume an interrupted run), not a per-node capture-and-chain.

### 1.2 Objective

Add deterministic, fail-soft **per-node session reuse** to the engine: capture each node's first-attempt
`session_id` and thread it as `resume` into **that same node's** retry and heal re-dispatches — the
only re-dispatches whose prompt and model are provably identical — lowering their realized floor from
`FRESH_FLOOR_USD` to `RESUME_FLOOR_USD`. The independent verifier stays **fresh** (its independence is
the point, REQ-WF-002). Admission stays **`FRESH_FLOOR_USD`-based** (a conservative upper bound), so the
deterministic pre-allocation and the T-204 pre-flight estimator are byte-identical with reuse on or off —
**reuse lowers only realized spend, never the admitted set.** The capability is an **opt-in toggle,
default off**, so with it off the engine is byte-identical to v0.4.x (REQ-NF-025 lineage).

### 1.3 Scope

**In scope.**

- **Session capture** — `_attempt` surfaces the dispatch `session_id` alongside its parsed result, so a
  node's first attempt yields a session a later same-node dispatch can `--resume`.
- **Within-node reuse** — when `session_reuse` is on, the node's **retry** (`_run_node:393`) and
  **verify-heal** (`:411`) re-dispatches pass `resume=<first session_id>`, charging `RESUME_FLOOR_USD`.
  The independent verifier dispatch is **always fresh** (never reused).
- **Fail-soft fallback** — a reused (`--resume`) re-dispatch that returns a non-`ok` status (stale or
  invalid session) **falls back to a fresh re-dispatch within the same attempt budget**, so reuse can
  never make a node drop that a fresh dispatch would have completed. Never raises.
- **Config toggle** — `orchestration.session_reuse` (bool, default `false`, strict `is True`, fail-soft),
  added to `_workflow_config.py`'s `_TOGGLES`, mirroring the v0.4.0 capability toggles.
- **Admission/estimator invariance** — `_preallocate` and `estimate_admission` keep charging
  `FRESH_FLOOR_USD`; the admitted/dropped split is identical with reuse on or off.
- **Audit fidelity** — the T-203 `events.jsonl` `workflow_run` record stays one line per run; reused
  re-dispatches show up only as a lower `total_cost_usd` (schema unchanged; an additive `reused` count
  is permitted but not required).
- ADR-010 (within-node-only reuse, admission stays fresh, default-off). Tests + docs.

**Out of scope (this release).**

- **Per-branch / cross-node (linear-chain) reuse** — resuming a *dependency's* session for a *dependent*
  node. Heterogeneous prompts/models across a DAG generally defeat `--resume`, the marginal saving is
  smaller (dependents have different prompts), and the correctness argument is far weaker than the
  same-node case. Deferred to a follow-up, gated on measured value (§6).
- **Verifier reuse** — the verifier is deliberately a fresh, independent critique (REQ-WF-002); reusing
  the node's session would defeat its purpose. Permanently excluded.
- **Changing the admission floor or the estimator** — both stay on `FRESH_FLOOR_USD` (conservative);
  reuse is a realized-cost optimization, never an admission input (preserves AC-WF-014).
- **Caveman mode** (prompt-content compression) — orthogonal feature, its own release (§6).
- The other two "engine made real" trio items — top-level LLM-generated workflows and
  pipeline-as-WorkflowSpec (§6).

### 1.4 Design principles

- **Reuse only what is provably identical.** A node's retry and heal re-dispatch the **same prompt with
  the same model**; `--resume` is semantically valid there. Cross-node and verifier dispatches are not
  identical and are excluded. No heuristic "is this resumable?" guessing.
- **Admission is never a function of reuse.** The deterministic pre-allocation charges the fresh floor
  for every node; reuse can only make the run *cheaper than predicted*, which is the safe direction. The
  estimator and the run still agree on the admitted/dropped split (REQ-NF-029 / AC-WF-014 intact).
- **Off ⇒ byte-identical to v0.4.x.** The capability is a default-off toggle; with it off, no
  `session_id` is captured for reuse and every re-dispatch is fresh — the engine's observable behavior is
  unchanged (REQ-NF-025 lineage).
- **Reuse never costs correctness.** A stale/invalid resumed session falls back to a fresh dispatch
  within the same attempt budget; reuse can lower cost but can never turn a would-succeed node into a
  drop. Fail-soft, never-raises (REQ-NF-024 / REQ-F-003).
- **Determinism and the stdout contract are untouched.** Reuse changes realized cost (and the
  model-nondeterministic *content* of a retry, which was never deterministic); it never changes the
  engine's **ordered** result/drops/summary structure or writes a byte to stdout (REQ-NF-026 / T-128).
- **Stdlib only, `.forge`-only, atomic.** No new dependency; the cost ledger and audit writes are the
  existing atomic ones.

---

## 2. Functional Requirements

### 2.1 Session capture

- **REQ-WF-016** — `_attempt` (`scripts/_workflow.py:319`) surfaces the dispatch `session_id` together
  with its `(result, reason, cost)` — widening the internal return to a 4-tuple `(obj, reason, cost,
  session_id)` (consistent with the module's positional-tuple convention; `_attempt` has a single caller,
  `_run_node`). It returns the `session_id` whenever the dispatch **returned one** (`status="ok"`, a real
  resumable session exists) and `None` on every no-session path (dispatch raised, `skipped`/`error`/
  `unavailable` status, `is_error`). The refactor is behavior-preserving: existing `_run_node` semantics
  and tests are unchanged. Captured ids are confined to **within-node** use — never threaded across nodes.

### 2.2 Within-node reuse

- **REQ-WF-017** — When `orchestration.session_reuse` is on, `_run_node`'s **retry** (`:393`) and
  **verify-heal** (`:411`) re-dispatches pass `resume=<most-recent captured session_id>` into the
  dispatch kwargs via a **per-attempt copy** (`{**kwargs, "resume": sid}`) — never a mutation of the
  shared kwargs dict the caller still holds (the same dict flows on to `_run_verify`). The wrapper then
  emits `--resume` and charges `RESUME_FLOOR_USD`. The node tracks the newest non-`None` session across
  attempts, so each re-dispatch resumes the most recent same-node context. The **heal** path is the
  primary reuse case (its first attempt succeeded ⇒ a session exists); a retry after a *hard* failure
  correctly stays fresh because no session was returned to resume. Reuse applies **only** to the node's
  own production re-dispatches; the independent verifier (`_run_verify:370`) is **always dispatched
  fresh** — and structurally so: `_verify.run_verify` already does `call["resume"] = None`
  (`scripts/_verify.py:88-90`), so verifier independence (REQ-WF-002) holds even if the node's kwargs
  carry a `resume`.

### 2.3 Fail-soft fallback

- **REQ-WF-018** — A reused (`--resume`) re-dispatch that returns a non-`ok` status (e.g. a stale or
  invalid session id) triggers **one fresh fallback re-dispatch of the same node within the same attempt
  budget** before the node is considered failed. Reuse therefore can never cause a node to drop that a
  fresh dispatch would have completed. The fallback path never raises (REQ-F-003) and adds no new drop
  reason string when it recovers.

### 2.4 Capability toggle

- **REQ-WF-019** — `orchestration.session_reuse` (bool, default `false`) is added to
  `scripts/_workflow_config.py`'s `OrchestrationConfig` and `_TOGGLES`, parsed with the existing strict
  `is True` / fail-soft discipline (a stray truthy scalar never enables it; absent/malformed config →
  default off). The toggle threads from `OrchestrationConfig` through `parallel_build` /
  `workflow_loader` / `_orchestrate` into `run_workflow`. With the toggle **off**, the engine captures no
  session for reuse and every re-dispatch is fresh — observably byte-identical to v0.4.x.

### 2.5 Admission, estimator & audit invariance

- **REQ-WF-020** — `_preallocate` (`:545`) and `estimate_admission` (`:592`) continue to charge
  `FRESH_FLOOR_USD` per node regardless of `session_reuse`. The admitted/dropped split, the
  `dropped_reasons` strings, and the deterministic id-ordered narration summary (T-202) are **identical
  with reuse on or off**. The estimator-equals-run-drops invariant (AC-WF-014) holds in both modes.
- **REQ-WF-021** — The T-203 `events.jsonl` `workflow_run` record stays **exactly one** schema-versioned
  line per run; reused re-dispatches are reflected only in a **lower `total_cost_usd`**, leaving
  `completed`/`dropped`/`admitted`/`verdicts` unchanged. An additive integer `reused` field is permitted
  but not required; if added it is PII-free and version-bumped.

### 2.6 Release

- **REQ-WF-022** — Release v0.6.0: `bump-version.py 0.6.0`; CHANGELOG `[0.6.0]`; ROADMAP + progress rows;
  ADR-010 committed; banner/social-preview are evergreen (no per-release stats → no refresh). Pre-release
  gate green; PR→develop→main→tag `v0.6.0`→mirror both remotes→GitHub releases→delete branch.

---

## 3. Non-Functional Requirements

- **REQ-NF-038** — **Stdlib only; fail-soft; never-raises.** No new dependency. The reuse path, the
  toggle parse, and the fallback all degrade to fresh-dispatch behavior on any error and never raise into
  `run_workflow`/`parallel_build` (REQ-NF-024 / REQ-F-003).
- **REQ-NF-039** — **Determinism + stdout contract preserved (REQ-NF-026 / T-128).** Parallel and
  sequential runs remain byte-identical in their ordered result/drops/summary; reuse adds **no** byte to
  stdout (all cost/audit output stays in the existing `.forge/` appends + stderr narration). The realized
  *content* of a retry/heal may differ (it carries the prior attempt's context) — this is
  model-nondeterministic regardless and never affects the engine's ordered structure.
- **REQ-NF-040** — **Behavior-preserving when off (REQ-NF-025 lineage) + split-determinism.** With
  `session_reuse` off, the engine is byte-identical to v0.4.x for the same dispatcher. The behavior-
  preserving `_attempt` return-shape refactor (REQ-WF-016) is committed **separately** from the new reuse
  behavior (REQ-WF-017/018), so the refactor commit leaves the full existing test set green and unchanged.

---

## 4. Acceptance Criteria

- **AC-WF-017** (REQ-WF-016/017) — With `session_reuse` on and an injected fake `dispatch_fn` that
  returns deterministic `session_id`s: a node that fails verify then heals has its **heal re-dispatch
  receive `resume=<first id>`** with realized cost reflecting `RESUME_FLOOR_USD`, while the **verifier
  dispatch receives no `resume`** (fresh); a node whose first attempt returns `status="ok"` but
  unparseable output and then succeeds on retry has its **retry receive `resume=<first id>`**; and a node
  whose first attempt returns `status="error"` (no session) has its **retry dispatched fresh** (no
  `resume`).
- **AC-WF-018** (REQ-WF-018) — A reused re-dispatch whose fake result is `status="error"` triggers one
  **fresh** fallback re-dispatch; the node still completes; no exception escapes and no spurious drop
  reason is recorded when the fallback succeeds.
- **AC-WF-019** (REQ-WF-019/NF-040) — With `session_reuse` **off**, no dispatch receives a `resume`
  derived from a prior same-node attempt, and the engine's ordered result/drops/summary is **byte-
  identical** to the v0.4.x output for the same fake dispatcher. The strict `is True` parse rejects a
  stray truthy scalar.
- **AC-WF-020** (REQ-WF-020) — `estimate_admission` and the run's admitted/dropped split are **identical
  with reuse on vs off**; for a `max_budget_usd`-capped spec the estimator's split **equals** the run's
  drops in both modes (AC-WF-014 preserved), since both charge `FRESH_FLOOR_USD`.
- **AC-WF-021** (REQ-WF-021) — A reuse-on run writes exactly one `workflow_run` line whose
  `completed`/`dropped`/`admitted` match the reuse-off run and whose `total_cost_usd` is **lower**;
  the record stays schema-versioned + PII-free.
- **AC-WF-022** (REQ-WF-022) — Full unit suite green; `validate-plugin.py` 0; `full-pipeline.sh` 12/12
  with every `orchestration` toggle both **off (default) and on**; manifests at `0.6.0`; `v0.6.0` tagged
  on origin + polygon with GitHub releases; ADR-010 present.

---

## 5. Architecture notes (for ADR-010)

- **ADR-010 — Per-node session reuse: within-node only, admission stays fresh, default-off.** The engine
  reuses a node's own `claude -p` session across its **retry and heal** re-dispatches (provably identical
  prompt + model), captured from the first attempt's `session_id`. **Decisions, with rationale:**
  - **Exclude the independent verifier** — its fresh-context independence is the whole point (REQ-WF-002);
    a reused verifier would judge with the producer's context and stop being independent.
  - **Exclude cross-node (per-branch) chains** — heterogeneous prompts/models across a DAG defeat
    `--resume`; the same-node case is the only one with a clean correctness argument. Per-branch is a
    future, measurement-gated follow-up (§6), not a v0.6.0 line item.
  - **Keep admission on `FRESH_FLOOR_USD`** — reuse must not feed the deterministic pre-allocation, or the
    estimator would drift from the run (violating AC-WF-014). The fresh floor is a conservative upper
    bound; reuse simply makes the realized run cheaper than the estimate, which is always safe.
  - **Default-off toggle** — reuse changes a retry's realized content (it now carries the failed
    attempt's context) and cost; gating it off-by-default keeps v0.6.0 byte-identical to v0.4.x unless a
    user opts in, matching the engine's capability-toggle discipline (REQ-NF-025).
  - **Fallback to fresh on a stale session** — keeps reuse strictly non-regressive: it can lower cost but
    never turn a would-succeed node into a drop (REQ-F-003).

---

## 6. Roadmap (remaining "engine made real" work + caveman mode)

This release ships **trio item 1** (session reuse) in its safest slice. Remaining program order:

1. **v0.6.0 (this SRS)** — per-node within-node session reuse.
2. **Per-branch / cross-node session reuse** — the deferred half of trio item 1; only if a measured
   workload shows linear-chain reuse pays for its added risk. Its own SRS + ADR.
3. **Top-level LLM-generated workflows** (trio item 2, srs-v0.4.1 §5.1) — lift the validated-slot model
   (`allow_generated_subdags`) from an in-node sub-DAG to a whole generated top-level `WorkflowSpec`,
   behind the same validate-before-dispatch rails. L; higher risk.
4. **Pipeline-as-WorkflowSpec** (trio item 3) — express the 12-stage SDLC as a `WorkflowSpec`. "Stretch,
   never required"; only if it simplifies. L; architecturally significant.
5. **Caveman mode** (orthogonal cost feature, decided 2026-06-23 to ship **separately** from v0.6.0) —
   an opt-in `orchestration.caveman_mode` (default off) that (a) statically tightens Forge-authored prompt
   constants and (b) prepends a stdlib "terse-output" preamble at the single dispatch chokepoint
   (`hooks/_background_agent.py:dispatch`). The `caveman-compress` (needs a model call + pip) and
   `caveman-shrink` (Node/MCP proxy) levers are **out** — they violate the stdlib-only / no-`pip` rule
   (REQ-NF-024) and the standing non-goals. Honest expectation: Forge's background output is mostly
   schema-constrained JSON the model is already told to keep terse, so caveman's headline ~65% does **not**
   transfer — low-double-digit % on free-prose dispatches, ~0% on JSON; the work is **measurement-gated**
   (prove the saving via the `_cost_cap` output-token ledger before committing the toggle). Candidate
   v0.6.1; its own SRS + ADR.

The **standing non-goals** (srs-v0.4.1 §5.4) are unchanged and authoritative — in particular
embedding/vector retrieval, a resident supervisor, and any `pip install` dependency remain non-goals.

---

## 7. Traceability

| REQ-ID | Tasks (assigned in task-dag-v0.6.0) |
|--------|-------------------------------------|
| REQ-WF-016 | `_attempt` session capture (behavior-preserving refactor) |
| REQ-WF-017 | within-node reuse (retry + heal) |
| REQ-WF-018 | fail-soft reuse fallback |
| REQ-WF-019 | `session_reuse` config toggle |
| REQ-WF-020 | admission/estimator invariance |
| REQ-WF-021 | audit realized-cost fidelity |
| REQ-WF-022 | release |
| REQ-NF-038..040 | every task (invariants) |
| ADR-010 | capture + reuse tasks |

---

## 8. References & provenance

### 8.1 Internal contracts reused

- **`hooks/_background_agent.py` (T-168 / REQ-F-002 / REQ-HARNESS-001/002)** — `dispatch(resume=...)`,
  `FRESH_FLOOR_USD` / `RESUME_FLOOR_USD`, `DispatchResult.session_id`, `_cost_cap.precheck`/`record`. The
  reuse mechanism this release finally drives from the engine.
- **`scripts/_workflow.py` (T-191..T-204)** — `_attempt` / `_run_node` / `_run_verify`, `_preallocate`,
  `estimate_admission`, `run_workflow`, the T-202 narration summary, the T-203 `events.jsonl` record. The
  surfaces extended for reuse, with their invariants (REQ-NF-026/029, AC-WF-014) preserved.
- **`scripts/_workflow_config.py` (T-193 / REQ-WF-003)** — `OrchestrationConfig` + `_TOGGLES` + the strict
  `is True` / fail-soft parse. The home of the new `session_reuse` toggle.
- **REQ-WF-002** — the fresh-context independent verifier, which reuse must **not** touch.
- **REQ-NF-024 / REQ-F-003** — stdlib-only / fail-soft / never-raises discipline.

### 8.2 Backlog provenance

- `build/01-srs/srs-v0.4.1.md:220-222` (§5.1 item 1) — "Session reuse across heterogeneous DAG nodes …
  design a reuse strategy (per-branch / within-retry) that lowers the per-node floor without breaking
  deterministic admission." v0.6.0 ships the **within-retry** (within-node) half; per-branch is deferred
  (§6).
- `build/01-srs/srs-v0.5.0.md:265-266` (§6) — the engine trio sequenced after the v0.5.0 graduation layer.
- 2026-06-23 caveman research (workflow `caveman-research`) — established caveman mode is orthogonal to
  session reuse (`fits_v060: separate-release`) and that only the stdlib levers port to Forge; recorded in
  §6 as a separate measurement-gated release.
