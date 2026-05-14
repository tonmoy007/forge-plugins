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

### 2026-05-12 — `@dataclass` on importlib-loaded modules needs `sys.modules` registration
- **Trigger**: Loading a hyphenated script via `importlib.util.spec_from_file_location(...)` + `module_from_spec(...)` + `exec_module(...)` when the script defines `@dataclass` classes with `field(default_factory=...)`
- **Rule**: Insert `sys.modules[spec.name] = module` *before* calling `spec.loader.exec_module(module)`. Without it, `@dataclass` introspection fails with `AttributeError: 'NoneType' object has no attribute '__dict__'` because `sys.modules.get(cls.__module__)` returns `None`.
- **Why**: Python 3.12 `dataclasses._is_type` resolves the defining module via `sys.modules.get(cls.__module__).__dict__`. A module created with `module_from_spec` is not auto-registered, so the lookup returns `None` and crashes at *import* time (not at test time), breaking collection entirely.
- **Tags**: [python, testing, importlib, dataclasses]

### 2026-05-07 — Hyphenated script filenames can't be imported directly
- **Trigger**: Writing tests for any script in `scripts/` with a hyphen in its filename (e.g. `validate-plugin.py`, `check-gate.py`)
- **Rule**: Use `importlib.util.spec_from_file_location` to import by file path, not by module name. Never name test imports after the hyphenated filename.
- **Why**: Python module names cannot contain hyphens; `from validate_plugin import ...` fails when the file is `validate-plugin.py`.
- **Tags**: [testing, python, imports]

### 2026-05-14 — Claude Code plugin install needs a marketplace.json, not just plugin.json
- **Trigger**: Publishing a Claude Code plugin to a GitHub repo for external install
- **Rule**: The repo needs both `.claude-plugin/plugin.json` (plugin manifest) AND `.claude-plugin/marketplace.json` (registry that points to the plugin via `"source": "."`). Install is a two-step flow: `/plugin marketplace add owner/repo` then `/plugin install <name>@<marketplace>`. There is no single-command install from a raw GitHub URL.
- **Why**: Claude Code separates "marketplace" (registry) from "plugin" (thing installed). Locally, the plugin works via `plugin.json` alone because Claude Code is reading the directory directly. From a remote repo, the marketplace.json is what tells Claude Code which plugins the repo offers.
- **Tags**: [claude-code, plugin, marketplace, install, distribution]

### 2026-05-14 — Claude Code marketplace.json `source` must be an object or a path to a plugin directory, never `"."` or repo-root
- **Trigger**: Publishing a single-plugin marketplace from a GitHub repo
- **Rule**: Use `"source": {"source": "github", "repo": "owner/repo"}` if the plugin occupies the whole repo, OR `"source": "./plugins/<name>"` if the plugin lives in a subdirectory. Never `"source": "."` — that fails with "source type your version does not support" on most Claude Code versions.
- **Why**: The `source` field expects either an explicit source-object (github/url/git-subdir) or a relative path pointing to the plugin's own directory (one containing `.claude-plugin/plugin.json`). The shorthand `"."` resolves to the marketplace directory itself, not a plugin directory.
- **Validation**: Run `/plugin validate .` from the marketplace directory before pushing — it catches schema errors locally.
- **Tags**: [claude-code, plugin, marketplace, schema, distribution]

### 2026-05-14 — Claude Code plugin.json: auto-discover by default; explicit arrays are paths, not globs
- **Trigger**: Setting up `.claude-plugin/plugin.json` for a plugin with agents/skills/commands at standard locations
- **Rule**: Omit `agents`/`skills`/`commands`/`hooks` fields entirely — Claude Code auto-discovers from `./agents/*.md`, `./skills/*/SKILL.md`, `./commands/*.md`, `./hooks/hooks.json`. Only declare them if files live in non-standard locations.
- **If declared**: `agents` is an array of file paths (each agent = one .md file). `skills` is an array of directory paths (each skill = one folder with SKILL.md inside). No globs. No object forms. The asymmetry is real — agents are files, skills are directories.
- **Why**: The validator rejects globs, single strings, and object forms with the unhelpful message `"Invalid input"`. Auto-discovery sidesteps all of this and reduces maintenance burden — adding a new agent doesn't require a plugin.json edit.
- **Tags**: [claude-code, plugin, manifest, schema, auto-discovery]

### 2026-05-14 — Claude Code plugin.json: omit declarations, use CLAUDE_PLUGIN_ROOT, drop unsupported fields
- **Trigger**: Authoring `.claude-plugin/plugin.json` for first publish
- **Rules**:
  - Omit `agents`/`skills`/`commands` fields — auto-discovery from standard locations is the supported path. Globs (`"agents/*"`) explicitly fail validation with "Invalid input".
  - Use `${CLAUDE_PLUGIN_ROOT}` for plugin-relative paths in hook commands. `${CLAUDE_PLUGIN_DIR}` doesn't exist and expands to empty string.
  - Hook command objects accept `type`, `command`, `timeout` — not `async`. Implement async by detaching a subprocess inside the script.
  - Skip fields not in the documented schema: `displayName`, `claude_code_version`, `engines`, `async`. They're either ignored or trigger warnings; document those constraints in README instead.
  - Schema URL: `https://json.schemastore.org/claude-code-plugin-manifest.json` (real). `https://claude.ai/schemas/plugin.v1.json` doesn't exist.
- **Why**: The validator rejects unknown shapes with unhelpful messages. Auto-discovery + minimal declared fields = fewer ways to break.
- **Validation**: `/plugin validate .` catches these before push.
- **Tags**: [claude-code, plugin, manifest, schema, hooks, env-vars]

### 2026-05-14 — Slash command name = plugin name + skill `name:` frontmatter, not directory name
- **Trigger**: Plugin installs successfully but `/<expected-command>` returns "Unknown command"
- **Rule**: Slash commands from plugin skills follow `/<plugin-name>:<skill-name>`, where `plugin-name` is from `plugin.json` and `skill-name` is from the `name:` field in `SKILL.md` frontmatter. The skill directory name is NOT the command — only the frontmatter `name:` matters.
- **Diagnosis**: Run `/help` to see what commands actually registered. If your expected command isn't there, check (a) `plugin.json` "name" matches expected prefix, (b) `SKILL.md` has YAML frontmatter with `name:` field matching expected suffix.
- **Why**: Easy to assume directory name → command name. They're independent. A skill in `skills/forge-init/` with frontmatter `name: init` becomes `/<plugin>:init`, not `/<plugin>:forge-init`.
- **Tags**: [claude-code, plugin, skills, slash-commands, naming]

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
