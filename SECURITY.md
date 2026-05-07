# Security

> Security considerations for the Forge plugin.

## Threat Model

Forge runs as a Claude Code plugin with full filesystem access in the user's working
context. It does NOT phone home, NOT submit telemetry, NOT include any network access
in its core flow.

### What Forge Can Do
- Read, write, and modify files in the project directory
- Read, write, and modify files in `~/.forge/`
- Spawn subprocesses (Claude subagents)
- Read environment variables visible to the user

### What Forge Will Not Do
- Make network calls in hooks (the latency budget forbids it)
- Store credentials, tokens, or secrets in any of its files
- Capture file *contents* in patterns.jsonl or session-log.jsonl (only paths and tool names)
- Transmit any data outside the user's machine
- Modify files outside the project + `~/.forge/`

## Hook Safety

Hooks run as the user. They have full filesystem access. Forge hooks are designed to:

1. Read inputs and validate them
2. Write only to documented paths (pipeline/, tasks/, .forge/)
3. Fail gracefully — a hook crash logs to stderr and exits, never blocks the session
4. Stay within latency budgets to avoid degrading the user experience

Users can audit any Forge hook by reading the Python source. There are no compiled
binaries, no obfuscation. Plain scripts.

## Pattern Logging Privacy

`.forge/patterns.jsonl` captures tool sequences for skill mining. Specifically:
- Tool name (e.g., "Edit", "Bash")
- File path being acted on (relative to project)
- Timestamp

It does NOT capture:
- File contents
- Bash command output
- User prompts
- Claude's responses

If you're working in a sensitive context and want to disable pattern logging entirely,
set in `~/.forge/config.yaml`:

```yaml
pattern_logging: false
auto_skill_creation: false
```

## Lesson Storage

Lessons captured from your corrections are stored in plain text in `tasks/lessons.md`
(project-level) and `~/.forge/global-lessons.md` (cross-project). They never leave your
machine. They're committed to git only if you choose to commit them.

If a lesson contains sensitive information you don't want recorded, edit or delete the
relevant entry from `tasks/lessons.md`. The next session-start will regenerate the YAML
mirror.

## Reporting Vulnerabilities

If you find a security issue:
- **Do not** open a public issue
- Email the maintainer directly (TBD when published)
- Provide reproducible steps and expected vs actual behavior
- Allow time for a fix before public disclosure (suggested: 30 days)

## Dependency Hygiene

Dependencies are minimal and listed in `requirements.txt`:
- `python-frontmatter` — for parsing state.md
- `PyYAML` — for parsing references and lessons
- `pytest` (dev only)

These are pinned to major versions. Updates go through normal PR review and CI.

## Code Audit

All Forge components are plain Python and Markdown. No compiled binaries. No remote code
execution. To audit a component:

```bash
# Read any hook
cat hooks/session-start.py

# Read any script
cat scripts/state-manager.py

# Validate plugin structure
python scripts/validate-plugin.py
```

If you find anything suspicious, file an issue.
