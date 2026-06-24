# Task DAG — Forge v0.6.1 (caveman mode: opt-in output-token reduction)

> **Status**: **Ready to build** (2026-06-23). Derived from `build/01-srs/srs-v0.6.1.md`.
> Numbering continues from v0.6.0 (T-214..T-219); this is **T-220..T-226**. A small **opt-in cost
> feature**, orthogonal to the engine trio: a default-off `orchestration.caveman_mode` that prepends a
> stdlib terse-output preamble to **free-prose** dispatches at the single dispatch chokepoint (skipping
> schema-constrained ones), plus a one-time deterministic tightening of Forge's most-verbose non-verdict
> prompt constants. **Measurement-gated and honest** — caveman's headline ~65% does not transfer.
>
> Format: `T-NNN [size] title` — Size: S (~30min), M (~2hr), L (~half-day).
>
> | Milestone | Tag | Gate |
> |-----------|-----|------|
> | M1 Core (config + _caveman) | — | v0.6.0 landed |
> | M2 Wire + tighten + measure | — | M1 landed |
> | M3 Docs + ADR | — | M2 landed |
> | M4 Release | v0.6.1 | M1–M3 landed |
>
> **Invariants** (every task): stdlib-only + fail-soft + **never-raises** (`_caveman.apply` and the config
> parse degrade to identity/defaults, never raise into `dispatch`); **off ⇒ byte-identical to v0.6.0**
> (`caveman_mode` default off, strict `is True`); **schema-constrained dispatches never altered** (the
> chokepoint skips when `output_schema` is set); the **verifier / skeptic / gate-verdict / observer**
> prompts are **never** caveman-wrapped or tightened (clarity-/schema-sensitive); determinism + stdout
> contract untouched; TDD **red-first**; full unit suite + `validate-plugin.py` 0 + `full-pipeline.sh`
> **12/12 with every `orchestration` toggle off and on** green per task. Baseline before T-220: **1776
> unit tests** (post-v0.6.0). Reuses `hooks/_background_agent.py:dispatch` (`output_schema` awareness +
> `_cost_cap` output-token recording), `scripts/_workflow_config.py` (`OrchestrationConfig` + `_TOGGLES` +
> strict `is True` parse — mirror `session_reuse`), the v0.6.0 toggle-threading pattern.

---

## Milestone 1: Core

### T-220 [S] `caveman_mode` + `caveman_level` config (inert)
- **Description**: Add `caveman_mode: bool = False` (to `_TOGGLES`, strict `is True`) and
  `caveman_level: str = "lite"` (coerced to `lite|full`, else default) to `OrchestrationConfig` in
  `scripts/_workflow_config.py`; fail-soft parse. Inert this task (not yet wired) ⇒ byte-identical.
- **Files**: `scripts/_workflow_config.py`, `tests/unit/test_workflow_config.py`
- **Done when**: REQ-CM-003 — `caveman_mode` enables only on a real bool `true`; `caveman_level` coerces
  an invalid value to `lite`; absent/malformed config → defaults; full suite green.
- **Depends on**: none (v0.6.0 landed)
- **REQ-IDs**: REQ-CM-003, NF-041

### T-221 [M] `hooks/_caveman.py` core
- **Description**: New stdlib, never-raising module: `terse_preamble(level) -> str` (a string constant per
  `lite`/`full`; unknown ⇒ `lite`) and `apply(prompt, *, enabled, has_schema, level) -> str` returning
  `prompt` unchanged when `enabled` is false OR `has_schema` is true, else `terse_preamble(level) +
  prompt`. Any internal error ⇒ return the original `prompt`. No `ultra`/`wenyan`/abbreviation.
- **Files**: `hooks/_caveman.py` (new), `tests/unit/test_caveman.py` (new)
- **Done when**: REQ-CM-001 — identity when disabled or schema-constrained; prepends the level preamble
  otherwise; unknown level ⇒ lite; a monkeypatched-raising `terse_preamble` ⇒ original prompt (never
  raises); stdlib only.
- **Depends on**: none (parallelizable with T-220 — disjoint files)
- **REQ-IDs**: REQ-CM-001, NF-041

---

## Milestone 2: Wire + tighten + measure

### T-222 [M] Wire caveman at the dispatch chokepoint (schema-skip)
- **Description**: In `hooks/_background_agent.py:dispatch`, apply `_caveman.apply` to the built `prompt`
  **before** assembling `cmd`, with `has_schema = output_schema is not None`. Resolve the level from a
  threaded `caveman` argument (resolved from `OrchestrationConfig.caveman_level` by the engine/dispatch
  callers, mirroring v0.6.0's `session_reuse` threading), falling back to the `FORGE_CAVEMAN`
  (`off|lite|full`) env var, else off. Schema-constrained dispatches stay byte-identical; off ⇒
  byte-identical to v0.6.0.
- **Files**: `hooks/_background_agent.py`, `scripts/_workflow.py`, `scripts/parallel_build.py`,
  `scripts/autopilot.py`, `scripts/observer.py`, `scripts/dreamer.py`, `tests/unit/test_background_agent.py`
- **Done when**: AC-CM-001 (no-schema dispatch prompt carries the preamble; schema dispatch byte-identical;
  off ⇒ both byte-identical) + AC-CM-002 (never-raises; env override honored), via an injected fake
  dispatcher / captured `cmd` (no real spend).
- **Depends on**: T-220, T-221
- **REQ-IDs**: REQ-CM-002, NF-041

### T-223 [S] Static non-verdict prompt tightening (separate commit)
- **Description**: Drop pure filler (pleasantries, redundant articles) from the verbose **non-verdict**
  prompt constants — `dreamer._CONSOLIDATION_PROMPT`, `autopilot._stage_prompt`/`_heal_prompt`,
  `parallel_build._default_build_prompt`. Deterministic, **no toggle**, **separate commit**; update the
  prompt-shape unit tests. Leave the **verify / skeptic / gate-verdict / observer** prompts unchanged.
- **Files**: `scripts/dreamer.py`, `scripts/autopilot.py`, `scripts/parallel_build.py`,
  `tests/unit/test_dreamer.py`, `tests/unit/test_autopilot.py`, `tests/unit/test_parallel_build.py`
- **Done when**: AC-CM-003 — tightened prompts assert the new strings; verify/skeptic/gate/observer prompts
  asserted unchanged; full suite green.
- **Depends on**: T-222 (avoid editing the same caller files concurrently)
- **REQ-IDs**: REQ-CM-004, NF-041

### T-224 [S] Measurement + mechanism consolidation + toggle decision
- **Description**: Add/consolidate the mechanism unit tests (free-prose applied · schema skipped · off
  identity · never-raises). Run a documented before/after on a representative **free-prose** dispatch
  (e.g. the Dreamer digest) using the `_cost_cap` output-token ledger; record the realized reduction.
  **Decision gate (REQ-CM-005)**: if the net free-prose saving is < 10%, drop the toggle (keep only the
  T-223 static tightening) and record the decision in `decisions.md`; else keep it and document the figure.
- **Files**: `tests/unit/test_caveman.py`, `tests/unit/test_background_agent.py`,
  `build/05-implementation/decisions.md`, `build/06-evaluation/` (measurement note)
- **Done when**: AC-CM-004 — mechanism tests green; the before/after reduction is recorded with the honest
  figure; the keep-or-drop decision is logged.
- **Depends on**: T-222, T-223
- **REQ-IDs**: REQ-CM-005, NF-041

---

## Milestone 3: Docs + ADR

### T-225 [S] ADR-011 + reference / README / ROADMAP / progress docs
- **Description**: Write **ADR-011** (caveman mode: schema-aware prompt-in preamble at the chokepoint,
  verifier/skeptic excluded, default-off, measurement-gated; `caveman-compress`/`caveman-shrink` rejected
  for stdlib-only). Document the `orchestration.caveman_mode`/`caveman_level` toggle + the honest savings
  framing in `references/workflow-engine.md` (or a caveman section) + README; record the v0.6.1 row in
  `ROADMAP.md`, `build/05-implementation/progress.md`, `decisions.md`.
- **Files**: `build/02-architecture/adr/011-caveman-mode.md` (new), `references/workflow-engine.md`,
  `README.md`, `ROADMAP.md`, `build/05-implementation/progress.md`, `build/05-implementation/decisions.md`
- **Done when**: ADR-011 present + linked; the toggle + honest savings documented; ROADMAP/progress carry
  the v0.6.1 row; no code change (validate 0).
- **Depends on**: T-224 (documents the measured outcome)
- **REQ-IDs**: REQ-CM-006, ADR-011

---

## Milestone 4: Release

### T-226 [S] Release v0.6.1
- **Description**: `bump-version.py 0.6.1`; CHANGELOG `[0.6.1]` (with the honest measured figure); ROADMAP
  + progress rows; banner/social evergreen. Pre-release green; PR→develop→main→tag `v0.6.1`→mirror both
  remotes→GitHub releases→delete branch. (Note: the develop→main promotion also carries the already-merged
  `fix/release-title-param` (PR #46), so `release.yml` can be dispatched with `-f title="v0.6.1 — caveman
  mode"`.)
- **Files**: `.claude-plugin/*`, `CHANGELOG.md`, `ROADMAP.md`, `build/05-implementation/progress.md`,
  `README.md`
- **Done when**: AC-CM-005 — suite green, validate 0, full-pipeline 12/12 (toggles off **and** on),
  manifests 0.6.1, tags + GitHub releases on both remotes; two-remote parity.
- **Depends on**: T-220..T-225
- **REQ-IDs**: REQ-CM-006

---

## Critical path

```
T-220 (config) ┐
               ├→ T-222 (wire @ chokepoint) → T-223 (static tighten) → T-224 (measure + decide)
T-221 (_caveman)┘                                                          → T-225 (ADR + docs) → T-226 (v0.6.1)
```

T-220 and T-221 are disjoint (config vs new module) and may parallelize; everything else sequences —
T-222 threads the toggle through the same caller files (autopilot/parallel_build/dreamer) that T-223
tightens, so they serialize to avoid merge friction. T-224's measurement gate may **drop the toggle**,
leaving only T-223's static tightening — that outcome is recorded, not hidden.

---

## Acceptance gate (v0.6.1)

**AC-CM-005**: full unit suite green; `validate-plugin.py` 0; `full-pipeline.sh` **12/12 with every
`orchestration` toggle off and on**; `v0.6.1` tagged on origin + polygon with GitHub releases; manifests
`0.6.1`. Plus AC-CM-001..004 — in particular **AC-CM-001** (schema-constrained + toggle-off dispatches
byte-identical) and **AC-CM-004** (the saving is measured and honestly reported, with a documented
keep-or-drop decision).

---

## Risk register

| ID | Risk | Impact | Likelihood | Mitigation |
|----|------|--------|------------|------------|
| R-1 | Caveman corrupts schema-constrained JSON output | H | L | Structural skip via `output_schema` at the chokepoint; AC-CM-001 asserts schema dispatches are byte-identical. |
| R-2 | Terse preamble degrades verifier/skeptic reasoning | M | M | Those dispatches are schema-constrained (skipped) and their prompts are never tightened (REQ-CM-004 excludes them); ADR-011 records the exclusion. |
| R-3 | Real saving is negligible (Forge prompts already terse) | M | H | Measurement gate (REQ-CM-005): if < 10% on free-prose, drop the toggle and ship only static tightening; release notes state the honest figure. |
| R-4 | Chokepoint edit degrades EVERY background agent | H | L | `apply` is identity-when-off and wrapped never-raises; AC-CM-001/002 assert byte-identical-when-off + never-raises at the single site. |
| R-5 | Static tightening silently changes agent behavior | L | M | Deterministic, separate commit, prompt-shape tests updated; non-verdict prose only. |

---

## Out of scope (this release)

`caveman-compress` (model call + `pip`) and `caveman-shrink` (Node/MCP proxy) — violate REQ-NF-024;
`ultra`/`wenyan` levels + dictionary abbreviation; any transform of schema-constrained output or
verify/skeptic/gate/code/error content; the engine trio (`srs-v0.6.0.md` §6). Consolidated there + the
standing non-goals in `srs-v0.4.1.md` §5.4.
