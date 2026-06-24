# ADR-011: Caveman Mode — Measured and Rejected; Static Prompt Tightening Only

**Status**: Accepted (caveman runtime toggle rejected by the measurement gate)
**Date**: 2026-06-24

## Context

v0.6.1 investigated **caveman mode** — porting the token-reduction approach from
[`JuliusBrussee/caveman`](https://github.com/JuliusBrussee/caveman) to Forge — to cut the **output
tokens** Forge pays for on its background `claude -p` dispatches (recorded to the `_cost_cap` ledger).

The 2026-06-23 `caveman-research` workflow found that only caveman's **stdlib lever** ports under
Forge's no-`pip` rule (REQ-NF-024): a prompt-instructed terse-output preamble. `caveman-compress` (an
LLM rewrite needing the Anthropic SDK / `pip`) and `caveman-shrink` (a Node/MCP stdio proxy) were
**out** — both violate stdlib-only and the standing non-goals (srs-v0.4.1 §5.4).

Two honest limits were known up front (`srs-v0.6.1.md` §1.1): most Forge dispatches are
**schema-constrained** (already minimal — must never be touched), and Forge's free-prose prompts are
**already terse** (e.g. the Dreamer digest already says "Terse and concrete. No bullet lists." and
bounds itself to "3-5 sentences"). So caveman's headline ~65% was expected **not** to transfer. The
SRS therefore made the feature **measurement-gated** (REQ-CM-005): prove a ≥10% free-prose
output-token saving against the existing ledger, or drop the toggle and ship only the deterministic
static prompt tightening.

## Decision

**Build the mechanism, measure it honestly, and let the gate decide — then follow the gate.**

1. **Built (and fully tested) the stdlib lever** behind a default-off, opt-in toggle: `_caveman.apply`
   prepended a terse preamble at the **single dispatch chokepoint** (`_background_agent.dispatch`),
   applied to **free-prose** dispatches only and skipped structurally whenever `output_schema` was set
   (so verify / skeptic / gate / structured-miner output was never altered). The level threaded from
   `orchestration.caveman_mode`/`caveman_level` config through the engine, mirroring `session_reuse`,
   plus a `FORGE_CAVEMAN` env switch. With the toggle off it was byte-identical to v0.6.0. The
   four-point mechanism matrix (free-prose applied · schema skipped · off identity · never-raises)
   passed (20 tests at commit `52bc5d1`).

2. **Measured it** — a real before/after on the representative free-prose dispatch (the Dreamer
   consolidation prompt), model `haiku`, N=5/arm, reading the model's actual `usage.output_tokens`
   through the production chokepoint. Result: **mean −52.9%** (OFF 621.2 → ON 949.6) — *no* reduction;
   the preamble arm was larger on average, with a noise-robust median saving of only ~5%. Both readings
   are under the 10% bar. Full data + limitations: `build/06-evaluation/v0.6.1-caveman-measurement.md`.

3. **Rejected the runtime toggle** per the gate. Reverted the config (T-220), `hooks/_caveman.py`
   (T-221), and the chokepoint + engine wiring (T-222). **Kept** the deterministic non-verdict prompt
   tightening (T-223) — a real, always-on **input**-token win, independent of any toggle, that drops
   pure filler from the verbose `dreamer`/`autopilot`/`parallel_build` prompt constants while leaving
   the verify / skeptic / gate-verdict / observer prompts untouched.

## Why

- **No headroom.** A generic "answer with maximum brevity" instruction cannot shrink output that the
  prompt has *already* bounded ("3-5 sentences, terse, no bullet lists"). The measurement confirmed the
  SRS's own prior, rather than the upstream headline.
- **Honesty over sunk cost.** The mechanism was built, clean, default-off, and byte-identical when
  off — tempting to keep "since it costs nothing." But shipping a token-*reduction* toggle that
  measurably does not reduce tokens misrepresents the product. The measurement gate exists precisely to
  stop that, and following one's own pre-registered gate — instead of rationalizing around it — is the
  discipline that makes the gate worth having.
- **The deterministic tightening is the real win.** It is small but provable (fewer input tokens every
  dispatch, no model dependency, no toggle), and it ships.

## Alternatives considered

- **Keep the toggle, label it "experimental."** Rejected — contradicts the binding REQ-CM-005 gate and
  would ship an unproven, mislabeled "saving."
- **Take many more samples hoping a ≥10% win is hidden in the variance.** Rejected — the mean points the
  wrong way and the prompt is already length-bounded; more samples tighten an estimate that is not ≥10%,
  they do not create one. N=5 is acknowledged as a limitation in the eval note, but the *decision* needs
  only "no evidence of ≥10%," which holds in every reading.
- **`caveman-compress` / `caveman-shrink`.** Rejected at research time — model call + `pip` / Node-MCP
  proxy, both violating stdlib-only (REQ-NF-024).
- **Leave `_caveman.py` as dead code.** Rejected — "drop the toggle" means remove the mechanism.

## Consequences

- `_background_agent.dispatch`, `run_workflow`, `_orchestrate.fan_out`, and `OrchestrationConfig` are
  **byte-identical to v0.6.0**. There is no `caveman_mode` config and no `FORGE_CAVEMAN` env var.
- v0.6.1 ships the **static prompt tightening** plus this **documented negative result**, which closes
  the caveman investigation: future sessions read this ADR and the eval note instead of re-attempting
  the preamble approach.
- The deterministic tightening of verbose, non-verdict prompts remains a valid, low-risk lever for any
  future cost work. Genuine output-token reduction, if ever pursued, would need a different mechanism
  (e.g. cheaper models per dispatch class) — not a brevity preamble.
- The measurement-gated discipline is reinforced as a pattern: build behind a gate, measure for real,
  and let the data — not the effort already spent — decide what ships.
