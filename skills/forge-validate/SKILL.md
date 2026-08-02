---
name: forge-validate
description: Run a full pipeline gap analysis and confirm traceability end-to-end —
  malformed IDs (wrong case/separator/digit-padding), misplaced ID definitions
  (e.g. a REQ-* heading defined outside pipeline/01-srs/srs.md), duplicate ID
  definitions, and unimplemented/orphaned requirements (a REQ/NFR/FEAT/UF never
  referenced downstream) — plus a rollup of the existing traceability-check.py and
  gate-completeness scripts. Use when the user runs /forge:validate, asks "check
  traceability", "find gaps in the pipeline", "are any requirements unimplemented",
  "validate the IDs", or wants a gap analysis before a gate/release.
allowed-tools: [Read, Bash]
---

# /forge:validate — pipeline gap analysis & traceability confirmation

`/forge:validate` runs `scripts/validate-traceability.py`, which combines four checks
the per-stage gate scripts don't cover (malformed IDs, misplaced ID definitions,
duplicate ID definitions, unimplemented/orphaned requirements) with a rollup of the
existing traceability and gate-completeness scripts, into one report.

## When to Use

- `/forge:validate` — run the full report now.
- Before a gate check or `/forge:release`, to catch drift the mechanical
  per-stage gates don't check (e.g. a requirement defined but never picked up by any
  task).
- After a big edit to `pipeline/**/*.md` (renamed/renumbered requirements, merged
  docs) to confirm nothing broke the ID chain.
- The user explicitly asks about traceability, ID hygiene, or gap analysis.

## When NOT to Use

- A single stage's gate → that's `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-gate.py
  --stage N` (via `/forge:status` or the stage's own skill), not this.
- The user wants the pipeline actually advanced → `/forge:orchestrate` or the
  specific stage's `/forge:*` command.

## Pre-flight Check

Read `pipeline/state.md` to confirm this is a Forge project. If it doesn't exist,
tell the user to run `/forge:init` first and stop — an uninitialized project has no
`pipeline/` directory for this to scan.

## Steps

1. Run the report:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate-traceability.py --cwd . \
     --plugin-dir ${CLAUDE_PLUGIN_ROOT}
   ```
2. Present the full markdown report verbatim. It has two parts:
   - **Traceability & Gate Rollup** — pass/fail per existing script
     (`traceability-check.py --full-chain`, DAG completeness/completion, SRS
     acceptance, spec coverage, NFR coverage, progress sync, TODO ticketing).
   - **Four gap-analysis sections** — Malformed IDs, Misplaced ID Definitions,
     Duplicate ID Definitions, Unimplemented / Orphaned Requirements — each with a
     count and, when non-empty, the exact id/file/reason for every finding.
3. Interpret the **Status** line for the user:
   - **CLEAN** — every rollup check passed and all four gap-analysis sections are
     empty. No action needed.
   - **ISSUES FOUND** — walk through each non-empty section and suggest the fix:
     - *Malformed*: rename the id to the canonical form the detail line names.
     - *Misplaced*: either move the definition into its home doc, or if the second
       occurrence is meant to be a reference (not a new definition), drop it down
       from a heading to inline prose.
     - *Duplicate*: the two blocks under the same heading id likely diverged —
       merge them or renumber the second one.
     - *Unimplemented*: either add the missing downstream reference (a task, a
       progress row, an eval entry) or confirm with the user it's genuinely out of
       scope and should be marked as such in the SRS.
4. If the user wants a saved copy instead of (or in addition to) the chat output:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate-traceability.py --cwd . \
     --plugin-dir ${CLAUDE_PLUGIN_ROOT} --out pipeline/validation-report.md
   ```

## Verification

- Exit code 0 = clean (every rollup check passed, all four gap sections empty),
  non-zero = at least one issue.
- Re-running after fixes should show fewer (ideally zero) findings in the sections
  that were addressed — re-run to confirm rather than assuming a fix worked.
- The rollup section's pass/fail matches what `check-gate.py` would report for the
  relevant stage — this report doesn't invent new gate semantics, it aggregates the
  existing ones plus the four new checks.

## Examples

**User**: "/forge:validate"

**Claude**: [runs the script]
"Traceability report — **ISSUES FOUND**:
- ✅ Traceability chain, DAG completeness, SRS acceptance, TODO ticketing
- ❌ NFR coverage — NFR-002 never evaluated
- Malformed IDs (1): `REQ-7` in `pipeline/01-srs/srs.md` — expected 3-digit id
- Unimplemented (1): `REQ-014` in `pipeline/01-srs/srs.md` — never referenced in
  task-dag.md, progress.md, or eval-report.md

Two things to fix: rename REQ-7 → REQ-007, and either scope REQ-014 into a task or
mark it explicitly out-of-scope."

**User**: "/forge:validate" (on a clean project)

**Claude**: [runs the script]
"**CLEAN** — traceability chain intact, all gate-completeness checks pass, and no
malformed, misplaced, duplicate, or orphaned IDs found."
