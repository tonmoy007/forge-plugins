# Task DAG — Forge v0.4.1 (operable engine: observability, cost pre-flight, dogfood)

> **Status**: **Ready to build** (2026-06-21). Derived from `build/01-srs/srs-v0.4.1.md`.
> Numbering continues from v0.4.0 (T-191..T-201); this is **T-202..T-206**. A **hardening**
> release: make the shipped v0.4.0 engine observable and safe to run with **zero change to its
> semantics**. No new capability toggle, no new node type; the only added config key
> (`orchestration.narrate`, default on) gates no engine behavior.
>
> Format: `T-NNN [size] title` — Size: S (~30min), M (~2hr), L (~half-day).
>
> | Milestone | Tag | Gate |
> |-----------|-----|------|
> | M1 Observability (narration + audit) | — | v0.4.0 landed |
> | M2 Cost predictability | — | M1 landed |
> | M3 Dogfood + docs | — | M1–M2 landed |
> | M4 Release | v0.4.1 | M1–M3 landed |
>
> **Invariants** (every task): stdlib + PyYAML fail-soft; **never-raises** — narration, the audit
> write, and the estimator each degrade to a no-op on error and never raise into
> `run_workflow`/`parallel_build`; **zero behavior change** — with narration off, byte-identical to
> v0.4.0, and with narration on, the engine's **stdout** result is byte-identical (all added output
> is **stderr** or a `.forge/` append; the T-128 stdout-contract rule); the REQ-NF-026 determinism
> split is untouched; the estimator is a **pure function** of `(spec, cap-state)` reusing the *same*
> topological pre-allocation (REQ-NF-029) and the *single* `_cost_cap` model (no second cost model);
> `.forge/`-only atomic writes; TDD red-first; full suite + `validate-plugin.py` 0 +
> `full-pipeline.sh` 12/12 (toggles **off and on**) green per task. Reuses `scripts/_workflow.py`
> + its admission set, `scripts/parallel_build.py`, `hooks/_error_log.append_jsonl` (T-146),
> `hooks/_cost_cap` (`FRESH_FLOOR_USD` + headroom), `scripts/workflow_loader.py` + `/forge:flow`,
> the v0.1.6 stderr-narration idiom (REQ-INTERACTIVE-NARRATE-001).

---

## Milestone 1: Observability

### T-202 [M] Live run narration (stderr; stdout-invariant preserved)
- **Description**: Add `[Forge]`-style narration to **stderr** in `run_workflow` (`scripts/_workflow.py`)
  and `parallel_build` (`scripts/parallel_build.py`): a per-wave header
  (`workflow '<name>': wave k/N — M node(s)`), per-node `start` then `done` / `dropped: <reason>`
  with the node's cost, and a final **id-ordered summary block** (`completed:[...]`,
  `dropped:[{id,reason}]`, `total $X.XXXX`). Route every line through a single stderr-only helper so
  **no narration byte reaches stdout**. Default **on**; silenced by `orchestration.narrate: false`
  (new fail-soft config key) or `FORGE_WF_QUIET=1`. Live per-node lines may interleave under
  parallelism (accepted, informational); the **summary block is deterministic, id-ordered**. A
  narration failure degrades to silence — never raises.
- **Files**: `scripts/_workflow.py`, `scripts/parallel_build.py`, `scripts/_workflow_config.py`
  (the `narrate` knob), `tests/unit/test_workflow.py`, `tests/unit/test_parallel_build.py`
- **Done when**: AC-WF-012 — per-node `start`/`done`/`dropped:<reason>` + a deterministic id-ordered
  summary on **stderr**; **stdout byte-identical with narration on vs off**; `narrate:false` /
  `FORGE_WF_QUIET=1` silences; a forced narration error degrades to silence, no raise.
- **Depends on**: none (v0.4.0 landed)
- **REQ-IDs**: REQ-WF-011, NF-030, NF-031

### T-203 [S] `events.jsonl` audit record (one line per run)
- **Description**: On every `run_workflow` / `parallel_build` completion, append **exactly one**
  structured JSON line to `.forge/events.jsonl` via `hooks/_error_log.append_jsonl` (rotation +
  atomic single-line write): `schema_version`, `ts` (injectable; defaults to wall clock),
  `event:"workflow_run"`, `name`, `nodes`, `waves`, `completed:[id…]`, `dropped:[{id,reason}]`,
  `total_cost_usd`, `verdicts` (verify/adversarial when present), `admitted` (the admission set).
  PII-free, versioned. Fail-soft: unwritable `.forge` ⇒ silent; an over-cap or invalid-spec run
  still writes a record carrying its drops. Never raises.
- **Files**: `scripts/_workflow.py`, `scripts/parallel_build.py`, `tests/unit/test_workflow.py`,
  `tests/unit/test_parallel_build.py`
- **Done when**: AC-WF-013 — exactly one well-formed JSON line per run with
  completed/dropped/cost/verdicts/admitted; over-cap **and** invalid-spec runs still write; unwritable
  `.forge` degrades silently; line is schema-versioned + PII-free.
- **Depends on**: T-202 (shares the run-completion seam in the same two files)
- **REQ-IDs**: REQ-WF-012, NF-031, NF-032

---

## Milestone 2: Cost predictability

### T-204 [M] Cost pre-flight estimator + loud drops
- **Description**: Add a **pure** `estimate_admission(spec, cap_state)` to the engine that replays
  the *same* topological pre-allocation loop `run_workflow` uses (REQ-NF-029) against
  `_cost_cap.FRESH_FLOOR_USD` + remaining daily/monthly headroom + `max_budget_usd`/`max_total`,
  returning `estimate ≈ admitted_count × floor` and the **deterministic admitted-vs-pre-dropped
  split** — **zero dispatch**. Surface it in the `/forge:flow` dry-run plan (estimate, cap headroom,
  which nodes run vs drop) **before** any run. At runtime, an actual admission drop fires a **loud**
  narration line (reuses T-202) and is captured in the audit record (T-203).
- **Files**: `scripts/_workflow.py`, `scripts/workflow_loader.py`, `skills/forge-flow/SKILL.md`,
  `tests/unit/test_workflow.py`, `tests/unit/test_workflow_loader.py`
- **Done when**: AC-WF-014 — for a spec whose `node_count × floor` exceeds the cap, the estimator's
  split is **identical** to what the run drops; `/forge:flow` surfaces estimate + headroom **before**
  running; estimator is a pure function (same inputs ⇒ same result, no dispatch); a runtime drop emits
  a loud narration line.
- **Depends on**: T-202 (loud-drop line), T-203 (drop captured in the audit record)
- **REQ-IDs**: REQ-WF-013, NF-033

---

## Milestone 3: Dogfood + docs

### T-205 [M] Dogfood example flow + parallel-build integration test + docs
- **Description**: Ship a real, validated `.forge/workflows/doc-review.yaml` in-repo (a small diamond
  — `split → {reviewer-a, reviewer-b} → synthesize`) that loads + validates clean and becomes the
  **worked example** in README / `references/workflow-engine.md`. Add a `tests/integration/` test that
  drives the `parallel_build` path against `examples/sample-todo-api/` with `parallel_build` **on**,
  using an **injected fake `dispatch_fn`** (no real spend, deterministic) to assert fan-out →
  adversarial-verify join → merge → worktree teardown. Document the gap: the `.forge/workflows/*.yaml`
  schema, the four `orchestration:` toggles + `narrate`, and the per-node **cost-sizing rule**.
  Write the SRS §5 consolidated roadmap + standing-non-goals into `ROADMAP.md`.
- **Files**: `.forge/workflows/doc-review.yaml` (new), `tests/integration/test_parallel_build_e2e.py`
  (new), `README.md`, `references/workflow-engine.md`, `ROADMAP.md`
- **Done when**: AC-WF-015 — the example validates clean + is referenced in README; the integration
  test exercises `parallel_build` end-to-end with a fake dispatcher (fan-out + adversarial join +
  merge + teardown asserted); README / `references/` document the YAML schema, the toggles, and the
  cost-sizing rule; `full-pipeline.sh` 12/12 with toggles off **and** on.
- **Depends on**: T-202, T-203, T-204
- **REQ-IDs**: REQ-WF-014, NF-030

---

## Milestone 4: Release

### T-206 [S] Release v0.4.1
- **Description**: `bump-version.py 0.4.1`; CHANGELOG `[0.4.1]`; ROADMAP + progress rows; refresh
  banner stats + **re-render `social-preview.png`** (coupled pair). Pre-release green;
  PR→develop→main→tag `v0.4.1`→mirror both remotes→GitHub releases→delete branch.
- **Files**: `.claude-plugin/*`, `CHANGELOG.md`, `ROADMAP.md`,
  `build/05-implementation/progress.md`, `README.md`, `assets/banner.svg`, `social-preview.png`
- **Done when**: AC-WF-016 — suite green, validate 0, full-pipeline 12/12 (toggles off **and** on),
  manifests 0.4.1, tags + GitHub releases on both remotes; two-remote parity.
- **Depends on**: T-202, T-203, T-204, T-205
- **REQ-IDs**: (release)

---

## Critical path

```
T-202 (narration seam) → T-203 (audit, same seam) → T-204 (pre-flight + loud drops)
      → T-205 (dogfood + integration test + docs) → T-206 (v0.4.1)
```

Linear by design: T-203 and T-204 build on the run-completion seam T-202 establishes and touch the
same two engine files, so they sequence rather than parallelize (avoids needless merge friction in a
small release). T-204's loud-drop line reuses T-202's narration and its drop is captured by T-203's
audit record. T-205 documents and dogfoods all three; T-206 ships.

---

## Acceptance gate (v0.4.1)

**AC-WF-016** is the release gate: full unit suite green; `validate-plugin.py` 0; `full-pipeline.sh`
**12/12 with every `orchestration` toggle both off (default) and on**; `v0.4.1` tagged on `origin` +
`polygon` with GitHub releases; manifests at `0.4.1`. Plus the per-feature gates AC-WF-012..015 — in
particular the **byte-identical-stdout** check (AC-WF-012) and the **estimator-equals-run-drops** check
(AC-WF-014), which together prove "observable + predictable, zero semantic change."

---

## Risk register

| ID | Risk | Impact | Likelihood | Mitigation |
|----|------|--------|------------|------------|
| R-1 | Parallel narration interleaving on stderr misread as non-determinism | L | M | The tested artifacts are the **deterministic id-ordered summary block** + the `events.jsonl` record; live per-node lines are documented best-effort (T-202). |
| R-2 | A stray narration write to **stdout** corrupts the id-list/result contract | H | L | All narration routes through a single stderr-only helper; **AC-WF-012 asserts byte-identical stdout** with narration on vs off. |
| R-3 | Estimator drifts from actual admission (a second cost model) | M | M | REQ-NF-033: estimator **reuses the same topo pre-allocation path** + the single `_cost_cap` source; test asserts the split equals the run's drops (AC-WF-014). |
| R-4 | Integration test is flaky or incurs real spend | M | L | **Injected fake `dispatch_fn`** (no network, no spend), deterministic; any live-dispatch path stays capability-gated and out of CI. |
| R-5 | Audit append races/partials under parallel fan-out | M | L | Single atomic line via the existing rotation-aware `append_jsonl` (REQ-NF-032 / T-146 ledger-safety). |

---

## Out of scope (future)

All deferred work is consolidated in **`build/01-srs/srs-v0.4.1.md` §5** (program-wide roadmap +
standing non-goals): the v0.5.0 "engine made real" trio (session reuse · top-level generation ·
pipeline-as-WorkflowSpec); the unified `~/.forge` graduation layer; the Managed-Agents track
(≥ v0.6); the blocked-upstream in-session context trigger; and the standing non-goals (embeddings,
in-session Agent driving, resident supervisor, repackaging, full policy DSL, RL, web UI). Nothing
there is built in v0.4.1.
