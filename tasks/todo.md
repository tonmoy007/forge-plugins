# tasks/todo.md

> Active work tracker. The current task lives at the top. Completed tasks archive below.

---

## Active Task: T-002 — forge-init skill

**Goal**: Skill that scaffolds `pipeline/`, `tasks/`, `.forge/` in a target project. Detects project type. Writes initial `state.md`.

**Context**:
- See `prompts/development/T-002-forge-init.md` for the full prompt.
- Depends on T-001 (done).

---

## Archive

### T-001 — Plugin scaffolding ✅ 2026-05-07
- `.claude-plugin/plugin.json` with all 7 hook registrations
- `scripts/validate-plugin.py` (stdlib only, exits 0)
- 7 executable stub hooks in `hooks/`
- `tests/unit/test_validate_plugin.py` — 5 tests passing
- Note: `python` resolves to Python 2.7 on this system; all commands use `python3`
