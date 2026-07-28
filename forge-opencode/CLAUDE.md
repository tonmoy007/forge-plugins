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

Same as Claude Code version: `/forge:init`, `/forge:srs`, `/forge:status`, etc., plus
two OpenCode-only additions:

- `/forge:orchestrate` — full-pipeline driver (`agents/orchestrator.md` +
  `skills/forge-orchestrate/SKILL.md`). OpenCode's `session.idle` payload never
  carries a `transcript_path` (no OpenCode event exposes one), so
  `stop-reflect.py`'s automatic done-signal detection is permanently `False` here —
  there is no passive path to a per-stage `state.md` advance. This agent is the
  active replacement: it explicitly runs `state-manager.py advance` after every
  stage's gate passes and re-reads `state.md` to confirm the write landed, rather
  than assuming it.
- `/forge:validate` — pipeline gap analysis (`scripts/validate-traceability.py` +
  `skills/forge-validate/SKILL.md`): malformed/misplaced ID detection, unimplemented
  (orphaned) requirement detection, and a rollup of the existing traceability/gate
  scripts into one report.
- `/forge:trace-matrix` — full id x stage traceability matrix
  (`scripts/trace-matrix.py` + `agents/traceability-matrix.md` +
  `skills/forge-trace-matrix/SKILL.md`): same gap categories as `/forge:validate`,
  but each one attributed to the specific stage agent responsible for it, and
  written to `.forge/traceability-gaps.jsonl` — `hooks/session-start.py` surfaces an
  advisory note to that agent when their stage becomes active.

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
`scripts/extract-lessons.py`'s `--propose` fix and `scripts/validate-traceability.py`
+ `scripts/trace-matrix.py` + `scripts/_trace_scan.py` were built in this port first,
then ported back to the root Claude Code plugin — both trees are back in parity for
these files (no intentional divergence remains):

- `scripts/extract-lessons.py`'s `--propose` flag emits YAML to stdout instead of
  writing `tasks/lessons.md` directly — `hooks/stop-reflect.py`'s Step 2 calls it
  with `--cwd`/`--input`/`--propose` and `cwd=` pinned on the subprocess. It used to
  be called with `--transcript`/`--since-flag`, which don't exist in the script's
  argparse — every invocation failed with an argparse usage error (exit 2), so
  lessons were never written until this fix.
- `scripts/_trace_scan.py` is the shared module both `validate-traceability.py` and
  `trace-matrix.py` import — ID-scanning primitives (malformed/misplaced/
  duplicate/unimplemented detection) plus the `attribute()` helper that resolves a
  gap to its responsible `(stage, agent)` via `_stage_table.py`.
- `scripts/validate-traceability.py` and `scripts/trace-matrix.py` — see Commands
  above.

## Dependencies

Python 3.11+, pyyaml. Same as Claude Code version.
