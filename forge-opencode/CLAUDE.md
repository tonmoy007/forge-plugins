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

All 72 Python scripts work unchanged — they read `FORGE_ROOT` env var for their path.

## Dependencies

Python 3.11+, pyyaml. Same as Claude Code version.
