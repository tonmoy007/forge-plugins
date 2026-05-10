# tasks/todo.md

> Active work tracker. The current task lives at the top. Completed tasks archive below.

---

## Active Task: T-005

**Goal**: `references/gate-criteria.md` — machine-readable YAML exit criteria for all 12 stages.

**Context**:
- Depends on T-001 (done). Can proceed independently of T-004.
- See `build/04-plan/task-dag.md` T-005 for details.

---

## Archive

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
