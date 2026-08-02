---
name: forge-doctor
description: Run the Forge diagnostic report to surface environment, plugin, project,
  and global-state issues. Use this skill whenever a user types `/forge:doctor`,
  reports that Forge isn't working, says hooks aren't firing, asks "is my Forge
  install OK?" or "what's wrong with Forge?", or wants a health check before
  reporting a bug. Make sure to use this skill BEFORE suggesting reinstallation or
  other heavy remediations — the doctor output frequently identifies the actual
  problem and the exact fix command to run.
allowed-tools: [Bash]
---

# Forge Doctor

Runs `scripts/doctor.py`, which performs 13 deterministic checks across environment,
plugin integrity, project state, and global state. Each failing check includes a specific
fix command. The script exits 0 if all checks pass (warnings allowed), 1 if any fail.

## When to Use

- User types `/forge:doctor` or `/forge:health`
- User says "Forge isn't working", "hooks aren't firing", "something's wrong with Forge"
- User reports a Forge bug — run this BEFORE suggesting reinstall or workarounds
- Pre-flight check before a Forge upgrade or before tagging a release
- User asks "why isn't `/forge:init` running?" or any other Forge command-failure question
- User pastes an error message that mentions Forge, hooks, or `pipeline/`

## Steps

1. Determine the project directory:
   - If `$ARGUMENTS` contains a path, use it
   - Otherwise use `${CLAUDE_PROJECT_DIR}` if set, else the current working directory
2. Run the diagnostic. Default invocation:
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py --cwd "<project>"
   ```
3. If the user wants only failures and warnings (no passes), add `--quiet`
4. If the user wants machine-readable output (parsing in a script), add `--json`
5. Present the output to the user **verbatim**. Do NOT paraphrase the `Fix:` lines —
   they are literal shell commands the user must run, not English advice
6. If the report shows recent entries under `Recent errors`, recommend the user view
   `.forge/hook-errors.log` for full tracebacks
7. After presenting the report, only restate the recommended next steps if the user
   explicitly asks "what should I do?"

## Verification

After running, all of these should be true:
- The full diagnostic report is shown to the user, including any per-check `Fix:` lines
- The exit code has been interpreted: 0 means healthy (warnings allowed), 1 means at
  least one hard failure
- If any check failed, the user knows the exact command to run next (verbatim from output)
- If the `hook_errors` check warned, the user has been pointed at `.forge/hook-errors.log`

## Examples

**User**: "Forge isn't injecting anything at session start"

**Claude**: [runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py --cwd "$(pwd)"`]

```
Forge Doctor — diagnostic report
=================================

Environment:
  ✓ Python 3.11.7
  ✓ PyYAML 6.0.1
  ✗ Claude Code 2.0.4 (≥ 2.1.0 required)
    Fix: Upgrade Claude Code via your installer

Plugin:
  ✓ plugin.json valid (name=forge, version=0.1.3)
  ✓ All 7 hooks present
  ✓ 16 agent definitions (≥ 12 expected)
  ✓ Gate criteria parsed: 60 criteria across 12 stages

Result: 1 failure.
```

"Your Claude Code is below the minimum required version — SessionStart hooks rely on the
2.1.0 schema, so they're being ignored. Upgrade Claude Code via your installer, then run
`/forge:doctor` again to confirm."

---

**User**: "/forge:doctor --json"

**Claude**: [runs with `--json`, presents JSON output verbatim without paraphrasing]

---

**User**: "Just tell me what's broken with Forge"

**Claude**: [runs with `--quiet --cwd "$(pwd)"`, presents only failures/warnings]
"Two things need attention:
- ⚠ `.forge/` not in `.gitignore` (runtime state shouldn't be committed)
  Fix: `echo '.forge/' >> .gitignore`
- ⚠ Last hook errors:
    {\"ts\": \"2026-05-15T10:23Z\", \"hook\": \"stop-reflect\", \"kind\": \"timeout\", ...}
  Fix: Investigate `/home/user/proj/.forge/hook-errors.log`"