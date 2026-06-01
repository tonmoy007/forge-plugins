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

**Source**: EF-004 (and EF-016; OQ-5 resolved 2026-06-01 → mandatory)

**Trigger**: A `/forge:*` skill or `state-manager` advances stage and
emits a next-step hint to the user.

**Status**: OQ-5 resolved 2026-06-01 — Stage 2 is **mandatory**. REQ
locked to the mandatory-branch wording. Companion REQ-GATE-ENTRY-001
covers the pre-flight block.

**Behavior**:

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

**Resolved**: OQ-1 locked 2026-06-01 — canonical name is **`04-spec`**
(matches `forge:init` scaffold and `check-gate.py` expectations).
`skills/forge-spec/SKILL.md` step 4 (writes to `pipeline/04-technical-spec/`)
must change to `pipeline/04-spec/`. Any v0.1.3.x projects with a
populated `04-technical-spec/` directory get a one-time migration note
in the v0.1.5 CHANGELOG.

---

### REQ-GATE-ENTRY-001 — Pre-flight entry blocks for skippable stages

**Source**: OQ-5 resolved → mandatory branch; companion to REQ-NEXTHINT-001.

**Trigger**: A stage skill is invoked while its prior-stage prerequisite
artifact is missing (e.g. `/forge:arch` invoked without `prd.md`).

**Behavior** (sketch):

- Every stage skill that depends on a prior stage's primary artifact
  runs a pre-flight check before adopting its persona. If the required
  artifact is missing, the skill exits 2 with a one-line message naming
  the missing file and the prior-stage skill to run instead.
- Applies to stages 2–11. Stage 1 has no prerequisite; stage 12 has its
  own release gate. Per-stage prerequisite map lives alongside the
  stage-order table that powers REQ-NEXTHINT-001 (single source of truth).
- `scripts/_state_lib.py:advance_stage` **rejects** `to > old + 1`
  unless invoked from `/forge:force-advance`. The current warn-but-
  don't-block behavior is removed. `force-advance.py` becomes the only
  documented path for intentional skips.

**Acceptance** (sketch):

- AC-GATE-ENTRY-001a: For each stage 2–11, a synthetic invocation with
  the prior-stage artifact missing produces exit 2 and a message
  naming the missing file. One test per stage.
- AC-GATE-ENTRY-001b: `state-manager.py advance --to N` where N > current+1
  exits non-zero unless `--force` is passed. `/forge:force-advance` is
  the user-facing path to `--force`.
- AC-GATE-ENTRY-001c: The pre-flight check and the next-step hint
  derive from the same stage-order table (no duplicated stage logic).

**Relation to other REQs**: Hardens [[req-nexthint-001]]'s mandatory
contract; complements [[req-doctor-001]] / [[req-silentstate-001]] by
preventing the surface-healthy-substance-inert antipattern at the
*entry* gate (those REQs cover the *exit* gate and runtime state).

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

**Thresholds**: All 5 producers enabled per OQ-6 resolution (2026-06-01).
Producer (1) hook-error cluster N=5; producer (2) repeated `PreToolUse`
block M=2; producers (3) (4) (5) binary on first occurrence.

---

### REQ-BUILDBATCH-001 — `/forge:build` supports milestone-scoped batches

**Source**: EF-020 (OQ-8 resolved 2026-06-01 → option B)

**Trigger**: User wants to drive multiple tasks of a milestone without
re-issuing `/forge:build` per task.

**Status**: OQ-8 resolved 2026-06-01 — **option B (`--milestone N`)**.
`--all` deferred to v0.1.6+; revisit only if v0.1.5 dogfood shows
milestone batches insufficient and context-degradation isn't a problem.

**Behavior**:

- `/forge:build --milestone N` walks every T-ID under
  `## Milestone N:` in `pipeline/05-plan/task-dag.md` in dependency
  order. Each task still: runs the Builder persona, runs tests, commits
  with `feat(T-XXX):` per task, marks done in `progress.md`. No batched
  commits, no batched tests.
- On the **first** task failure (test red, gate red, or hook block),
  the batch **pauses**, prints which T-ID failed and why, leaves the
  preceding task commits in place, and exits non-zero. User resumes
  with `/forge:build` (single task) or `/forge:build --milestone N
  --resume` (continues from the failed T-ID after the user has fixed
  it).
- Context discipline: the skill warns *"large batch — N tasks, consider
  splitting"* when `N > 10` (threshold revisited per OQ-8). Default
  batch limit is the milestone size; `--all` is intentionally not
  offered in v0.1.5.
- `/forge:build` (no flag) keeps current single-task behavior. The
  default footer is updated to mention `--milestone` as an option.

**Acceptance** (sketch):

- AC-BUILDBATCH-001a: A synthetic project with a 3-task milestone
  invoked as `/forge:build --milestone 1` produces exactly 3 commits,
  each with the corresponding T-ID prefix, in dependency order.
- AC-BUILDBATCH-001b: Same project with one task scripted to fail —
  the failure halts the batch, leaves prior commits intact, and
  `--resume` continues correctly after the failure is patched.
- AC-BUILDBATCH-001c: Single-task invocation (`/forge:build` no flag)
  produces identical output to v0.1.4 — backward compatible.

**Relation to other REQs**: Composes with [[req-stagereflect-001]]
(per-stage reflection) — a milestone-batch run gives the per-stage
reflector richer data to summarize. Composes with [[req-silentstate-001]] /
[[req-doctor-001]] — if state surfaces stop being silent, batch failure
diagnostics get much better.

---

### REQ-GATESTUB-001 — Gate criteria pointing at unimplemented scripts fail loud

**Source**: EF-019 (OQ-7 resolved 2026-06-01 → both)

**Trigger**: `check-gate.py` evaluates a `script_returns_zero` criterion
whose `script:` path does not exist in the plugin.

**Status**: OQ-7 resolved 2026-06-01 — **both branches** in scope:
fail-loud on missing scripts **and** implement the 15 missing scripts
this cycle. v0.1.5 ships both halves together; partial delivery is not
acceptance.

**Behavior** (sketch, fail-loud half):

- An unimplemented check script is treated as a configuration bug, not
  a soft pass. `check-gate.py` reports the criterion as `inconclusive`
  (not `False`-with-warning) and the gate summary surfaces a top-line
  *"⚠️ N criteria unimplemented — gate result is provisional"* banner.
- `severity: warning` for a missing-script criterion is **promoted to
  blocker** at evaluation time. Rationale: a stub gate that silently
  warns hides the same antipattern family as `/forge:doctor` reporting
  healthy on a wedged stage. Lessons learned (EF-017, EF-007).
- Audit: at REQ-GATESTUB-001 acceptance time, enumerate every
  `script_returns_zero` criterion in `references/gate-criteria.md`,
  confirm each referenced script exists, file follow-up REQs for any
  that don't.

**Acceptance** (sketch):

- AC-GATESTUB-001a: A synthetic gate criterion pointing at a
  nonexistent script produces `inconclusive` output and exits the gate
  with non-zero status, regardless of declared severity.
- AC-GATESTUB-001b: All 15 missing scripts ship in v0.1.5 — concretely:
  `check_srs_acceptance.py`, `traceability-check.py`, `spec-coverage.py`,
  `check_dag_completeness.py`, `check_dag_completion.py`, `token-audit.py`,
  `check_coverage.py`, `check_todos.py`, `check_progress_sync.py`,
  `check_nfr_coverage.py`, `check_open_bugs.py`, `check_health.py`,
  `check_hotfix_tests.py`, `check_git_tag.py`, `some_check.py`
  (or the criterion is removed/rewritten with explicit justification).
  No `script_returns_zero` criterion in `references/gate-criteria.md`
  may reference a missing script at v0.1.5 tag time.
- AC-GATESTUB-001c: `/forge:doctor` and `/forge:status` surface the
  *"N criteria unimplemented"* banner so a wedged pipeline cannot be
  rationalized as "warnings only."

**Relation to antipattern family**: Fourth instance of the surface-
healthy / substance-inert family. Sister REQs: REQ-SILENTSTATE-001
(hook layer), REQ-DOCTOR-001 (doctor layer), REQ-LESSON-SOURCES-001
(lesson capture). REQ-GATESTUB-001 covers the **gate-config layer**.

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
spec) needs current best-practice grounding. Planner excluded per OQ-3.

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
| REQ-GATE-ENTRY-001      | OQ-5 → EF-016       | bug         |
| REQ-PATHS-001           | EF-005              | bug         |
| REQ-LARGEDOC-001        | EF-006              | friction    |
| REQ-PATTERN-001         | EF-008              | bug         |
| REQ-SILENTSTATE-001     | EF-007 (+EF-002)    | bug         |
| REQ-DOCTOR-001          | EF-017              | bug         |
| REQ-LESSON-SOURCES-001  | EF-018              | bug         |
| REQ-GATESTUB-001        | EF-019              | bug         |
| REQ-BUILDBATCH-001      | EF-020              | friction    |
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

- **OQ-1** *(resolved 2026-06-01 → `04-spec`)* — Should REQ-PATHS-001
  standardize on `04-spec` or `04-technical-spec`? **Decision**:
  `04-spec` is canonical (matches `forge:init` scaffold and
  `check-gate.py`). `skills/forge-spec/SKILL.md` step 4 needs the path
  changed in v0.1.5. CHANGELOG to include a one-time migration note
  for v0.1.3.x projects with populated `04-technical-spec/` dirs.
- **OQ-2** *(resolved 2026-06-01 → yes, define schema now)* — Is
  `pattern.jsonl` worth fixing in v0.1.5 even without downstream
  consumers? **Decision**: yes. Define and populate the schema in
  v0.1.5 — prevents drift, lets the skill-miner ≥3-use trigger fire on
  synthetic test data, small effort relative to design-debt cost later.
  REQ-PATTERN-001 stays in scope.
- **OQ-3** *(resolved 2026-06-01 → exclude planner)* — Should
  REQ-WEBSEARCH-001 apply to the planner stage too? **Decision**:
  exclude planner. WebSearch enabled on SRS / product / architecture /
  spec only. Planner's job is structural; cite-or-skip doesn't fit and
  the tool budget is better spent upstream. Revisit if v0.1.6 dogfood
  shows planner agents want benchmarking data.
- **OQ-4** *(resolved 2026-06-01 → wait for dogfood)* — Does v0.1.5
  wait for v0.1.4 dogfood to complete before locking scope, or can it
  start in parallel? **Decision**: wait. EF-013 decomposition and any
  new findings land in the same SRS pass; tighter scope, slower cadence.
- **OQ-6** *(resolved 2026-06-01 → all 5 producers enabled with
  recommended thresholds)* — Which implicit lesson-capture signals are
  worth flagging, and at what threshold? **Decision**: enable all five
  producers in v0.1.5 with the thresholds below. Revisit cutoffs after
  v0.1.5 dogfood shows real false-positive rates.
  - **(1) Hook-error cluster** — fires when any single hook produces
    ≥ **5** errors in one session.
  - **(2) Repeated `PreToolUse` block** — fires when ≥ **2** consecutive
    blocks on similar Write paths in one session.
  - **(3) Bash heredoc after Write block** — binary; fires on first
    occurrence within the same minute.
  - **(4) Gate pass→wedge within session** — binary; fires on first
    occurrence.
  - **(5) State-read regression** (empty/default after prior successful
    read in same session) — binary; fires on first occurrence.
  AC-LESSON-SOURCES-001a covers one test per producer; AC-001c covers
  the clean-control zero-flag check.
- **OQ-5** *(resolved 2026-06-01 → mandatory)* — Is stage 2 (product/UX)
  mandatory or advisory? **Decision**: option (A) **mandatory**.
  `forge-arch` pre-flight exits 2 if `prd.md` missing; `advance_stage`
  rejects `to > old + 1` unless invoked from `/forge:force-advance`.
  REQ-NEXTHINT-001 locked to mandatory-branch wording. Companion
  **REQ-GATE-ENTRY-001** added to cover pre-flight blocks for all
  skippable stages 2–11 (same shape as stage 2). Source: EF-016.
- **OQ-7** *(resolved 2026-06-01 → both)* — Fail-loud on unimplemented
  check scripts, or implement the missing scripts first? **Decision**:
  option (C) **both**. v0.1.5 ships the fail-loud `check-gate.py`
  change **and** all 15 missing scripts together; partial delivery is
  not acceptance. Audit (run 2026-06-01) found only 1 of 16
  `script_returns_zero` scripts present; full list in AC-GATESTUB-001b.
  The pattern is the bug, not the individual scripts — addressing both
  layers in the same release. Source: EF-019.
- **OQ-8** *(resolved 2026-06-01 → option B; `--all` deferred)* —
  Per-task only, `--milestone N`, or also `--all`? **Decision**: option
  (B) — ship `--milestone N` with per-task commits/gates and
  pause-on-failure semantics (REQ-BUILDBATCH-001 as written). `--all`
  is **deferred to v0.1.6+** and revisited only if v0.1.5 dogfood shows
  milestone batches insufficient *and* context-degradation isn't a
  problem. Milestone is the planner's natural unit; unbounded batching
  invites context-degradation issues the project has no signal on yet.
  Source: EF-020.

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
