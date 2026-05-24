# SRS — Forge v0.1.4 (delta)

> Delta requirements for the v0.1.4 release. Composes with the v0.1.0 SRS at
> `build/01-srs/srs.md` and the v0.1.3 delta at `build/01-srs/srs-v0.1.3.md`.
> All prior REQs remain in force; this file adds new requirements only.
>
> **Theme**: Pay the debt. v0.1.3 shipped with the external-user dogfood
> explicitly deferred (D-V13-11). v0.1.4 exists to discharge that deferral.
> Its scope is intentionally narrow: get real users in front of Forge,
> record what they find, do *not* try to fix everything in the same release.
>
> **SRS posture**: Two-phase. The acceptance gates and intake infrastructure
> are fully specified now. The findings list, friction bucket, and tester
> notes are stubs labeled `TBD (post-dogfood)` and get filled in-place when
> the testers report back. The SRS is the single source of truth across
> both phases — do not split it.

---

## 1. Scope

**In scope for v0.1.4:**

- External-user dogfood: 2 testers (1 disciplined-engineer archetype + 1
  vibes-coder archetype) complete the 30-minute test path from
  `docs/getting-feedback.md` and report back.
- Feedback intake infrastructure: GitHub issue template, findings doc
  location, dogfood log artifact.
- Tester recruitment record: who tested, when, archetype, mode of report.
- Triage of all findings into one of four buckets — hotfix-now,
  fix-v0.1.5, defer-out-of-scope, no-action — with rationale per item.
- README traceability screenshot (deferred from v0.1.3 §9.5; the screenshot
  itself depends on having a real dogfood pipeline to capture).
- Acceptance Definition (§9) re-locked with **no waiver path** for the
  dogfood gate, per D-V13-11.
- CHANGELOG + version bump.

**Out of scope for v0.1.4 (deferred by explicit decision):**

- **Fixing friction items found in dogfood.** The decision (2026-05-20) is
  that v0.1.4 *documents only*. Actual fixes flow into v0.1.5. This avoids
  acceptance becoming a moving target as new findings arrive, and keeps
  the dogfood from quietly turning into a 3-month feature release.
- New pipeline stages — never (the 12 are fixed).
- Background daemons (Observer, Dreamer, Health, Skill-Miner) — v0.2.
- Multi-agent orchestration — v0.2.
- Cross-tool orchestration (Codex CLI, Gemini CLI) — v0.3+.
- Windows support — v0.2 at earliest.
- Hook-error log rotation — v0.2 (paired with bus rotation).
- Generalizing `suggest_only` to other profiles (v0.1.3 OQ-4) — revisit
  *after* dogfood says it matters.

**Exception carve-out — "Forge install is broken" hotfix path:**

If dogfood surfaces a defect that makes the install or first-run path
unusable (e.g., plugin doesn't load on a clean machine, `/forge:init`
crashes, gate runner hangs), it becomes a v0.1.3.1 patch in a separate
SRS — *not* a v0.1.4 fix. v0.1.4 stays document-only by construction.
This carve-out is for genuine install-blockers, not for "I found the
UX rough" friction. See REQ-DOGFOOD-005 for the trigger.

**Forward-compatibility:**

The `build/06-evaluation/v0.1.4-dogfood-findings.md` schema (REQ-FEEDBACK-002)
is designed to be reusable for v0.1.5+ dogfood rounds. The four-bucket
triage taxonomy (REQ-TRIAGE-001) becomes the standard intake taxonomy
going forward.

---

## 2. Functional Requirements

### Family REQ-DOGFOOD: External-User Dogfood

#### REQ-DOGFOOD-001 — Two external testers complete the 30-minute path

**Trigger**: v0.1.4 acceptance review.

**Maps to**: T-200

**Behavior**:

- Two external testers (neither is the project author) each install Forge
  from the published marketplace, follow the 8-step path in
  `docs/getting-feedback.md` §"The 30-minute test path", and report back
  in any of the three modes (copy-paste log / GitHub issue / debrief call).
- Tester 1 matches the **disciplined-engineer** archetype: writes specs,
  cares about traceability.
- Tester 2 matches the **vibes-coder** archetype: treats Claude Code as
  "just write me the code".
- Both testers receive the drop-in message from `docs/getting-feedback.md`
  §"The drop-in message" verbatim (or a faithful adaptation), so framing
  is consistent across testers.

**Acceptance**:

- **AC-DOGFOOD-001a**: Two distinct testers recorded in the recruitment
  log (REQ-DOGFOOD-002) with archetype, contact channel, date contacted,
  date completed. Author's own runs do not count.
- **AC-DOGFOOD-001b**: At least one tester encountered a gate failure
  during their session — i.e., the gate UX (`/forge:why`, `/forge:doctor`,
  optionally `/forge:force-advance`) was exercised. If neither tester hit
  a gate naturally, the testing instructions are amended for tester 2 to
  ensure exposure.
- **AC-DOGFOOD-001c**: At least one tester completed steps 1 through 8
  (install through uninstall) without dropping out mid-session. The other
  may have stopped earlier; the drop-out point is itself recorded as a
  finding.

---

#### REQ-DOGFOOD-002 — Recruitment + completion log

**Trigger**: Each tester is contacted, accepts, or completes/declines.

**Maps to**: T-200

**Behavior**:

- A single file at `build/06-evaluation/v0.1.4-dogfood-log.md` records
  per-tester rows: handle (or alias if private), archetype, contact date,
  consent confirmed (Y/N), session date, completion status
  (completed / partial / declined / no-show), report mode used.
- No PII beyond what the tester is comfortable having recorded. Aliases
  are acceptable. The author is responsible for keeping the underlying
  contact details out of the repo.
- Declined / no-show rows count toward effort but not toward AC.

**Acceptance**:

- **AC-DOGFOOD-002a**: Log file exists at the path above with at minimum
  two rows in `completed` status (matching AC-DOGFOOD-001a).
- **AC-DOGFOOD-002b**: Schema is documented at the top of the file so
  future dogfood rounds can append without re-inventing the columns.

---

#### REQ-DOGFOOD-003 — Findings doc captures everything the testers said

**Trigger**: Tester finishes the 30-minute path and reports back.

**Maps to**: T-201

**Behavior**:

- All findings are aggregated into `build/06-evaluation/v0.1.4-dogfood-findings.md`.
- Each finding is one bulleted entry with: source (tester alias), raw
  quote (verbatim if written; paraphrase if from a call, marked as such),
  category (bug / friction / confusion / suggestion / out-of-scope),
  and triage bucket from REQ-TRIAGE-001.
- Nothing is silently dropped. If a finding is deemed out-of-scope or
  no-action, the rationale is recorded, not the absence.
- The author's editorial commentary is permitted but visually distinct
  (indented under the quote, prefixed `author:`), so the tester's voice
  is preserved.

**Acceptance**:

- **AC-DOGFOOD-003a**: Findings doc exists with N≥1 finding per
  completed tester (zero findings means the test was not adversarial
  enough; revisit framing).
- **AC-DOGFOOD-003b**: Every finding has a category and a triage bucket
  assigned.
- **AC-DOGFOOD-003c**: Verbatim quotes are visually distinguishable from
  paraphrase (e.g., `> quoted text` vs `(paraphrased)` tag).

---

#### REQ-DOGFOOD-004 — Lessons captured from dogfood

**Trigger**: A finding represents a pattern the author should not repeat
or that future Claude sessions should know about.

**Maps to**: T-201

**Behavior**:

- Anything from the findings doc that is a pattern (not a one-off bug) is
  promoted to `tasks/lessons.md` as a `dogfood-v0.1.4`-tagged lesson with
  the standard format (Trigger / Rule / Why / Tags).
- Lessons are captured *before* any code fix is proposed — capture
  precedes correction, per CLAUDE.md "Capture lessons immediately".

**Acceptance**:

- **AC-DOGFOOD-004a**: `tasks/lessons.md` has ≥1 entry with the
  `dogfood-v0.1.4` tag.
- **AC-DOGFOOD-004b**: Each such lesson is cross-referenced from at least
  one finding in `v0.1.4-dogfood-findings.md` (so the chain
  finding → lesson is auditable).

---

#### REQ-DOGFOOD-005 — Install-blocker triggers v0.1.3.1, not v0.1.4

**Trigger**: A tester reports that install / `/forge:init` / first
gate-check is broken in a way that prevents the 30-minute path from
completing on a clean machine.

**Maps to**: T-200 (process), out-of-band code change

**Behavior**:

- The finding is logged as category `bug` and triage bucket `hotfix-now`.
- The author cuts a v0.1.3.1 hotfix in a separate SRS
  (`build/01-srs/srs-v0.1.3.1.md`), shipped before v0.1.4 testing continues.
- v0.1.4 itself remains document-only; the hotfix is not folded into v0.1.4.

**Rationale**: Keeps v0.1.4's "document only" rule honest while
acknowledging that the user-facing path being broken is a different
class of problem than friction.

**Acceptance**:

- **AC-DOGFOOD-005a**: If `hotfix-now` items exist in the findings doc,
  the triage section explicitly references the v0.1.3.1 SRS by path. If
  none exist, the section says so.

---

### Family REQ-FEEDBACK: Intake Infrastructure

#### REQ-FEEDBACK-001 — GitHub issue template

**Trigger**: A tester opts for Mode 2 reporting (GitHub issues) from
`docs/getting-feedback.md`.

**Maps to**: T-202

**Behavior**:

- A file exists at `.github/ISSUE_TEMPLATE/forge-feedback.md` matching
  the template shown in `docs/getting-feedback.md` §"Mode 2: GitHub
  issues" (verbatim or with minor formatting adjustments).
- GitHub renders it as a selectable issue template when a tester opens
  an issue in the repo.
- The template includes: what I was trying to do / what Forge did / what
  I expected / `/forge:doctor` output / hook errors / severity checkbox.

**Acceptance**:

- **AC-FEEDBACK-001a**: File exists at the path above with all six
  sections from the docs template.
- **AC-FEEDBACK-001b**: The template's front matter includes `name`,
  `about`, `labels` (at least `feedback,v0.1.4`) so issues are
  filterable.

---

#### REQ-FEEDBACK-002 — Findings + log schema documented

**Trigger**: First use of `v0.1.4-dogfood-findings.md` and
`v0.1.4-dogfood-log.md`.

**Maps to**: T-202

**Behavior**:

- Each file begins with a `## Schema` section describing its columns /
  bullet structure so a future Claude session can append without
  inventing format.
- Schema lives in the file itself, not in a separate spec, so the
  document is self-describing.

**Acceptance**:

- **AC-FEEDBACK-002a**: Both files have a `## Schema` section at the
  top before any data.
- **AC-FEEDBACK-002b**: A second dogfood round (real or simulated) can
  append to either file using only the in-file schema, no other context.

---

### Family REQ-TRIAGE: Findings Triage

#### REQ-TRIAGE-001 — Four-bucket triage taxonomy

**Trigger**: A finding from `v0.1.4-dogfood-findings.md` needs a
disposition.

**Maps to**: T-201

**Behavior**:

- Every finding lands in exactly one of four buckets:
  - **hotfix-now** — install-blocker; cut v0.1.3.1 (REQ-DOGFOOD-005)
  - **fix-v0.1.5** — actionable bug or friction; queued for next release
  - **defer-out-of-scope** — recognized but explicitly not planned (e.g.,
    Windows, web UI, agent teams)
  - **no-action** — design disagreement or noise; documented and closed
- The bucket assignment is the author's call; the rationale (1–3
  sentences) is recorded in the findings doc inline with the finding.
- This taxonomy becomes the standard for v0.1.5+ dogfood rounds.

**Acceptance**:

- **AC-TRIAGE-001a**: No finding lacks a bucket.
- **AC-TRIAGE-001b**: The findings doc includes a tally section
  ("hotfix: 0, v0.1.5: 7, defer: 2, no-action: 1") so the shape of
  feedback is visible at a glance.
- **AC-TRIAGE-001c**: `fix-v0.1.5` items are mirrored into a stub
  `build/01-srs/srs-v0.1.5.md` (or equivalent backlog file) so they
  don't get lost between releases.

---

#### REQ-TRIAGE-002 — Triage is not a fix

**Trigger**: Author is tempted to fix a finding inside v0.1.4.

**Maps to**: (process)

**Behavior**:

- Only `hotfix-now` items (REQ-DOGFOOD-005) get a code change in the
  v0.1.4 window, and that change ships as v0.1.3.1, not as part of
  v0.1.4.
- No `fix-v0.1.5` item gets code in v0.1.4. If a fix feels easy and
  tempting, it still waits.
- Rationale: The acceptance bar for v0.1.4 must be writable *before*
  the testers run. Letting fixes leak in makes the bar move as findings
  arrive.

**Acceptance**:

- **AC-TRIAGE-002a**: `git log v0.1.3..v0.1.4` shows commits only for:
  documentation, the findings/log/lessons files, the issue template,
  the README screenshot, the v0.1.4 SRS+CHANGELOG+version. No
  hooks/scripts/skills/agents source changes.
- **AC-TRIAGE-002b**: If a hotfix is required, it appears on the
  `v0.1.3.1` tag, not the v0.1.4 tag.

---

### Family REQ-TRACE-SHOT: README Traceability Screenshot

#### REQ-TRACE-SHOT-001 — Traceability screenshot in README

**Trigger**: v0.1.4 release prep.

**Maps to**: T-203

**Behavior**:

- README has at least one screenshot (PNG, ≤ 250 KB, alt text required)
  showing the REQ-ID → task → commit → test chain on a real pipeline.
- The pipeline shown can be either Forge-on-Forge (this repo) or one of
  the dogfood testers' pipelines (with their permission).
- The screenshot lives at `assets/readme/traceability-v0.1.4.png` and
  is referenced from the README's existing traceability section.

**Acceptance**:

- **AC-TRACE-SHOT-001a**: Image file exists at the path above and is
  embedded in `README.md` with alt text.
- **AC-TRACE-SHOT-001b**: The chain in the screenshot is verifiable —
  i.e., a reader could open this repo (or the dogfood pipeline if
  external) and find the same REQ → task → commit linkage.

---

### Family REQ-FINDINGS (post-dogfood — `TBD`)

> This family's contents are **stubs**. They get filled in *after* the
> dogfood runs. Until then, this section exists as a placeholder so the
> findings doc has a home in the SRS even though its REQ-IDs are not yet
> defined.

#### REQ-FINDINGS-001 — `TBD (post-dogfood)`

**Trigger**: TBD — populated once findings exist.

**Maps to**: TBD

**Behavior**: TBD. Will enumerate the friction items the testers raised
that are scoped to v0.1.5. Each gets a REQ-FINDINGS-NNN ID at that
time, with full acceptance criteria, and is also reflected in
`srs-v0.1.5.md`.

**Acceptance**: TBD. Per the v0.1.5 SRS, not v0.1.4's.

---

## 3. Non-Functional Requirements

- **NFR-DOGFOOD-001** — Each tester's 30-minute path is genuinely
  bounded. If the test session exceeds 60 minutes, the author intervenes
  (offers an escape hatch / stops the session) rather than letting the
  tester grind through. Long sessions inflate signal with frustration
  artifacts and make findings hard to weigh.
- **NFR-DOGFOOD-002** — No tester is asked to read source code,
  CLAUDE.md, the SRS, or the task DAG before testing. Documentation
  gaps surface only if testers don't have docs to fall back on.
- **NFR-FEEDBACK-001** — The findings doc (`v0.1.4-dogfood-findings.md`)
  is updated within 24 hours of each tester's report-back, so quotes
  don't drift in the author's memory.
- **NFR-TRIAGE-001** — The four-bucket taxonomy (REQ-TRIAGE-001) is
  fixed for v0.1.4. Inventing new buckets mid-triage defeats the point.
  New buckets can be proposed for v0.1.5+ via the normal SRS update flow.

---

## 4. Gate Additions

None. v0.1.4 is documentation + acceptance discipline; it does not add
new automated gates. The discipline lives in §9 (acceptance definition)
and is checked manually, not by `check-gate.py`.

The v0.1.5 SRS may add a `G-DOGFOOD-001` (cross-stage gate: "dogfood log
shows ≥ N testers for this release") once the cadence is proven. v0.1.4
does not specify that gate — premature formalization.

---

## 5. New Lesson Tags

These compose with v0.1.0 and v0.1.3 lesson tags:

| Tag                 | Producer              | Trigger                                                  |
| ------------------- | --------------------- | -------------------------------------------------------- |
| `dogfood-v0.1.4`    | Author (manual)       | A dogfood finding is a pattern, not a one-off            |
| `external-friction` | Author (manual)       | Specifically friction (not bug) raised by external user  |

(`force-advance`, `unexpected-exit-2`, `timeout` from v0.1.3 remain in
force unchanged.)

---

## 6. Non-Goals (explicit)

- Fixing v0.1.4 friction items — v0.1.5 by the document-only decision
- Background daemons — v0.2
- Multi-agent orchestration — v0.2
- New pipeline stages — never
- Windows support — v0.2 at earliest
- Hook-error log rotation — v0.2
- A `/forge:dogfood` automation skill — too ambitious; manual process for
  v0.1.4 keeps the loop tight. Revisit at v0.2+ once we've run dogfood
  more than once.
- Anonymous telemetry — out of scope indefinitely; feedback is solicited
  and explicit, not collected.

---

## 7. REQ → Task Traceability

| REQ                       | Tasks        |
| ------------------------- | ------------ |
| REQ-DOGFOOD-001..005      | T-200, T-201 |
| REQ-FEEDBACK-001..002     | T-202        |
| REQ-TRIAGE-001..002       | T-201        |
| REQ-TRACE-SHOT-001        | T-203        |
| REQ-FINDINGS-001 (TBD)    | v0.1.5       |

Forward mapping populated in `build/04-plan/task-dag-v0.1.4.md` when the
plan stage runs.

---

## 8. Open Questions

- **OQ-1** — Should the recruitment log be in the repo at all, even with
  aliases? Argument for: discoverable, auditable. Argument against: any
  PII risk lives next to the code. **Current proposal**: Yes, aliases
  only, and the file is mentioned in `docs/getting-feedback.md` so
  testers know what's logged.
- **OQ-2** — If only one tester completes, can v0.1.4 still ship with a
  documented "second tester slot deferred to v0.1.5 retro"? **Current
  proposal**: No. That's the exact failure mode D-V13-11 warned against.
  v0.1.4 holds until N=2.
- **OQ-3** — Should the v0.1.3.1 hotfix carve-out (REQ-DOGFOOD-005) also
  apply to severe friction (not just install-blockers) if it's blocking
  enough? **Current proposal**: No. Strict definition: hotfix = the
  30-minute path cannot complete. Anything weaker waits for v0.1.5.
  Re-evaluate if dogfood proves the line is too narrow.
- **OQ-4** — Should the findings doc be readable by the testers
  themselves after the fact (i.e., we share it back)? **Current
  proposal**: Yes — closes the "thank them concretely" loop from
  `docs/getting-feedback.md` §"What to do with the feedback". Tester
  reviews after publication, not before.

---

## 9. Acceptance Definition for v0.1.4 Release

All of the following must be true before tagging v0.1.4. There is **no
waiver path** for items 1–4 — D-V13-11 made this the trade-off for
shipping v0.1.3 early.

1. **N=2 external testers completed the 30-minute path** (REQ-DOGFOOD-001),
   split 1 disciplined-engineer + 1 vibes-coder, recorded in
   `build/06-evaluation/v0.1.4-dogfood-log.md`.
2. **Findings doc exists** at `build/06-evaluation/v0.1.4-dogfood-findings.md`
   with every finding categorized and triaged into one of the four buckets
   (REQ-DOGFOOD-003, REQ-TRIAGE-001).
3. **At least one tester encountered a gate failure** during the session,
   exercising `/forge:why` / `/forge:doctor` / `/forge:force-advance`
   (REQ-DOGFOOD-001b).
4. **≥1 lesson tagged `dogfood-v0.1.4`** added to `tasks/lessons.md`
   (REQ-DOGFOOD-004).
5. **GitHub issue template** exists at
   `.github/ISSUE_TEMPLATE/forge-feedback.md` (REQ-FEEDBACK-001).
6. **README has a traceability screenshot** at
   `assets/readme/traceability-v0.1.4.png`, embedded with alt text
   (REQ-TRACE-SHOT-001).
7. **No code changes leaked into v0.1.4** — diff `v0.1.3..v0.1.4` touches
   docs, findings, log, lessons, README, issue template, version, and
   CHANGELOG only (REQ-TRIAGE-002, AC-TRIAGE-002a).
8. **Stub `srs-v0.1.5.md` exists** with the `fix-v0.1.5` items from
   triage mirrored in (AC-TRIAGE-001c). Empty `fix-v0.1.5` triage is
   acceptable; absent file is not.
9. **CHANGELOG.md** has a `[0.1.4]` entry summarizing the dogfood
   round + intake infrastructure.
10. **`.claude-plugin/plugin.json` version** bumped to `0.1.4`.

The acceptance definition was deliberately written *before* the testers
ran. Items 1–6 are objective and defined; items 7–10 are mechanical.
This is the discharge of D-V13-11.

---

## 10. Two-Phase SRS Marker

The following sections are populated in **Phase 2** (post-dogfood):

- **REQ-FINDINGS-NNN** entries (under §2 Family REQ-FINDINGS) — created
  per-finding once testers report back. Each carries its own AC and is
  also mirrored into `srs-v0.1.5.md` for actual implementation.
- **§7 Traceability table** rows for REQ-FINDINGS-* — added when those
  REQs are written.
- **§8 Open Questions** may grow with dogfood-specific OQs.

Phase 1 (this writing, 2026-05-20) defines everything above and freezes
the §9 acceptance bar. Phase 2 fills in REQ-FINDINGS-* and updates
traceability; it must not loosen §9.
