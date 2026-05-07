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
