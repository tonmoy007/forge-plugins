---
name: forge-eval
description: Run Stage 7 of the Forge pipeline — evaluation and quality assurance.
  Use when the user says /forge:eval, wants to verify the implementation, check test
  coverage, or validate against requirements. Requires Stage 1–6. Invokes the evaluator.
allowed-tools: [Read, Write, Bash, Grep, Glob]
---

# /forge:eval — Evaluation

## When to Use

- User says `/forge:eval`
- User wants to verify the implementation, check test coverage, or validate against the SRS
- Working in a Forge project at Stage 6 or 7

## Pre-flight Check

1. Read `pipeline/state.md` — confirm Forge project.
2. Confirm `pipeline/01-srs/srs.md` and `pipeline/04-technical-spec/technical-spec.md` exist.
3. Run `python3 ${CLAUDE_PLUGIN_DIR}/scripts/check-gate.py --stage 6` to see Stage 6 status.
   If critical criteria fail, warn the user before proceeding.

## Steps

1. Read `agents/evaluator.md` to load the Evaluator persona.
2. Adopt that persona — you are now the Evaluator.
3. Read `pipeline/01-srs/srs.md` to enumerate all REQ-IDs.
4. Follow the Evaluator workflow: run tests, check each REQ-ID for evidence, assess NFRs.
5. Write `pipeline/07-evaluation/eval-report.md` per the Output Contract.
6. Run `python3 ${CLAUDE_PLUGIN_DIR}/scripts/state-manager.py advance --to 7` to mark Stage 7 active.

## Verification

After running, confirm:
- `pipeline/07-evaluation/eval-report.md` exists with per-REQ-ID verdicts
- Test results are documented (not just "tests pass")
- `pipeline/state.md` shows `current_stage: 7`

## Next Step

"Evaluation complete. If all requirements pass: `/forge:deploy`. If gaps found: fix and re-run `/forge:eval`."
