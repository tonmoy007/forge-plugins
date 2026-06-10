# ADR-006: Orchestration Primitive Wraps In-Session Subagents With a Structured Contract

**Status**: Accepted
**Date**: 2026-06-10

## Context

P2 needs deterministic multi-agent fan-out for two consumers: parallel reviewers
(REQ-F-034) and brownfield extraction (REQ-F-038). This is **in-session**
orchestration — Claude spawning subagents within the current session — and is
explicitly **distinct from the P1 background-agent API** (daemons). Conflating the
two would couple a non-gated P2 feature to the spike-gated P1 capability.

The SRS asks (OQ-002): does the primitive wrap the Agent tool / agent-teams or shell
out, and what is the structured-output contract? It also demands determinism
(REQ-NF-009): the same inputs must produce the same synthesized output whether the
work ran in parallel or sequentially.

The codebase already has a structured-proposal discipline: `hooks/_proposals.py`
defines Pydantic models and pins LLM-originated content to `trust="ephemeral"`;
`_validator.py`/`_executor.py` validate and atomically apply them.

## Decision

**Add `scripts/_orchestrate.py` as the single adapter wrapping the in-session
subagent mechanism. Each fan-out item declares a Pydantic result schema; subagents
return one validated JSON object; the primitive collects them index-ordered, dedups,
and returns deterministically. Parallel where the host supports agent-teams,
identical-output sequential fallback otherwise.**

- **One adapter per mechanism** (REQ-NF-010): a Python `scripts/` primitive cannot
  reach Claude's in-session Agent/Task tool (that is the *model's* tool, not callable
  from a subprocess), so `_orchestrate.py` **delegates each single agent call to
  `_background_agent.dispatch`** (the sole `claude -p` wrapper) and layers the
  deterministic fan-out on top. There is still exactly one place that touches the host
  binary. *(Correction, 2026-06-10: an earlier draft of this ADR said the primitive
  "wraps the in-session subagent mechanism" and rejected `claude -p`. That was not
  buildable from a script; REQ-F-031 explicitly has the **script** spawn the subagents,
  which means `claude -p`. The decision below is corrected accordingly.)*
- **Structured-output contract**: malformed subagent output is retried at the call
  layer; on repeated failure the item drops to `null` and is `log()`ged — never
  silently truncated.
- **Bounded** (REQ-F-033): `orchestration.max_parallel` (default small) + a total
  cap; every spawned agent routes cost through `_cost_cap.py`.
- **Determinism by construction** (REQ-NF-009): results are ordered by input index
  (not completion order); sequential and parallel paths synthesize byte-identical
  output. This is enforced as a **test invariant**, not merely asserted in prose.
- **Boundary reuse**: orchestrated results become proposal objects → validator →
  executor (REQ-F-035). No new trust machinery.

## Rationale

1. **Decouples P2 from P1**: in-session fan-out works regardless of the
   background-agent spike outcome, so brownfield/review ship independently.
2. **Reuses proven safety**: the Pydantic proposal pattern already governs every
   write to long-term memory; orchestrated output rides the same rails.
3. **Determinism is testable**: index-ordering + a shared synthesis function make the
   "sequential == parallel" claim a concrete equality test, not a hope.
4. **Single call site** keeps host-API churn (agent-teams evolving) contained.

## Alternatives considered

- **Drive Claude's in-session Agent tool from the script.** Not possible — that tool
  belongs to the model loop, not to a subprocess. (This is why the original "in-session
  subagent" framing was corrected above.)
- **Couple to the spike gate.** Using `claude -p` does *not* re-couple P2 to the daemon
  spike gate: that gate (O-2 completion-rate) is about *detached, fire-and-forget*
  reliability. Orchestration is **synchronous** — it awaits and validates each result,
  retrying on failure — so daemon reliability is irrelevant. P2 stays decoupled from P1.
- **Free-text subagent results parsed heuristically.** Rejected: non-deterministic,
  brittle, and at odds with the existing structured-proposal discipline.
- **Unbounded parallelism.** Rejected: cost and host limits; bounded fan-out with a
  sequential fallback gives the same results, only slower.

## Consequences

- `_orchestrate.py` must ship with a determinism test (sequential output ==
  parallel output for a fixed work-list) before any consumer depends on it.
- The first consumer (`/forge:review`, REQ-F-034) doubles as the E2E proof of the
  primitive before brownfield builds on it.
- A new Pydantic `FindingProposal`/result schema may be added to `_proposals.py`,
  keeping all structured contracts in one place.
