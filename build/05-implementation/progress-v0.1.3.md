# Progress — Forge v0.1.3

> Tracks the v0.1.3 patch release (T-100..T-110). Composes with the v0.1.0
> progress log at `build/05-implementation/progress.md`. Source of truth for
> "where are we" — keep in sync with `build/04-plan/task-dag-v0.1.3.md`.

**Last updated**: 2026-05-19
**Current state**: All engineering complete (T-100..T-108, T-110). T-109 text
rewrite complete; only its GIF/screenshot asset remains (deferred to the
dogfood run). Plus three post-DAG correctness fixes landed (validate-plugin,
env-var rename, README reframe). **Sole remaining release blocker**:
external-user dogfood (R-V13-1) — requires a non-author human; cannot be
satisfied in an AI session.

`main` and `develop` are in sync, **14 commits ahead of origin (unpushed)**,
no `v0.1.3` tag cut yet (intentionally — gated on dogfood).

---

## Task Status

| Task  | Title                              | Status     | Tests |
|-------|------------------------------------|------------|-------|
| T-100 | Hook resilience wrapper            | ✅ done    | 25 (`test_hook_runner.py`) |
| T-101 | `/forge:doctor`                    | ✅ done    | 35 (`test_doctor.py`) |
| T-102 | `/forge:uninstall`                 | ✅ done    | 21 (`test_uninstall.py`) |
| T-103 | `/forge:init --dry-run` + manifest | ✅ done    | covered by init tests; smoke-verified |
| T-104 | Gate result formatter              | ✅ done    | 17 (`test_format_gate_result.py`) |
| T-105 | `/forge:force-advance`             | ✅ done    | 17 (`test_force_advance.py`) |
| T-106 | `/forge:why`                       | ✅ done    | 26 (`test_why.py`) |
| T-107 | `script` project profile           | ✅ done    | 36 (`test_detect_project_type.py`) |
| T-108 | First-run round-trip test          | ✅ done    | `test_v013_first_run.sh` (exit 0) |
| T-109 | README rewrite                     | 🟡 partial | text done; GIF/screenshot deferred |
| T-110 | CHANGELOG + version bump           | ✅ done    | n/a (release ceremony, tag pending) |

**Test suite**: 692 unit tests pass + the v0.1.3 integration test.
srs-v0.1.3 §9 target was ≥ 615 — met.

---

## What's Done

- **T-100..T-106** — hook resilience wrapper, `/forge:doctor`,
  `/forge:uninstall`, gate result formatter, `/forge:force-advance`,
  `/forge:why`. Scripts + skills + unit tests, all committed.
- **T-103** — `init-pipeline.sh` `--dry-run` / `--manifest-only`;
  `forge-init` SKILL.md gitignore step + Verification section. Smoke-verified:
  dry-run writes nothing, manifest is valid JSON.
- **T-107** — `script` profile + `suggest_only` (never auto-assigned);
  `detect-project-type.py` indicators; `check-script-runnable.py` /
  `check-script-has-tests.py`. Verified: `script` is suggested, not assigned.
- **T-108** — `tests/integration/test_v013_first_run.sh` + fixture. Exercises
  doctor → init dry-run → init → gate failure → why → force-advance → why
  (tag) → uninstall dry-run → uninstall → idempotent re-run. Exits 0 on a
  clean checkout. (Caught a real test-helper variable-shadowing bug during
  authoring; fixed.)
- **T-109 (text)** — README leads with sequencing/discipline, explicitly
  acknowledges Claude Code's own memory, and enumerates the genuine
  differentiators. `docs/gate-philosophy.md` written. Milestones table removed
  from README (stale, redundant with the DAG).
- **T-110** — `plugin.json` + `marketplace.json` → `0.1.3`; CHANGELOG v0.1.3
  entry. Git tag / GitHub release intentionally **not** cut (gated on dogfood).

### Post-DAG correctness fixes (not original v0.1.3 tasks)

- **`validate-plugin.py`** — removed the bogus `claude_code_version` required
  field (not in the official manifest schema; removed from `plugin.json` back
  in v0.1.1). Validator now passes on the real manifest; regression tests added
  (incl. one that validates the actual in-repo manifest).
- **`${CLAUDE_PLUGIN_DIR}` → `${CLAUDE_PLUGIN_ROOT}`** across 28 skill/doc/
  script files. `CLAUDE_PLUGIN_DIR` is not a real env var (expands to empty).
  CHANGELOG and lessons references to the old name intentionally preserved.
- **README reframe** — see T-109 above.

---

## Remaining Work

- **T-109 GIF/screenshot** — the only outstanding T-109 done-when item. A
  binary visual asset; capture it during the R-V13-1 dogfood run so it adds no
  new critical-path work.

## Release Blockers (srs-v0.1.3 §9)

1. ⬜ External-user dogfood (R-V13-1) — **the single most important criterion**;
   notes go to `build/05-implementation/dogfood-notes-v0.1.3.md`.
2. ✅ `test_v013_first_run.sh` passes on a clean checkout (T-108).
3. ✅ README leads with discipline + traceability, not memory (T-109 text).
4. ✅ CHANGELOG entry + `plugin.json` → `0.1.3` (T-110).
5. ✅ Test count ≥ 615 (currently 692 unit + integration).

Blockers 2–5 are cleared. Only the dogfood (and the screenshot captured during
it) stands between this and a `v0.1.3` tag.

---

## Next Session Starts Here

1. Decide on push: `main`/`develop` are 14 commits ahead of origin, unpushed.
   Project convention wants a `develop → main` PR before `main` ships.
2. Run / arrange the external-user dogfood (R-V13-1); capture notes in
   `build/05-implementation/dogfood-notes-v0.1.3.md` and grab the README
   screenshot during it.
3. After dogfood passes: cut the `v0.1.3` tag and GitHub release (T-110 close).
