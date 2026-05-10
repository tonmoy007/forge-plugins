# tasks/todo.md

> Active work tracker. The current task lives at the top. Completed tasks archive below.

---

## Active Task: T-008

**Goal**: `hooks/prompt-submit.py` — detects stage intent from prompt, prunes context, flags corrections.

**Context**:
- Depends on T-003 (done).
- Done when: detects "/forge:build" → returns Stage 6 context; corrections flagged to file.
- See `build/04-plan/task-dag.md` T-008, `build/03-spec/technical-spec.md` §2.2.
- REQ-IDs: REQ-031

---

## Archive

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
