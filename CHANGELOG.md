# Changelog

All notable changes to Forge are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.3.1] — 2026-05-24

Hotfix release. Removes the runtime dependency on the `python-frontmatter` PyPI
package, which silently broke every external install: Claude Code plugin installs
do not run `pip install`, and the bare PyPI name `frontmatter` resolves to an
unrelated package (no `.load()`), so users who tried to self-remediate hit
`AttributeError: module 'frontmatter' has no attribute 'load'`. State management
now uses PyYAML + a stdlib frontmatter splitter; PyYAML is already a documented
runtime dep checked by `/forge:doctor`.

### Fixed
- `scripts/_state_lib.py` — replaced `import frontmatter` and all `frontmatter.load`
  / `frontmatter.dumps` calls with stdlib parsing of the `---` fence + PyYAML for
  the YAML block. On-disk `pipeline/state.md` byte layout preserved.
- `scripts/load-profile.py` — `_read_project_type()` now delegates to
  `_state_lib.read_state` instead of importing `frontmatter` directly.

### Added
- 3 regression tests in `tests/unit/test_state_manager.py` (`TestNoFrontmatterDependency`)
  that shadow `frontmatter` with an `ImportError`-raising shim and assert read/set/
  advance still work. Catches future re-introductions of the dep.
- One lesson in `tasks/lessons.md` capturing the dep-vs-package-name foot-gun.

### User impact
- External users on v0.1.3 hit `ModuleNotFoundError: No module named 'frontmatter'`
  in every `state-manager.py` invocation (SessionStart, UserPromptSubmit, Stop hooks,
  and `/forge:init` post-setup). v0.1.3.1 makes a clean install work end-to-end with
  only PyYAML installed.

---

## [0.1.3] — 2026-05-19

First-run hardening release. Theme: make the first ten minutes — install, init,
first gate failure, recovery, uninstall — hard to mess up, and make a Forge bug
never break the user's Claude Code session.

### Added

- **Hook resilience wrapper** (`scripts/_hook_runner.py`, T-100) — all 7 lifecycle
  hooks wrapped: top-level exception barrier (logs JSONL to
  `.forge/hook-errors.log`, exits 0), per-hook `SIGALRM` timeout, blocking hooks
  never block on internal failure, non-blocking hooks suppress accidental exit 2.
  POSIX-only (documented).
- **`/forge:doctor`** (`scripts/doctor.py` + skill, T-101) — 13 deterministic
  checks across environment/plugin/project/global, each failing check carries a
  literal fix command. `--json`/`--quiet`/`--cwd`.
- **`/forge:uninstall`** (`scripts/uninstall.py` + skill, T-102) — filesystem
  state removal with mandatory `--dry-run` preview, `--keep-artifacts`,
  `--include-global` (separate confirmation), idempotent re-runs.
- **`/forge:init --dry-run` and `--manifest-only`** (T-103) — preview-only mode
  that writes nothing; JSON manifest drives the post-init `.gitignore` prompt.
- **Gate result formatter** (`scripts/format-gate-result.py`, T-104) — renders
  `check-gate.py` JSON as readable text grouped by severity with per-criterion
  fix hints (longest-prefix lookup over all 12 stages + profile families).
- **`/forge:force-advance`** (`scripts/force-advance.py` + skill, T-105) —
  override a blocking gate; `--reason` (≥10 chars) required and recorded as a
  `force-advance` lesson with the overridden blocker IDs. Override is
  per-advancement, not per-criterion.
- **`/forge:why`** (`scripts/why.py` + skill, T-106) — explains a gate ID,
  lesson tag, stage number, or the current blocker(s). Deterministic lookup.
- **`script` project profile** (T-107) — 6th profile for sub-500-LOC projects
  (4 active stages). `suggest_only` flag: `script` is never auto-assigned, only
  prompted. New `check-script-runnable.py` / `check-script-has-tests.py` gate
  scripts (G6-SCRIPT-001 / G7-SCRIPT-001).
- **First-run round-trip integration test**
  (`tests/integration/test_v013_first_run.sh`, T-108) — exercises doctor → init
  dry-run → init → gate failure → why → force-advance → uninstall →
  idempotent re-run. Passes on a clean checkout.
- **`docs/gate-philosophy.md`** — when to resolve a blocker vs. override it.
- ~158 new unit tests (hook_runner 25, doctor 35, uninstall 21,
  format-gate-result 17, force-advance 17, why 26, plus detect-project-type
  additions). Total unit suite: **690 passing**.

### Changed

- `README.md` now leads with discipline + traceability (gates and REQ-ID chains)
  instead of memory; test badge updated to 690.
- `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` version
  bumped to `0.1.3`.

### Known limitations

- POSIX-only (hook resilience uses `SIGALRM`); Windows deferred to v0.2.
- Hook-error log has a per-record cap but no rotation yet (deferred to v0.2).
- Animated traceability walkthrough in the README is still pending (text
  diagram in place); deferred to v0.1.4.
- **No external-user dogfood gate for this release.** v0.1.3 ships on
  engineering + integration evidence by explicit decision; real-user testing
  is a non-waivable acceptance gate in v0.1.4. Recovery surface for early
  external users: `/forge:doctor`, `/forge:why`, `/forge:force-advance`, and
  hook crash isolation.

---

## [0.1.2] — 2026-05-14

Patch release: skill-miner noise filter and `--cwd` positional fix for AI-callable CLIs.

### Fixed
- `scripts/mine-skills.py` — `_is_substantive()` filter blocks spurious proposals generated by
  same-tool bursts. A 5-Bash burst produced 3 overlapping sliding-window records with identical
  signature, hitting count=3 from one session in 8 seconds. New filter requires ≥2 distinct tool
  types, ≥2 distinct sessions (relaxed when `--session` is active), and ≥60s first-to-last span.
- `scripts/state-manager.py` — `--cwd` now accepted in any argument position. Previous
  `parents=[common]` approach caused subparser `default=os.getcwd()` to overwrite the main
  parser's parsed value when `--cwd` appeared before the subcommand. Fix: subparsers use
  `default=argparse.SUPPRESS` so the namespace value is never silently overwritten.

### Added
- 12 new tests: 8 `_is_substantive` unit tests (including the exact `forge-bash-bash-bash`
  noise scenario), 4 `TestCwdPositioning` CLI tests covering pre- and post-subcommand placement.
- `.forge/skill-blacklist.txt` — `3287e5ddb4be` (forge-bash-bash-bash noise proposal) blacklisted.
- Two new lessons in `tasks/lessons.md` documenting both root causes.

---

## [0.1.1] — 2026-05-14

Patch release: corrected plugin manifest, added marketplace support, updated install docs.

### Added
- `.claude-plugin/marketplace.json` — registry file enabling two-step install:
  `/plugin marketplace add tonmoy007/forge-plugins` then `/plugin install forge@forge-plugins`
- `README.md` Install section updated with correct marketplace commands

### Changed
- `.claude-plugin/plugin.json` — fixed `$schema` URL to schemastore, renamed plugin
  `sdlc-orchestrator` → `forge`, removed invalid fields (`displayName`, `claude_code_version`,
  `engines`), removed unsupported glob declarations for skills/agents (auto-discovery used
  instead), fixed hook env var `CLAUDE_PLUGIN_DIR` → `CLAUDE_PLUGIN_ROOT`

### Removed
- `docs/superpowers/specs/2026-05-11-extract-lessons-design.md` — vendored Superpowers spec
  removed; plugin now uses the installed Superpowers plugin directly

---

## [0.1.0] — 2026-05-12

First stable release. Full 12-stage SDLC pipeline with hooks, agents, memory, and
auto-skill creation — validated end-to-end on the sample Todo API project (532 tests pass).

### Added

**M1: Core Skeleton**
- `plugin.json` — Claude Code plugin manifest wiring all hooks and skills
- `/forge:init` skill — detects project type, scaffolds `pipeline/`, writes `state.md`
- `state-manager.py` — CLI for reading and updating pipeline state (36 tests)
- `/forge:status` skill — shows current stage, task, blockers, recent history
- `gate-criteria.md` — machine-readable exit criteria for all 12 stages (60 criteria)
- `check-gate.py` — evaluates `file_exists`, `file_contains`, `script_returns_zero`,
  `all_tests_pass` checks; always exits 0 and outputs JSON (14 tests)

**M2: Hook System**
- `session-start.py` — injects stage context and top lessons at session open (≤ 2 000 tokens; 17 tests)
- `prompt-submit.py` — detects stage intent and flags user corrections (16 tests)
- `stop-reflect.py` — evaluates output against gate criteria; surfaces skill proposals (48 tests)
- `session-end.py` — writes session summary to `.forge/sessions/` (18 tests)
- `pre-tool-write.py` — enforces design token compliance, traceability, naming conventions (35 tests)
- `post-tool-use.py` — logs tool use to `patterns.jsonl` for skill mining (18 tests)
- `subagent-stop.py` — captures cross-stage agent reflections

**M3: Specialized Agents**
- 12 stage agent personas (SRS analyst through release manager)
- 4 cross-stage agents: reflector, lesson-extractor, skill-miner, gate-checker
- `context-pruner.py` — stage-aware artifact selection within token budget (35 tests)
- `/forge:resume` skill — restores context after session restart

**M4: Memory + Lessons**
- `extract-lessons.py` — rule-based correction extraction → structured YAML lessons (43 tests)
- `sync-lessons.py` — mirrors `lessons.md` to `.forge/lessons.yaml` (37 tests)
- `promote-lessons.py` — promotes high-frequency lessons to `~/.forge/global-lessons.yaml` (39 tests)
- Session-start lesson injection: filters by stage tags and project type, sorted by frequency, capped at 5

**M5: Adaptive Workflow**
- `detect-project-type.py` — detects `api`, `fullstack`, `ml-pipeline`, `cli`, `library` types (10 tests)
- `project-type-profiles.md` — per-type gate overrides and stage emphasis rules (5 profiles, ≥3 overrides each)
- `load-profile.py` — applies profile overrides to stage skill context (24 tests)
- All 12 stage skills profile-aware (skip/replace_with/add_step)

**M6: Auto-Skill Creation**
- Sliding 3-tool window pattern tracker with SHA-1 signature stability detection (22 tests)
- `mine-skills.py` — aggregates patterns (frequency ≥ 3) → SKILL.md drafts with name/description/steps (33 tests)
- `skill-approval.py` — list/approve/modify/reject mined proposals (22 tests)
- `/forge:retro` skill — cycle-completion retrospective writing to `pipeline/12-release/retro.md`

**M7: Polish + Documentation**
- `README.md` — user-facing install, quickstart, full 12-stage command reference, hook table, config docs
- `CONTRIBUTING.md` — contributor guide with dev workflow, commit format, PR checklist
- `docs/agent-authoring.md` — step-by-step walkthroughs for adding agents, stages, and profiles
- `tests/integration/full-pipeline.sh` — end-to-end test: 29 artifacts, 12/12 gate checks, traceability chain
- `examples/sample-todo-api/fixtures/` — 29 pre-populated stage artifacts for e2e validation
- `scripts/check_dir_nonempty.py` — gate helper for ADR directory non-empty check (G3-005)

### Tests

532 unit + integration tests. Coverage spans all hooks, scripts, and integration paths.

---

## [Unreleased]

### Fixed
- `tests/unit/test_force_advance.py` — replaced 4 `import frontmatter` calls with
  `_state_lib.read_state()` / `_state_lib._split_frontmatter()`. No longer requires
  `python-frontmatter` to run tests (EF-021).
- `hooks/post-tool-use.py` — added `isinstance` guard for string `tool_input` / `tool_response`
  payloads from Bash/Read events. Hook no longer crashes on non-Write tool events (EF-022).
- `hooks/pre-tool-write.py` — added `isinstance` guard for string `tool_input` payloads
  from inline Write events (EF-023).
- **Stage path collision (EF-005, REQ-PATHS-001, T-102)** — stage skills and agent
  personas wrote/read artifacts at directories and filenames the gates never checked,
  silently wedging stages 4, 8, 9, 10, and 11. Canonicalized every stage path to the
  single source of truth (`references/stage-order.md` + `gate-criteria.md`):
  `04-technical-spec/`→`04-spec/`, `08-deployment/`→`08-deploy/`,
  `09-monitoring/`→`09-monitor/`, `11-resolution/`→`11-resolve/`;
  `deployment-plan.md`→`deploy-plan.md`, `slo-definition.md`→`observability.md`,
  `resolution-log.md`→`hotfixes.md`, `triage-report.md`→`triage.md`. `/forge:feedback`
  now also writes `feedback-log.md` and `/forge:resolve` now also writes
  `backlog-updates.md` (both are gate blockers that were never produced).
  `tests/unit/test_canonical_paths.py` guards against re-drift.

  > **Migration note**: projects created with v0.1.3.x may have artifacts under the
  > old directories (`pipeline/04-technical-spec/`, `08-deployment/`, `09-monitoring/`,
  > `11-resolution/`) or old filenames. Move them to the canonical names above so the
  > gate checks find them; otherwise the affected stage gate will report the artifact
  > missing.

### Added
- Comprehensive external test findings to `build/06-evaluation/v0.1.3.1-early-feedback.md`:
  7 new entries (EF-021 through EF-027) covering 3 hotfixes and 4 fix-v0.1.5 items.

### Changed
- `build/06-evaluation/v0.1.3.1-early-feedback.md` — tally updated from 20 → 27 total
  findings across all buckets.

### Planned (v0.1.5 scope)
- Stage boundary enforcement in `_state_lib.advance_stage()` — cap at [0, 12],
  cycle wrapping after Release (EF-024)
- Case-insensitive gate ID lookup in `scripts/why.py` (EF-025)
- Global lessons TTL/expiry in `scripts/promote-lessons.py` (EF-026)
- `--cwd` flag support for `scripts/extract-lessons.py` (EF-027)

- Claude Code marketplace publication (pending marketplace availability)
- CI/CD workflow for automated testing on pull requests
- Additional project-type profiles (data-contract, mobile, monorepo)
