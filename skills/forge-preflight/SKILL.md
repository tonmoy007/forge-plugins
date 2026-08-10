---
name: preflight
description: Detect missing required CLIs (docker, docker compose, gh) for the
  current project and offer to install them. Use whenever the user runs
  /forge:preflight, session-start's tool advisory points here, or the user asks
  "do I have the tools I need", "is docker installed", or "can I deploy this".
  Never auto-runs an installer — every install happens only after the user
  explicitly confirms it.
allowed-tools: [Read, Bash]
---

# forge-preflight

Surfaces which required tools are missing for this project and, only after the
user confirms, runs the exact install command for one of them. This is the
**only** surface in Forge that runs an installer — `hooks/session-start.py` and
`scripts/doctor.py` only ever detect and report.

## When to Use

- User runs `/forge:preflight`
- `session-start`'s tool advisory line points here (`⚠ Required tool ... run /forge:preflight`)
- `/forge:doctor` reports a missing required tool
- User asks whether a needed CLI is installed, or hits a wall at deploy/release
  because a tool turned out to be missing

## Detect

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tool_preflight.py check --cwd .
```

This prints JSON — one entry per registry tool (`references/tool-registry.md`),
each with `present`, `version`, `required`, `reason`, and `install_cmd` fields.
Present the tools where `required` is true and `present` is false. If none, tell
the user everything required is already installed and stop here.

## Confirm, Then Install — Never Auto-Run

For each missing required tool, show its exact install command
(`install_cmd` from the JSON above — this is per-OS, resolved by
`tool_preflight.py` from the registry, never invented) and ask the user to
confirm **before running anything**. Only once the user explicitly confirms a
specific tool, run that tool's exact command via Bash. If the user declines a
tool, or does not respond affirmatively, do not run its install command — move
on to the next tool or stop. Never run an install command the user has not
seen and approved, and never install a tool the user has declined.

If a tool has no `install_cmd` for the current OS (an unsupported platform),
say so and point at the tool's own documentation instead of guessing a command.

## Report

After any installs, re-run `tool_preflight.py check --cwd .` and confirm the
tool now shows `present: true`. Summarize what was installed, what was
declined, and what remains missing.

## Orchestration Rules

This skill SHALL detect via `tool_preflight.py check` first; show every missing
required tool's exact install command before running it; run an install
command only after the user's explicit confirmation for that specific tool;
and re-check after installing.

This skill SHALL NOT run any install command without prior confirmation;
install a tool the user declined; invent an install command not sourced from
the registry; or treat a missing optional (non-required) tool as blocking
anything.
