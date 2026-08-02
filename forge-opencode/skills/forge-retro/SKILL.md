---
name: forge-retro
description: Run a cycle-completion retrospective after Stage 12 (Release). Synthesizes
  what went well, what didn't, lessons captured, and pending skill proposals into
  `pipeline/12-release/retro.md`. Use when the user runs /forge:retro, says
  "retrospective", "retro", "post-mortem", or asks to close out a release cycle in
  a Forge project.
allowed-tools: [Read, Write, Bash, Glob, Grep]
---

# forge-retro

Close out a release cycle. Synthesize the cycle's history, blockers, lessons, and
mined skill proposals into a single retrospective document the user can review,
share, and act on for the next cycle.

## When to Use

- User runs `/forge:retro`
- Stage 12 (Release) gate has just passed
- User says "retro", "retrospective", "post-mortem", "wrap up the cycle"
- Before starting a new cycle, to lock in lessons and approve mined skills

## Pre-flight

Confirm the project is at the right point:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py --cwd . read
```

If `pipeline/state.md` is missing, tell the user the project is not Forge-managed
and suggest `/forge:init`. If `current_stage < 12`, warn that the cycle is not
complete and ask whether to proceed early (acceptable for mid-cycle pulse checks).

Refresh the skill-mining results so the retro shows the latest proposals:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/skill_miner_bg.py --forge-dir .forge --cwd .
```

## Steps

### 1. Collect cycle inputs

Read each of these in parallel — they all contribute to the retro:

- `pipeline/state.md` — current stage, cycle, stage history, last reflection, blockers
- `tasks/todo.md` — Archive section (completed tasks for this cycle)
- `tasks/lessons.md` — lessons captured (filter to entries dated within this cycle)
- `.forge/sessions/*.md` — session summaries written by `session-end.py`
- Pending skill proposals:
  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/scripts/skill-approval.py --cwd . list
  ```

### 2. Identify what went well

From the inputs above, extract:
- Stages whose gate passed on the first attempt (no rework loops in state history)
- Tasks completed ahead of plan or with notably clean commits
- Reflections containing positive markers ("clean", "shipped", "no rework",
  "tests green on first run")
- Successful design decisions visible in `build/05-implementation/decisions.md`
  (or the project's equivalent)

Write 3–5 concrete bullets. **Cite the source** (task ID, stage, file) for each.

### 3. Identify what didn't go well

From the inputs above, extract:
- Blockers that took > 1 session to clear (look at `blockers:` in state.md history)
- Gate criteria that failed and required retries
- Lessons added during this cycle — each lesson implies a prior mistake worth surfacing
- Sessions whose `session-end.py` summary flagged corrections
- Stages that took disproportionately long versus the plan

Write 3–5 concrete bullets. **Cite the source** for each.

### 4. Summarize lessons captured

From `tasks/lessons.md`, list every `###` entry whose date falls within this cycle.
Render as a table:

| Date | Title | Tags |
|------|-------|------|
| YYYY-MM-DD | Short title | tags |

If lessons were promoted to `~/.forge/global-lessons.yaml` by `promote-lessons.py`,
note which ones and the projects that triggered promotion.

### 5. Surface skill proposals

From the JSON returned by `skill-approval.py list`, render each pending proposal:

```
- **<slug>** (signature `<sig>`, <N> occurrences)
    description: <description>
    Approve: python3 scripts/skill-approval.py approve --slug <slug>
    Reject:  python3 scripts/skill-approval.py reject  --slug <slug>
```

If there are none, write a single line: *"No skill proposals pending. Patterns
may not have reached the frequency threshold yet."*

### 6. Action items for next cycle

Propose 2–4 concrete commitments the user should agree to before the next cycle.
Examples: "Add CI step that runs `check-gate.py --stage 7` automatically",
"Promote lesson L-007 from cycle-local to project-wide", "Approve mined skill
`forge-X` and reject `forge-Y`."

Each action item must have:
- A specific verb (add, remove, configure, approve, document)
- A target (file, command, decision)
- A deadline or trigger (next cycle start, next Stage 6, etc.)

### 7. Write the retro file

Write the full retro to `pipeline/12-release/retro.md` (create the directory if
absent). Use this structure exactly so future cycles' retros are comparable:

```markdown
# Retrospective — Cycle <N>

**Project**: <project_type>
**Cycle**: <cycle> (started <start_date>, completed <end_date>)
**Stages completed**: <count>/12
**Tasks completed**: <count>
**Sessions**: <count>

## What Went Well

- ...

## What Didn't Go Well

- ...

## Lessons Captured

| Date | Title | Tags |
|------|-------|------|
| ... | ... | ... |

## Skill Proposals

- ...

## Action Items

- [ ] ...
- [ ] ...
```

If `pipeline/12-release/retro.md` already exists (e.g., a prior cycle), append a
`# Retrospective — Cycle <N>` block at the top rather than overwriting.

### 8. Display summary

Print to the user:

```
📋 Retro written to pipeline/12-release/retro.md
   <bullets summarizing top item from each section>

Next steps:
  - Review the retro
  - Approve or reject pending skill proposals
  - Commit the retro before starting the next cycle
```

## Verification

The skill worked correctly if:
- `pipeline/12-release/retro.md` exists and contains all six section headers
  (`What Went Well`, `What Didn't Go Well`, `Lessons Captured`, `Skill Proposals`,
  `Action Items`, plus the header block with project/cycle/stage counts)
- Every bullet in "What Went Well" / "What Didn't Go Well" cites a concrete source
  (task ID, stage number, file path, session timestamp)
- "Lessons Captured" reflects the actual contents of `tasks/lessons.md`
- "Skill Proposals" matches the output of `skill-approval.py list`
- The user can take action — approve a proposal, file an issue, or schedule a
  decision — directly from the retro without re-discovering context

## Notes

- The retro is generated from inputs, not from your memory of the session. Always
  read the files in step 1 — do not paraphrase from conversation context.
- If the user disagrees with a bullet, treat the disagreement as a correction
  (`prompt-submit.py` will flag it) and add a lesson via the standard flow rather
  than silently editing the retro.
- This skill calls `skill_miner_bg.py` (the v0.3.5 semantic miner) and
  `skill-approval.py list` directly. If either is missing in the project's
  `.claude-plugin/` install (older Forge version), surface that clearly rather
  than failing silently.
