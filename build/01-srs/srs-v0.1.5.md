# SRS — Forge v0.1.5 (delta, stub)

> **Status**: Stub. Composes with `srs.md`, `srs-v0.1.3.md`, `srs-v0.1.4.md`.
> Created 2026-05-24 to capture `fix-v0.1.5`-bucket items from triage in
> `build/06-evaluation/v0.1.3.1-early-feedback.md` (pre-dogfood) so they
> don't get lost between releases.
>
> **Posture**: REQ shells with acceptance bars sketched but not finalized.
> Each REQ will be tightened — and possibly merged or split — when v0.1.4
> dogfood adds more findings and the v0.1.5 scope is locked in.
>
> **Theme** (provisional): "Sand off the v0.1.3 sharp edges surfaced by
> external eyes." Bug-fix-heavy, plus small UX nudges (next-step hint,
> session log enrichment, WebSearch for research stages). No new
> pipeline stages, no agent orchestration, no daemons.

---

## 1. Scope

**In scope (provisional)**:

- Bug fixes for next-step hint ordering, scaffold/output path collision,
  and pattern bus producing nothing useful (EF-004, EF-005, EF-008).
- Documentation: troubleshooting note about third-party plugin hooks
  triggering on prose (EF-003).
- UX nudges: session log enrichment, per-stage reflection rollup, large
  doc splitting convention, WebSearch in research/spec stages
  (EF-006, EF-009/015, EF-010, EF-012).
- Decomposition of "agents should be more interactive" into ≥2 concrete
  REQs based on v0.1.4 dogfood probing (EF-013).

**Out of scope (firm)**:

- Sprint planning / per-sprint review workflow (EF-011) — v0.2.
- Brownfield multi-agent fan-out for requirements extraction (EF-014) —
  v0.2.
- Fixing third-party plugins (EF-003) — never. Docs only.
- All v0.1.4 non-goals from `srs-v0.1.4.md` §6 remain non-goals here.

---

## 2. Functional Requirements (provisional)

### REQ-NEXTHINT-001 — Post-stage "next step" hint matches pipeline order

**Source**: EF-004 (and blocked on OQ-5; see EF-016)

**Trigger**: A `/forge:*` skill or `state-manager` advances stage and
emits a next-step hint to the user.

**Status**: Behavior below is the **mandatory** branch (OQ-5 option A).
If OQ-5 lands on advisory (option B), this REQ is rewritten to offer
both `/forge:product` and `/forge:arch` after SRS with trade-off
guidance.

**Behavior** (sketch):

- After `01-srs`, the next-step hint says **product/UX**, not architecture.
- The hint is derived from a single source of truth (stage order table)
  rather than per-skill hardcoded strings.

**Acceptance** (sketch):

- AC-NEXTHINT-001a: A unit test enumerates each stage transition and
  asserts the hint string names the correct next stage.
- AC-NEXTHINT-001b: No `/forge:*` skill contains a hardcoded "next
  step" string outside the shared helper.

---

### REQ-PATHS-001 — Canonical pipeline stage directory names

**Source**: EF-005

**Trigger**: `forge:init` scaffolds the pipeline directory, or any stage
skill writes its output.

**Behavior** (sketch):

- Decide one canonical name per stage (`04-spec/` or `04-technical-spec/`,
  not both). Document the canonical list in `references/`.
- Init scaffolds and stage skills both use the canonical names.

**Acceptance** (sketch):

- AC-PATHS-001a: Integration test (`tests/integration/full-pipeline.sh`)
  fails if any stage writes outside its canonical directory.
- AC-PATHS-001b: No two directories under `pipeline/` correspond to the
  same stage.

**Open**: Pick `04-spec` (matches existing init scaffold) vs
`04-technical-spec` (matches existing skill output). Decide during plan.

---

### REQ-LARGEDOC-001 — Convention for splitting large stage documents

**Source**: EF-006

**Trigger**: An SRS / spec / architecture document grows past a
readability threshold and the author wants to split it.

**Behavior** (sketch):

- Document a multi-file layout convention: `pipeline/0X-stage/<doc>/`
  becomes a directory with numbered `.md` files and a top-level
  `index.md` manifest listing them in order.
- Backward-compatible: single-file `pipeline/0X-stage/<doc>.md` still works.
- Downstream stages locate sections via the manifest, not by filename
  guessing.

**Acceptance** (sketch):

- AC-LARGEDOC-001a: Convention documented in
  `references/large-doc-layout.md`.
- AC-LARGEDOC-001b: At least one stage skill (likely `forge:spec`)
  demonstrates reading either single-file or multi-file layout.

---

### REQ-PATTERN-001 — `pattern.jsonl` carries actionable events

**Source**: EF-008

**Trigger**: Any session that runs `/forge:*` skills or stage skills.

**Behavior** (sketch):

- Pattern bus records: skill invocations, gate outcomes, tool-use
  patterns relevant to skill-mining. One event per line, schema versioned.
- Empty / noise-only `pattern.jsonl` on a real session is treated as a
  bug, not a feature.

**Acceptance** (sketch):

- AC-PATTERN-001a: After running the integration test pipeline,
  `pattern.jsonl` is non-empty and every line parses against the
  documented schema.
- AC-PATTERN-001b: The skill-miner trigger (≥3 uses → proposal) actually
  fires on a synthetic 3-use sequence.

---

### REQ-SILENTSTATE-001 — State-read failures surface visibly

**Source**: EF-007 (corroborated by EF-002 error-log evidence)

**Trigger**: Any hook, script, or skill tries to read `pipeline/state.md`
and fails (file missing, frontmatter malformed, import error, permission
denied, etc.).

**Behavior** (sketch):

- Hooks must not silently swallow state-read errors. Current pattern
  (catch, log to `error_logs.jsonl`, continue with default/empty state)
  produces fake-green sessions where gates evaluate against missing data
  and the user sees no validation feedback. Evidence: 28 silent
  `state_read_failed` events across a 24-hour window in the v0.1.3
  tester's `error_logs.jsonl`.
- Failure-handling policy:
  1. **First state-read failure in a session** → surface a one-line
     warning to the user via the hook's normal output channel, naming
     the file and the underlying error.
  2. **Gate checks** running against an unreadable state must report
     `inconclusive` (not `pass`), and `/forge:why` must explain that
     state could not be read.
  3. `/forge:doctor` reads `error_logs.jsonl` and surfaces any
     `state_read_failed` events from the current session at the top of
     its output, so the user can see the problem without hunting.
  4. The session-end Stop hook prints a footer summarizing any
     `state_read_failed` count > 0.
- Existing `error_logs.jsonl` keeps the structured trail; this REQ adds
  the *surfacing* layer on top.

**Acceptance** (sketch):

- AC-SILENTSTATE-001a: A synthetic test in which `pipeline/state.md`
  is unreadable produces (i) a visible warning on first hook fire,
  (ii) `inconclusive` gate output, (iii) a `/forge:doctor` callout, and
  (iv) a Stop-hook footer with the event count.
- AC-SILENTSTATE-001b: No hook code path catches an exception around
  `read_state()` without also re-raising or emitting a user-visible
  signal. Enforced via grep test against `except` blocks adjacent to
  state-read call sites.

---

### REQ-DOCTOR-001 — Doctor includes current-stage gate in its check set

**Source**: EF-017

**Trigger**: User runs `/forge:doctor` while the project is mid-pipeline
and the current stage's exit gate has unmet blockers.

**Behavior** (sketch):

- `doctor.py` runs the current stage's gate as part of its check set
  (via `check-gate.py` against the stage in `pipeline/state.md`). Each
  blocker gate failure becomes a doctor check failure.
- Top-line status changes from a flat `"all checks passed"` to one of:
  - `healthy` — all checks pass *and* current-stage gate has 0 blocker
    failures.
  - `wedged` — environment/plugin checks pass but current-stage gate has
    ≥1 blocker failure. Output names the failing criteria (e.g.
    `G4-001: pipeline/04-spec/technical-spec.md does not exist`) and
    links to `/forge:status` and `/forge:why` for detail.
  - `broken` — environment/plugin checks themselves fail (Python
    version, missing hook, etc.). Highest-severity diagnostic.
- The check is **inline**, not a separate command — doctor cannot
  contradict status on the same session, which is the bug.

**Acceptance** (sketch):

- AC-DOCTOR-001a: A synthetic test where `pipeline/state.md` says
  `current_stage: 4` and the stage-4 artifacts are missing produces
  doctor output with `status: wedged` and the failing G4-* IDs.
- AC-DOCTOR-001b: A synthetic test where all current-stage blockers
  pass produces `status: healthy`. Warnings on the current stage do
  not downgrade to `wedged` (they're noted but don't block).
- AC-DOCTOR-001c: Output schema for `/forge:doctor` and `/forge:status`
  never produces contradictory verdicts on the same project state.
  Enforced by a smoke test that runs both back-to-back and diffs.

**Relation to REQ-SILENTSTATE-001**: Both REQs fight the same
antipattern (surface-level "healthy" while system is stuck). This one
fixes the *doctor* layer; REQ-SILENTSTATE-001 fixes the *hook* layer.
They share AC-pattern but are mechanically distinct.

---

### REQ-LESSON-SOURCES-001 — Expand lesson capture trigger surface

**Source**: EF-018

**Trigger**: A session emits one or more *implicit* signals that a
mistake or pathology occurred, even though the user never typed an
explicit correction prompt.

**Behavior** (sketch):

- Today, `prompt-submit.py` is the only producer of
  `.forge/correction-flags.jsonl` entries, and it only fires on user
  prompts matching `don't X` / `use X not Y` / `always X` / `prefer X`.
  This REQ adds **implicit signal producers** that also write
  correction-flag rows with synthetic prompt text the existing
  rule-based extractor can pattern-match on.
- Candidate signal producers (final set decided per OQ-6):
  1. **Hook-error threshold** — if any single hook fires ≥ N errors
     per session (e.g. the 28-event `state_read_failed` cluster from
     EF-002), emit a flag describing the failure mode.
  2. **Repeated `PreToolUse` block on the same tool** — ≥ M blocks of
     `Write` to similar paths in one session signals a tool/policy
     mismatch (the EF-003 false-positive pattern).
  3. **Bash heredoc write following `Write` block** — direct evidence
     that the model is routing around a hook (the EF-003 bypass
     pattern; concrete enough to detect via tool-call sequence).
  4. **Gate transitioning from `pass` to `wedged` within a session** —
     signals premature advance (the EF-005 / EF-017 pattern).
  5. **State read returning empty/default after a successful prior
     read in the same session** — silent state corruption signal
     (the EF-007 / REQ-SILENTSTATE-001 pattern).
- The extractor (`scripts/extract-lessons.py`) is reused unchanged.
  Producers just need to write flag rows whose `prompt` text is
  pattern-match friendly (e.g. `"don't bypass Write via bash heredoc"`,
  `"never advance stage when next gate cannot read prior artifacts"`).

**Acceptance** (sketch):

- AC-LESSON-SOURCES-001a: A synthetic session that reproduces each
  enabled signal produces ≥1 `correction-flags.jsonl` row from that
  signal. One test per producer.
- AC-LESSON-SOURCES-001b: At session end, `tasks/lessons.md` contains
  ≥1 lesson per enabled producer that fired. `.forge/lessons.yaml`
  is regenerated and non-empty.
- AC-LESSON-SOURCES-001c: No producer fires false positives on a
  clean control session (no hook errors, no blocks, no wedges) — a
  control test must yield zero flags.

**Open**: Producers (1) and (4) need threshold values. See OQ-6.

---

### REQ-SESSIONLOG-001 — `session.jsonl` enrichment

**Source**: EF-009, EF-015

**Trigger**: Stop hook (or equivalent) writes the per-session record.

**Behavior** (sketch):

- `session.jsonl` records per session: commands invoked, token usage
  (from hook payload), and a back-reference (by session_id) to the
  reflection-log entry. No PII; no raw prompt content.
- Schema versioned; existing fields preserved.

**Acceptance** (sketch):

- AC-SESSIONLOG-001a: A real session produces a `session.jsonl` row
  containing `commands`, `tokens`, `reflection_ref` fields.
- AC-SESSIONLOG-001b: A consumer (script or test) can rebuild a session
  timeline from `session.jsonl` alone.

---

### REQ-STAGEREFLECT-001 — Per-stage reflection rollup

**Source**: EF-010

**Trigger**: A stage's gate passes and the pipeline advances out of that
stage.

**Behavior** (sketch):

- At stage-exit, emit a stage-level reflection summarizing what happened
  across all sessions in that stage (key decisions, surprises, lessons).
- Written to `pipeline/0X-stage/reflection.md` (one per stage).
- Complements, does not replace, per-session reflections from
  `stop-reflect.py`.

**Acceptance** (sketch):

- AC-STAGEREFLECT-001a: Completing a stage produces
  `pipeline/0X-stage/reflection.md`.
- AC-STAGEREFLECT-001b: File contents reference the session_ids that
  contributed and the gate outcome.

---

### REQ-WEBSEARCH-001 — WebSearch in research/spec stage agents

**Source**: EF-012

**Trigger**: A research-oriented stage agent (SRS, product, architecture,
spec, plan) needs current best-practice grounding.

**Behavior** (sketch):

- WebSearch added to the tool allowlist for those agents only.
- Each agent's persona file includes a "when to search" rule: cite the
  source in the output, or skip the search. No silent browsing.
- Tool budget guidance (target ≤ N searches per stage) to keep latency /
  cost bounded.

**Acceptance** (sketch):

- AC-WEBSEARCH-001a: Each affected agent file lists `WebSearch` in its
  tools and contains the cite-or-skip rule.
- AC-WEBSEARCH-001b: Output documents from those stages, when WebSearch
  was used, contain at least one citation block referencing the search.

---

### REQ-INTERACTIVE-001 — Decompose "agents should be more interactive"

**Source**: EF-013 (vague, needs decomposition)

**Trigger**: v0.1.4 dogfood probes this with a follow-up question.

**Behavior** (sketch):

- Before v0.1.5 scope is locked, ≥2 concrete REQs are derived from the
  dogfood signal. Candidates: clarifying-question pattern in
  requirements-analyst, staged confirmation in spec/plan stages, progress
  narration in builder.
- This REQ's acceptance is "decomposed and removed," not "implemented."

**Acceptance** (sketch):

- AC-INTERACTIVE-001a: This REQ is replaced in `srs-v0.1.5.md` by ≥2
  specific REQs before v0.1.5 implementation starts. If it isn't, v0.1.5
  ships without an "interactive" REQ.

---

### REQ-DOCS-001 — Troubleshooting note for third-party plugin hooks

**Source**: EF-003

**Trigger**: A user reports cryptic PreToolUse / PreToolWrite / Stop hook
errors that don't reference Forge file paths.

**Behavior** (sketch):

- Add a `## Troubleshooting third-party hooks` section to README or
  `docs/getting-feedback.md` showing how to identify the hook owner
  (`/plugin list`, grep `~/.claude/plugins/` for the hook script name).
- Note that Forge's only PreToolUse hook is `hooks/pre-tool-write.py`;
  any other PreToolUse warning is from another plugin.

**Acceptance** (sketch):

- AC-DOCS-001a: Section exists with the diagnostic command and the
  Forge-vs-third-party distinction.
- AC-DOCS-001b: Section is linked from the README's top-level "If
  something looks wrong" entry point.

---

## 3. Non-Goals (firm)

- Sprint planning / per-sprint review (EF-011)
- Brownfield multi-agent fan-out (EF-014)
- Anything from `srs-v0.1.4.md` §6

---

## 4. REQ → Source Traceability

| REQ                     | Source EF-ID(s)     | Category    |
| ----------------------- | ------------------- | ----------- |
| REQ-NEXTHINT-001        | EF-004              | bug         |
| REQ-PATHS-001           | EF-005              | bug         |
| REQ-LARGEDOC-001        | EF-006              | friction    |
| REQ-PATTERN-001         | EF-008              | bug         |
| REQ-SILENTSTATE-001     | EF-007 (+EF-002)    | bug         |
| REQ-DOCTOR-001          | EF-017              | bug         |
| REQ-LESSON-SOURCES-001  | EF-018              | bug         |
| REQ-SESSIONLOG-001      | EF-009, EF-015      | suggestion  |
| REQ-STAGEREFLECT-001    | EF-010              | suggestion  |
| REQ-WEBSEARCH-001       | EF-012              | suggestion  |
| REQ-INTERACTIVE-001     | EF-013              | friction    |
| REQ-DOCS-001            | EF-003              | bug (ext.)  |

(EF-007 promoted to REQ-SILENTSTATE-001 on 2026-05-24 after the tester's
`error_logs.jsonl` showed 28 silent state-read failures over 24 hours;
no longer pending re-verification.)

---

## 5. Open Questions

- **OQ-1** — Should REQ-PATHS-001 standardize on `04-spec` or
  `04-technical-spec`? Pick during plan; renaming has cascade effects
  through skills, gate checks, and existing test fixtures.
- **OQ-2** — Is `pattern.jsonl` worth fixing in v0.1.5 if skill-miner
  proposals aren't being consumed by anyone yet? Argument for: defining
  the schema now prevents drift. Argument against: empty bus is fine if
  nothing reads it. Decide once skill-miner's downstream use is clear.
- **OQ-3** — Should REQ-WEBSEARCH-001 apply to the planner stage too,
  or only the upstream research stages? The planner's job is structural,
  not research; cite-or-skip may not fit. Default: exclude planner.
- **OQ-4** — Does v0.1.5 wait for v0.1.4 dogfood to complete before
  locking scope, or can it start in parallel? Recommend: lock scope only
  after dogfood, so EF-013 decomposition and any new findings can land
  in the same SRS pass.
- **OQ-6** *(blocks REQ-LESSON-SOURCES-001 acceptance)* — **Which
  implicit signals are worth flagging, and at what threshold?** The
  five candidate producers in REQ-LESSON-SOURCES-001 are not equal
  cost/value. Decide per producer:
  - **Hook-error threshold**: N = 1 (any error)? N = 5 (a cluster)?
    N = 20+ (mass failure like the EF-002 case)? Lower N catches more
    but risks lesson churn from transient noise. Recommend N = 5 as a
    starting point — the EF-002 case would still fire (28 events), but
    a one-off hook hiccup wouldn't.
  - **Repeated `PreToolUse` block**: M = 2? M = 3? Recommend M = 2 —
    two consecutive blocks on similar writes is already a clear policy
    mismatch.
  - **Bash heredoc after Write block**: binary signal — fires on first
    occurrence within the same minute. No threshold.
  - **Gate pass→wedge within session**: binary signal — fires on first
    occurrence. No threshold.
  - **State-read regression**: binary signal — fires on first
    occurrence. No threshold.
  Default to enabling all five producers in v0.1.5 with the suggested
  thresholds; revisit cutoffs after v0.1.5 dogfood shows real false-
  positive rates.
- **OQ-5** *(blocks REQ-NEXTHINT-001)* — **Is stage 2 (product/UX)
  mandatory or advisory?** Current code says advisory:
  `skills/forge-arch/SKILL.md` step 3 warns-but-doesn't-block on missing
  `prd.md`, and `_state_lib.py:advance_stage` only emits a stderr
  warning when jumping stages. But EF-004's framing ("next step *should*
  be product/UX") implies mandatory. Source: EF-016. Two branches:
  - **(A) Mandatory** — `forge-arch` pre-flight exits 2 if `prd.md`
    missing; `advance_stage` rejects `to > old + 1` unless invoked from
    `/forge:force-advance`; REQ-NEXTHINT-001 reads as written.
  - **(B) Advisory** — keep current code; rewrite REQ-NEXTHINT-001 so
    the hint after SRS offers both paths ("`/forge:product` for UX work,
    or `/forge:arch` to skip to architecture") and explains the
    trade-off.
  Decide before REQ-NEXTHINT-001 is finalized. If (A), add a new
  REQ-GATE-ENTRY-001 covering pre-flight blocks for all skippable stages
  (not just stage 2 — stages 4–11 have the same shape).

---

## 6. Acceptance Definition (placeholder)

To be written when v0.1.4 dogfood is complete and the full v0.1.5 scope
is known. At minimum will include:

- Every `fix-v0.1.5` REQ above either implemented with AC met, or
  explicitly deferred to v0.1.6 with rationale.
- All v0.1.4 dogfood `fix-v0.1.5` findings folded into this SRS.
- CHANGELOG `[0.1.5]` entry + version bump.
- Forge-on-Forge: the v0.1.5 pipeline run inside this repo passes its
  own gates (continued meta-validation).
