---
name: forge-trace-matrix
description: Generate the full ID x stage traceability matrix and a gap report,
  with each gap attributed to the stage agent responsible for resolving it. Use
  when the user runs /forge:trace-matrix, asks "generate a traceability matrix",
  "which requirements are missing", "show me ID coverage across the pipeline",
  "who owns this gap", or wants to see the whole pipeline's ID health at a glance.
  Writes .forge/traceability-gaps.jsonl, which session-start.py reads to advise
  the responsible agent when their stage becomes active.
allowed-tools: [Read, Bash]
---

# /forge:trace-matrix — full traceability matrix & gap attribution

`/forge:trace-matrix` runs `scripts/trace-matrix.py`, which adopts the
Traceability Auditor persona (`agents/traceability-matrix.md`) to produce:

1. **A matrix** — every id found anywhere under `pipeline/` as a row, every stage
   directory with activity on it as a column, showing where each id is *defined*
   vs merely *referenced*.
2. **A gap report** — the same four categories `/forge:validate` checks (malformed,
   misplaced, duplicate, unimplemented), each one attributed to the specific
   `(stage, agent)` responsible for fixing it.

Unlike `/forge:validate` (a pass/fail gate-style check), this skill's primary
output is the *matrix* — a map of the whole pipeline's ID coverage — with the gap
list as a secondary, attributed punch list.

## When to Use

- `/forge:trace-matrix` — generate and present the current matrix + gap report.
- The user asks "which requirements haven't been picked up," "who's responsible
  for X," or wants to see ID coverage across every stage at once.
- Periodically during a long-running project, or before a milestone review, to
  catch drift the per-stage gates don't surface on their own.

## When NOT to Use

- The user wants a pass/fail gate check → `/forge:validate` (same underlying gap
  categories, but framed as a report you can act on immediately, not a matrix).
- The user wants the pipeline advanced → `/forge:orchestrate` or a specific
  stage's `/forge:*` command.

## Relationship to `/forge:validate`

Both are built on `scripts/_trace_scan.py` and detect the same four gap
categories. `/forge:validate` also rolls up the pre-existing gate/traceability
scripts into a pass/fail report; `/forge:trace-matrix` instead emphasizes the
full id x stage matrix and writes the responsible-agent attribution to
`.forge/traceability-gaps.jsonl` for advisory surfacing. Run either, or both —
they don't conflict, and running one doesn't invalidate the other's output.

## Steps

1. Read `agents/traceability-matrix.md` and adopt that persona for this run.
2. Run the generator:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/trace-matrix.py --cwd . \
     --plugin-dir ${CLAUDE_PLUGIN_ROOT}
   ```
3. Present the full report verbatim — the matrix table, then the gap table.
4. Summarize the gap table grouped by responsible agent so the user sees
   ownership at a glance, e.g.: "Stage 5 (planner) has 2 open gaps: REQ-004 and
   NFR-001 were never referenced in task-dag.md."
5. If the user asks who owns a specific id's gap, name the `(stage, agent)` pair
   directly from the gap table rather than making them look it up.
6. Mention that `.forge/traceability-gaps.jsonl` was refreshed, and that the
   responsible agent will see an advisory note the next time their stage becomes
   active (via `hooks/session-start.py`) — this is informational only; nothing is
   blocked by it.

## Verification

- `pipeline/traceability-matrix.md` exists and its matrix rows match every id
  actually present in `pipeline/**/*.md`.
- `.forge/traceability-gaps.jsonl` is a fresh, complete snapshot (fully
  overwritten, not appended) — a gap that was fixed since the last run must not
  still appear.
- Every gap row has a `(stage, agent)` pair, or explicitly `unassigned` if the
  file's path didn't resolve to a known stage directory (never silently dropped).
- Re-running after a fix should show that gap gone from both the report and the
  jsonl snapshot.

## Examples

**User**: "/forge:trace-matrix"

**Claude**: [adopts the persona, runs trace-matrix.py]
"Traceability matrix generated — 5 ids tracked across stages 1, 2, and 5.

Gaps by responsible agent:
- **Stage 1 (requirements-analyst)**: `req-002` malformed (lowercase prefix),
  `FEAT-001` never referenced back in the SRS.
- **Stage 2 (product-designer)**: `REQ-001` misplaced — redefined in prd.md
  instead of just referenced.
- **Stage 5 (planner)**: `REQ-004`, `NFR-001` never referenced in task-dag.md.

Written to `pipeline/traceability-matrix.md`; gap snapshot refreshed in
`.forge/traceability-gaps.jsonl` — each responsible agent will see their items
surfaced next time their stage is active."

**User**: "who owns the REQ-004 gap?"

**Claude**: "REQ-004 is attributed to Stage 5 — the planner — since task-dag.md
is the earliest downstream doc that should have referenced it but doesn't."
