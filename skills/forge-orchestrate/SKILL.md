---
name: forge-orchestrate
description: Drive the full 12-stage Forge pipeline end-to-end by adopting the
  Orchestrator persona — runs each stage's own skill in turn, checks its gate, and
  explicitly advances and verifies pipeline/state.md before moving on. Use when the
  user runs /forge:orchestrate, says "orchestrate the pipeline", "run the whole
  pipeline", "drive this end-to-end", "take this from SRS to release", or "act as
  the pipeline orchestrator". For self-healing / background-dispatch /
  context-checkpointed runs, prefer /forge:autopilot instead (see Relationship note
  below).
allowed-tools: [Read, Bash, Edit, Write]
---

# /forge:orchestrate — full-pipeline orchestration

`/forge:orchestrate` is a dedicated, single-purpose answer to "run the pipeline for
me." It adopts the Orchestrator persona (`agents/orchestrator.md`) and walks the
pipeline stage-by-stage, reusing each stage's own `/forge:*` skill — never
reimplementing stage logic — while owning one thing no other driver in the system
treats as a checked postcondition: verifying `pipeline/state.md` actually advanced
after every single stage, not just assuming `state-manager.py advance`'s exit code
means the write landed.

## When to Use

- `/forge:orchestrate` (defaults to running through to stage 12, or the current
  cycle's exit stage).
- `/forge:orchestrate to stage N` — run up to and including stage N.
- `/forge:orchestrate iteration` / `hotfix` / `tech-debt` — run one of the named
  cycles from `references/stage-order.md`'s `cycles` table (entry → exit).
- The user wants several stages driven without issuing each `/forge:*` command by
  hand, and wants a persona explicitly accountable for the pipeline bookkeeping.

## When NOT to Use

- A single stage → just run that stage's own command (e.g. `/forge:build`).
- The user wants self-heal on gate failure, background dispatch, or context-window
  checkpointing → that's `/forge:autopilot`, which already implements all three (see
  Relationship note below); don't duplicate that machinery here.
- The user wants to override a known blocker → `/forge:force-advance`, not this.

## Relationship to `/forge:autopilot`

Both skills drive multiple stages. Use this table to route:

| Need | Use |
|---|---|
| Self-heal a blocked gate via `/forge:resolve` | `/forge:autopilot` |
| Background/headless dispatch, session reuse | `/forge:autopilot` |
| Context-window checkpoint/rotate on a long run | `/forge:autopilot` |
| A named, dedicated persona driving the run with a hard verify-every-advance rule | `/forge:orchestrate` (this skill) |

They are not mutually exclusive: `/forge:orchestrate`'s per-stage loop is
deliberately simpler (no self-heal, no background mode) so the state.md verification
step is the one thing it can never skip — including cases where autopilot's own
advance step (`state-manager.py advance` + `autopilot.py record`) doesn't itself
re-read `state.md` afterward.

## Steps

1. **Adopt the persona.** Read `agents/orchestrator.md` and follow it completely for
   the rest of this run — it is your operating protocol, not background reading.

2. **Orient.**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py read --cwd .
   ```
   If `pipeline/state.md` doesn't exist, tell the user to run `/forge:init` first and
   stop. Note `current_stage` and `cycle`.

3. **Resolve the plan.** Read `references/stage-order.md` in full. Determine the
   ordered list of stages to run:
   - No argument → from `current_stage + 1` through 12 (or the current cycle's
     `exit`, if `current_stage` falls inside a non-`full` cycle's `entry..exit`
     range).
   - `to stage N` → from `current_stage + 1` through `N`.
   - A cycle name (`iteration`/`hotfix`/`tech-debt`) → that cycle's `entry..exit`
     range, only if `current_stage` is at or before `entry`.
   If the request is ambiguous about scope, ask once (bundled, not a drip) before
   starting.

4. **Pre-flight the first stage in the plan:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py preflight --stage {first_stage} --cwd .
   ```
   A non-zero exit means the prerequisite artifact is missing — stop and relay the
   error (it names the missing file and the skill that produces it).

5. **Loop over the plan, one stage at a time.** For each `{stage}`:

   a. Narrate: `[Forge] orchestrator: stage {stage} — {label from stage-order.md}`.

   b. **Run the stage.** Read that stage's row in `stage-order.md` for its `agent`
      and `skill`, then read and follow `skills/forge-<name>/SKILL.md` exactly (the
      same file that stage's own `/forge:*` command would run) — including its own
      persona-adoption step. Do not skip or summarize that skill's steps.

   c. **Check the gate:**
      ```bash
      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-gate.py --stage {stage} --cwd . \
        --plugin-dir ${CLAUDE_PLUGIN_ROOT}
      ```
      Parse the JSON `details[]`. Any `severity: blocker` entry with `passed: false`
      → **STOP**: print the unmet blockers verbatim and tell the user to fix them
      (or run `/forge:autopilot` for self-heal, or `/forge:force-advance --reason
      "…"` to override deliberately). Do not advance past a blocker.

   d. **Advance + reflect** on a clean gate:
      ```bash
      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to {stage + 1} --cwd .
      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/stage-reflect.py --stage {stage} --cwd . \
        --gate-status pass
      ```

   e. **Verify the advance landed** — this is the step this skill exists to
      guarantee:
      ```bash
      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py read --cwd .
      ```
      Confirm `current_stage` now equals `{stage + 1}`. If it does not, STOP
      immediately and report a state.md write failure — never tell the user the
      stage completed when the file disagrees.

   f. If `{stage}` was the last one in the plan, or `{stage} == 12`, exit the loop.

6. **Finish.** Summarize: stages completed this run, the final `current_stage` (read
   fresh, not assumed), and the `next_hint`:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage {last completed stage}
   ```
   If stage 12 completed, say the cycle is done, point to `/forge:retro`, and note
   the next advance wraps to `(cycle + 1, stage 0)`.

## Verification

After a run, these should hold:

- `pipeline/state.md`'s `current_stage` matches exactly what was reported to the
  user — never inferred, always re-read after each `advance`.
- Every stage the loop claims to have completed has a passing gate recorded (check
  `check-gate.py`'s output for that stage, or the stage's `reflection.md`).
- A run that stopped at a blocker left `state.md` at the *last successfully verified*
  stage, not at the blocked one.
- No stage's persona work happened without its own `SKILL.md` being followed (this
  skill never substitutes its own shortcut version of a stage's steps).

## Examples

**User**: "/forge:orchestrate to stage 3"

**Claude**: [adopts orchestrator persona, reads state.md: current_stage=1]
"Running stages 2–3. Starting Stage 2 (Product + UX)…" [follows forge-product's
SKILL.md, gate passes, advances, verifies current_stage=2] "Stage 2 done, verified.
Starting Stage 3 (Architecture)…" [gate fails: blocker] "🚫 Stopped at Stage 3 —
architecture.md is missing a data model section (blocker). Fix that and re-run
`/forge:orchestrate to stage 3`, or `/forge:autopilot` to self-heal."
