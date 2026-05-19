# SRS — Forge v0.1.3 (delta)

> Delta requirements for the v0.1.3 patch release. Composes with the v0.1.0 SRS
> at `build/01-srs/srs.md`. v0.1.0 REQs remain in force; this file adds new
> requirements only.
>
> **Theme**: Reduce first-run tension. v0.1.0 shipped a working pipeline but
> nobody outside the author has used it. v0.1.3 makes the first ten minutes —
> install, init, first gate failure, optional uninstall — hard to mess up.

---

## 1. Scope

**In scope for v0.1.3:**

- Hook crash isolation and timeout enforcement (so a Forge bug never breaks
  the user's Claude Code session)
- `/forge:doctor` diagnostic command
- `/forge:uninstall` filesystem-state removal command
- `/forge:init --dry-run` and file-manifest output
- Gate failure formatter with per-criterion fix hints
- `/forge:force-advance` blocker override (records a lesson)
- `/forge:why` contextual help for blockers and lessons
- `script` project profile for sub-500-LOC projects
- First-run round-trip integration test (install → init → recover → uninstall)
- README rewrite leading with discipline + traceability (not memory)
- CHANGELOG + version bump

**Out of scope for v0.1.3 (deferred to v0.2 or later):**

- New pipeline stages
- Background daemons (Observer, Dreamer, Health Daemon, Skill Miner)
- Multi-agent orchestration (parallel reviewers, daemon bus)
- New agent personas
- CI workflow changes
- Cross-tool orchestration (Codex CLI, Gemini CLI)

**Forward-compatibility:**

The hook resilience wrapper (REQ-RES-*) and gate result formatter (REQ-GATE-*)
are designed to also support v0.2 needs (background daemons run as long-lived
hook variants; multi-agent gates use the same formatter).

---

## 2. Functional Requirements

### Family REQ-RES: Hook Resilience

#### REQ-RES-001 — Hook crash isolation

**Trigger**: Any of the 7 lifecycle hooks raises an uncaught exception (including
`BaseException` subclasses like `KeyboardInterrupt`, `MemoryError`).

**Maps to**: T-100

**Behavior**:

- The exception is caught at the hook entry point by a shared runner (`scripts/_hook_runner.py`).
- The full traceback is logged to `<project>/.forge/hook-errors.log` as a single JSONL record with fields `ts`, `hook`, `kind`, `detail` (capped at 1000 chars).
- The hook process exits 0, regardless of which hook event fired.
- Claude Code receives no error signal; the user's session continues uninterrupted.

**Acceptance**:

- **AC-RES-001a**: `tests/unit/test_hook_runner.py::TestExceptionIsolation` covers exception → exit 0, traceback logged, log file created if absent.
- **AC-RES-001b**: `KeyboardInterrupt` and `MemoryError` are caught and isolated (`test_keyboard_interrupt_isolated`).
- **AC-RES-001c**: If `.forge/hook-errors.log` is itself unwritable (e.g., disk full, permission denied), the runner falls back to stderr and still exits 0; never raises.

---

#### REQ-RES-002 — Per-hook timeout enforcement

**Trigger**: A hook's `main()` function runs longer than its configured budget.

**Maps to**: T-100

**Behavior**:

- The runner installs a `SIGALRM` handler before invoking the hook's `main()` and uses `signal.setitimer(ITIMER_REAL, timeout)`.
- On timeout, `_Timeout` exception is raised, caught, logged as `kind: "timeout"`, and the process exits 0.
- Default timeouts:
  - `session-start`, `session-end`: 30s (once per session, may sync lessons + promote cross-project)
  - `stop-reflect`: 10s (4-step reflect pipeline)
  - `subagent-stop`: 5s
  - `post-tool-use`: 2s
  - `pre-tool-write`, `prompt-submit`: 1s (per-turn; latency matters)
- Override via env: `FORGE_HOOK_TIMEOUT` (global) and `FORGE_HOOK_TIMEOUT_<NAME>` (per-hook, e.g., `FORGE_HOOK_TIMEOUT_SESSION_START=60`).

**Acceptance**:

- **AC-RES-002a**: A hook that sleeps longer than its budget exits 0 with a logged `timeout` record (`test_timeout_kills_hook`).
- **AC-RES-002b**: `FORGE_HOOK_TIMEOUT_*` env overrides are respected (`test_env_override_can_extend_timeout`).
- **AC-RES-002c**: The `setitimer` is disarmed in a `finally` block so a subsequent SIGALRM cannot fire after the hook returns (`test_setitimer_disarmed_after_run`).
- **AC-RES-002d**: POSIX-only is documented in `scripts/_hook_runner.py` module docstring. Windows is out of scope for v0.1.3.

---

#### REQ-RES-003 — Blocking hooks never block on internal failure

**Trigger**: A blocking hook (`pre-tool-write`, `stop-reflect`, `subagent-stop`)
either crashes with an unhandled exception or exceeds its timeout.

**Maps to**: T-100

**Behavior**:

- Only an **explicit `sys.exit(2)`** from the hook's own logic propagates as a blocking signal to Claude Code.
- Exceptions and timeouts in blocking hooks still result in exit 0 — never exit 2.
- Non-blocking hooks (`session-start`, `prompt-submit`, `post-tool-use`, `session-end`) that accidentally call `sys.exit(2)` have it suppressed to 0 with an `unexpected-exit-2` lesson recorded.

**Rationale**: A Forge bug must never block the user's tool calls or stops. The
worst case for a buggy hook is "skip this hook," not "user cannot save their file."

**Acceptance**:

- **AC-RES-003a**: A blocking hook with an unhandled exception exits 0 (`test_blocking_hook_with_exception_does_not_block`).
- **AC-RES-003b**: A blocking hook that times out exits 0 (`test_blocking_hook_with_timeout_does_not_block`).
- **AC-RES-003c**: An explicit `sys.exit(2)` from a blocking hook propagates as exit 2 (`test_blocking_hook_propagates_exit_2`).
- **AC-RES-003d**: An accidental `sys.exit(2)` from a non-blocking hook is suppressed to 0 with `unexpected-exit-2` logged (`test_nonblocking_hook_suppresses_exit_2`).

---

#### REQ-RES-004 — Structured hook error log

**Trigger**: Any hook failure (exception, timeout, or unexpected exit 2).

**Maps to**: T-100

**Behavior**:

- Errors are appended to `<project>/.forge/hook-errors.log` as JSONL.
- Each record: `{"ts": "<ISO8601>", "hook": "<name>", "kind": "<category>", "detail": "<truncated to 1000 chars>"}`.
- Log location is resolved via: (1) explicit `cwd` arg, (2) `CLAUDE_PROJECT_DIR` env, (3) `os.getcwd()` fallback.
- The log directory is created on demand (`mkdir -p`).
- The `/forge:doctor` command reads the last 5 records and surfaces them as a warning if non-empty (REQ-DIAG-002).

**Acceptance**:

- **AC-RES-004a**: First-ever error creates `.forge/hook-errors.log` and parent dir (`test_creates_log_dir_and_file`).
- **AC-RES-004b**: Subsequent errors append (`test_appends_multiple_records`).
- **AC-RES-004c**: Detail field is capped at 1000 chars (`test_detail_capped`).
- **AC-RES-004d**: Logger does not raise even on unwritable target (`test_never_raises_on_unwritable_dir`).

---

### Family REQ-DIAG: Diagnostic Self-Check

#### REQ-DIAG-001 — `/forge:doctor` command

**Trigger**: User invokes `/forge:doctor`, or reports Forge misbehavior.

**Maps to**: T-101

**Behavior**:

- New skill at `skills/forge-doctor/SKILL.md` that invokes `scripts/doctor.py`.
- Default: prints a human-readable report grouped by category (environment, plugin, project, global).
- Flags: `--json` (machine-readable), `--quiet` (failures and warnings only), `--cwd` (override project dir).
- Exits 0 on all-pass (warnings allowed), 1 on any hard failure.

**Acceptance**:

- **AC-DIAG-001a**: `/forge:doctor` prints a categorized report with ✓/✗/⚠/· icons (`tests/unit/test_doctor.py::TestCLI::test_text_output_contains_summary`).
- **AC-DIAG-001b**: `--json` emits a list of `{name, category, status, detail, fix}` records (`test_json_output_is_valid`).
- **AC-DIAG-001c**: SKILL.md instructs Claude to present `Fix:` lines verbatim (never paraphrase shell commands).

---

#### REQ-DIAG-002 — Diagnostic check coverage

**Trigger**: `/forge:doctor` invocation.

**Maps to**: T-101

**Behavior**: Runs 13 deterministic checks:

| Category | Checks |
|----------|--------|
| environment | Python ≥ 3.11; PyYAML installed; Claude Code ≥ 2.1.0 |
| plugin | `plugin.json` valid; all 7 hooks present; ≥ 12 agents; gate-criteria.md parses |
| project | `pipeline/` writable; current stage from state.md; `.gitignore` configured |
| global | `~/.forge/` writable; disk space > 500 MB; last 5 hook errors |

Each check returns `{name, category, status, detail, fix?}`. Failures have a literal shell command in `fix`.

**Acceptance**:

- **AC-DIAG-002a**: All 13 checks individually tested (`TestEnvironmentChecks`, `TestPluginManifest`, `TestHooks`, `TestAgents`, `TestPipelineDir`, `TestState`, `TestGitignore`).
- **AC-DIAG-002b**: `claude --version` subprocess has a 3-second timeout (won't hang on broken Claude Code).
- **AC-DIAG-002c**: PyYAML is optional — if missing, gate-criteria check warns instead of failing.

---

### Family REQ-CLEAN: Filesystem-State Removal

#### REQ-CLEAN-001 — `/forge:uninstall` command

**Trigger**: User invokes `/forge:uninstall`, says "remove Forge", or asks to start over.

**Maps to**: T-102

**Behavior**:

- New skill at `skills/forge-uninstall/SKILL.md` that invokes `scripts/uninstall.py`.
- Removes `<project>/.forge/` and (unless `--keep-artifacts`) `<project>/pipeline/`.
- Optionally removes `~/.forge/` with `--include-global` (separate confirmation).
- Does NOT unregister the plugin from Claude Code; reminds user to run `/plugin uninstall forge@forge-plugins` separately.

**Acceptance**:

- **AC-CLEAN-001a**: `--yes` removes `.forge/` and `pipeline/` from the cwd (`test_yes_removes_without_prompt`).
- **AC-CLEAN-001b**: Script output always ends with both follow-up commands: `/plugin uninstall` and the reinstall sequence (`test_plan_output_mentions_reinstall`).

---

#### REQ-CLEAN-002 — Mandatory dry-run preview

**Trigger**: Any invocation of `/forge:uninstall`.

**Maps to**: T-102

**Behavior**:

- SKILL.md MUST instruct Claude to run `--dry-run` first and present the plan to the user.
- Removal proceeds only after explicit confirmation in the same turn.
- The plan output shows each target path with label, file count, and size.

**Acceptance**:

- **AC-CLEAN-002a**: `--dry-run` lists targets without removing (`test_dry_run_does_not_remove`).
- **AC-CLEAN-002b**: SKILL.md `When to Use` section explicitly requires preview-first; description has "Make sure to ALWAYS run with --dry-run first".

---

#### REQ-CLEAN-003 — Idempotent removal

**Trigger**: `/forge:uninstall` run twice in a row, or after partial removal.

**Maps to**: T-102

**Behavior**:

- Re-running on an already-cleaned project exits 0 with "Nothing to remove".
- A target that is already gone is recorded as `status: skipped`, not `error`.

**Acceptance**:

- **AC-CLEAN-003a**: Two successive runs both exit 0 (`test_idempotent_repeat`).
- **AC-CLEAN-003b**: Empty project exits 0 with "Nothing to remove" message (`test_empty_project_exits_clean`).

---

#### REQ-CLEAN-004 — Global state separation

**Trigger**: `/forge:uninstall --include-global` selected.

**Maps to**: T-102

**Behavior**:

- Global removal (`~/.forge/`) requires a SEPARATE confirmation, distinct from project-local confirmation, with explicit text warning that the action affects ALL Forge projects, not just this one.
- The user can decline global removal while still proceeding with project-local removal.

**Acceptance**:

- **AC-CLEAN-004a**: SKILL.md `Steps` section requires separate confirmation for global state.
- **AC-CLEAN-004b**: Declining the second confirmation removes the global target from the removal list while keeping project-local removals.

---

### Family REQ-UX: First-Run Experience

#### REQ-UX-001 — `/forge:init --dry-run`

**Trigger**: User invokes `/forge:init --dry-run`.

**Maps to**: T-103

**Behavior**:

- `scripts/init-pipeline.sh` accepts `--dry-run` flag.
- Lists every file that *would* be created without writing anything.
- Output format: `would create: <path>` per file, plus summary line at end.
- Exit 0.

**Acceptance**:

- **AC-UX-001a**: `bash scripts/init-pipeline.sh --dry-run` in an empty dir prints all 18 file paths without creating any.
- **AC-UX-001b**: `--dry-run` on a partially-initialized project shows only files that would be newly created.

---

#### REQ-UX-002 — Manifest output

**Trigger**: User or skill invokes `/forge:init` (any mode).

**Maps to**: T-103

**Behavior**:

- `init-pipeline.sh` prints `created: <path>` per file as it writes.
- Skipped existing files are tracked but not printed (unless verbose).
- A summary line at end states `N file(s) created; M already existed`.
- `--manifest-only` mode emits JSON `{dry_run: bool, root: path, created: [...], skipped: [...]}` for the SKILL.md to parse (used for the gitignore prompt — REQ-UX-003).

**Acceptance**:

- **AC-UX-002a**: `--manifest-only` produces valid JSON.
- **AC-UX-002b**: `created` and `skipped` arrays are mutually exclusive and complete.

---

#### REQ-UX-003 — Gitignore prompt

**Trigger**: `/forge:init` completes (not dry-run) and `.forge/` is not already in `.gitignore`.

**Maps to**: T-103

**Behavior**:

- `skills/forge-init/SKILL.md` instructs Claude to check `.gitignore` after init.
- If `.forge/` is not present, Claude asks the user via chat: "Add `.forge/` to .gitignore? (it's runtime state, not for committing)".
- On yes, Claude appends to `.gitignore`. On no, Claude moves on without warning again.

**Acceptance**:

- **AC-UX-003a**: SKILL.md contains explicit `## Verification` step covering the gitignore check.
- **AC-UX-003b**: The check is non-blocking — Forge works fine even if user declines.

---

### Family REQ-GATE: Gate UX

#### REQ-GATE-001 — Human-readable gate result formatter

**Trigger**: Gate check completes (success or failure).

**Maps to**: T-104

**Behavior**:

- New script `scripts/format-gate-result.py` consumes `check-gate.py` JSON output.
- Text output groups failures by severity (BLOCKERS / WARNINGS), shows each criterion with description, message, and a per-criterion fix hint.
- Three input modes: pipe from stdin, `--input <file>`, or `--stage <N>` (runs check-gate.py for you).
- `--json` mode emits the input enriched with `fix_hint` field per failing criterion.

**Acceptance**:

- **AC-GATE-001a**: All-pass result renders "All criteria passed. Stage may advance." (`test_all_passing`).
- **AC-GATE-001b**: Blocker failure renders "CANNOT advance until all blockers are resolved" + force-advance hint (`test_blocker_failure`).
- **AC-GATE-001c**: Warning-only failure renders "Stage may advance. Address warnings when convenient." (`test_warnings_dont_block`).
- **AC-GATE-001d**: Passing criteria appear as a compact inline list, not full blocks (`test_passed_summary_compact`).

---

#### REQ-GATE-002 — Per-criterion fix hints

**Trigger**: A criterion fails.

**Maps to**: T-104

**Behavior**:

- Fix-hint lookup uses longest-prefix-first match on gate ID against a built-in dict in `format-gate-result.py`.
- Coverage: all 12 stages + profile-specific extensions (G7-API-*, G7-FS-*, G7-ML-*, G7-CLI-*, G7-LIB-*, G12-LIB-*) + forward-compatible entries for v0.2 (G7-MAS-*, G-MAS-*).
- Fallback hierarchy: gate-ID prefix → check-type-specific guidance → universal "/forge:why for context" fallback.
- Future patch (out of v0.1.3 scope): per-criterion `fix_hint:` field in `gate-criteria.md` overrides the built-in dict.

**Acceptance**:

- **AC-GATE-002a**: `G7-API-001` resolves to API-specific hint, not the more generic `G7-` (`test_longest_prefix_wins`).
- **AC-GATE-002b**: Unknown gate ID + known check type → check-type-specific hint (`test_check_type_fallback`).
- **AC-GATE-002c**: Unknown gate ID + unknown check type → universal `/forge:why` fallback (`test_universal_fallback`).

---

#### REQ-GATE-003 — `/forge:force-advance` override

**Trigger**: User invokes `/forge:force-advance` when blockers exist.

**Maps to**: T-105

**Behavior**:

- New skill at `skills/forge-force-advance/SKILL.md` + script `scripts/force-advance.py`.
- Requires `--reason "<text>"` — a non-empty justification, ≥ 10 chars.
- On invocation: records a lesson with `tag: force-advance`, advances stage in `pipeline/state.md`, prints the lesson and stage transition.
- The blocker criteria themselves are not "fixed" — they remain failed in subsequent gate runs. The override is per-advancement, not per-criterion.

**Acceptance**:

- **AC-GATE-003a**: Without `--reason`, exits non-zero with "must provide --reason".
- **AC-GATE-003b**: Records a lesson with the user's reason verbatim and the list of blockers that were overridden.
- **AC-GATE-003c**: Stage advances by 1 in state.md; previous stage's history entry is annotated with `(force-advanced)`.

---

#### REQ-GATE-004 — `/forge:why` contextual help

**Trigger**: User invokes `/forge:why <gate-id|lesson-tag|stage-N>`.

**Maps to**: T-106

**Behavior**:

- New skill at `skills/forge-why/SKILL.md` + script `scripts/why.py`.
- For a gate ID: explains the criterion, its rationale, and the fix hint.
- For a lesson tag: shows the lesson(s) with that tag and the source corrections.
- For a stage number: explains what that stage produces and why it exists.
- Bare `/forge:why` (no arg): explains the current blocker(s), if any.

**Acceptance**:

- **AC-GATE-004a**: `/forge:why G1-001` returns the criterion description + fix hint.
- **AC-GATE-004b**: `/forge:why force-advance` lists recent force-advance lessons.
- **AC-GATE-004c**: Bare `/forge:why` with active blockers explains the current blocker(s).

---

### Family REQ-PROF: Project Profiles

#### REQ-PROF-001 — `script` profile definition

**Trigger**: `/forge:init` invoked on a project matching `script` indicators, or user opts in.

**Maps to**: T-107

**Behavior**:

- New profile in `references/project-type-profiles.md`.
- Stages 2, 5, 8, 9, 10, 11 are skipped (no-ops with passing gates).
- Stages 3, 4, 12 are optional.
- Stages 1, 6, 7 are active with simplified gates.
- New gates: `G6-SCRIPT-001` (runnable), `G6-SCRIPT-002` (help text — warning), `G7-SCRIPT-001` (≥ 1 test), `G7-SCRIPT-002` (smoke run — warning).

**Acceptance**:

- **AC-PROF-001a**: `script` profile loads via the existing profile resolution mechanism without modifying stage skills (the profile's `skip: true` entries are honored by the stage agents).
- **AC-PROF-001b**: `/forge:init --type script` on an empty repo produces a `pipeline/` where Stages 2/5/8/9/10/11 are pre-marked as skipped.

---

#### REQ-PROF-002 — `suggest_only` detection flag

**Trigger**: `/forge:init` detects a profile match with `suggest_only: true`.

**Maps to**: T-107

**Behavior**:

- New flag in profile definition: `suggest_only: true`.
- When `scripts/detect-project-type.py` matches such a profile, it returns `suggested_profile` rather than `assigned_profile`.
- `skills/forge-init/SKILL.md` prompts the user to confirm or pick a different profile before writing to `state.md`.
- Currently only the `script` profile uses this flag; other profiles continue to auto-assign on detection.

**Rationale**: Prevents the "I `/forge:init`'d my real project and got a stripped-down pipeline" failure mode.

**Acceptance**:

- **AC-PROF-002a**: `detect-project-type.py` distinguishes `assigned_profile` from `suggested_profile` in its output.
- **AC-PROF-002b**: SKILL.md handles `suggested_profile` by prompting; user can decline and select any of the 6 profiles or `unknown`.

---

### Family REQ-TEST: Round-trip Validation

#### REQ-TEST-001 — First-run integration test

**Trigger**: CI / pre-release validation.

**Maps to**: T-108

**Behavior**:

- New test `tests/integration/test_v013_first_run.sh`.
- Performs: install → `/forge:init` → simulate gate failure → `/forge:doctor` → `/forge:why` → `/forge:force-advance` → `/forge:uninstall`.
- Verifies that each command produces the expected output and side effects.
- Runs against the plugin repo itself (dogfood).

**Acceptance**:

- **AC-TEST-001a**: Test exits 0 when run on a clean checkout.
- **AC-TEST-001b**: Test catches regressions on each of: dry-run preview presence, gate fix hint rendering, force-advance reason requirement, uninstall idempotency.

---

## 3. Non-Functional Requirements

- **NFR-RES-001** — Hook overhead in the success path is ≤ 5 ms (the wrapper adds only signal setup + try/except).
- **NFR-RES-002** — Hook error log size is bounded by `_DETAIL_CAP = 1000` per record. Long-term rotation is out of scope for v0.1.3 (deferred to v0.2 alongside the bus design's rotation policy).
- **NFR-DIAG-001** — `/forge:doctor` completes in ≤ 5 seconds in a healthy environment.
- **NFR-CLEAN-001** — `/forge:uninstall --dry-run` is mandatory in the SKILL.md flow; no path through the skill leads to destruction without preview.
- **NFR-GATE-001** — `format-gate-result.py` adds < 100 ms wall-clock over `check-gate.py` alone.
- **NFR-COMPAT-001** — POSIX-only is acceptable for v0.1.3 (hook resilience uses `SIGALRM`). Windows support deferred to v0.2 at earliest.

---

## 4. Gate Additions

### Stage 6 — `script` profile additions

```yaml
- id: G6-SCRIPT-001
  description: Script is runnable (has shebang + executable bit, OR runs via `python <script>`)
  check: script_returns_zero
  args: { script: "scripts/check-script-runnable.py" }
  severity: blocker

- id: G6-SCRIPT-002
  description: Help text or --help flag exists if the script accepts arguments
  severity: warning
```

### Stage 7 — `script` profile additions

```yaml
- id: G7-SCRIPT-001
  description: At least one test exists (pytest test, bash assertion, or executable example)
  check: script_returns_zero
  args: { script: "scripts/check-script-has-tests.py" }
  severity: blocker

- id: G7-SCRIPT-002
  description: Script runs end-to-end without error on a sample input
  severity: warning
```

---

## 5. New Lesson Tags

These compose with v0.1.0's existing lesson extraction:

| Tag                       | Producer                  | Trigger                                                  |
| ------------------------- | ------------------------- | -------------------------------------------------------- |
| `force-advance`           | `force-advance.py`        | User overrode a blocker gate (REQ-GATE-003)              |
| `lead-only-violation`     | `pre-tool-write.py`       | (v0.2; tag reserved here for forward-compat)             |
| `unexpected-exit-2`       | `_hook_runner.py`         | Non-blocking hook returned exit 2 (REQ-RES-003)          |
| `timeout`                 | `_hook_runner.py`         | Hook exceeded its timeout budget (REQ-RES-002)           |
| `agent-teams-unavailable` | (v0.2; reserved)          | —                                                        |

---

## 6. Non-Goals (explicit)

- Background daemons (Observer/Dreamer/Health/Skill-Miner) — v0.2
- Multi-agent orchestration — v0.2
- New pipeline stages — never (the 12 are fixed)
- Cross-tool orchestration (Codex CLI, Gemini CLI) — v0.3+
- Windows support — v0.2 at earliest
- Hook-error log rotation — v0.2 (paired with bus rotation)
- A `forge:fix` auto-remediation command — too risky for v0.1.3
- Streamlit/web UI for `/forge:status` — out of scope indefinitely

---

## 7. REQ → Task Traceability

| REQ          | Tasks |
| ------------ | ----- |
| REQ-RES-001..004  | T-100 |
| REQ-DIAG-001..002 | T-101 |
| REQ-CLEAN-001..004 | T-102 |
| REQ-UX-001..003   | T-103 |
| REQ-GATE-001..002 | T-104 |
| REQ-GATE-003      | T-105 |
| REQ-GATE-004      | T-106 |
| REQ-PROF-001..002 | T-107 |
| REQ-TEST-001      | T-108 |

Reverse mapping lives in `build/04-plan/task-dag-v0.1.3.md`.

---

## 8. Open Questions

- **OQ-1** — Should `/forge:force-advance` re-run the gate after recording the lesson, to confirm the user understood which blockers were overridden? **Current proposal**: No — the lesson capture is sufficient; re-running gate would be confusing if the user already understood. Revisit after dogfood.
- **OQ-2** — Should hook errors older than N days be auto-pruned from `.forge/hook-errors.log`? **Current proposal**: Not in v0.1.3. The cap on detail length plus the typical low frequency keeps the file small. Add rotation in v0.2 alongside the daemon bus.
- **OQ-3** — Should `/forge:why` invoke an LLM for unknown gate IDs (Claude itself, via subagent)? **Current proposal**: No — deterministic lookup only in v0.1.3. LLM fallback is a v0.2 candidate.
- **OQ-4** — Does the `script` profile's `suggest_only: true` flag generalize to other profiles where detection might be too aggressive? **Current proposal**: Wait for dogfood evidence. Apply it elsewhere only if real users complain.

---

## 9. Acceptance Definition for v0.1.3 Release

All of the following must be true before tagging v0.1.3:

1. All AC-* criteria above pass.
2. `tests/integration/test_v013_first_run.sh` passes on a clean checkout.
3. Total test count ≥ 615 (532 baseline + ≥ 83 new across hook_runner, doctor, uninstall, format-gate-result).
4. ~~At least one external user (not the author) has run `/plugin install` → `/forge:init` → encountered a gate failure → recovered.~~ **WAIVED for v0.1.3 by explicit owner decision (2026-05-19).** Real-user dogfood and the README traceability screenshot are moved to **v0.1.4** (tracked as REQ-TEST-002 / R-V14-1). v0.1.3 ships on engineering + integration evidence alone. Rationale and accepted risk recorded in `build/05-implementation/decisions-v0.1.3.md` (D-V13-11). This is a conscious deviation, not an oversight — the v0.1.2 retro critique still stands and is the reason v0.1.4 carries it as a hard, non-waivable gate.
5. README.md leads with discipline + traceability (not memory).
6. CHANGELOG.md has an entry for v0.1.3.
7. `.claude-plugin/plugin.json` version bumped to `0.1.3`.

Item 4 was the hardest and was, by explicit decision, deferred — not silently
skipped. v0.1.4's acceptance MUST include it with no waiver path.