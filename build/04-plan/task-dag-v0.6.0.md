# Task DAG — Forge v0.6.0 (engine made real I: per-node session reuse)

> **Status**: **Ready to build** (2026-06-23). Derived from `build/01-srs/srs-v0.6.0.md`.
> Numbering continues from v0.5.0 (T-207..T-213); this is **T-214..T-219**. A **cost-reduction**
> release with **zero default behavior change**: drive the `_background_agent.dispatch(resume=...)`
> reuse path — already built but unused by the engine — from `run_workflow`, lowering the realized
> per-node floor on a node's **own** retry/heal re-dispatches (`FRESH_FLOOR_USD` → `RESUME_FLOOR_USD`)
> **without touching deterministic admission**. Scoped to **within-node reuse only**; per-branch reuse,
> the other trio items, and caveman mode are each their own later release (srs-v0.6.0 §6).
>
> Format: `T-NNN [size] title` — Size: S (~30min), M (~2hr), L (~half-day).
>
> | Milestone | Tag | Gate |
> |-----------|-----|------|
> | M1 Plumbing (toggle + param) | — | v0.5.0 landed |
> | M2 Reuse (capture → consume → invariance) | — | M1 landed |
> | M3 Docs + ADR | — | M2 landed |
> | M4 Release | v0.6.0 | M1–M3 landed |
>
> **Invariants** (every task): stdlib only + fail-soft + **never-raises** (the reuse path, toggle parse,
> and stale-session fallback all degrade to fresh-dispatch behavior, never raise into
> `run_workflow`/`parallel_build`); **off ⇒ byte-identical to v0.4.x** (`session_reuse` default off,
> strict `is True`); **admission stays `FRESH_FLOOR_USD`** — `_preallocate` + `estimate_admission`
> charge the fresh floor regardless of reuse, so the admitted/dropped split and the T-204
> estimator-equals-run-drops check (AC-WF-014) are identical with reuse on or off; **determinism +
> stdout contract** untouched (REQ-NF-026 / T-128 — no new stdout byte); the **verifier is never reused**
> (REQ-WF-002; `_verify.run_verify` already strips `resume`); TDD **red-first**; full unit suite +
> `validate-plugin.py` 0 + `full-pipeline.sh` **12/12 with every `orchestration` toggle off and on**
> green per task. Baseline before T-214: **74 tests** across `tests/unit/test_workflow.py` +
> `test_background_agent.py`. Reuses `hooks/_background_agent.py` (`dispatch(resume=...)`,
> `FRESH_FLOOR_USD`/`RESUME_FLOOR_USD`, `DispatchResult.session_id`), `scripts/_workflow.py`
> (`_attempt`/`_run_node`/`_run_verify`, `_preallocate`, `estimate_admission`, the T-203 audit record),
> `scripts/_workflow_config.py` (`OrchestrationConfig` + `_TOGGLES`), `scripts/_verify.py`.

---

## Milestone 1: Plumbing

### T-214 [S] `session_reuse` config toggle + `run_workflow` param (inert; byte-identical)
- **Description**: Add `session_reuse: bool = False` to `OrchestrationConfig` and to `_TOGGLES` in
  `scripts/_workflow_config.py` (strict `is True`, fail-soft parse, mirroring `flows_enabled` &
  siblings). Add a `session_reuse: bool = False` keyword to `run_workflow` (`scripts/_workflow.py`) and
  thread the config value through the call chain (`scripts/parallel_build.py`,
  `scripts/workflow_loader.py`, `scripts/_orchestrate.py`). The param is **unused** this task (no reuse
  behavior yet) so the engine is byte-identical to v0.4.x — this is pure inert plumbing.
- **Files**: `scripts/_workflow_config.py`, `scripts/_workflow.py`, `scripts/parallel_build.py`,
  `scripts/workflow_loader.py`, `scripts/_orchestrate.py`, `tests/unit/test_workflow_config.py`,
  `tests/unit/test_workflow.py`
- **Done when**: config parse admits `session_reuse: true` only as a real bool (a stray `1`/`"yes"`
  stays off); absent/malformed config → off; `run_workflow(session_reuse=...)` defaults off and changes
  no output; full suite green, byte-identical engine output vs `main`.
- **Depends on**: none (v0.5.0 landed)
- **REQ-IDs**: REQ-WF-019, NF-038, NF-040

---

## Milestone 2: Reuse

### T-215 [M] `_attempt` session capture (behavior-preserving refactor; separate commit)
- **Description**: Widen `_attempt` (`scripts/_workflow.py:319`) to return `(obj, reason, cost,
  session_id)` — surfacing `res.session_id` on the `status="ok"` path and `None` on every no-session path
  (dispatch raised / `skipped` / `error` / `unavailable` / `is_error`). Update the three `_run_node`
  call sites (`:391`, `:393`, `:411`) to unpack the 4-tuple but **ignore** the session for now (every
  re-dispatch still fresh). This is the **split-determinism refactor** (REQ-NF-040): committed
  **separately** from any reuse behavior, leaving the full existing test set green and unchanged.
- **Files**: `scripts/_workflow.py`, `tests/unit/test_workflow.py`
- **Done when**: AC-WF-016 — `_attempt` returns the session id on success and `None` on every failure
  path; `_run_node` behavior + all existing tests are unchanged (byte-identical engine output); the
  commit contains **no** reuse logic.
- **Depends on**: T-214
- **REQ-IDs**: REQ-WF-016, NF-040

### T-216 [M] Within-node reuse (retry + heal) + fail-soft fallback
- **Description**: When `session_reuse` is on, thread the **most-recent captured `session_id`** into
  `_run_node`'s retry (`:393`) and heal (`:411`) re-dispatches via a **per-attempt copy**
  (`{**kwargs, "resume": sid}`) — never mutating the shared kwargs dict (it still flows to
  `_run_verify`). Track the newest non-`None` session across attempts. The verifier stays fresh (no
  `resume`; `_verify.run_verify` already strips it — REQ-WF-002). A reused re-dispatch that returns a
  non-`ok` status (stale/invalid session) triggers **one fresh fallback re-dispatch within the same
  attempt budget** (REQ-WF-018), so reuse never turns a would-succeed node into a drop; never raises and
  adds no spurious drop reason on recovery. With the toggle off, no `resume` is derived from a prior
  attempt — byte-identical to v0.4.x.
- **Files**: `scripts/_workflow.py`, `tests/unit/test_workflow.py`, `tests/unit/test_parallel_build.py`
- **Done when**: AC-WF-017 (heal re-dispatch reuses `resume=<first id>` at `RESUME_FLOOR_USD`; verifier
  fresh; ok-but-unparseable retry reuses; hard-`error` retry stays fresh), AC-WF-018 (stale-session →
  fresh fallback, node completes, never raises), AC-WF-019 (toggle off ⇒ byte-identical, strict-bool
  parse) — all via an injected fake `dispatch_fn` returning deterministic session ids; no real spend.
- **Depends on**: T-215
- **REQ-IDs**: REQ-WF-017, REQ-WF-018, NF-038, NF-039, NF-040

### T-217 [S] Admission / estimator / audit invariance + determinism
- **Description**: Prove (with tests) that reuse changes **only realized cost**: `estimate_admission`
  and the run's admitted/dropped split are **identical with `session_reuse` on vs off** (both charge
  `FRESH_FLOOR_USD`), and for a `max_budget_usd`-capped spec the estimator split **equals** the run drops
  in both modes (AC-WF-014 preserved). Assert the T-203 `events.jsonl` `workflow_run` record stays
  **exactly one** schema-versioned line per run with unchanged `completed`/`dropped`/`admitted` and a
  **lower** `total_cost_usd` under reuse (an additive integer `reused` field is optional; if added,
  bump `schema_version` and keep it PII-free). Assert the parallel≡sequential determinism split and the
  byte-identical stdout (AC-WF-012 lineage) hold with reuse on.
- **Files**: `scripts/_workflow.py` (only if adding the optional `reused` field),
  `tests/unit/test_workflow.py`
- **Done when**: AC-WF-020 (estimator split identical on/off; equals run drops when capped) + AC-WF-021
  (one audit line, lower cost, schema-versioned + PII-free) green; determinism + stdout-invariant tests
  pass with reuse on.
- **Depends on**: T-216
- **REQ-IDs**: REQ-WF-020, REQ-WF-021, NF-039

---

## Milestone 3: Docs + ADR

### T-218 [S] ADR-010 + reference/README/ROADMAP/progress docs
- **Description**: Write **ADR-010** (per-node session reuse: within-node only, admission stays fresh,
  default-off; verifier + cross-node excluded; fallback-to-fresh). Document the `orchestration.session_reuse`
  toggle and the reuse semantics in `references/workflow-engine.md` (and the toggle table); add a README
  line; record the v0.6.0 row + the deferred per-branch/caveman items in `ROADMAP.md`,
  `build/05-implementation/progress.md`, and `decisions.md`.
- **Files**: `docs/adr/ADR-010-session-reuse.md` (new — match the existing ADR path/format),
  `references/workflow-engine.md`, `README.md`, `ROADMAP.md`,
  `build/05-implementation/progress.md`, `build/05-implementation/decisions.md`
- **Done when**: AC — ADR-010 present + linked; the reuse toggle + within-node semantics are documented;
  ROADMAP/progress carry the v0.6.0 row and the deferred follow-ups (per-branch reuse, trio items 2–3,
  caveman mode).
- **Depends on**: T-216 (documents shipped behavior)
- **REQ-IDs**: REQ-NF-038, ADR-010

---

## Milestone 4: Release

### T-219 [S] Release v0.6.0
- **Description**: `bump-version.py 0.6.0`; CHANGELOG `[0.6.0]`; ROADMAP + progress rows; banner/social
  evergreen (no per-release stats → no refresh). Pre-release green; PR→develop→main→tag
  `v0.6.0`→mirror both remotes→GitHub releases→delete branch.
- **Files**: `.claude-plugin/*`, `CHANGELOG.md`, `ROADMAP.md`,
  `build/05-implementation/progress.md`, `README.md`
- **Done when**: AC-WF-022 — suite green, validate 0, full-pipeline 12/12 (toggles off **and** on),
  manifests 0.6.0, tags + GitHub releases on both remotes; two-remote parity.
- **Depends on**: T-214, T-215, T-216, T-217, T-218
- **REQ-IDs**: (release)

---

## Critical path

```
T-214 (toggle + inert param) → T-215 (capture refactor) → T-216 (reuse + fallback)
      → T-217 (invariance) → T-218 (ADR + docs) → T-219 (v0.6.0)
```

Linear by design: T-215's refactor must land (and be a clean separate commit, REQ-NF-040) before T-216
consumes the captured session; T-217 proves the admission/estimator/audit invariants on the shipped
reuse; T-218 documents it; T-219 ships. A small release touching mostly two engine files — sequencing
avoids needless merge friction (mirrors the v0.4.1 cadence).

---

## Acceptance gate (v0.6.0)

**AC-WF-022** is the release gate: full unit suite green; `validate-plugin.py` 0; `full-pipeline.sh`
**12/12 with every `orchestration` toggle both off (default) and on**; `v0.6.0` tagged on `origin` +
`polygon` with GitHub releases; manifests at `0.6.0`. Plus the per-feature gates AC-WF-016..021 — in
particular **AC-WF-019** (toggle-off byte-identical to v0.4.x) and **AC-WF-020** (estimator split
identical on/off and equal to run drops when capped), which together prove "cheaper, zero semantic
change."

---

## Risk register

| ID | Risk | Impact | Likelihood | Mitigation |
|----|------|--------|------------|------------|
| R-1 | Reuse mutates the shared `kwargs` dict, corrupting the verifier/heal path | H | M | Per-attempt copy `{**kwargs, "resume": sid}` only; never mutate; T-216 test asserts the verifier dispatch receives no `resume`. |
| R-2 | Reuse leaks into deterministic admission, breaking AC-WF-014 | H | L | Admission/estimator stay on `FRESH_FLOOR_USD` (NF-029); T-217 asserts the split is identical on/off. |
| R-3 | A stale/invalid `--resume` turns a would-succeed node into a drop | M | M | Fail-soft fallback to a fresh re-dispatch within the same attempt budget (REQ-WF-018); T-216 test forces a `status="error"` resumed dispatch and asserts recovery. |
| R-4 | Toggle-on changes engine output structure (not just cost) | M | L | Reuse only alters realized cost + model-nondeterministic retry content; determinism split + stdout-invariant tests run with reuse **on** (T-217). |
| R-5 | The capture refactor (T-215) silently changes `_run_node` behavior | M | L | Behavior-preserving, separate commit (REQ-NF-040); the existing suite must stay green and unchanged before T-216. |

---

## Out of scope (this release)

Per-branch / cross-node session reuse; top-level LLM-generated workflows; pipeline-as-WorkflowSpec; and
**caveman mode** (the orthogonal prompt-compression feature — `fits_v060: separate-release`, candidate
v0.6.1, measurement-gated, stdlib levers only). All consolidated in **`build/01-srs/srs-v0.6.0.md` §6**
and the standing non-goals in `srs-v0.4.1.md` §5.4. Nothing there is built in v0.6.0.
