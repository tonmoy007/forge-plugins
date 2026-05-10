---
name: forge-status
description: Show the current Forge pipeline status — stage, task, blockers, and progress.
  Use whenever the user asks what stage they are on, what is happening in the pipeline,
  what the current task is, what blockers exist, or says "status", "where are we",
  "what stage", "show progress", "forge status". Always use this skill before suggesting
  what to work on next in a Forge-managed project.
allowed-tools: [Read, Bash]
---

# forge-status

Display a formatted dashboard of the current pipeline state.

## When to Use

Use this skill whenever the user:
- Runs `/forge:status`
- Asks "what stage am I on?", "where are we?", "what's the current task?"
- Asks about blockers, progress, or pipeline state
- You need to orient before recommending the next step in a Forge project

## Steps

1. Read state by running:
   ```bash
   python3 ${CLAUDE_PLUGIN_DIR}/scripts/state-manager.py --cwd . read
   ```
   If the command fails with exit code 1, the project is not initialized — tell the user
   to run `/forge:init` first.

2. Parse the JSON output and build the status dashboard:

   ```
   ## Forge Pipeline Status

   Project : <project_type>          Cycle: <cycle>
   Stage   : <current_stage> / 12   [████████░░░░] (<pct>%)
   Task    : <current_task or "(none)">
   Milestone: <current_milestone or "(none)">
   Updated : <last_updated>

   Blockers:
     <each blocker on its own line, or "(none)" if blockers is empty>
   ```

   Compute the progress bar: 8 filled blocks = `current_stage / 12 * 8` blocks,
   remainder as empty blocks.

3. If `scripts/check-gate.py` exists, run:
   ```bash
   python3 ${CLAUDE_PLUGIN_DIR}/scripts/check-gate.py --stage <current_stage> --cwd .
   ```
   and append a **Gate** section showing pass/fail per criterion.
   If `check-gate.py` does not exist yet, skip this step silently.

4. Print the dashboard to the user.

5. Suggest the obvious next action based on state:
   - `current_stage == 0` → "Run `/forge:srs` to begin Stage 1 (Requirements)"
   - `blockers` non-empty → "Resolve blockers before advancing"
   - Otherwise → "Continue with `/forge:<current-stage-command>`"

## Stage Names

| Stage | Command |
|-------|---------|
| 0 | (not started) |
| 1 | `/forge:srs` |
| 2 | `/forge:ux` |
| 3 | `/forge:architecture` |
| 4 | `/forge:spec` |
| 5 | `/forge:plan` |
| 6 | `/forge:build` |
| 7 | `/forge:eval` |
| 8 | `/forge:deploy` |
| 9 | `/forge:monitor` |
| 10 | `/forge:feedback` |
| 11 | `/forge:resolve` |
| 12 | `/forge:release` |

## Verification

The skill worked correctly if:
- The dashboard renders with correct stage number and project type
- Blockers list matches what is in `pipeline/state.md`
- The next-step suggestion matches the current stage

## Example Output

```
## Forge Pipeline Status

Project : ml-pipeline          Cycle: 1
Stage   : 3 / 12   [████░░░░░░░░] (25%)
Task    : T-007
Milestone: M2
Updated : 2026-05-07T14:32:00Z

Blockers:
  (none)

Next: Continue with `/forge:spec` (Stage 4)
```
