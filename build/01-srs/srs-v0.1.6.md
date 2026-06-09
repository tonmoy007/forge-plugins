# SRS — Forge v0.1.6 (delta, locked)

> **Status**: **Scope locked 2026-06-09.** Composes with `srs.md`,
> `srs-v0.1.3.md`, `srs-v0.1.4.md`, `srs-v0.1.5.md`. This release implements the
> three interactive requirements that were *defined* in `srs-v0.1.5.md` §
> "REQ-INTERACTIVE-*" (decomposed from REQ-INTERACTIVE-001 by T-122) but
> deliberately **deferred** to v0.1.6 because they are net-new behavior, not
> v0.1.5 bug fixes.
>
> **Theme**: "Make Forge interactive — clarify before scoping, confirm before
> expensive writes, narrate during builds." Three agent/skill behavior changes,
> structurally tested. No new pipeline stages, no scripts beyond a narration
> hook, no daemons.
>
> **Lock basis**: the three REQs already carry triggers, behavior, and
> acceptance criteria (authored under T-122 from two on-project testers' signal,
> EF-013). Nothing new to discover; this delta schedules and builds them.

---

## 1. Scope

**In scope (firm)**:

- **CLARIFY** — `/forge:srs` asks a bounded batch of clarifying questions before
  writing the SRS, and records explicit assumptions for whatever stays
  unanswered (REQ-INTERACTIVE-CLARIFY-001).
- **CONFIRM** — `/forge:spec` and `/forge:plan` present an outline and pause for
  confirmation before generating the full artifact (REQ-INTERACTIVE-CONFIRM-001).
- **NARRATE** — `/forge:build` narrates progress at task boundaries instead of
  working silently (REQ-INTERACTIVE-NARRATE-001).
- Release wiring: traceability, progress/roadmap updates, version bump, CHANGELOG.

**Out of scope (firm)**:

- Any *new* interactive surface beyond these three agents (e.g. confirmation in
  deploy/release) — revisit only if dogfood asks.
- Runtime/behavioral test harnesses that drive a live LLM. Acceptance is
  **structural** (the directive is present and well-formed in the skill/agent
  instruction), consistent with `test_agent_tools.py` and
  `test_interactive_decomposition.py`. An LLM's runtime compliance is not unit-
  testable deterministically; we test that the instruction exists and is bounded.
- Sprint planning, daemons, agent orchestration — v0.2.

---

## 2. Requirements

> These three REQ bodies are restated verbatim-in-substance from `srs-v0.1.5.md`
> (their canonical definition), now with build-facing acceptance for v0.1.6.

### REQ-INTERACTIVE-CLARIFY-001 — Clarifying-question pattern (requirements-analyst)

**Trigger**: `/forge:srs` is run with a vague or under-specified project
description.

**Behavior**: Before writing `srs.md`, the requirements-analyst asks **one
bounded batch** of clarifying questions (a single round, not a drip) covering the
highest-ambiguity areas (scope, users, constraints), then proceeds — recording
explicit **assumptions** in the SRS for anything still unanswered.

**Acceptance**:
- **AC-INTERACTIVE-CLARIFY-001a** — `skills/forge-srs/SKILL.md` and
  `agents/requirements-analyst.md` both direct a single bounded clarifying-
  question round *before* `srs.md` is written (the bound — one batch / "not a
  drip" / a max-rounds cap — is stated, not open-ended).
- **AC-INTERACTIVE-CLARIFY-001b** — the same instructions require recording
  explicit assumptions for unanswered items in the SRS.

### REQ-INTERACTIVE-CONFIRM-001 — Staged confirmation (spec / plan)

**Trigger**: `/forge:spec` or `/forge:plan` is about to commit a large or
irreversible artifact (full technical spec, full task DAG).

**Behavior**: The agent presents a short outline / table of contents and pauses
for confirmation before writing the full document, so the user can redirect
before the expensive generation.

**Acceptance**:
- **AC-INTERACTIVE-CONFIRM-001a** — both `skills/forge-spec/SKILL.md` and
  `skills/forge-plan/SKILL.md` present an outline/TOC **and** an explicit
  confirmation pause before writing the full artifact.

### REQ-INTERACTIVE-NARRATE-001 — Progress narration (builder)

**Trigger**: `/forge:build` works a task (or a `--milestone N` batch).

**Behavior**: The builder narrates progress at task boundaries — which task it is
starting, the test/commit outcome, and what's next — instead of working
silently, so a long batch is observable.

**Acceptance**:
- **AC-INTERACTIVE-NARRATE-001a** — `skills/forge-build/SKILL.md` and
  `agents/builder.md` direct per-task start/result/next narration at task
  boundaries.
- **AC-INTERACTIVE-NARRATE-001b** — `scripts/build-batch.py` emits a per-task
  narration line (start + identifier) when listing a milestone's tasks, so a
  batch run is observable from the tool layer, not only the agent's prose.

---

## 3. Non-functional

- **NFR-COMPAT-001**: no breaking change to existing skills/agents/hooks; the
  interactive steps are additive instructions. The full pre-existing suite stays
  green.
- **NFR-DEP-001**: no new runtime dependency (PyYAML remains the only one).

---

## 4. Traceability

| REQ-ID                          | Source            | Task(s)        | Test |
|---------------------------------|-------------------|----------------|------|
| REQ-INTERACTIVE-CLARIFY-001     | srs-v0.1.5 (T-122)| T-126          | tests/unit/test_interactive_clarify.py |
| REQ-INTERACTIVE-CONFIRM-001     | srs-v0.1.5 (T-122)| T-127          | tests/unit/test_interactive_confirm.py |
| REQ-INTERACTIVE-NARRATE-001     | srs-v0.1.5 (T-122)| T-128          | tests/unit/test_interactive_narrate.py |
| NFR-COMPAT-001                  | this delta        | T-126..T-130   | full suite green |
| NFR-DEP-001                     | this delta        | T-130          | requirements.txt unchanged for runtime |

---

## 5. Open questions

- **OQ-1**: Should CONFIRM also gate `/forge:architecture` (another large
  artifact)? **Resolved: no** — scope is exactly the two named in the REQ
  (spec/plan). Revisit if dogfood asks. Keeps the release tight.

---

## 6. Acceptance Definition (release is done when)

- All three REQ acceptance criteria pass via their structural tests
  (`test_interactive_clarify.py`, `test_interactive_confirm.py`,
  `test_interactive_narrate.py`).
- The full suite (`pytest tests/ -q`) is green, `scripts/validate-plugin.py`
  exits 0, and `tests/integration/full-pipeline.sh` passes 12/12.
- `.claude-plugin/plugin.json` + `marketplace.json` both at `0.1.6`; CHANGELOG
  `## [0.1.6]` section at the top.
- Traceability table above is fully satisfied (every REQ → task → green test).
