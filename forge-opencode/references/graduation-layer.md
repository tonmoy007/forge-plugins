# The Graduation Layer — promoting lessons, skills, and workflows across projects

Forge accumulates three kinds of reusable memory inside each project's `.forge/`. The
**graduation layer** promotes the best of each tier into a shared `~/.forge` store so they
become available in *every* Forge project on the machine — automatically, silently, and
fail-soft at session-start. A new project starts benefiting from what older projects learned.

This is one tier-agnostic core (`scripts/_graduation.py`) plus three thin tier adapters, one
per memory kind. See [ADR-008](../build/02-architecture/adr/008-graduation-layer.md) for the
design and [ADR-009](../build/02-architecture/adr/009-skill-recall-symlink.md) for skill
recall.

---

## The three tiers and their gates

Each tier promotes on a gate **matched to its artifact's nature**: lessons are *emergent*
(promote on cross-project breadth); skills and workflows are *deliberate single artifacts*
(promote on quality + an existing human/validation gate, because they rarely recur
independently across projects and a breadth gate would leave them dormant).

| Tier | Source | Promotion gate | Global store | Conflict key | Recall |
|------|--------|----------------|--------------|--------------|--------|
| **Lessons** | `.forge/lessons.yaml` | breadth ≥ **3** distinct projects **AND** total frequency ≥ 2 (EF-026), clustered by trigger similarity | `~/.forge/global-lessons.yaml` | lesson trigger-cluster | injected at session-start |
| **Skills** | approved skills installed at the plugin `skills/<slug>/` path + that project's `.forge/skill-stats.jsonl` ExpeL ledger | **approved** **AND** ExpeL `weight > 0` **AND** `use ≥ 2` | `~/.forge/skills/<slug>/` (copied dir) + `~/.forge/global-skills.yaml` index | skill `slug` | **symlink** into the plugin `skills/` path (ADR-009) |
| **Workflows** | `.forge/workflows/*.yaml` | **validates clean** (`workflow_loader.load_workflow_file`) **AND** ≥ **2** successful `workflow_run` records in `.forge/events.jsonl` (success = ≥ 1 completed node, no failing verify verdict) | `~/.forge/workflows/<name>.yaml` + `~/.forge/global-workflows.yaml` index | workflow `name` | loader **search path** overlay |

The skill use/weight threshold (`_MIN_SKILL_USES`, default 2) and the workflow run threshold
(`_MIN_WORKFLOW_RUNS`, default 2) are tunable constants in the respective adapters.

---

## The `~/.forge` layout

```
~/.forge/
├── projects.yaml            # the registry: every Forge project path (register/load)
├── global-lessons.yaml      # promoted lessons (project-lessons-win on recall)
├── skills/
│   └── <slug>/              # one promoted skill dir per slug (single source of truth)
├── global-skills.yaml       # skills index: slug · projects · weight · use · last_used
├── workflows/
│   └── <name>.yaml          # one promoted workflow YAML per name
└── global-workflows.yaml    # workflows index: name · projects · runs · last_used
```

Every store write is **atomic** (temp + `os.replace`, via the core's `write_atomic`). Nothing
is written outside `~/.forge` and the project's `.forge`. The core is **stdlib + PyYAML only**.

---

## Project always wins (the conflict rule)

Recall is **project-wins** in every tier. A project's own lesson / skill / workflow whose
conflict key (trigger-cluster · slug · name) matches a global one **shadows** the global
entry. The global store is a *fallback library* — it never overrides a project's own artifact.

- **Lessons** — project lessons win on injection (the long-standing T-022 rule).
- **Skills** — recall symlinks a global skill into the plugin `skills/` path **only** when no
  same-slug project/plugin skill already exists, and never clobbers a real file (ADR-009).
- **Workflows** — `workflow_loader.resolve_workflows` overlays
  `[project/.forge/workflows, ~/.forge/workflows]` and a project file of the same `name`
  shadows the global one, so `/forge:flow` lists and runs both but a local edit always wins.

Removing the project artifact surfaces the global fallback (AC-GR-004).

---

## The 30-day TTL

A single shared 30-day staleness TTL (`is_stale`) governs **decay-from-recall** for all
tiers: a global record whose `last_used` is older than 30 days is **not surfaced** at recall
(no skill symlink is created for it; it is dropped from the workflow search path; a stale
lesson is not injected). The record stays on disk — the TTL gates recall, not storage. A
missing/unparseable date is treated as *not stale* (kept).

---

## When graduation runs

- **Automatically at session-start.** `hooks/session-start.py _register_and_promote` registers
  the current project (`register_project`) and runs `graduate(...)` over all three tiers, then
  per-tier recall (skill symlinks land here). It is **silent** (no user-visible output),
  **bounded** (within the existing lesson-promote budget), and **fail-soft per tier**: one
  tier's failure degrades that tier to a no-op and never blocks or delays startup. Set
  **`FORGE_NO_GRADUATE=1`** to skip all graduation work entirely.
- **Manually via `/forge:graduate`.** A thin CLI over the same core — no second promotion path:
  - `--dry-run` previews what each tier *would* promote, writing nothing.
  - `list` enumerates the current `~/.forge` global store per tier (lessons / skills /
    workflows) with counts and `last_used`.
  - a force `--promote` runs an immediate scan, promoting exactly the dry-run-predicted set.

---

## Fail-soft, idempotent, never-raises

- Every external read (the registry, project `.forge/*`, `~/.forge/*`, `events.jsonl`,
  `skill-stats.jsonl`) is guarded; a missing/unreadable/malformed input degrades **that tier**
  to a no-op. A failure in one tier never aborts the `graduate()` driver, a sibling tier, or
  session-start (REQ-NF-034). The driver itself never raises.
- Graduation is **idempotent**: a second run with no new qualifying artifacts changes no file
  on disk (keyed `merge_by_key` upsert + byte-identical rewrite) and adds/removes no symlink
  (recall is symlink-if-absent).

---

## What graduation does *not* do

- It does **not** change how skills are mined/approved or how workflows are authored/run — it
  *consumes* those outputs.
- It does **not** sync `~/.forge` across machines — that transport stays the user's (git/rsync,
  per [`docs/forge-sync.md`](../docs/forge-sync.md)). Graduation makes `~/.forge` durable and
  portable, not auto-synced.
- It uses **no** embedding / vector retrieval — gates are frequency/quality/breadth and
  Claude's own description-matching (a standing non-goal preserves the stdlib-only rule).
