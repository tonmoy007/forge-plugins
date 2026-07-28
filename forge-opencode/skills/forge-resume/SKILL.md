---
name: forge-resume
description: Resume work on a Forge-managed project after a session restart. Reads pipeline
  state, injects the prioritized context for the current stage, shows the last reflection,
  and states the next concrete action. Use whenever the user runs /forge:resume, says
  "resume", "pick up where we left off", "continue from last session", or starts a new
  session and asks what to work on in a Forge project.
allowed-tools: [Read, Bash]
---

# forge-resume

Re-orient after a session break. Inject the stage-appropriate context and state the
exact next action — no re-discovery required.

## When to Use

- User runs `/forge:resume`
- User starts a new session and asks to continue Forge work
- User says "pick up where we left off", "resume", "what was I doing?"
- After a long gap and the context window is fresh

## Pre-flight

Run this check first:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py --cwd . read
```

If the command fails or the directory has no `pipeline/state.md`, tell the user
the project is not initialized and suggest `/forge:init`.

## Steps

### 1. Read pipeline state

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py --cwd . read
```

Extract: `current_stage`, `current_task`, `current_milestone`, `last_updated`, `blockers`.

### 2. Load stage-appropriate context

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context-pruner.py \
  --stage <current_stage> \
  --cwd . \
  --budget 1800
```

For each artifact in the returned `artifacts` list:
- Read its `content` field directly (do not re-read from disk — use what the pruner returned)
- Inject the content into your working context

These artifacts are already priority-ordered and budget-capped. Do not load additional
files beyond what the pruner returns unless the user explicitly asks.

### 3. Read last reflection

From `pipeline/state.md`, extract the **Last Reflection** section. This shows what happened
in the previous session segment. If it is empty, note "no prior reflection found."

### 4. Read recent lessons

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py --cwd . read
```

From `tasks/lessons.md`, read the 3 most recent lesson entries (those under the most recent
`###` headings). Surface any lessons tagged for the current stage.

### 5. Check gate status

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-gate.py \
  --stage <current_stage> \
  --cwd . \
  --plugin-dir ${CLAUDE_PLUGIN_ROOT}
```

Note how many gate criteria pass. If any `blocker`-severity criteria fail, surface them.

### 6. Display the resume summary

Print this exact structure (fill in the values):

```
## Forge Resume

**Project**: <project_type>   **Stage**: <current_stage>/12 (<stage_name>)
**Task**: <current_task or "(none)">   **Cycle**: <cycle>
**Last updated**: <last_updated>

### Context loaded
<list each artifact path and its token count, e.g.:>
  - pipeline/state.md (142 tokens)
  - pipeline/05-plan/task-dag.md (680 tokens)
  - pipeline/04-spec/spec.md (423 tokens)
Total: <total_tokens> / 1800 tokens

### Last reflection
<paste the Last Reflection section content, or "(none)">

### Gate status
<current_stage>/<total> criteria passing
<list any unmet blocker-severity criteria>

### Blockers
<list blockers from state.md, or "(none)">

### Next action
<one concrete sentence describing exactly what to do next>
```

### 7. Proceed

After displaying the summary, immediately continue working. Do not wait for the user to
re-explain the task — you have the context. Pick up from the `current_task` or, if that
is empty, from the next unstarted task for the current stage.

If there are unmet blocker-severity gate criteria, surface them before proceeding and
ask whether to address them first or continue anyway.

## Stage Names

| Stage | Name | Command |
|-------|------|---------|
| 0 | not started | — |
| 1 | SRS | `/forge:srs` |
| 2 | Product/UX | `/forge:product` |
| 3 | Architecture | `/forge:arch` |
| 4 | Spec | `/forge:spec` |
| 5 | Plan | `/forge:plan` |
| 6 | Build | `/forge:build` |
| 7 | Eval | `/forge:eval` |
| 8 | Deploy | `/forge:deploy` |
| 9 | Monitor | `/forge:monitor` |
| 10 | Feedback | `/forge:feedback` |
| 11 | Resolve | `/forge:resolve` |
| 12 | Release | `/forge:release` |

## Verification

The skill worked correctly if:
- The resume summary shows the correct stage, task, and project type
- Artifacts listed match what `context-pruner.py` returned for the stage
- The "Next action" is specific and actionable (not "continue working")
- You are actively working on the task within 1-2 turns, not still asking questions

## Example Output

```
## Forge Resume

**Project**: saas-api   **Stage**: 6/12 (Build)
**Task**: T-007 — implement auth middleware   **Cycle**: 1
**Last updated**: 2026-05-11T09:14:00Z

### Context loaded
  - pipeline/state.md (187 tokens)
  - pipeline/05-plan/task-dag.md (643 tokens)
  - pipeline/04-spec/spec.md (498 tokens)
  - pipeline/02-product-ux/design-system.md (201 tokens)
Total: 1529 / 1800 tokens

### Last reflection
**Timestamp**: 2026-05-11T09:14:00Z
**Stage**: 6 | **Task**: T-007
**Turns this session segment**: 4 user message(s)
**Files touched**: src/middleware/auth.py, tests/unit/test_auth.py

### Gate status
2/5 criteria passing
⚠️ Unmet blockers:
  - all_tests_pass: tests/unit/ must be green

### Blockers
(none)

### Next action
Run the failing test suite (`pytest tests/unit/test_auth.py`) and fix the 2
authentication header validation errors before proceeding to T-008.
```
