# Progress — Forge v0.1.3

> Tracks the v0.1.3 patch release (T-100..T-110). Composes with the v0.1.0
> progress log at `build/05-implementation/progress.md`. Source of truth for
> "where are we" — keep in sync with `build/04-plan/task-dag-v0.1.3.md`.

**Last updated**: 2026-05-19
**Current state**: All engineering tasks (T-100..T-108, T-110) complete. T-109
partial (text traceability diagram in README; animated walkthrough deferred).
Sole remaining release blocker: external-user dogfood (R-V13-1) — cannot be
satisfied by an AI session; requires a non-author human.

---

## Task Status

| Task  | Title                              | Status     | Tests |
|-------|------------------------------------|------------|-------|
| T-100 | Hook resilience wrapper            | ✅ done    | 25 (`test_hook_runner.py`) |
| T-101 | `/forge:doctor`                    | ✅ done    | 35 (`test_doctor.py`) |
| T-102 | `/forge:uninstall`                 | ✅ done    | 21 (`test_uninstall.py`) |
| T-103 | `/forge:init --dry-run` + manifest | 🟡 partial | covered by existing init tests |
| T-104 | Gate result formatter              | ✅ done    | 17 (`test_format_gate_result.py`) |
| T-105 | `/forge:force-advance`             | ✅ done    | 17 (`test_force_advance.py`) |
| T-106 | `/forge:why`                       | ✅ done    | 26 (`test_why.py`) |
| T-107 | `script` project profile           | 🟡 partial | 36 (`test_detect_project_type.py`) |
| T-108 | First-run round-trip test          | ⬜ todo    | — |
| T-109 | README rewrite                     | ⬜ todo    | — |
| T-110 | CHANGELOG + version bump           | ⬜ todo    | — |

**Test suite**: 690 unit tests pass (baseline 532 + 158 new for v0.1.3).
srs-v0.1.3 §9 target was ≥ 615 — met.

---

## What's Done

- **T-100** — `scripts/_hook_runner.py` created; all 7 hooks wrapped with
  `run_hook(main, hook_name=...)` (commit `cbfd8d0`). Exception isolation,
  SIGALRM timeout, blocking-hook safety, exit-2 suppression all tested.
- **T-101** — `scripts/doctor.py` + `skills/forge-doctor/SKILL.md`. 13
  deterministic checks across environment/plugin/project/global.
- **T-102** — `scripts/uninstall.py` + `skills/forge-uninstall/SKILL.md`.
  Mandatory dry-run, idempotent, separate global confirmation.
- **T-104** — `scripts/format-gate-result.py`. Three input modes, longest-prefix
  fix-hint lookup, severity grouping.
- **T-105** — `scripts/force-advance.py` + `skills/forge-force-advance/SKILL.md`.
  `--reason` required (≥ 10 chars), records `force-advance` lesson, advances stage.
- **T-106** — `scripts/why.py` + `skills/forge-why/SKILL.md`. Resolves gate IDs,
  lesson tags, stage numbers, and bare invocation against active blockers.

## In Progress

- **T-103 (partial)** — `scripts/init-pipeline.sh` rewritten for `--dry-run` /
  `--manifest-only`. `skills/forge-init/SKILL.md` modified (uncommitted) for the
  gitignore-prompt step; needs final review against AC-UX-003a/b.
- **T-107 (partial)** — `scripts/detect-project-type.py` updated (uncommitted);
  `scripts/check-script-runnable.py` and `scripts/check-script-has-tests.py`
  created. Profile reference (`references/project-type-profiles.md`) updated.
  Remaining: confirm `suggest_only` end-to-end through the init SKILL prompt.

## Not Started

- **T-108** — `tests/integration/test_v013_first_run.sh` does not exist yet.
  Blocked-by-design on T-103/T-107 finalization.
- **T-109** — README rewrite + `docs/gate-philosophy.md`.
- **T-110** — version bump (`plugin.json` still `0.1.2`), CHANGELOG, tag.

---

## Release Blockers (srs-v0.1.3 §9)

1. ⬜ External-user dogfood (R-V13-1) — **the single most important criterion**;
   notes go to `build/05-implementation/dogfood-notes-v0.1.3.md`.
2. ⬜ `test_v013_first_run.sh` passing on clean checkout (T-108).
3. ⬜ README leads with discipline + traceability (T-109).
4. ⬜ CHANGELOG entry + `plugin.json` → `0.1.3` (T-110).
5. ✅ Test count ≥ 615 (currently 690).

---

## Next Session Starts Here

1. Finalize T-103 SKILL.md gitignore step; verify AC-UX-003a/b.
2. Finalize T-107 `suggest_only` prompt path; verify AC-PROF-002b.
3. Commit the currently-uncommitted v0.1.3 work (scripts, skills, tests, build docs).
4. Write T-108 integration test once T-103/T-107 are locked.
