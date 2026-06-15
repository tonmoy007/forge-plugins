---
name: forge-autopilot
description: Drive the Forge pipeline hands-off — run stages back-to-back, checking each
  stage's gate and advancing only when it passes, stopping at the first blocker. Use when
  the user runs /forge:autopilot, says "autopilot", "run the pipeline for me", "take it
  from here", "build through to stage N", "run the next few stages automatically", or
  "drive the rest of the pipeline". Bounded and safe by default (stop-on-gate, never
  force). Stop anytime with /forge:autopilot-stop.
allowed-tools: [Read, Bash, Edit, Write, Task]
---

# forge-autopilot — bounded autonomous pipeline execution

Autopilot walks the pipeline for the user: for each planned stage it runs that stage's
agent, checks the stage gate, and **advances only on a pass** — **stopping at the first
blocker** instead of forcing past it. It generalizes `/forge:force-advance` (one gated
advance) and `/forge:build --milestone` (a within-stage batch) to a cross-stage loop.

The plan is computed deterministically by `scripts/autopilot.py`; this skill executes it
in-session (a script can't drive the Agent tool — ADR-006).

## When to Use

- `/forge:autopilot` (optionally `to stage N`, `the next K stages`, or `until a gate`).
- The user wants several stages run without issuing each `/forge:*` command by hand.

## When NOT to Use

- A single stage → just run that stage's command (e.g. `/forge:build`).
- The user wants to override a known blocker → that's `/forge:force-advance`, not autopilot.

## Safety rails (always)

- **Stop-on-gate.** On any blocking gate failure, autopilot STOPS and surfaces the
  blockers. It **never** force-advances unless `.forge/config.yaml` →
  `autopilot.allow_force: true` **and** the user supplied a reason.
- **Bounded.** It runs only the planned stages (target + `autopilot.max_stages` /
  `stop_before` caps); it never loops unbounded.
- **Interruptible.** `/forge:autopilot-stop` halts it before the next stage.
- **Background mode** (`--mode background`) is cost-capped + capability-gated and a clean
  no-op when background agents are unavailable or `FORGE_NO_BACKGROUND=1`.

## Steps

1. **Plan.** Translate the user's intent to flags and get the ordered plan:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/autopilot.py --cwd . --json \
     [--to N | --stages K | --until-gate] [--mode in-session|background] [--resume]
   ```
   Each plan item is `{stage, skill, label}`. If the plan is empty, tell the user there's
   nothing to run (already at target, or no pipeline) and stop.

2. **Loop** over the plan items **in order**. For each `{stage, skill, label}`:
   a. If `.forge/autopilot-session.json` has `stop_requested: true`, STOP (see
      `/forge:autopilot-stop`).
   b. Narrate: `[Forge] autopilot: stage {stage} — {label}`.
   c. **Run the stage** by following its command `{skill}` (e.g. `/forge:build`) — the
      stage's agent does the work. Interactive stages (SRS/spec/plan) may pause for
      CLARIFY/CONFIRM; that is expected (autopilot is hands-off, not unattended).
   d. **Check the gate**:
      ```bash
      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-gate.py --stage {stage} --cwd . \
        --plugin-dir ${CLAUDE_PLUGIN_ROOT}
      ```
      Parse the JSON `details[]`. If any `severity: blocker` is not `passed` → **STOP**:
      surface the blockers and tell the user to fix and re-run `/forge:autopilot --resume`,
      or override with `/forge:force-advance --reason "…"`. Do **not** advance.
   e. **Advance** on a clean gate:
      ```bash
      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --cwd .
      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/autopilot.py record --cwd . --stage {stage} --status done
      ```
   f. **Checkpoint policy** (`autopilot.checkpoint`): `gate` (default) — continue unless a
      gate blocks; `every` — pause for the user's OK between stages; `never` — run straight
      through.

3. **Summarize**: stages completed, where it stopped, and the next step.

## Notes

- Honor any `always` project rules surfaced in context while running each stage.
- `--resume` skips stages already recorded `done` in `.forge/autopilot-runs.jsonl`, so a
  run that stopped at a blocker continues cleanly after the fix.
- Autopilot mutates pipeline state only through `state-manager.py advance` (the sanctioned
  path) and writes its run-log only under `.forge/`.
