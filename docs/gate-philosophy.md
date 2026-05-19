# Gate Philosophy — when to resolve a blocker vs. override it

Forge gates are not bureaucracy. Each stage gate encodes a question of the form
*"is the work from this stage actually done well enough to build the next stage
on top of it?"* A failing blocker means the answer is currently "no."

This document explains the one escape hatch — `/forge:force-advance` — and when
using it is legitimate engineering judgment versus when it is just skipping the
work.

---

## The default: resolve, don't override

A blocker exists because something downstream depends on it. `G1-001` (SRS file
exists) blocks Stage 2 because you cannot design a product experience for
requirements that were never written down. The default response to a blocker is
to **do the work the gate is asking for**, then re-run the gate.

`/forge:why <gate-id>` explains what a criterion checks and why it exists. Read
that before deciding the gate is wrong.

---

## The escape hatch: `/forge:force-advance`

Sometimes the gate is genuinely wrong for *this* project, or the cost of
satisfying it mechanically exceeds its value. Forge does not pretend that never
happens. `/forge:force-advance --reason "<why>"` advances the stage anyway.

What it does **not** do:

- It does **not** mark the blocker as passed. The criterion still fails on every
  subsequent `check-gate` run for that stage. The override is *per-advancement*,
  not *per-criterion* — you bought one step forward, not a green gate.
- It does **not** delete or rewrite the criterion.

What it **does** do:

- Requires a non-empty `--reason` (≥ 10 chars). No silent overrides.
- Records a lesson tagged `force-advance` containing your verbatim reason and the
  exact list of blocker IDs that were overridden.
- Annotates the stage history in `pipeline/state.md` as `(force-advanced)`.

The reason is not a formality. It is the audit trail. "Skipping perf NFR — this
is an internal one-off script, p99 latency is irrelevant" is a defensible
override. "skip" is not.

---

## When an override is legitimate

- **The criterion does not apply to this project class.** A `script`-profile
  one-off does not need the full non-functional-requirements battery a
  production API does. (The `script` profile already relaxes these, but edge
  cases remain.)
- **The criterion is satisfied in substance but not in the form the check can
  see.** Example: acceptance criteria live in an external tracker, not inline in
  the SRS. Record that in the reason so the next reader knows where to look.
- **A deliberate, time-boxed trade-off.** Shipping a hotfix ahead of full eval
  coverage, with the gap explicitly named and owned.

In every legitimate case the reason answers: *what is the risk we are accepting,
and why is it acceptable here?*

## When an override is just skipping the work

- The reason restates the blocker ("SRS not written yet") instead of justifying
  proceeding without it.
- The same gate is force-advanced repeatedly across sessions. That is not a
  judgment call anymore — it is a pattern, and the gate (or the workflow) needs
  to change, not be bypassed each time.
- The override is used to hit a deadline by hiding incomplete work rather than
  naming it.

---

## Revisiting overridden gates

Overrides are visible, not buried:

- `/forge:why force-advance` lists recent force-advance lessons with their
  reasons and overridden blocker IDs.
- Stage 12 (`/forge:retro`) surfaces force-advance lessons in the retrospective.
  Repeated overrides of the same gate are a signal: either the criterion is
  miscalibrated and should be amended, or the team is accruing real debt and
  should pay it down.

A force-advanced gate is a debt with a name attached. The system's job is to
keep that debt visible until it is either repaid (resolve the criterion) or
consciously written off (amend the gate). It is never to forget it.

---

## Summary

| Situation | Action |
|-----------|--------|
| Blocker is correct and applies | Do the work, re-run the gate |
| Unsure why the gate exists | `/forge:why <gate-id>` first |
| Gate genuinely wrong for this project | `/forge:force-advance --reason "<risk accepted + why ok>"` |
| Same gate overridden repeatedly | Stop. Amend the criterion or fix the workflow |

The gate model only works if overrides stay rare, reasoned, and visible.
`/forge:force-advance` is designed so that they are.
