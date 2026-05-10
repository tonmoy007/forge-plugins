# Lessons Learned

> Append-only log of corrections and the rules that prevent them.
> Read at session start. Each entry is an actionable rule, not a vague reminder.

## Format

```markdown
### YYYY-MM-DD — <short title>
- **Trigger**: <when this rule applies>
- **Rule**: <what to do (or not do)>
- **Why**: <the failure mode this prevents>
- **Tags**: [<topic1>, <topic2>]
```

---

## Lessons

### 2026-05-07 — System `python` is Python 2; use `python3` explicitly
- **Trigger**: Any time a script is run via `python` or referenced in plugin.json hook commands
- **Rule**: Always use `python3` (not `python`) in hook commands, shebang lines, and verification steps. The system `python` resolves to 2.7 on this dev machine.
- **Why**: Python 2 rejects type annotations and non-ASCII characters without a coding declaration, causing silent breakage in hooks and the validator.
- **Tags**: [python, hooks, plugin.json]

### 2026-05-10 — PyYAML parses ISO timestamps as datetime objects
- **Trigger**: Any time `python-frontmatter` (or raw PyYAML) loads a YAML file containing bare ISO-8601 timestamps (e.g. `last_updated: 2026-05-07T12:00:00Z`)
- **Rule**: After calling `frontmatter.load()`, pass the metadata dict through a normalization function that converts `datetime.datetime`/`datetime.date` to strings before validation or returning to callers.
- **Why**: PyYAML automatically coerces ISO timestamps to `datetime` objects. If your schema expects `str`, all round-trip write operations will fail with a type error.
- **Tags**: [python, frontmatter, yaml, state-manager]

### 2026-05-10 — Subprocess-tested CLIs show 0% coverage
- **Trigger**: When a CLI script is tested entirely via `subprocess.run()` (not by importing and calling functions directly)
- **Rule**: Coverage for the thin CLI layer won't register. Put all real logic in an importable library (`_state_lib.py`), keep the CLI as a thin dispatch wrapper, and measure coverage on the library. Accept 0% on the CLI entry-point file.
- **Why**: `coverage.py` only tracks the current process; subprocess children run in a separate process with no coverage instrumentation.
- **Tags**: [testing, coverage, subprocess, cli]

### 2026-05-10 — sys.exit() raises SystemExit, not Exception; catch it explicitly

- **Trigger**: Any hook that calls `_state_lib.read_state()` inside a `try/except Exception` block without first checking that `pipeline/state.md` exists
- **Rule**: Always check `(cwd / "pipeline" / "state.md").exists()` before calling `read_state()`. If you must wrap it, catch `BaseException` or `SystemExit` specifically — `except Exception` does not catch `sys.exit()`.
- **Why**: `_state_lib._ensure_state_exists()` calls `sys.exit(1)` when the file is missing. `sys.exit()` raises `SystemExit(BaseException)`, which bypasses `except Exception` and propagates uncaught, exiting the hook with code 1 instead of 0.
- **Tags**: [python, hooks, _state_lib, error-handling]

### 2026-05-10 — Regex negative lookaheads backtrack through \s* — use explicit substring checks

- **Trigger**: Writing patterns like `re.compile(r"font-family\s*:\s*(?!var\(--font)")` to skip CSS variable usage
- **Rule**: Instead of `pattern:\s*(?!keyword)`, use `re.search(r"pattern:", line) and "keyword" not in line`. The `\s*` before the lookahead lets the engine backtrack to a zero-match, placing the lookahead before the whitespace, causing false positives.
- **Why**: `\s*` is greedy but can match 0; when the lookahead fails at `\s*=N`, the engine retries with `\s*=N-1`, shifting the lookahead position before the space — where the keyword no longer appears.
- **Tags**: [python, regex, hooks, pre-tool-write]

### 2026-05-07 — Hyphenated script filenames can't be imported directly
- **Trigger**: Writing tests for any script in `scripts/` with a hyphen in its filename (e.g. `validate-plugin.py`, `check-gate.py`)
- **Rule**: Use `importlib.util.spec_from_file_location` to import by file path, not by module name. Never name test imports after the hyphenated filename.
- **Why**: Python module names cannot contain hyphens; `from validate_plugin import ...` fails when the file is `validate-plugin.py`.
- **Tags**: [testing, python, imports]

---

## Patterns by Category

### Plugin Development
*(Empty — fill as patterns emerge)*

### Hook Implementation
*(Empty)*

### Agent Authoring
*(Empty)*

### Testing
*(Empty)*

### Communication with User
*(Empty)*
