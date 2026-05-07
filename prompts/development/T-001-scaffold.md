# T-001: Plugin Scaffolding

## Context

This is the **first task** in the build. Before this task there is no plugin — only the build
artifacts (SRS, architecture, spec, plan).

Read these before starting:
- `CLAUDE.md` — working principles
- `build/01-srs/srs.md` §2.2 — slash command requirements
- `build/02-architecture/architecture.md` §2 — component boundaries
- `build/03-spec/technical-spec.md` §1 — exact `plugin.json` schema

You need to know:
- The plugin is named `sdlc-orchestrator` (display name "Forge")
- It targets Claude Code v2.1.0+
- It will eventually have 16 skills, 16 agents, 7 hooks
- For T-001, we're **only** creating the scaffolding — no real implementation

## Task

Create the plugin scaffold that allows the rest of the work to land.

**Files to create**:

1. **`.claude-plugin/plugin.json`** — exactly as specified in technical-spec.md §1
   - Use the full schema from the spec
   - The `hooks` section should reference all 7 hook scripts (which don't exist yet — that's fine; T-007–T-012 will create them)
   - Skills and agents directories are referenced via globs (`skills/*`, `agents/*`)

2. **`scripts/validate-plugin.py`** — a small Python script that:
   - Parses `.claude-plugin/plugin.json`
   - Validates required fields are present (`name`, `version`, `claude_code_version`)
   - Validates hook events use known event names
   - Checks that referenced hook scripts exist (warns, doesn't fail, since they're stubs at this point)
   - Returns exit code 0 on success, 1 on failure
   - Uses stdlib only (no pyyaml/etc — this script must work before deps are installed)

3. **Stub hook scripts** in `hooks/` — empty placeholders so plugin.json references resolve:
   - `hooks/session-start.py`, `hooks/prompt-submit.py`, `hooks/pre-tool-write.py`,
     `hooks/post-tool-use.py`, `hooks/stop-reflect.py`, `hooks/subagent-stop.py`,
     `hooks/session-end.py`
   - Each is a Python file with shebang, a TODO comment, and `sys.exit(0)`
   - Each is executable (`chmod +x`)

4. **`requirements.txt`** — Python dependencies for scripts (not hooks):
   ```
   python-frontmatter>=1.0
   pyyaml>=6.0
   pytest>=7.0
   ```

5. **`.gitignore`** — covers Python (`__pycache__/`, `*.pyc`, `.pytest_cache/`),
   editor (`.vscode/`, `.idea/`), and Forge-specific (`.forge/sessions/`, `*.log`)

6. **`tests/unit/test_validate_plugin.py`** — a basic test:
   - Validates a good plugin.json passes
   - Validates a missing-name plugin.json fails

## Definition of Done

- [ ] `.claude-plugin/plugin.json` validates against technical-spec.md §1
- [ ] `python scripts/validate-plugin.py` exits 0
- [ ] All 7 stub hook scripts exist and are executable
- [ ] `pytest tests/unit/test_validate_plugin.py` passes
- [ ] `.gitignore` and `requirements.txt` exist with sensible content
- [ ] No actual hook logic implemented (those are T-007–T-012)
- [ ] No skills or agents created (those are T-014, T-015)

## Verification

Run these in order; all must succeed:

```bash
# 1. Plugin JSON parses
python -c "import json; json.load(open('.claude-plugin/plugin.json'))"

# 2. Validator script runs
python scripts/validate-plugin.py
echo "Exit: $?"  # must be 0

# 3. Hook stubs are executable
for h in hooks/*.py; do
  test -x "$h" || { echo "FAIL: $h not executable"; exit 1; }
done

# 4. Hook stubs run without error
for h in hooks/*.py; do
  echo '{}' | python "$h" || { echo "FAIL: $h crashed"; exit 1; }
done

# 5. Tests pass
pytest tests/unit/test_validate_plugin.py -v
```

## Commit

```
feat(T-001): plugin scaffolding with validation script

- .claude-plugin/plugin.json with full hook registration
- scripts/validate-plugin.py validates schema and references
- 7 stub hook scripts (executable, exit 0)
- requirements.txt, .gitignore
- tests/unit/test_validate_plugin.py

Ref: T-001
REQ: REQ-010, REQ-011, REQ-012
```

## Update Trail

After finishing:

1. Update `build/05-implementation/progress.md`:
   - T-001 status: 🟢 done, with date and commit hash
   - Update "Current task" to T-002

2. Update `tasks/todo.md`:
   - Move T-001 to archive
   - Set active task to T-002

3. If you learned anything (about plugin.json schema quirks, validation gotchas, etc.):
   - Add to `tasks/lessons.md`

4. Add to `build/05-implementation/decisions.md` if you made any non-obvious choices.

## Notes

- Keep it minimal. This task is foundation; later tasks fill in the actual logic.
- The hook stubs MUST exit 0 — if they crash, every Claude Code session breaks until T-007+ fixes them.
- Don't implement validation beyond what's listed — over-engineering at this stage breaks future tasks.
