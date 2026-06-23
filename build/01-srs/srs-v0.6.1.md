# SRS — Forge v0.6.1 (caveman mode: opt-in output-token reduction)

> **Status**: **Draft — ready for build** (2026-06-23). A small, **opt-in** cost feature, orthogonal
> to the engine trio (decided 2026-06-23 to ship separately from v0.6.0's session reuse). It adds a
> default-off `orchestration.caveman_mode` that prepends a tiny stdlib **terse-output preamble** to the
> **free-prose** `claude -p` dispatches Forge makes, reducing their output tokens — and **never** touches
> schema-constrained dispatches (already minimal, and correctness-sensitive). Plus a one-time,
> deterministic tightening of Forge's own most-verbose prompt constants (the reliable "free win"). It is
> **measurement-gated and honest**: Forge's background output is mostly schema-constrained JSON the model
> is already told to keep terse, so caveman's headline ~65% does **not** transfer — expect low-double-digit
> % on the free-prose dispatches and ~0% on the JSON ones.
>
> **Provenance**: the 2026-06-23 `caveman-research` workflow analyzed
> https://github.com/JuliusBrussee/caveman and found only its **stdlib levers** port to Forge under
> REQ-NF-024 (stdlib-only / no `pip`): Lever 1 (a prompt-instructed terse-output ruleset, ports as the
> preamble) and the spirit of its static prompt tightening. **Out**: `caveman-compress` (needs a model
> call + the Anthropic SDK / `pip`) and `caveman-shrink` (a Node/MCP stdio proxy) — both violate
> stdlib-only and the standing non-goals (srs-v0.4.1 §5.4). See `srs-v0.6.0.md` §6.
>
> **Grounding** (verified 2026-06-23): the single dispatch chokepoint
> `hooks/_background_agent.py:dispatch` (`cmd = [bin_, "-p", prompt, …]` at `:196`) already receives
> `output_schema` (`:162`, `:201-206`) — so it can apply caveman to the prompt **only when no schema is
> set**; `_cost_cap.record` captures `usage.output_tokens` (`hooks/_cost_cap.py:184,198`;
> `_background_agent.py:246`) — the measurement signal. Forge's authored prompt constants:
> `scripts/autopilot.py:497/506/518` (`_stage_prompt`/`_heal_prompt`/`_verify_prompt`),
> `scripts/dreamer.py:52` (`_CONSOLIDATION_PROMPT`, free-prose, already "Be terse"),
> `scripts/observer.py:51` (`_PROMPT`, asks for "ONLY a compact JSON array … No prose" — schema-constrained),
> `scripts/parallel_build.py:60/86` (`_default_build_prompt`/`_skeptic_prompt`). The
> `orchestration:` config block + strict `is True` / fail-soft parse (`scripts/_workflow_config.py`,
> `OrchestrationConfig` + `_TOGGLES`).

---

## 1. Overview

### 1.1 Problem

Every Forge background agent shells out to `claude -p` through one wrapper
(`hooks/_background_agent.py:dispatch`) and pays for the **output tokens** the agent produces (recorded
to the `_cost_cap` ledger). Some of those dispatches produce **free prose** — the Dreamer's
consolidation digest, build-result summaries, decompose generation — whose verbosity is pure cost. There
is no opt-in way to make the agent answer more tersely. The `caveman` project offers a
prompt-instructed terse-output approach, but only its **stdlib** lever fits Forge's no-`pip` constraint.

Two honest limits, both confirmed against the code, bound the win:

1. **Most Forge dispatches are schema-constrained.** Verify verdicts, observer findings, and adversarial
   skeptics all dispatch with `--json-schema` — their output is already minimal, and telling them to be
   "caveman terse" risks malformed JSON and degraded reasoning. Caveman must **never** touch them.
2. **Forge's free-prose prompts are already terse.** The Dreamer digest prompt already says "Be terse and
   concrete. No bullet lists." So the marginal headroom is small — the feature must prove its saving, not
   assert it.

### 1.2 Objective

Ship an **opt-in, default-off** `orchestration.caveman_mode` that prepends a small, stdlib-built
terse-output preamble to **free-prose** dispatches at the single dispatch chokepoint — reducing their
output tokens — while leaving **schema-constrained dispatches byte-identical** (correctness-sensitive and
already minimal). Add a one-time, deterministic tightening of Forge's most-verbose *non-verdict* prompt
constants (the reliable win, independent of the toggle). **Zero default behavior change** (off ⇒
byte-identical to v0.6.0), stdlib-only, fail-soft, never-raises. **Measurement-gated**: prove the
free-prose saving via the existing output-token ledger before committing the toggle; if the net saving is
under 10%, ship only the static tightening and drop the toggle.

### 1.3 Scope

**In scope.**

- **`hooks/_caveman.py`** — a stdlib, never-raising module: a pure `terse_preamble(level) -> str` and
  `apply(prompt, *, enabled, has_schema, level) -> str` that returns the prompt **unchanged** when
  `enabled` is false **or** `has_schema` is true, and otherwise prepends the level's preamble. Levels:
  `lite` (drop filler/pleasantries/hedging, keep sentences) and `full` (also drop articles, prefer
  fragments). `ultra` / `wenyan` / prose-word abbreviation are **out** (accuracy risk; Forge output is
  largely machine-read).
- **Dispatch wiring** — apply `_caveman.apply` to `prompt` in `hooks/_background_agent.py:dispatch` after
  the prompt is built and **before** `cmd`, passing `has_schema = output_schema is not None`, so all
  callers benefit from one site and schema-constrained dispatches are automatically skipped.
- **Config** — `caveman_mode` (bool, default `false`, strict `is True`) + `caveman_level` (enum
  `lite|full`, default `lite`) in `OrchestrationConfig`; fail-soft parse. The resolved level threads to
  `dispatch` (mirroring how `session_reuse` threads); an env override `FORGE_CAVEMAN` (`off|lite|full`)
  gives a global switch and a deterministic test hook.
- **Static prompt tightening** — drop pure filler (pleasantries, redundant articles) from the verbose,
  *non-verdict* Forge prompt constants (`dreamer._CONSOLIDATION_PROMPT`, `autopilot._stage_prompt` /
  `_heal_prompt`, `parallel_build._default_build_prompt`). Deterministic, no toggle, prompt-shape tests
  updated; a **separate commit**. The verify / skeptic / gate-verdict / observer prompts are **left
  unchanged** (clarity- and schema-sensitive).
- **Measurement + tests** — unit tests prove the *mechanism* (preamble applied to free-prose, skipped for
  schema-constrained, off-by-default identity, never-raises); a documented before/after using the
  `_cost_cap` output-token ledger on a representative free-prose dispatch demonstrates the realized
  saving, recorded in the release notes.
- ADR-011 (caveman mode: prompt-in preamble at the chokepoint, schema-skip, default-off, measurement-gated).

**Out of scope.**

- `caveman-compress` (LLM rewrite of memory files — needs a model call + `pip` SDK) and `caveman-shrink`
  (a Node/MCP stdio proxy) — both violate REQ-NF-024 and the standing non-goals.
- Any caveman transform of **schema-constrained** output, the **verifier / skeptic / gate-verdict**
  prompts, or **code / commit / error** content.
- `ultra` / `wenyan` intensity levels and dictionary abbreviation.
- The engine trio (session reuse done in v0.6.0; items 2–3 are their own releases — `srs-v0.6.0.md` §6).

### 1.4 Design principles

- **One chokepoint, schema-aware skip.** Caveman is applied at exactly one site
  (`dispatch`), and that site already knows whether the dispatch is schema-constrained — so the
  correctness-sensitive, already-minimal JSON dispatches are skipped structurally, not by a fragile
  allowlist.
- **Off ⇒ byte-identical to v0.6.0.** Default-off toggle; with it off `apply` is the identity and no
  prompt byte changes. The static tightening is the only unconditional change, and it touches only
  non-verdict prose, behind updated prompt-shape tests.
- **Honest and measured.** The feature's value is proven against the existing output-token ledger before
  the toggle ships; the release notes state the realistic figure (low-double-digit % on free-prose, ~0%
  on JSON), never caveman's non-transferable headline.
- **Never costs correctness.** Caveman never touches schema-constrained output, verdict/skeptic reasoning,
  or code/error fidelity; `apply` never raises (a malformed preamble degrades to the original prompt).
- **Stdlib only.** `_caveman.py` is pure stdlib; no model call, no `pip`, no proxy.

---

## 2. Functional Requirements

- **REQ-CM-001** — `hooks/_caveman.py` provides `terse_preamble(level) -> str` (a stdlib string constant
  per level) and `apply(prompt, *, enabled, has_schema, level) -> str`. `apply` returns `prompt`
  **unchanged** when `enabled` is false OR `has_schema` is true; otherwise it returns
  `terse_preamble(level) + prompt`. Unknown level ⇒ `lite`. Never raises (any internal error ⇒ return the
  original `prompt`). Stdlib only.
- **REQ-CM-002** — `hooks/_background_agent.py:dispatch` applies `_caveman.apply` to the built `prompt`
  before assembling `cmd`, with `has_schema = output_schema is not None`, so (a) every caller benefits
  from the single site and (b) schema-constrained dispatches are never altered. The caveman level is
  resolved from the threaded config/`caveman` argument, falling back to the `FORGE_CAVEMAN` env var, else
  off.
- **REQ-CM-003** — `OrchestrationConfig` gains `caveman_mode: bool = False` (added to `_TOGGLES`, strict
  `is True`) and `caveman_level: str = "lite"` (coerced to `lite`|`full`, else default), both fail-soft.
  The resolved level threads from the config through the engine/dispatch callers into `dispatch`
  (mirroring `session_reuse`). With `caveman_mode` off, dispatch behavior is byte-identical to v0.6.0.
- **REQ-CM-004** — The verbose, **non-verdict** Forge prompt constants
  (`dreamer._CONSOLIDATION_PROMPT`, `autopilot._stage_prompt`/`_heal_prompt`,
  `parallel_build._default_build_prompt`) are tightened to drop pure filler (pleasantries, redundant
  articles) — deterministic, **no toggle**, a **separate commit**, with prompt-shape tests updated. The
  verify / skeptic / gate-verdict / observer prompts are **not** changed.
- **REQ-CM-005** — The free-prose output saving is **measured**: unit tests assert the mechanism (applied
  to a no-schema dispatch, skipped for a schema dispatch, identity when off, never-raises); a documented
  before/after using the `_cost_cap` output-token ledger on a representative free-prose dispatch (e.g. the
  Dreamer digest) records the realized reduction in the release notes. **Gate**: if the measured net
  saving on free-prose dispatches is < 10%, the toggle is dropped and only REQ-CM-004 ships.
- **REQ-CM-006** — Release v0.6.1: `bump-version.py 0.6.1`; CHANGELOG `[0.6.1]` (with the honest measured
  figure); ROADMAP + progress rows; ADR-011; banner/social evergreen. Pre-release green;
  PR→develop→main→tag `v0.6.1`→mirror both remotes→GitHub releases→delete branch.

---

## 3. Non-Functional Requirements

- **REQ-NF-041** — **Stdlib only; fail-soft; never-raises; correctness-preserving.** No model call, no
  `pip`, no proxy (REQ-NF-024). `_caveman.apply` and the config parse degrade to identity/defaults on any
  error and never raise into `dispatch`. **Schema-constrained dispatches are never altered**; the
  verifier / skeptic / gate-verdict prompts are never caveman-wrapped or tightened. With `caveman_mode`
  off, dispatch output is **byte-identical to v0.6.0** (REQ-NF-025 lineage). The static tightening
  (REQ-CM-004) is a separate commit and changes only non-verdict prose.

---

## 4. Acceptance Criteria

- **AC-CM-001** (REQ-CM-001/002) — With `caveman_mode` on: a **no-schema** dispatch's `prompt` is prefixed
  with the level's terse preamble (the `cmd` `-p` argument carries it); a **schema-constrained** dispatch
  (`output_schema` set) is **byte-identical** to v0.6.0 (no preamble). With `caveman_mode` off, **both**
  are byte-identical to v0.6.0.
- **AC-CM-002** (REQ-CM-001/NF-041) — `apply` never raises: a `None`/odd `level`, or a monkeypatched-raising
  `terse_preamble`, returns the original `prompt`; the config parse rejects a stray truthy scalar for
  `caveman_mode` and coerces an invalid `caveman_level` to `lite`.
- **AC-CM-003** (REQ-CM-004) — The tightened non-verdict prompts drop the targeted filler (prompt-shape
  tests assert the new strings) while the verify / skeptic / gate-verdict / observer prompts are unchanged
  (asserted), and the full suite stays green.
- **AC-CM-004** (REQ-CM-005) — The documented before/after shows the realized output-token reduction on a
  free-prose dispatch via the `_cost_cap` ledger; the mechanism unit tests pass; the release notes state
  the honest figure. If < 10%, the toggle is dropped and only REQ-CM-004 ships (recorded as a decision).
- **AC-CM-005** (REQ-CM-006) — Full unit suite green; `validate-plugin.py` 0; `full-pipeline.sh` 12/12
  with every `orchestration` toggle off **and** on; manifests `0.6.1`; `v0.6.1` tagged on origin +
  polygon with GitHub releases; ADR-011 present.

---

## 5. Architecture notes (for ADR-011)

- **ADR-011 — Caveman mode: a schema-aware prompt-in preamble at the single chokepoint, default-off,
  measurement-gated.** Caveman ports as **one stdlib lever** — a terse-output preamble prepended to the
  prompt — applied at `hooks/_background_agent.py:dispatch`. **Decisions:**
  - **Skip schema-constrained dispatches structurally** (via the `output_schema` the chokepoint already
    has) rather than via an allowlist — they are already minimal and telling them to be terse risks
    malformed JSON / degraded reasoning.
  - **Never touch the verifier / skeptic / gate-verdict prompts** — their clarity is load-bearing
    (caveman's own "auto-clarity safety valve" reverts for exactly this class).
  - **Default-off toggle** keeps v0.6.0 byte-identical unless opted in; **stdlib-only** keeps the no-`pip`
    rule; `caveman-compress` and `caveman-shrink` are rejected because they need a model call / a Node
    proxy.
  - **Measurement-gated**: the saving is proven against the existing output-token ledger before the toggle
    ships; if < 10% on free-prose, only the deterministic static tightening ships. Honest framing: caveman's
    headline ~65% does not transfer because Forge output is mostly already-terse schema-constrained JSON.

---

## 6. Roadmap context

v0.6.1 is the orthogonal **cost feature**, not part of the engine trio. Remaining program order is
unchanged from `srs-v0.6.0.md` §6: trio item 1b (per-branch reuse, measurement-gated) · trio item 2
(top-level LLM-generated workflows) · trio item 3 (pipeline-as-WorkflowSpec, stretch). Standing non-goals
(srs-v0.4.1 §5.4) unchanged.

---

## 7. Traceability

| REQ-ID | Tasks (assigned in task-dag-v0.6.1) |
|--------|-------------------------------------|
| REQ-CM-001 | `hooks/_caveman.py` core |
| REQ-CM-002 | dispatch-chokepoint wiring (schema-skip) |
| REQ-CM-003 | `caveman_mode` / `caveman_level` config |
| REQ-CM-004 | static non-verdict prompt tightening |
| REQ-CM-005 | measurement + mechanism tests |
| REQ-CM-006 | release |
| REQ-NF-041 | every task (invariants) |
| ADR-011 | core + wiring tasks |

---

## 8. References & provenance

- **2026-06-23 `caveman-research` workflow** — established `fits_v060: separate-release`, the four caveman
  levers, and that only the stdlib lever (terse preamble) + static tightening port; recorded in
  `srs-v0.6.0.md` §6 and the `caveman-mode-separate-release` memory.
- **`hooks/_background_agent.py:dispatch`** — the single `claude -p` chokepoint with `output_schema`
  awareness and `_cost_cap` output-token recording.
- **`scripts/_workflow_config.py`** — `OrchestrationConfig` + `_TOGGLES` + strict `is True` / fail-soft
  parse; home of the new toggle (mirrors `session_reuse`, v0.6.0).
- **REQ-NF-024 / standing non-goals (srs-v0.4.1 §5.4)** — the no-`pip` / no-proxy rule that excludes
  `caveman-compress` and `caveman-shrink`.
