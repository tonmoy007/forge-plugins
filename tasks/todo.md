# tasks/todo.md

> Active work tracker. The current task lives at the top. Completed tasks archive below.

---

## Active Task: T-026

**Goal**: Pattern tracker in `hooks/post-tool-use.py` — detect repeated tool sequences, log to `.forge/patterns.jsonl` with a stable signature.

**Context**:
- Done when: same 3-tool sequence appearing 3 times produces 3 entries with the same signature
- See `build/04-plan/task-dag.md` T-026.
- REQ-IDs: REQ-070
- Depends on: T-012 (post-tool-use.py hook)

---

## Archive

### T-025 — Wire profiles into stage skills ✅ 2026-05-12
- `scripts/load-profile.py` — CLI: `--cwd PATH [--stage N] [--profiles-file PATH] [--format markdown|json]`; parses `## Profile: <name>` YAML blocks from `references/project-type-profiles.md`; reads `project_type` from `pipeline/state.md`
- `references/project-type-profiles.md` — added G7-ML-005 "Drift detection strategy documented" to ml-pipeline stage_7
- All 12 stage skills (forge-srs … forge-release) now call `load-profile.py` in pre-flight with their stage number; workflow step instructs the agent to apply overrides (skip flags, replace_with, additional_artifacts/concerns/criteria, stage_emphasis)
- `tests/unit/test_load_profile.py` — 24 tests; done-when verified (ML stage 7 surfaces drift detection); all 5 required profiles parse with ≥3 stage overrides
- 451/451 tests pass; plugin metadata still valid

### T-024 — project-type-profiles.md ✅ 2026-05-12
- `references/project-type-profiles.md` audited and extended
- Fullstack profile gained stage_3 (rendering/SSR architecture, BFF, auth flow) and stage_6 (design tokens, bundle size, RSC boundary) overrides
- All 5 required profiles (api, fullstack, ml-pipeline, cli, library) now have ≥3 stage overrides each
- YAML in every profile block parses cleanly; 427/427 tests pass

### T-023 — Project type detection in forge-init ✅ 2026-05-12
- `scripts/detect-project-type.py` rewritten: ML (train.py, *.ipynb, ML libs), API (fastapi/flask/django, routes/ dir), all 5 types
- `skills/forge-init/SKILL.md` updated: profile assignment step, low-confidence prompt, profile influence on lessons/gates
- 10 new tests; 427/427 suite pass

### T-022 — Tier 3 cross-project memory ✅ 2026-05-12
- `scripts/promote-lessons.py` — scans registered projects, clusters lessons by trigger similarity, promotes lessons in 3+ projects to `~/.forge/global-lessons.yaml`
- `~/.forge/` scaffold: `projects.yaml` (registry) + `global-lessons.yaml` (promoted lessons)
- `hooks/session-start.py` updated — calls promote-lessons.py to register project + run promotion each session
- `tests/unit/test_promote_lessons.py` — 39 tests; done-when (3-project → 4th session-start) verified
- 417/417 tests pass

### T-021 — .forge/lessons.yaml mirror ✅ 2026-05-12
- `scripts/sync-lessons.py` — parses tasks/lessons.md, merges with existing lessons.yaml (preserving stage/project_types/frequency/last_used), atomic write
- `hooks/session-start.py` updated — calls sync-lessons.py when lessons.md is newer than lessons.yaml
- `tests/unit/test_sync_lessons.py` — 37 tests; done-when + session-start integration verified
- 378/378 tests pass

### T-020 — Lesson injection in SessionStart ✅ 2026-05-12
- `hooks/session-start.py` already had `_load_lessons()` with stage + project_type filtering (built in T-007)
- Added 3 new tests: done-when (ML/GPU), project-type exclusion, frequency-sort order
- 341/341 tests pass



### T-019 — extract-lessons.py ✅ 2026-05-11
- `scripts/extract-lessons.py` — CLI: `--input`, `--output`, `--dry-run`, `--since`, `--llm`
- Rule-based extraction: don't/never/stop/always/prefer/use-instead patterns → Trigger/Rule/Why/Tags
- Deduplication via `difflib.SequenceMatcher` (ratio ≥ 0.8); atomic write
- `tests/unit/test_extract_lessons.py` — 43 tests; done-when criterion verified

### T-018 — forge-resume skill ✅ 2026-05-11
- `skills/forge-resume/SKILL.md` — reads state, calls context-pruner.py, injects stage-appropriate context
- Resume summary: stage/task/last reflection/gate status/next action
- Auto-registered via `skills/*` glob in plugin.json

### T-017 — context-pruner.py ✅ 2026-05-11
- `scripts/context-pruner.py` — CLI: `--stage N --cwd PATH [--budget N]` → JSON
- Per-stage artifact priority map (12 stages); stage 6 excludes SRS + architecture per REQ-023
- Section extraction for large files; max_tokens cap per artifact; partial-include on tight budget
- `tests/unit/test_context_pruner.py` — 35 tests; done-when criterion verified

### T-016 — cross-stage agent personas ✅ 2026-05-10
- `agents/reflector.md` — reviews session turn, writes to pipeline/state.md Last Reflection
- `agents/lesson-extractor.md` — distills correction flags into tasks/lessons.md entries
- `agents/skill-miner.md` — detects repeated patterns, proposes skills to .forge/proposals.jsonl
- `agents/gate-checker.md` — evaluates stage gate criteria with evidence-backed verdicts

### T-015 — 12 stage skill files ✅ 2026-05-10
- `skills/forge-{srs,product,arch,spec,plan,build,eval,deploy,monitor,feedback,resolve,release}/SKILL.md`
- Each: YAML frontmatter + When to Use / Pre-flight / Steps / Verification / Next Step
- Added "product" (→2) and "arch" (→3) aliases to `hooks/prompt-submit.py`
- 201 tests pass; `validate-plugin.py` OK

### T-014 — 12 agent persona files ✅ 2026-05-10
- `agents/requirements-analyst.md` through `agents/release-manager.md`
- Each: YAML frontmatter + Role/Goal/Context Scope/Output Contract/Workflow sections

### T-013 — plugin.json wiring ✅ 2026-05-10
- Pre-wired in T-001; validate-plugin.py confirms all 7 hooks + skills valid

### T-012 — post-tool-use.py hook ✅ 2026-05-10
- `hooks/post-tool-use.py` — session-log.jsonl append + pattern detection
- `tests/unit/test_post_tool_use.py` — 18 tests

### T-011 — pre-tool-write.py hook ✅ 2026-05-10
- `hooks/pre-tool-write.py` — 5 design system violation types (hex, px, font-family, z-index, !important)
- `tests/unit/test_pre_tool_write.py` — 35 tests
- Lesson: regex `\s*(?!pat)` false positive — use substring check instead

### T-010 — session-end.py hook ✅ 2026-05-10
- `hooks/session-end.py` — session summary to `.forge/sessions/<ts>.md`
- `tests/unit/test_session_end.py` — 18 tests

### T-009 — stop-reflect.py hook ✅ 2026-05-10
- `hooks/stop-reflect.py` — 4-step pipeline: reflect, lesson extract, gate check, skill mine (async)
- `hooks/_invoke_agent.py` — subagent invocation stub (LLM reflector deferred to T-016)
- `tests/unit/test_stop_reflect.py` — 20 tests; `tests/integration/test_stop_pipeline.py` — 8 tests
- All 130 tests pass

### T-008 — prompt-submit.py hook ✅ 2026-05-10
- `hooks/prompt-submit.py` — stage intent detection + correction flagging
- `tests/unit/test_prompt_submit.py` — 16 tests, all pass

### T-007 — session-start.py hook ✅ 2026-05-10
- `hooks/session-start.py` — loads state + lessons (≤5 project, ≤3 global) + gate summary
- Token budget: ≤2000 tokens enforced; silent exit on non-Forge dirs; graceful on corrupt state
- `tests/unit/test_session_start.py` — 17 tests covering all spec cases

### T-006 — check-gate.py ✅ 2026-05-10
- `scripts/check-gate.py` — CLI: `--stage N --cwd PATH --plugin-dir PATH` → JSON report
- Implements all 4 check types: file_exists, file_contains, script_returns_zero, all_tests_pass
- Missing helper scripts fail gracefully with "not yet implemented" message
- `tests/unit/test_check_gate.py` — 14 tests, all pass

### T-005 — gate-criteria.md ✅ 2026-05-07 (pre-authored)
- `references/gate-criteria.md` — 12 stages, 60 criteria total, all YAML parses cleanly
- Was included in foundation commit b023844; no additional implementation needed

### T-004 — forge-status skill ✅ 2026-05-10
- `skills/forge-status/SKILL.md` — reads state, renders dashboard, suggests next step
- Handles missing check-gate.py gracefully (skips gate section)
- plugin.json picks it up via `skills/*` glob — no manual registration

### T-003 — state-manager script ✅ 2026-05-10
- `scripts/_state_lib.py` — importable library: read/write/advance/append_to_section/validate
- `scripts/state-manager.py` — CLI: read, advance, set, reflect, history-add subcommands
- `tests/unit/test_state_lib.py` — 21 tests, 93% coverage on `_state_lib.py`
- `tests/unit/test_state_manager.py` — 15 tests covering all CLI subcommands via subprocess
- Atomic writes via tempfile+fsync+rename; schema validation rejects bad frontmatter
- Key lesson: PyYAML parses ISO timestamps as `datetime` — normalize on load

### T-002 — forge-init skill ✅ 2026-05-07
- `skills/forge-init/SKILL.md` with correct frontmatter (name, description, allowed-tools)
- `scripts/init-pipeline.sh` — idempotent, creates 12 stage dirs + tasks/ + .forge/
- `scripts/detect-project-type.py` — 5 project types, stdlib only, `--cwd` flag, JSON output
- `tests/unit/test_init_pipeline.py` — 5 tests passing
- `tests/unit/test_detect_project_type.py` — 9 tests passing
- 14/14 tests pass; plugin.json still validates

### T-001 — Plugin scaffolding ✅ 2026-05-07
- `.claude-plugin/plugin.json` with all 7 hook registrations
- `scripts/validate-plugin.py` (stdlib only, exits 0)
- 7 executable stub hooks in `hooks/`
- `tests/unit/test_validate_plugin.py` — 5 tests passing
- Note: `python` resolves to Python 2.7 on this system; all commands use `python3`
