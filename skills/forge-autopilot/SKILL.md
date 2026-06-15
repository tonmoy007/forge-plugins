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

- **Bounded self-heal, then stop-on-gate.** On a blocking gate failure, autopilot makes a
  bounded number of fix attempts via `/forge:resolve` (`autopilot.max_heal_attempts`,
  default **1**; `0` restores classic stop-on-gate), re-checking the gate after each. When
  heal is exhausted (or disabled) and blockers remain it STOPS and surfaces them. It
  **never** force-advances unless `.forge/config.yaml` → `autopilot.allow_force: true`
  **and** the user supplied a reason.
- **Bounded.** It runs only the planned stages (target + `autopilot.max_stages` /
  `stop_before` caps); it never loops unbounded.
- **Interruptible.** `/forge:autopilot-stop` halts it before the next stage.
- **Background mode** (`--mode background`) is cost-capped + capability-gated and a clean
  no-op when background agents are unavailable or `FORGE_NO_BACKGROUND=1`.

## Steps

1. **Start + plan.** Mark the session active (idempotent — warns if one is already
   running, so two autopilots don't run at once):
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/autopilot.py start --cwd .
   ```
   If it reports `already_running`, tell the user and stop unless they confirm. Then get
   the ordered plan:
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
   c. **Run the stage.** In `--mode in-session` (default), follow the stage's command
      `{skill}` (e.g. `/forge:build`) so the stage's agent does the work; interactive
      stages (SRS/spec/plan) may pause for CLARIFY/CONFIRM — that is expected (autopilot
      is hands-off, not unattended). In `--mode background`, dispatch it headlessly and
      reuse the returned session across stages for cost:
      ```bash
      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/autopilot.py dispatch --cwd . \
        --stage {stage} --skill {skill} --label "{label}" \
        [--session {prev_session_id}] [--dispatch-count {n}]
      ```
      A `status: unavailable` result means background agents are off — fall back to
      in-session or stop. Carry the returned `session_id` into the next dispatch, and
      pass `--dispatch-count` (dispatches so far on this session) so a long run rotates
      to a fresh session per `autopilot.session_max_dispatches`, bounding context growth.
      Per-stage model routing (`autopilot.models`) and the per-dispatch `$` ceiling
      (`autopilot.max_budget_usd`) are applied automatically from `.forge/config.yaml`.
   d. **Check the gate**:
      ```bash
      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-gate.py --stage {stage} --cwd . \
        --plugin-dir ${CLAUDE_PLUGIN_ROOT}
      ```
      Parse the JSON `details[]`. If any `severity: blocker` is not `passed`, **self-heal**
      before giving up (see step e); only STOP when heal is exhausted or disabled.
   e. **Self-heal a blocked gate** (REQ-AUTO-001/002). Track `attempts_used` per stage,
      starting at 0. While the gate has blockers **and**
      `autopilot.py` `should_heal` allows another attempt — i.e. `attempts_used <
      autopilot.max_heal_attempts` (default **1**; `0` = classic stop-on-gate) — run one
      bounded fix through the Stage-11 resolver, then re-check the gate:
      - In `--mode in-session` (default): run `/forge:resolve` against this stage's
        blockers (pass the failing `details[]` so the resolver knows what to fix).
      - In `--mode background`: dispatch it headlessly (cost/budget/capability gated,
        session reused):
        ```bash
        python3 ${CLAUDE_PLUGIN_ROOT}/scripts/autopilot.py heal --cwd . \
          --stage {stage} --skill /forge:resolve --label "{label}" \
          --blockers "{failing criteria}" [--session {sid}] [--dispatch-count {n}]
        ```
      After each heal, re-run `check-gate.py` (step d) and increment `attempts_used`. On a
      now-clean gate → advance (step f). When `should_heal` returns false (cap reached or
      `max_heal_attempts: 0`) and blockers remain → **STOP**: surface the remaining
      blockers and tell the user to fix and re-run `/forge:autopilot --resume`, or override
      with `/forge:force-advance --reason "…"`. Autopilot **never** force-advances on its
      own (only `allow_force: true` + a reason does).
   f. **Self-verify** (optional; only when `autopilot.verify: true` — REQ-AUTO-003). After
      the gate is clean, run an **independent, fresh-context** verifier that checks the
      artifact against the stage's intent beyond the mechanical gate:
      - In `--mode in-session` (default): spawn a verifier subagent via the `Task` tool
        (fresh context — do not hand it this loop's history) asking for a `pass`/`fail`
        verdict with reasons on whether {skill}'s artifact genuinely satisfies stage
        {stage}'s intent.
      - In `--mode background`: dispatch a schema-constrained verdict headlessly:
        ```bash
        python3 ${CLAUDE_PLUGIN_ROOT}/scripts/autopilot.py verify --cwd . \
          --stage {stage} --skill {skill} --label "{label}"
        ```
      A `fail` verdict is treated **exactly like a gate blocker**: route back into the
      self-heal loop (step e), and STOP if heal is exhausted. A broken, empty, or
      `unavailable` verifier does **not** block (it's an extra check on an already-passing
      gate) — log it and advance.
   g. **Advance** on a clean gate:
      ```bash
      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --cwd .
      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/autopilot.py record --cwd . --stage {stage} --status done
      ```
   h. **Checkpoint policy** (`autopilot.checkpoint`): `gate` (default) — continue unless a
      gate blocks; `every` — pause for the user's OK between stages; `never` — run straight
      through.

3. **Finish.** Mark the session idle (also clears any stop flag), then summarize:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/autopilot.py finish --cwd .
   ```
   Report stages completed, where it stopped (gate blocker or stop request), and the next
   step (`/forge:autopilot --resume` to continue after a fix).

## Notes

- Honor any `always` project rules surfaced in context while running each stage.
- `--resume` skips stages already recorded `done` in `.forge/autopilot-runs.jsonl`, so a
  run that stopped at a blocker continues cleanly after the fix.
- Autopilot mutates pipeline state only through `state-manager.py advance` (the sanctioned
  path) and writes its run-log only under `.forge/`.
