# CLAUDE.md — Forge for OpenCode

## What This Is

Forge ported from Claude Code to OpenCode. Same 12-stage gated SDLC pipeline,
same learning system, different plugin API.

## How It Works

OpenCode plugin (`plugin.js`) routes lifecycle events to Python hook scripts.
Skills/agents/scripts are identical to the Claude Code version.

## Hook Files

- `hooks/session-start.py` — state injection at session start
- `hooks/prompt-submit.py` — intent detection on user messages
- `hooks/pre-tool-write.py` — design system enforcement
- `hooks/post-tool-use.py` — session logging, pattern tracking
- `hooks/stop-reflect.py` — reflection, lesson extraction, gate check
- `hooks/pre-compact.py` — autopilot checkpoint before compaction
- `hooks/session-end.py` — session summary, cleanup
- `hooks/_state_lib.py`, `_state_read.py`, `_hook_runner.py` — shared helpers

## Commands

Same as Claude Code version: `/forge:init`, `/forge:srs`, `/forge:status`, etc.

## Differences from Claude Code Version

1. **Event model**: OpenCode has more granular events (32+ vs 6)
2. **Blocking**: OpenCode uses `override: { decision: 'deny' }` instead of exit code 2
3. **Context injection**: OpenCode uses `console.log()` instead of `additionalContext` JSON
4. **Plugin location**: `~/.config/opencode/plugin/forge-opencode/` or `.opencode/plugin/forge-opencode/`

## Environment Variables Set by Plugin

- `FORGE_ROOT` → plugin root directory
- `FORGE_PROJECT_ROOT` → user's working directory
- `CLAUDE_PLUGIN_ROOT` → same as FORGE_ROOT (backward compat)
- `CLAUDE_PROJECT_DIR` → same as FORGE_PROJECT_ROOT (backward compat)

## Scripts

Most Python scripts work unchanged — they read `FORGE_ROOT` env var for their path.
Two scripts have diverged from the root Claude Code plugin specifically for this
port (root and `forge-opencode/` are no longer byte-identical for these):

- `scripts/extract-lessons.py` gained a `--propose` flag (emits YAML to stdout
  instead of writing `tasks/lessons.md` directly) — `hooks/stop-reflect.py`'s Step 2
  now calls it with `--cwd`/`--input`/`--propose` and `cwd=` pinned on the
  subprocess. Previously it was called with `--transcript`/`--since-flag`, which
  don't exist in the script's argparse — every invocation failed with an argparse
  usage error (exit 2), silently, so lessons were never written under this port.
- `scripts/validate-traceability.py` is new (see Commands above).

## Dependencies

Python 3.11+, pyyaml. Same as Claude Code version.
