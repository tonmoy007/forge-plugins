# SRS — Forge v0.3.5 (semantic skill mining + skill-creator)

> **Status**: **Draft — ready for build** (2026-06-15). Continues the v0.3 program. Replaces
> Forge's tool-name-n-gram skill-miner with a **semantic, success-gated, anti-unification-based**
> miner that proposes genuine reusable *workflows* and authors them via a `forge:skill-creator`
> skill — human-approved throughout.
>
> **Grounding**: derived from a three-stream research review (2026-06-15) of academic
> skill-induction (Voyager, **Agent Workflow Memory**, SkillWeaver, ExpeL, Reflexion, ADAS,
> Generative Agents, LILO, **Stitch/babble anti-unification**, TroVE), Anthropic **Agent Skills
> + skill-creator**, and production platforms (**Nous Hermes Agent**, **Xiaomi MiMo Code**,
> Devin, Cursor, Manus, OpenHands, Letta/MemGPT, Claude Code, Cline/Roo). Research artifacts are
> the session record; key citations inlined below.

---

## 1. Overview

### 1.1 Problem

Forge's current skill-miner (T-026/T-027) hashes **sliding 3-tool-name windows** from
`.forge/patterns.jsonl` and proposes a skill when a signature recurs ≥3 times. Because `Bash`,
`Read`, `Write`, and `Edit` appear in **every** workflow, the signatures are semantically empty:
the miner surfaces `forge-bash-read-write`-style noise, never the actual problem-solving pattern
(e.g. *diagnose failing test → locate root cause → patch → add regression test*). Two root
causes:

1. **Wrong alphabet.** Mining over opaque tool *names* cannot express intent. The literature is
   unanimous: operate on **semantic/outcome structure**, never raw action tokens.
2. **Wrong gate.** Bare frequency surfaces coincidental co-occurrence. **No shipping product
   gates on frequency alone** — Hermes (5+ tool-call *success*), MiMo Code `/distill`
   (repeated-workflow + confidence), Devin/Cursor (auto-suggest + approval) all gate on
   **success + human approval**. Forge's "3+ uses" is more aggressive than any of them.

The richer signal Forge needs is **already captured and discarded**: `hooks/post-tool-use.py`
writes `.forge/session-log.jsonl` with `{tool, file, success, stage}` per call, but the miner
only consumes the tool-name stream in `patterns.jsonl`.

### 1.2 Objective

Replace the n-gram miner with a pipeline that (a) **enriches** tool calls into semantic verbs,
(b) **segments** traces into outcome-bounded episodes, (c) finds recurring **parameterizable
workflows via anti-unification** (the stdlib filter that distinguishes a real workflow from a
coincidental n-gram), (d) gates on **success + repetition**, (e) **induces** a named, documented,
parameterized skill via a cheap LLM pass, (f) authors it through a `forge:skill-creator` skill,
(g) **verifies by replay** before admitting, and (h) **curates** the library over time — with a
human approval gate at the proposal boundary, throughout.

### 1.3 Scope

**In scope** — the eight-stage pipeline above, the `forge:skill-creator` skill, emission in the
**agentskills.io `SKILL.md`** format, replay verification, library curation/maintenance, and
migration off the n-gram path. Reuses existing rails: `_background_agent.dispatch` (cheap model,
`--json-schema`, `--max-budget-usd`), `_cost_cap`, capability gate, `FORGE_NO_BACKGROUND`, the
`skill-approval` flow, ADR-006 (skills drive in-session work; scripts can't drive the Agent tool).

**Out of scope (future)** — cross-project skill sharing via `~/.forge`; embedding/vector
retrieval of skills (Claude's description-matching handles invocation); RL/weight-level
self-improvement (MiMo-model style); fully unattended skill installation (human approval stays).

### 1.4 Design principles (from the research)

- **Enrich before mining.** Tool names are empty; args + results + exit codes + stage are not.
- **Anti-unification is the core filter.** Lift differing literals to parameters; identical
  diverging values map to the same variable. *If a recurring fragment cannot anti-unify into a
  coherent parameterized procedure, it is not a skill.* Pure stdlib (Plotkin/Stitch/babble). AWM
  showed a rule-based sequence-dedup version matches the LLM version (35.6 vs 35.5).
- **Gate on success, not frequency.** ≥k *distinct successful* episodes + a coherence gate.
- **Never store anonymous abstractions.** LILO: reusing unnamed abstractions dropped performance
  >30 points — auto-name + auto-document every candidate, and cite the source trace lines.
- **Verify before admit.** Generate/replay tests; ASI reports +23.5% from this gate alone.
- **Curate continuously.** ExpeL voting (ADD/UPVOTE/DOWNVOTE/EDIT, prune at 0) + TroVE frequency
  trim; a scheduled "dream" maintenance pass (MiMo Code `/dream` runs every 7 days: merge, dedup,
  path-validity) keeps the library from rotting.
- **Emit the standard.** `SKILL.md` per agentskills.io (name, description, When to Use,
  Procedure, Pitfalls, Verification), progressive disclosure.

---

## 2. Functional Requirements

### 2.1 Semantic miner core (deterministic, stdlib)

- **REQ-SM-001 — Semantic enrichment.** Canonicalize each tool call from
  `.forge/session-log.jsonl` into `(verb, args, outcome)` via a small rule table mapping
  `(tool, arg-pattern, exit/result, stage) → intent verb` (e.g. `pytest` exit≠0 →
  `run-tests(fail)`; `Edit(src/*)` after a failing test → `patch`; `Write(test_*)` after green →
  `add-regression-test`). Fail-soft; unknown calls map to a generic verb, never raise.
- **REQ-SM-002 — Episode segmentation.** Split the enriched stream into outcome-bounded
  *episodes* (a user turn / task starts one; a terminal success ends it), segmenting at outcome
  transitions — the **failure→fix delta** being the highest-signal boundary.
- **REQ-SM-003 — Anti-unification motif miner.** Over the *verb* sequences, find ordered
  fragments recurring across **≥k distinct episodes**, and **anti-unify** their instances:
  lift differing literals (file names, test names, error strings) to named parameters; map
  identical diverging values to the same variable. A fragment qualifies as a candidate **only if
  anti-unification yields a coherent parameterized skeleton** — this is the filter that replaces
  n-gram counting. Pure stdlib; deterministic.
- **REQ-SM-004 — Success + coherence gate.** A candidate is promoted only when its source
  episodes (a) are ≥k *distinct* and (b) ended in success (per `session-log` `success`/exit).
  Bare frequency is never sufficient. Replaces the v0.1 "≥3 occurrences" tool-name heuristic.

### 2.2 Induction + authoring

- **REQ-SM-005 — LLM induction with de-specialization.** For each candidate cluster, one
  cheap-model (`haiku`) background dispatch produces a **named, parameterized procedure** with a
  one-line description and **citations to the source trace lines** that justify it. Uses the
  structured-output path (`--json-schema`), cost- and capability-gated. **Degrades gracefully**:
  when background/LLM is unavailable, the deterministic anti-unified skeleton (REQ-SM-003) is the
  proposal — never a hard failure (REQ-NF: graceful degradation).
- **REQ-SM-006 — `SKILL.md` emission (agentskills.io).** Proposals are written as
  `.forge/proposed-skills/<slug>/SKILL.md` in the standard format: frontmatter (`name`,
  `description` — third-person, what+when, deliberately discoverable) + body sections *When to
  Use / Procedure / Pitfalls / Verification / Provenance*. Never store an unnamed proposal.
- **REQ-SM-007 — `forge:skill-creator` skill.** A new skill consumes a candidate and runs the
  Anthropic skill-creator loop (capture intent → write `SKILL.md` → test against a baseline →
  grade → improve → **optimize description** via the should-/should-not-trigger query test). Runs
  **in-session** (ADR-006: hooks/scripts cannot spawn the authoring agent). Human-in-the-loop.

### 2.3 Verify + curate

- **REQ-SM-008 — Replay verification.** Before a proposal is admitted/installed, **replay** it
  against the source episodes it was induced from; admit only if it reproduces the successful
  outcome (for coding, the oracle is the test suite — red→green). When no runnable oracle exists,
  fall back to a critic check. Reuses gate infrastructure.
- **REQ-SM-009 — Library curation.** Maintain skills with **ExpeL-style voting** — ADD (init
  weight), UPVOTE on successful reuse, DOWNVOTE on failed reuse, EDIT-merge near-duplicates,
  **prune at weight 0** — plus a **TroVE frequency trim** (drop skills used below a log-scaled
  threshold). A scheduled maintenance pass (`/dream`-style) merges near-duplicate descriptions,
  prunes stale/never-used skills, and flags skills whose referenced files/commands no longer
  exist. Cheap, offline, `.forge`-only.

### 2.4 Migration

- **REQ-SM-010 — Retire the n-gram path.** Replace the tool-name-window miner; keep a clean
  migration (existing `proposed-skills/` and `skill-blacklist.txt` still honored). Fix the
  doc-drift in the `forge:skill-miner` agent persona (it claims `.forge/proposals.jsonl`, which
  does not exist — the artifact is `.forge/proposed-skills/<slug>/SKILL.md`). Update
  `references/` + README.

---

## 3. Non-Functional Requirements

- **REQ-NF-016 — Stdlib + PyYAML fail-soft; never-raises.** Enrichment, segmentation, and
  anti-unification are pure stdlib; the miner runs on the hot/background path and must never raise.
- **REQ-NF-017 — Graceful degradation.** With no background/LLM capability or under
  `FORGE_NO_BACKGROUND=1`, the deterministic anti-unified proposal is still produced; LLM
  induction (REQ-SM-005) is an enhancement, not a dependency.
- **REQ-NF-018 — Bounded & gated.** LLM induction, replay, and maintenance are budget/attempt
  capped via `_cost_cap` + `--max-budget-usd`; the cheap model is pinned; `.forge`-only writes.
- **REQ-NF-019 — Human-in-the-loop.** No skill is installed without explicit approval; proposals
  are inspectable; the approval/blacklist flow is preserved and extended.
- Inherited: capability + cost gating, ADR-006, ≤2000-token session-start budget, two-remote
  parity, `python3`, TDD red-first.

---

## 4. Acceptance Criteria

- **AC-SM-001/003** — Given a session log containing `pytest(fail) → read → edit → pytest(pass)
  → write(test_*)` across **3 distinct sessions** with differing file/test names, the miner emits
  **one** candidate whose procedure is parameterized over the differing names (anti-unified), and
  emits **nothing** for a control stream where `Bash/Read/Write` merely co-occur without a
  coherent shape.
- **AC-SM-004** — A motif that recurs 3× but in episodes that all **failed** is **not** promoted.
- **AC-SM-005/006** — A promoted candidate yields a valid agentskills.io `SKILL.md` with a
  non-empty third-person `description` and source-line provenance; with background disabled, the
  deterministic skeleton proposal is still produced.
- **AC-SM-007** — `/forge:skill-creator` takes a candidate and produces a tested skill with a
  description that passes a should-/should-not-trigger check; nothing installs without approval.
- **AC-SM-008** — A candidate that fails replay (does not reproduce red→green) is **not** admitted.
- **AC-SM-009** — Two near-duplicate proposals are merged; a never-approved/never-used skill is
  pruned by the maintenance pass; a skill referencing a deleted file is flagged.

---

## 5. Traceability

| REQ-ID | Task |
|--------|------|
| REQ-SM-001, 002 | T-177 |
| REQ-SM-003, 004 | T-178 |
| REQ-SM-005 | T-179 |
| REQ-SM-006, 007 | T-180 |
| REQ-SM-008 | T-181 |
| REQ-SM-009 | T-182 |
| REQ-SM-010 | T-183 |
| (release) | T-184 |

---

## 6. Key citations (research, 2026-06-15)

- **Agent Workflow Memory** — arXiv 2409.07429 (rule-based sequence dedup ≈ LLM; cluster + induce + strip specifics).
- **Anti-unification** — Plotkin (1970); **Stitch** POPL'23 (2211.16605); **babble** PLDI'23 — the parameterization/abstraction mechanism.
- **Voyager** 2305.16291 (admit-on-verified-success; code + docstring; embed the description).
- **ExpeL** 2308.10144 (ADD/UPVOTE/DOWNVOTE/EDIT insight maintenance); **TroVE** 2401.12869 (execution-agreement verify + frequency trim).
- **LILO** 2310.19791 (mandatory naming of abstractions).
- **Reflexion** 2303.11366 (failure→fix is the high-signal delta); **Generative Agents** 2304.03442 (importance-threshold trigger; cite-the-evidence).
- **Nous Hermes Agent** (auto-induce `SKILL.md` after 5+ tool-call success / correction / dead-end recovery; `write_approval`; dedup/merge) — github.com/nousresearch/hermes-agent.
- **Xiaomi MiMo Code** (`/distill` repeated-workflow→skill; `/dream` 7-day merge/dedup/path-validity cron) — github.com/XiaomiMiMo/MiMo-Code.
- **Anthropic Agent Skills + skill-creator** (SKILL.md format; author→test→optimize-description loop; description is the retrieval key) — code.claude.com/docs/en/skills; github.com/anthropics/skills.
- **agentskills.io** — the converged SKILL.md standard (Claude Code, Cursor, OpenHands, Manus, Hermes, MiMo, Letta, …).
