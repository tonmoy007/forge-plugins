---
name: graduate
description: Promote a project's proven lessons, skills, and workflows into the shared
  `~/.forge` global store so they're recalled into your other projects. Use when the user runs
  /forge:graduate, says "graduate my skills/workflows/lessons", "promote to ~/.forge", "promote
  my reusable workflows", "list global store", "what's graduated", or "dry-run graduation".
  Runs the same three-tier graduation driver the session-start hook uses, on demand — a `list`
  view of the global store, a `--dry-run` preview that writes nothing, and a real scan that
  promotes everything past its tier gate.
allowed-tools: [Read, Bash]
---

# forge-graduate — promote proven lessons, skills & workflows to ~/.forge

`/forge:graduate` is the on-demand front end to Forge's **graduation layer**: the mechanism
that lifts what proved itself in one project into a shared `~/.forge` store, then recalls it
into your other projects. It runs the **same** `graduate()` driver the session-start hook runs
silently in the background — there is no second promotion path — so running it by hand just
makes that cross-project learning observable and explicit.

The driver loops `registered-projects × tiers`. Each tier is fail-soft and isolated: one tier's
fault degrades only that tier, never the others, and the driver never raises.

## The three tiers and their gates

- **lessons** (`global-lessons.yaml`) — a lesson graduates when the **same** concept (by
  trigger similarity) appears in **≥3 distinct projects** with summed frequency ≥2. Breadth is
  the signal: a lesson learned everywhere is worth carrying everywhere.
- **skills** (`global-skills.yaml` + `~/.forge/skills/<slug>/`) — an **approved** skill
  graduates when its ExpeL weight is positive and it has been **reused ≥2 times**. Skills are
  single deliberate artifacts, so the gate is depth (reuse), not breadth. Recalled into other
  projects by symlink (project/plugin always wins on a name clash).
- **workflows** (`global-workflows.yaml` + `~/.forge/workflows/<name>.yaml`) — a
  `.forge/workflows/<name>.yaml` that **validates clean** and has **≥2 successful runs** in
  `.forge/events.jsonl` graduates. Recall is the workflow loader's search path, TTL-filtered.

A 30-day `last_used` TTL governs recall for every tier: stale global entries decay out of
recall (they stay in the store but are not surfaced).

## When to Use

- `/forge:graduate` — run a real graduation scan now and promote everything past its gate.
- `/forge:graduate --dry-run` — preview what *would* promote, writing nothing.
- `/forge:graduate list` — enumerate the current global store per tier.

## When NOT to Use

- You just want to advance the 12-stage pipeline → that's `/forge:build`, `/forge:plan`, etc.
- You want to run a workflow → that's `/forge:flow`, not graduation.
- Nothing has met a gate yet (a brand-new project) → graduation is a clean no-op; that's
  expected, not a failure.

## The CLI

All three modes go through one thin CLI over the shared driver. `--global-dir` defaults to
`~/.forge`; override it only for testing.

**List the global store** (per tier: entry count + each entry's key and `last_used`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/_graduation.py" list
```

**Dry-run preview** (per-tier *would-promote* summary; **writes nothing** — no store files, no
copied skill/workflow artifacts):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/_graduation.py" --dry-run
```

**Force a real scan** (collect → gate → promote across every registered project; the default
action). This writes the per-tier global stores and copies graduated skill/workflow artifacts
into `~/.forge`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/_graduation.py"
# 'scan' is the explicit, equivalent form:
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/_graduation.py" scan
```

## Steps

1. **Default to a preview.** Unless the user explicitly asked to promote, run the **list** view
   and/or `--dry-run` first and relay the per-tier summary. A dry-run never writes, so it is
   always safe to show before committing to a real scan.
2. **Promote on request.** When the user wants graduation applied, run the real scan and report
   the per-tier promoted summary (tier → count → the keys promoted).
3. **Relay honestly.** If a tier promoted nothing, say so for that tier rather than implying the
   whole run promoted artifacts. If a tier degraded (its fault is isolated), report it as
   skipped this run.

## Verification

After running, these should hold:

- `--dry-run` printed a would-promote preview and wrote **nothing** (`~/.forge` is unchanged —
  no new `global-*.yaml`, no copied `skills/`/`workflows/` artifacts).
- A real scan that promoted a workflow/skill left a matching entry in the corresponding
  `global-*.yaml` and a copied artifact under `~/.forge/`.
- `list` reflects exactly the entries present in the store files (counts match).
- The command never crashed: even an unreadable store degrades to a clean message, not a
  traceback.

## Examples

**User**: "/forge:graduate list"

**Claude**: [runs the list view]
"Global store at ~/.forge:
  lessons: 2 entries
  skills: 1 entry
    - lint-fix (last_used: 2026-06-03)
  workflows: 1 entry
    - shipit (last_used: 2026-06-02)"

**User**: "/forge:graduate --dry-run"

**Claude**: [runs the dry-run; writes nothing]
"Dry-run graduation preview (nothing written):
  lessons: nothing to promote
  skills: nothing to promote
  workflows: Would promote 1 — shipit

Run `/forge:graduate` to apply this."
