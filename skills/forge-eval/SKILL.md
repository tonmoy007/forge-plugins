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
2. Confirm `pipeline/01-srs/srs.md` and `pipeline/04-spec/technical-spec.md` exist.
3. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-gate.py --stage 6` to see Stage 6 status.
   If critical criteria fail, warn the user before proceeding.
4. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 7` to load project-type evaluation criteria. **Every** profile criterion in `additional_criteria` (e.g., ML: model accuracy, GPU memory, drift detection; API: contract tests, load test, auth bypass; fullstack: Lighthouse, WCAG AA, responsive breakpoints; CLI: --help text, exit codes; library: API surface, semver, doc coverage) **must appear as a row in the eval matrix** with a pass/fail verdict and evidence.

## Steps

1. Read `agents/evaluator.md` to load the Evaluator persona.
2. Adopt that persona — you are now the Evaluator.
3. Read `pipeline/01-srs/srs.md` to enumerate all REQ-IDs.
4. Follow the Evaluator workflow: run tests, check each REQ-ID for evidence, assess NFRs. Then evaluate each `additional_criteria` row from the profile loaded in pre-flight — for an ML project this includes the drift detection criterion (G7-ML-005).
5. Write `pipeline/07-evaluation/eval-report.md` per the Output Contract. The eval matrix must explicitly list every profile criterion alongside REQ-IDs and NFRs.
6. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 7` to mark Stage 7 active.

## Verification

After running, confirm:
- `pipeline/07-evaluation/eval-report.md` exists with per-REQ-ID verdicts
- Test results are documented (not just "tests pass")
- `pipeline/state.md` shows `current_stage: 7`

## Next Step

Derive the hint from the canonical stage table — never hardcode it
(REQ-NEXTHINT-001, single source of truth). Run the helper and present its
output to the user verbatim:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 7
```

(If the eval found gaps, fix them and re-run this stage before advancing; the
hint above is the handoff once all requirements pass.)
