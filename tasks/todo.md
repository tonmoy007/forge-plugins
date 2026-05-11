# tasks/todo.md

> Active work tracker. The current task lives at the top. Completed tasks archive below.

---

## Active Task: T-018

**Goal**: `skills/forge-resume/SKILL.md` — `/forge:resume` reads state, injects full context for current task, continues work.

**Context**:
- Depends on T-003 (done), T-017 (done — context-pruner.py).
- Done when: After session restart, `/forge:resume` picks up exactly where last session ended.
- See `build/04-plan/task-dag.md` T-018.
- REQ-IDs: REQ-004, REQ-011

---

## Archive

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
