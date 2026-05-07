# T-003: state-manager.py Script

## Context

T-002 created the pipeline scaffold including `pipeline/state.md`. Now we need a
programmatic interface to read/write that file — every hook and several scripts will use it.

Read before starting:
- `build/02-architecture/architecture.md` §4.2 (state file format)
- `build/03-spec/technical-spec.md` §3.1 (state-manager CLI)
- `build/03-spec/technical-spec.md` §6.1 (state.md schema)

Key design point: `state.md` has YAML frontmatter for machine reading, plus markdown body
for humans. The script reads/writes the frontmatter + appends to body sections without
disturbing the rest.

## Task

Create `scripts/state-manager.py` with the following CLI:

```bash
python scripts/state-manager.py read
# → JSON of frontmatter

python scripts/state-manager.py read --field current_stage
# → just that field's value

python scripts/state-manager.py advance
# → increments current_stage, updates last_updated, returns new state JSON

python scripts/state-manager.py advance --to 6
# → jumps to specific stage (with warning if skipping)

python scripts/state-manager.py set --field current_task --value T-007
# → sets a single field

python scripts/state-manager.py reflect "<text>"
# → appends to "## Last Reflection" section in body

python scripts/state-manager.py history-add --stage 1 --result passed --note "..."
# → appends a row to "## Stage History" table
```

**Implementation requirements**:

1. Use `python-frontmatter` lib (already in requirements.txt)
2. Atomic writes: write to `state.md.tmp`, fsync, rename
3. All operations idempotent where possible
4. Schema validation: refuse to write invalid frontmatter (use a small validation function)
5. CWD detection: if not in a Forge project (no `pipeline/state.md`), error clearly with exit code 1
6. JSON output to stdout for read; status messages to stderr

## Files to Create

1. **`scripts/state-manager.py`** — the CLI
2. **`scripts/_state_lib.py`** — reusable functions importable by hooks (so hooks don't shell out)
   - `read_state(cwd) -> dict`
   - `write_state(cwd, frontmatter_dict) -> None`
   - `advance_stage(cwd, to=None) -> dict`
   - `append_to_section(cwd, section_title, content) -> None`
   - `validate_frontmatter(data) -> tuple[bool, list[str]]`
3. **`tests/unit/test_state_manager.py`** — covers all CLI subcommands
4. **`tests/unit/test_state_lib.py`** — covers all _state_lib functions

## Definition of Done

- [ ] All CLI subcommands implemented and tested
- [ ] `_state_lib.py` exposes a clean API for hook use
- [ ] Atomic writes verified by test (interrupt write, file remains valid)
- [ ] Schema validation rejects invalid frontmatter
- [ ] Tests cover happy path + error cases (no pipeline/, invalid YAML, missing fields)
- [ ] Test coverage > 90% on state-manager.py (run `pytest --cov`)

## Verification

```bash
# Setup test pipeline
cd /tmp && rm -rf forge-test && mkdir forge-test && cd forge-test
bash $OLDPWD/scripts/init-pipeline.sh

# Read works
python $OLDPWD/scripts/state-manager.py read
python $OLDPWD/scripts/state-manager.py read --field current_stage
# Expect: 0

# Advance works
python $OLDPWD/scripts/state-manager.py advance
python $OLDPWD/scripts/state-manager.py read --field current_stage
# Expect: 1

# Set works
python $OLDPWD/scripts/state-manager.py set --field current_task --value T-007
python $OLDPWD/scripts/state-manager.py read --field current_task
# Expect: T-007

# Reflection appends
python $OLDPWD/scripts/state-manager.py reflect "Test reflection at $(date -Iseconds)"
grep "Test reflection" pipeline/state.md
# Should match

# History add
python $OLDPWD/scripts/state-manager.py history-add --stage 1 --result passed --note "test"
grep -A 3 "Stage History" pipeline/state.md

# Error case: not in pipeline
cd /tmp && python $OLDPWD/scripts/state-manager.py read 2>&1
# Should error with exit 1

# Tests
cd $OLDPWD
pytest tests/unit/test_state_manager.py tests/unit/test_state_lib.py -v --cov=scripts
# Expect: > 90% coverage
```

## Commit

```
feat(T-003): state-manager script and reusable state library

- scripts/state-manager.py CLI for state.md operations
- scripts/_state_lib.py for in-process use by hooks
- Atomic writes via tempfile+rename
- Schema validation
- Unit tests covering CLI and library

Ref: T-003
REQ: REQ-002, REQ-003, REQ-004
```

## Update Trail

1. progress.md → T-003 🟢 done, current → T-004
2. todo.md → archive T-003, activate T-004
3. lessons.md → any insights about frontmatter/atomic writes
4. decisions.md → ADR-style note if you chose `python-frontmatter` vs alternatives

## Notes

- Hooks will import from `_state_lib.py`, NOT shell out to state-manager.py — performance.
- `_state_lib.py` has stdlib-only dependencies for parsing where possible (use `python-frontmatter` only at the boundary; keep the rest stdlib).
- This script is hot path — every session-start hook reads state. Optimize for fast reads.
