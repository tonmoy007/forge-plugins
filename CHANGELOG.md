# Changelog

All notable changes to Forge are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- The three interactive REQs (CLARIFY / CONFIRM / NARRATE-001) implementation — v0.1.6
- Claude Code marketplace publication (pending marketplace availability)
- CI/CD workflow for automated testing on pull requests
- Additional project-type profiles (data-contract, mobile, monorepo)

---

## [0.1.5.1] — 2026-06-09

Hotfix. Forge hooks crashed with a `ModuleNotFoundError` traceback at import time
when **PyYAML was not installed** in the user's Python (e.g. a bare conda env) —
every Stop/SessionStart/etc. event spammed the session. Same dependency-not-
installed failure mode as the v0.1.3.1 `python-frontmatter` bug, moved to `yaml`.

### Fixed
- The 6 active hooks (`session-start`, `prompt-submit`, `pre-tool-write`,
  `post-tool-use`, `stop-reflect`, `session-end`) now **fail soft** when PyYAML is
  absent: they print one actionable line — `[Forge] PyYAML is not installed —
  Forge hooks are inactive. Fix: pip install pyyaml (then run /forge:doctor).` —
  and exit 0 instead of crashing with a traceback. The guard runs at import time,
  before `_state_lib` (which requires PyYAML) is imported. `/forge:doctor` already
  detects the missing dependency.
- `tests/unit/test_pyyaml_missing.py` — shadows `yaml` with an ImportError shim
  and asserts every guarded hook exits 0 with the message and no traceback.

### Note
- This does not make Forge *function* without PyYAML (it remains a required
  runtime dependency, checked by `/forge:doctor`); it stops the crash-spam and
  tells the user exactly how to fix it.

## [0.1.5] — 2026-06-09

Bug-fix-heavy release driven by two on-project testers (EF-001…027). Theme: sand
off the v0.1.3 sharp edges and kill the **surface-healthy / substance-inert**
antipattern family at every layer (state, hook, doctor, gate-config, lesson-store),
plus small UX nudges. 25 tasks across 7 milestones; full unit + integration suite
green and the Forge-on-Forge pipeline passes its own gates.

> **Version history note**: there is no `0.1.4` tag. v0.1.4's scope (the dogfood
> ceremony) was **amended, not executed** — see `build/01-srs/srs-v0.1.4.md` §9
> Amendment — once two real testers existed. v0.1.5 supersedes it directly from
> v0.1.3.1.

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
- **Wrong / dead next-step hints (REQ-NEXTHINT-001, T-103)** — every stage skill
  hardcoded its `## Next Step` hint; two named commands that don't exist:
  `/forge:srs` pointed at `/forge:ux` and `/forge:product` pointed at
  `/forge:architecture` (canonical commands are `/forge:product` and `/forge:arch`).
  After `01-srs` the hint now correctly names **product/UX**, not architecture.
  Added a `next-hint` subcommand to `scripts/state-manager.py` that reads the
  canonical hint from `references/stage-order.md`; all 12 stage skills now invoke
  it instead of embedding a literal string. Also corrected the `forge-status`
  stage→command table (stage 2/3 named the same dead commands).
  `tests/unit/test_next_hint.py` enumerates all 12 transitions and guards against
  re-drift.

### Added
- Comprehensive external test findings to `build/06-evaluation/v0.1.3.1-early-feedback.md`:
  7 new entries (EF-021 through EF-027) covering 3 hotfixes and 4 fix-v0.1.5 items.

### Changed
- `build/06-evaluation/v0.1.3.1-early-feedback.md` — tally updated from 20 → 27 total
  findings across all buckets.

### Added — state machine & entry gates (M2)
- **Stage bounds + cycle-wrap (REQ-PIPEBOUNDS-001, T-104)** —
  `_state_lib.advance_stage` rejects out-of-range jumps and wraps past stage 12 to
  `(cycle+1, stage 0)`; `set current_stage` to `-1/99/13` is rejected, never
  persisted. (EF-024)
- **Pre-flight entry gates for stages 2–11 (REQ-GATE-ENTRY-001, T-105)** — each
  stage refuses to start when its prior-stage artifact is missing
  (`state-manager.py preflight`); multi-stage skips require `/forge:force-advance`.

### Added — fail-loud surfacing (M3)
- **State-read failures surface (REQ-SILENTSTATE-001, T-106)** — hooks stop
  swallowing `read_state` errors; visible warning, `inconclusive` gate output,
  `/forge:doctor` callout, and a session-end footer. (EF-007)
- **Doctor runs the current-stage gate inline (REQ-DOCTOR-001, T-107)** — top-line
  status is `healthy` / `wedged` / `broken`; doctor can't contradict status. (EF-017)
- **check-gate fails loud on missing scripts (REQ-GATESTUB-001, T-108)** — a
  criterion pointing at a missing script is `inconclusive`, promoted to blocker,
  and exits non-zero; doctor/status show an "N criteria unimplemented" banner. (EF-019)

### Added — gate scripts (M4)
- **All 15 gate scripts implemented (REQ-GATESTUB-001, T-109–T-111)**:
  `check_srs_acceptance`, `traceability-check`, `spec-coverage`,
  `check_dag_completeness`, `check_dag_completion`, `token-audit`, `check_coverage`,
  `check_todos`, `check_progress_sync`, `check_nfr_coverage`, `check_open_bugs`,
  `check_health`, `check_hotfix_tests`, `check_git_tag`. `some_check.py` is a
  doc-only format example (not a real criterion).
- **Gate-criteria audit (T-112)** — `test_gate_criteria_audit.py` fails if any
  `script_returns_zero` criterion references a missing script.

### Added — lesson capture (M5)
- **`extract-lessons.py --cwd` (REQ-EXTRACT-CWD-001, T-113)** — derives input/output
  from `--cwd`. (EF-027)
- **Implicit lesson-signal producers (REQ-LESSON-SOURCES-001, T-114)** — five
  producers turn hook-error clusters, repeated design violations, heredoc bypass,
  gate pass→wedge, and state-read regressions into lessons automatically. (EF-018)
- **Global-lessons TTL + promotion gate (REQ-LESSON-SOURCES-001 / EF-026, T-115)** —
  promote only at frequency ≥ 2; stale (> 30-day) global lessons decay out of recall.

### Added — UX nudges (M6)
- **`/forge:build --milestone N` (REQ-BUILDBATCH-001, T-116)** — milestone-scoped
  batch builds with per-task commits, pause-on-failure, and `--resume`. (EF-020)
- **Case-insensitive `/forge:why` gate-ID lookup (REQ-WHYCI-001, T-117)**. (EF-025)
- **`session.jsonl` enrichment (REQ-SESSIONLOG-001, T-118)** — versioned, PII-free
  rows with commands, tokens, and `reflection_ref`.
- **Per-stage reflection rollup (REQ-STAGEREFLECT-001, T-119)** —
  `pipeline/0X-stage/reflection.md` on stage exit.
- **Pattern-bus schema (REQ-PATTERN-001, T-120)** — versioned `patterns.jsonl` +
  `references/pattern-schema.md`. (EF-008)
- **WebSearch for research/spec agents (REQ-WEBSEARCH-001, T-121)** — cite-or-skip
  rule; planner excluded.

### Added — conventions & docs (M7)
- **REQ-INTERACTIVE-001 decomposed (T-122)** into CLARIFY / CONFIRM / NARRATE-001
  (scheduled for v0.1.6). (EF-013)
- **Large-document split convention (REQ-LARGEDOC-001, T-123)** —
  `references/large-doc-layout.md` + `scripts/read-doc.py` resolver. (EF-006)
- **Third-party-hook troubleshooting (REQ-DOCS-001, T-124)** +
  `.github/ISSUE_TEMPLATE/forge-feedback.md` (REQ-FEEDBACK-001). (EF-003)

### Changed — fixtures
- Harmonized the `sample-todo-api` fixture IDs (eval-report `REQ-F`/`REQ-NF` → canonical
  `REQ`/`NFR`; stray `REQ-NF-003` in architecture; added a stage-9 `health-report.md`)
  so the Forge-on-Forge `full-pipeline` passes all 12 gates.

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
