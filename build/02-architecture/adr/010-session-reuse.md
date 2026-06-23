# ADR-010: Per-Node Session Reuse — Within-Node Only, Admission Stays Fresh, Default-Off

**Status**: Accepted
**Date**: 2026-06-23

## Context

The v0.4.0 DAG engine dispatches **every node as a fresh `claude -p` session**. A fresh
session pays the ~42k-token cache-creation tax (the `FRESH_FLOOR_USD` floor, currently
`$0.06`); a `--resume` of an existing session is a cache read (`RESUME_FLOOR_USD`, `$0.01`).
The single dispatch wrapper (`hooks/_background_agent.dispatch`) was **built for reuse** — it
takes `resume=<session_id>`, emits `--resume`, charges the cheaper floor, and returns each
run's `session_id` — yet the engine never used it for node-to-node reuse:

- `_attempt` (`scripts/_workflow.py`) threw away the `session_id` it got back.
- A node that **fails and retries** (`_run_node`) re-dispatched **fresh**, paying a second
  full floor — even though the retry is the *same node, same prompt, same model* and could
  `--resume` the first attempt's session.
- A node that **fails verification and heals** re-dispatched **fresh** for the same reason.

So a node taking 2–3 production dispatches (first + retry, or first + heal) paid 2–3× the
fresh floor where the 2nd/3rd were provably resumable. The existing `run_workflow(resume=...)`
param does not help: it is a blunt **run-level** knob that threads one caller-supplied session
into **every** node identically (used to resume an interrupted run), not a per-node
capture-and-chain.

The open question this ADR settles: **how far should reuse reach, and what must stay
invariant** so that turning it on cannot change the engine's admitted/dropped set, its
determinism, or its correctness — only its realized cost.

## Decision

**Add deterministic, fail-soft per-node session reuse: capture each node's first-attempt
`session_id` and thread it as `resume` into that same node's retry and heal re-dispatches —
the only re-dispatches whose prompt and model are provably identical — behind a default-off
toggle, with admission kept on the fresh floor and a fallback to a fresh dispatch on any
stale session.**

Five load-bearing decisions, each with its rationale:

- **Within-node reuse only; exclude cross-node (per-branch) chains.** A node's **retry** and
  **heal** re-dispatch the *same prompt with the same model*, so `--resume` is semantically
  valid there. Resuming a *dependency's* session for a *dependent* node spans heterogeneous
  prompts/models, which generally defeats `--resume`, has a far weaker correctness argument,
  and a smaller marginal saving. Per-branch reuse is a future, **measurement-gated** follow-up
  (SRS §6), not a v0.6.0 line item. No heuristic "is this resumable?" guessing — only the
  provably-identical case.

- **The independent verifier is never reused.** The verifier's fresh-context independence is
  the whole point (REQ-WF-002); a reused verifier would judge with the producer's own context
  and stop being independent. Reuse threads `resume` only into the node's **own** production
  re-dispatches via a per-attempt copy (`{**kwargs, "resume": sid}`) — never a mutation of the
  shared kwargs dict that flows on to `_run_verify`. Structurally, `_verify.run_verify` already
  forces `call["resume"] = None`, so verifier independence holds even if the node's kwargs
  carried a `resume`.

- **Admission stays on `FRESH_FLOOR_USD`.** `_preallocate` and `estimate_admission` keep
  charging the fresh floor per node regardless of `session_reuse`. Reuse must **not** feed the
  deterministic pre-allocation, or the pre-flight estimator would drift from the run, violating
  the estimator-equals-run-drops invariant (AC-WF-014). The fresh floor is a conservative upper
  bound; reuse simply makes the realized run *cheaper than predicted* — always the safe
  direction. The admitted/dropped split, the `dropped_reasons` strings, and the id-ordered
  narration summary are **identical with reuse on or off**.

- **Default-off toggle (`orchestration.session_reuse`).** Reuse changes a retry's realized
  *content* (it now carries the failed attempt's context) and its cost; gating it off-by-default
  keeps v0.6.0 **byte-identical to v0.4.x** unless a user opts in, matching the engine's
  capability-toggle discipline (REQ-NF-025). The toggle parses with the existing strict
  `is True` / fail-soft rule — a stray `1`/`"yes"` never enables it; absent/malformed config →
  off — and threads from `OrchestrationConfig` through `parallel_build` / `workflow_loader` /
  `_orchestrate` into `run_workflow`.

- **Fall back to fresh on a stale session.** A reused (`--resume`) re-dispatch that returns a
  non-`ok` status (a stale or invalid session id) triggers **one fresh fallback re-dispatch of
  the same node within the same attempt budget** before the node is considered failed. Reuse can
  therefore lower cost but can **never** turn a would-succeed node into a drop. The fallback
  never raises (REQ-F-003) and adds no new drop-reason string when it recovers.

## Rationale

1. **Reuse only what is provably identical.** The same-node retry/heal case is the only one
   with a clean correctness argument; everything weaker (cross-node, verifier) is excluded by
   construction rather than by a runtime heuristic.
2. **Admission is never a function of reuse.** Keeping the fresh floor in the deterministic
   pre-allocation is what preserves AC-WF-014: the estimator and the run still agree on the
   admitted/dropped split, and reuse only makes the run cheaper than the estimate.
3. **Off ⇒ byte-identical to v0.4.x.** With the toggle off, no `session_id` is captured for
   reuse and every re-dispatch is fresh — observably unchanged (REQ-NF-025 lineage). The
   capture refactor (REQ-WF-016) was committed **separately** from the reuse behavior
   (REQ-WF-017/018), so the refactor commit left the full existing suite green and unchanged
   (split-determinism, REQ-NF-040).
4. **Reuse never costs correctness.** The stale-session fallback keeps reuse strictly
   non-regressive — fail-soft, never-raises (REQ-NF-024 / REQ-F-003).
5. **Determinism and the stdout contract are untouched.** Reuse changes realized cost (and the
   model-nondeterministic *content* of a retry, which was never deterministic); it never changes
   the engine's **ordered** result/drops/summary structure or writes a byte to stdout
   (REQ-NF-026 / T-128).

## Alternatives considered

- **Per-branch / cross-node (linear-chain) reuse in v0.6.0.** Rejected for this release:
  heterogeneous prompts/models across a DAG generally defeat `--resume`, the saving is smaller,
  and the correctness argument is far weaker than the same-node case. Deferred to a
  measurement-gated follow-up (SRS §6).
- **Reuse the verifier's session for the heal.** Rejected outright: it destroys the verifier's
  fresh-context independence (REQ-WF-002), the property the verifier exists to provide.
- **Let reuse lower the admission floor (charge `RESUME_FLOOR_USD` in pre-allocation).**
  Rejected: it would make the estimator drift from the run and break AC-WF-014; admission must
  stay a conservative, reuse-independent upper bound.
- **Ship reuse on-by-default.** Rejected: it would change a retry's realized content and cost
  for every existing user, breaking the v0.4.x byte-identical guarantee; reuse is opt-in like
  every other engine capability.
- **No fallback (let a stale `--resume` drop the node).** Rejected: a stale session would turn
  a would-succeed node into a drop, making reuse regressive. The fresh fallback within the same
  attempt budget is what makes reuse strictly cost-only.

## Consequences

- `_attempt` (`scripts/_workflow.py`) now surfaces the dispatch `session_id` as a 4-tuple
  `(obj, reason, cost, session_id)`; `_run_node` tracks the newest non-`None` session and
  reuses it for the node's own retry + heal re-dispatches via a per-attempt kwargs copy.
- `orchestration.session_reuse` (bool, default `false`) is added to `OrchestrationConfig` +
  `_TOGGLES` in `scripts/_workflow_config.py`, threaded into `run_workflow`.
- `_preallocate` / `estimate_admission` are unchanged (fresh floor); the T-203 `events.jsonl`
  `workflow_run` record stays exactly one schema-versioned, PII-free line per run — reuse shows
  up only as a **lower `total_cost_usd`** (the additive `reused` field was deliberately not
  added: optional, and a `schema_version` bump for no required benefit).
- With the toggle off the engine is byte-identical to v0.4.x; the per-feature gates
  AC-WF-016..021 (and AC-WF-019 toggle-off byte-identical, AC-WF-020 estimator invariance)
  prove "cheaper, zero semantic change."
- See **[`references/workflow-engine.md`](../../../references/workflow-engine.md)** (the
  `session_reuse` toggle row + the *Per-node session reuse* section) for the user-facing surface.
