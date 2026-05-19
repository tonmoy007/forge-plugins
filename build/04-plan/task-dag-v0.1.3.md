# Task DAG — Forge v0.1.3

> 11 tasks across 4 milestones for the v0.1.3 patch release.
> Composes with `build/04-plan/task-dag.md` (v0.1.0). T-001..T-033 are v0.1.0
> tasks (shipped). T-034..T-099 reserved for future v0.1.x patches.
> T-038+ may also appear in v0.2 work — see `build/01-srs/srs-v0.2.md`.
>
> Format: `T-NNN [size] title — description`
> Size: S (small, ~30 min), M (medium, ~2 hr), L (large, ~half-day)
> Status: ✅ done | 🟡 partial | ⬜ todo

---

## Status Snapshot

| ID    | Title                              | Size | Status |
|-------|------------------------------------|------|--------|
| T-100 | Hook resilience wrapper            | M    | ✅ done |
| T-101 | `/forge:doctor`                    | M    | ✅ done |
| T-102 | `/forge:uninstall`                 | M    | ✅ done |
| T-103 | `/forge:init --dry-run` + manifest | S    | 🟡 partial |
| T-104 | Gate result formatter              | S    | ✅ done |
| T-105 | `/forge:force-advance`             | S    | ✅ done |
| T-106 | `/forge:why`                       | S    | ✅ done |
| T-107 | `script` project profile           | S    | 🟡 partial |
| T-108 | First-run round-trip test          | S    | ⬜ todo |
| T-109 | README rewrite                     | S    | ⬜ todo |
| T-110 | CHANGELOG + version bump           | S    | ⬜ todo |

**Estimated remaining**: ~3 days of focused work + 1 day for external-user dogfood
(non-negotiable per srs-v0.1.3 §9 item 4).

---

## Milestone M-V13-1: Resilience Foundation

The foundation everything else builds on. v0.1.0's hooks silently failed when
they threw; v0.1.3 makes them crash-safe by design.

### T-100 ✅ Hook resilience wrapper

- **Description**: Library wrapper for hook entry points. Top-level exception
  barrier (logs to `.forge/hook-errors.log`, exits 0), per-hook SIGALRM timeout
  (configurable via env), blocking hooks never block on internal error or
  timeout, non-blocking hooks suppress accidental `exit 2`.
- **Files**:
  - `scripts/_hook_runner.py` (new)
  - `hooks/{session-start,prompt-submit,pre-tool-write,post-tool-use,stop-reflect,subagent-stop,session-end}.py` (modified — add 2-line wrap)
  - `tests/unit/test_hook_runner.py` (new — 22 tests)
- **Done when**:
  - All AC-RES-001a through AC-RES-004d pass.
  - All 7 hooks call `run_hook(main, hook_name='<name>')` in their `if __name__ == '__main__'` block.
  - Existing 532-test suite still green after wrapping.
- **Depends on**: none
- **REQ-IDs**: REQ-RES-001, REQ-RES-002, REQ-RES-003, REQ-RES-004
- **Note**: The session-start.py example is in `hooks/session-start.py`. The
  other 6 hooks need the same 2-line diff (1 import + 1 entry-point line).
  Apply mechanically; no logic changes.

---

## Milestone M-V13-2: Self-Service Commands

Commands that let the user diagnose and recover without needing the author's
help. These absorb the support questions you'd otherwise answer one-by-one.

### T-101 ✅ `/forge:doctor`

- **Description**: Diagnostic skill that runs 13 deterministic checks across
  environment, plugin, project, and global state. Each failing check includes
  a literal fix command.
- **Files**:
  - `scripts/doctor.py` (new — ~400 LOC)
  - `skills/forge-doctor/SKILL.md` (new)
  - `tests/unit/test_doctor.py` (new — 27 tests)
- **Done when**:
  - AC-DIAG-001a through AC-DIAG-002c pass.
  - `/forge:doctor` runs in < 5s on a healthy project.
  - Output presents `Fix:` lines verbatim (skill instructs Claude not to paraphrase).
- **Depends on**: T-100 (the `hook_errors` check reads the log T-100 produces)
- **REQ-IDs**: REQ-DIAG-001, REQ-DIAG-002

### T-102 ✅ `/forge:uninstall`

- **Description**: Filesystem-state removal skill. Mandatory `--dry-run` preview
  before any destruction. `--keep-artifacts` preserves `pipeline/`.
  `--include-global` removes `~/.forge/` with separate confirmation. Idempotent.
- **Files**:
  - `scripts/uninstall.py` (new — ~250 LOC)
  - `skills/forge-uninstall/SKILL.md` (new)
  - `tests/unit/test_uninstall.py` (new — 20 tests)
- **Done when**:
  - AC-CLEAN-001a through AC-CLEAN-004b pass.
  - SKILL.md requires explicit dry-run before any removal.
  - Script output always ends with the two follow-up commands (`/plugin uninstall` + reinstall).
- **Depends on**: none
- **REQ-IDs**: REQ-CLEAN-001, REQ-CLEAN-002, REQ-CLEAN-003, REQ-CLEAN-004

### T-103 🟡 `/forge:init --dry-run` + manifest

- **Description**: Add `--dry-run` and `--manifest-only` modes to
  `init-pipeline.sh`. Update the skill to use manifest output to drive the
  gitignore prompt.
- **Files**:
  - `scripts/init-pipeline.sh` (rewritten — supports `--dry-run`, `--manifest-only`)
  - `skills/forge-init/SKILL.md` (update — add Steps 6-8 for dry-run + gitignore check)
- **Done when**:
  - AC-UX-001a through AC-UX-003b pass.
  - Manifest JSON parses correctly when used by the skill.
- **Depends on**: none
- **REQ-IDs**: REQ-UX-001, REQ-UX-002, REQ-UX-003
- **Status note**: `init-pipeline.sh` rewrite is complete. SKILL.md update is
  pending — I need to see the current `skills/forge-init/SKILL.md` to write
  a precise diff. Drop-in replacement is risky without context on existing
  behaviors.

---

## Milestone M-V13-3: Gate UX

Make gate failures self-explanatory. Today's failures emit JSON; v0.1.3 makes
that JSON readable, and offers an explicit override path so users don't feel
trapped.

### T-104 ✅ Gate result formatter

- **Description**: New script `format-gate-result.py` that consumes
  `check-gate.py` JSON and emits human-readable text with per-criterion fix
  hints. Three input modes (pipe, file, `--stage`); two output modes (text,
  `--json` enriched).
- **Files**:
  - `scripts/format-gate-result.py` (new — ~250 LOC including fix-hint table)
  - `tests/unit/test_format_gate_result.py` (new — 14 tests)
- **Done when**:
  - AC-GATE-001a through AC-GATE-002c pass.
  - Fix-hint table covers all 12 stages + 5 profile-specific gate families.
- **Depends on**: none (decoupled from check-gate.py — pure formatter)
- **REQ-IDs**: REQ-GATE-001, REQ-GATE-002

### T-105 ✅ `/forge:force-advance`

- **Description**: Skill + script that overrides a blocking gate, recording a
  lesson with the user's stated reason. Stage advances by 1; the blocker
  criteria themselves remain failed in subsequent gate runs (the override is
  per-advancement, not per-criterion).
- **Files**:
  - `scripts/force-advance.py` (new — ~150 LOC)
  - `skills/forge-force-advance/SKILL.md` (new)
  - `tests/unit/test_force_advance.py` (new — ~15 tests)
- **Done when**:
  - AC-GATE-003a through AC-GATE-003c pass.
  - `--reason` is required, ≥ 10 chars.
  - Lesson is recorded with tag `force-advance` and lists overridden blocker IDs.
- **Depends on**: T-104 (force-advance reads failure list from check-gate output)
- **REQ-IDs**: REQ-GATE-003
- **Note**: This is the most philosophically loaded task in v0.1.3 — see
  `docs/gate-philosophy.md` (T-109 deliverable) for the reasoning on why
  overrides are allowed at all. Without this command, gate blocking feels
  like jail. With it, gates become honest negotiations.

### T-106 ✅ `/forge:why`

- **Description**: Contextual help command. `/forge:why <gate-id>` explains a
  criterion. `/forge:why <lesson-tag>` shows recent lessons with that tag.
  `/forge:why <stage-N>` explains a stage. Bare `/forge:why` explains the
  current blocker(s).
- **Files**:
  - `scripts/why.py` (new — ~120 LOC)
  - `skills/forge-why/SKILL.md` (new)
  - `tests/unit/test_why.py` (new — ~12 tests)
- **Done when**:
  - AC-GATE-004a through AC-GATE-004c pass.
  - Resolves gate IDs via `references/gate-criteria.md` + the fix-hint table from T-104.
  - Resolves lesson tags via `.forge/lessons.yaml`.
- **Depends on**: T-104 (shares the fix-hint lookup module)
- **REQ-IDs**: REQ-GATE-004

---

## Milestone M-V13-4: Profile + Validation + Release

Catch the small-project audience with the `script` profile, prove the whole
release works end-to-end with one round-trip test, and ship.

### T-107 🟡 `script` project profile

- **Description**: New 6th profile for sub-500-LOC projects. Compresses
  effective stages from 12 to 4 (SRS-lite, build, eval, optional release).
  Adds `suggest_only: true` profile flag — `script` is never auto-assigned;
  it's prompted.
- **Files**:
  - `references/project-type-profiles.md` (update — add `script` section + new detection block + new `suggest_only` field)
  - `scripts/detect-project-type.py` (update — implement `total_loc_under`, `no_file_exists`, `file_count_under`, `language_subset` indicators + honor `suggest_only`)
  - `scripts/check-script-runnable.py` (new — used by G6-SCRIPT-001)
  - `scripts/check-script-has-tests.py` (new — used by G7-SCRIPT-001)
  - `tests/unit/test_detect_project_type.py` (update — add script-profile detection cases)
- **Done when**:
  - AC-PROF-001a, AC-PROF-001b, AC-PROF-002a, AC-PROF-002b pass.
  - Running `/forge:init` on a 200-line repo prompts the user with the `script` suggestion.
  - The check-script-* scripts return 0/1 deterministically.
- **Depends on**: none (independent of other v0.1.3 work)
- **REQ-IDs**: REQ-PROF-001, REQ-PROF-002
- **Status note**: Profile definition and detection-block YAML are complete
  (see `references/project-type-profiles-script-addition.md`). The
  `detect-project-type.py` modifications and the two check-script-* scripts
  are pending — they need the existing `detect-project-type.py` as a starting
  point.

### T-108 ⬜ First-run round-trip integration test

- **Description**: Shell-script integration test that simulates a new user's
  complete first-day experience: install → `/forge:doctor` (healthy) → `/forge:init --dry-run` → `/forge:init` → simulate a Stage 1 gate failure → `/forge:why G1-001` → `/forge:force-advance --reason "..."` → `/forge:uninstall --dry-run` → `/forge:uninstall --yes`.
- **Files**:
  - `tests/integration/test_v013_first_run.sh` (new)
  - `tests/fixtures/v013_first_run/` (new — minimal fixture project)
- **Done when**:
  - AC-TEST-001a, AC-TEST-001b pass.
  - Test exits 0 on a clean checkout.
  - Test captures stdout/stderr of each command and asserts on expected substrings.
- **Depends on**: T-101, T-102, T-103, T-104, T-105, T-106 (the commands it exercises)
- **REQ-IDs**: REQ-TEST-001

### T-109 ⬜ README rewrite

- **Description**: Rewrite the first 200 words of README.md to lead with
  discipline + traceability (not memory). Add a `docs/gate-philosophy.md`
  explaining when blockers should be overridden vs. resolved.
- **Files**:
  - `README.md` (rewrite intro + "What Forge Does" sections)
  - `docs/gate-philosophy.md` (new)
- **Done when**:
  - Intro doesn't claim "Claude forgets between sessions" (no longer true).
  - At least one animated GIF or screenshot showing REQ-ID traceability across stages.
  - Gate-philosophy doc covers: when to override, what gets recorded, how to revisit overridden gates.
- **Depends on**: none (paperwork; can run in parallel with T-105/T-106/T-108)
- **REQ-IDs**: — (no SRS requirement; release readiness)

### T-110 ⬜ CHANGELOG + version bump

- **Description**: CHANGELOG entry summarizing v0.1.3. Version bump in
  plugin.json. Git tag.
- **Files**:
  - `CHANGELOG.md` (add v0.1.3 section)
  - `.claude-plugin/plugin.json` (bump `version` to `0.1.3`)
- **Done when**:
  - All other v0.1.3 tasks marked ✅.
  - CHANGELOG follows the existing v0.1.0/v0.1.1/v0.1.2 format.
  - At least one external user has run the round-trip (srs-v0.1.3 §9 item 4) and notes are committed to `build/05-implementation/dogfood-notes-v0.1.3.md`.
- **Depends on**: T-100..T-109 all ✅; plus external-user dogfood ✅
- **REQ-IDs**: — (release ceremony)

---

## Critical Path

```
T-100 (foundation)
  └─→ T-101 (doctor; reads T-100's hook-errors.log)

T-104 (gate formatter — independent)
  ├─→ T-105 (force-advance)
  └─→ T-106 (why)

T-102 (uninstall — independent)
T-103 (init dry-run — independent)
T-107 (script profile — independent)

T-101, T-102, T-103, T-105, T-106 ─┐
                                    ├─→ T-108 (round-trip test)
                                    │
T-109 (README — runs in parallel) ──┤
                                    │
                                    └─→ External-user dogfood
                                                  │
                                                  └─→ T-110 (release)
```

**Critical path length**: T-100 → T-104 → T-105 → T-108 → dogfood → T-110 = 6 tasks (~3 days of work + dogfood time).

**Parallelizable**: After T-100 lands, T-102 / T-103 / T-104 / T-107 / T-109 can all run in parallel. T-101 needs T-100 first because the doctor's `check_hook_errors` reads the log T-100 produces; without T-100, that check is a no-op.

---

## Risk Register

| ID | Risk | Impact | Likelihood | Mitigation |
|----|------|--------|------------|------------|
| R-V13-1 | No external user found before release | **High** | **High** | Hold release until at least one non-author has run install → init → first-gate-failure → recovery. This is the single most important release criterion (srs-v0.1.3 §9.4). Block T-110 on this. |
| R-V13-2 | SIGALRM in hook_runner interferes with subprocess timeouts inside hooks | Low | Low | subprocess uses different mechanism (waitpid/selectors); SIGALRM still fires correctly and interrupts the outer hook, abandoning the subprocess. Tested in T-100. |
| R-V13-3 | `--dry-run` mode confuses users who expect init to actually run | Medium | Medium | Plan output ends with explicit "Re-run without --dry-run to apply." Skill instructs Claude to present this line verbatim. |
| R-V13-4 | `/forge:force-advance` becomes the easy way out, defeats gate purpose | Medium | Medium | Every override records a lesson surfaced in `/forge:retro` (Stage 12). High-frequency forced advancements on the same gate are a signal to revisit the gate criterion. Documented in `docs/gate-philosophy.md` (T-109). |
| R-V13-5 | `script` profile auto-detected on real projects, strips pipeline | Medium | Medium | `suggest_only: true` flag — `script` profile NEVER auto-assigns; user must confirm. Confidence threshold also raised to 0.75. |
| R-V13-6 | `hook-errors.log` grows unbounded | Low | Low | Detail capped at 1000 chars per record. Frequency expected to be low in practice. Rotation deferred to v0.2 alongside bus design. |
| R-V13-7 | External user finds a class of bug the test suite doesn't catch | **High** | **High** | This is expected and desired. Hold the v0.1.3 release another 1-2 days to fix whatever they find. The whole point of dogfood is to catch what unit tests can't. |
| R-V13-8 | T-103 SKILL.md merge conflicts with author's local changes | Low | Medium | Provide the SKILL.md as a clear additive diff (Steps 6-8 added), not a wholesale replacement. |
| R-V13-9 | `script` profile detection requires more `detect-project-type.py` refactoring than estimated | Medium | Medium | T-107 may slip from S to M. Acceptable; not on the critical path. If it slips significantly, defer to v0.1.4 and ship the rest of v0.1.3. |

---

## Out of Scope (explicit reservations)

The following are NOT v0.1.3 tasks. Listed here so they don't accidentally
get pulled in:

- **CI workflow updates** — separate concern; the `.github/workflows/` directory should not be modified in v0.1.3.
- **Background daemons** (Observer, Dreamer, Health, Skill Miner) — v0.2.
- **Multi-agent orchestration** (parallel reviewers, daemon bus) — v0.2.
- **Hook-error log rotation** — v0.2 alongside the bus rotation policy.
- **Web/Streamlit UI for status** — out of scope indefinitely.
- **`forge:set-profile` for runtime profile switching** — useful follow-on; T-111 in v0.1.4 if dogfood shows demand.
- **LLM-based fallback for `/forge:why` on unknown IDs** — v0.2 candidate.
- **Windows support** — v0.2 at earliest (POSIX-only constraint is documented).

---

## Pre-Release Checklist

Before tagging v0.1.3:

- [ ] All 11 tasks marked ✅
- [ ] `tests/integration/test_v013_first_run.sh` passes on a clean checkout
- [ ] Total test count ≥ 615 (532 baseline + ≥ 83 new from T-100/101/102/104, plus T-105/106/107/108 tests when added)
- [ ] **At least one external user has completed the round-trip** (R-V13-1)
- [ ] Dogfood notes captured in `build/05-implementation/dogfood-notes-v0.1.3.md`
- [ ] README.md leads with discipline + traceability
- [ ] `docs/gate-philosophy.md` exists and is referenced from README
- [ ] CHANGELOG.md has v0.1.3 entry
- [ ] `.claude-plugin/plugin.json` version is `0.1.3`
- [ ] `marketplace.json` (if applicable) updated
- [ ] Git tag `v0.1.3` created and pushed
- [ ] GitHub release notes published

The external-user item is the easiest to skip and the hardest to recover from
if skipped. Don't.