# ADR-008: Unified Graduation Layer — One Core, Three Per-Tier-Gated Adapters

**Status**: Accepted
**Date**: 2026-06-22

## Context

Forge accumulates three kinds of reusable memory inside a project's `.forge/`:
**lessons** (`trigger → rule` records), **skills** (mined, curated, human-approved
`SKILL.md` workflows with an ExpeL reuse-quality ledger), and **workflows**
(declarative `.forge/workflows/*.yaml` DAGs run by the v0.4.0 engine).

Only lessons crossed the project boundary. `promote-lessons.py` (T-022) registers
every Forge project in `~/.forge/projects.yaml`, scans for lessons recurring across
≥ N projects, merges them into `~/.forge/global-lessons.yaml`, and recalls them at
session-start with **project-lessons-win** on conflict. Skills and workflows had **no
equivalent**: an approved skill in project A was invisible to project B (the plugin
`skills/` install is a machine-wide side effect, not durable, portable, or curated),
and a battle-tested workflow YAML could not be reused in another project at all.

The deferred backlog (srs-v0.4.1 §5.2) called for the fix to be **one unified
graduation layer** generalizing the lesson mechanism for all three tiers — **not**
three bespoke promoters. The open question this ADR settles: should every tier share a
single *breadth* (cross-project frequency) gate, as lessons use, or should each tier
gate on its own signal?

## Decision

**Ship one tier-agnostic core (`scripts/_graduation.py`) plus three thin tier adapters,
each with a promotion gate matched to its artifact's nature, and a project-wins recall
rule in every tier.**

- **One core, three thin adapters.** All cross-tier mechanics live once in
  `_graduation.py`: the registry (`register_project`/`load_registry` over
  `~/.forge/projects.yaml`), `write_atomic`, the single 30-day `is_stale` TTL, the
  idempotent `merge_by_key` upsert (keyed by a tier-supplied conflict key, with an
  optional `merge_fn` to accumulate fields), a `Tier` **protocol**
  (`collect`/`gate`/`key`/`promote`/`recall` + a `name`), and the `graduate()` driver.
  A tier adapter answers only five questions: *what does this project contribute, does
  it pass the gate, what is its conflict key, where does it live globally, how is it
  recalled.* The three adapters are **separate modules** — the lessons adapter
  (`LessonTier` in `promote-lessons.py`), `_graduation_skills.SkillTier`, and
  `_graduation_workflows.WorkflowTier`.

- **Per-tier gates, not a uniform breadth gate.** Lessons are *emergent* — they earn
  promotion on cross-project **breadth** (≥ 3 distinct projects **AND** total frequency
  ≥ 2, the EF-026 rule, behavior-preserved). Skills and workflows are *deliberate,
  single artifacts* that almost never recur independently across projects, so they
  promote on **quality + an existing human/validation gate**:
  - **Skills** gate on locally **approved** (installed at the plugin `skills/<slug>/`
    path) **AND** ExpeL `weight > 0` **AND** `use ≥ _MIN_SKILL_USES` (default 2).
  - **Workflows** gate on **validates clean** (`workflow_loader.load_workflow_file(...).ok`)
    **AND** ≥ `_MIN_WORKFLOW_RUNS` (default 2) successful `workflow_run` records in
    `.forge/events.jsonl` (a success = ≥ 1 completed node and no failing verify verdict).

  A breadth gate would leave skills and workflows **dormant** — the very artifacts the
  layer exists to share would rarely qualify.

- **Project always wins on recall.** A project's own lesson / skill / workflow shadows
  the global one with the same conflict key (lesson trigger-cluster · skill slug ·
  workflow name). The global store is a **fallback library**, never an override.

- **Fail-soft per tier; the driver never raises.** `graduate(global_dir, tiers, *,
  dry_run, project_path)` loops `registered-projects × tiers`, wrapping each tier so its
  exception degrades **only** that tier (its result becomes `[]`) and never aborts the
  driver or a sibling tier. Recall is isolated from promotion failures. Graduation runs
  silently at session-start and must never block or delay startup (REQ-NF-034).

- **A fourth tier would be a new adapter, not a new pipeline.** Because the core owns all
  cross-tier mechanics, adding a tier is implementing the five-method protocol — not
  extending the driver.

## Rationale

1. **The backlog already decided "one layer, not three."** This ADR records *how*: the
   shared mechanics that three bespoke promoters would each re-implement (registry,
   atomic IO, TTL, idempotent merge, the fail-soft loop) live exactly once.
2. **Gate-to-nature is the load-bearing choice.** Matching the gate to each artifact's
   nature is what makes the new tiers actually promote anything; a uniform breadth gate
   would have shipped a layer that never graduates a skill or a workflow.
3. **Behavior-preserving generalization keeps the lesson path safe.** The lessons tier is
   `promote-lessons.py` *refactored* over the core — same CLI, same `global-lessons.yaml`
   bytes, same tests green — and that refactor is a **separate commit** from the new-tier
   behavior (REQ-NF-036, split-determinism). The highest-risk regression (silently
   changing lesson promotion) is gated by AC-GR-001.
4. **Fail-soft-per-tier protects session-start.** Graduation is automatic and silent at
   session-start; isolating each tier means one broken input (an unwritable `~/.forge`, a
   malformed `events.jsonl`, a missing `skill-stats.jsonl`) degrades that tier to a no-op
   while every healthy tier still does its work (AC-GR-005).

## Alternatives considered

- **A uniform cross-project breadth gate for all three tiers.** Rejected: skills and
  workflows are deliberate single artifacts that rarely recur independently across
  projects, so a breadth gate would leave both tiers dormant — defeating the layer.
- **Three bespoke promoters (one per tier).** Rejected: triplicates registry, TTL, atomic
  IO, and merge logic; each promoter drifts independently; the backlog explicitly called
  for one layer.
- **Rewriting the lesson promoter rather than refactoring it.** Rejected: a rewrite risks
  silently changing `global-lessons.yaml` output. Generalizing in place keeps the existing
  suite as the regression oracle.

## Consequences

- `scripts/_graduation.py` (core) + `_graduation_skills.py` + `_graduation_workflows.py`
  land as the layer; `promote-lessons.py` keeps its CLI and becomes the lessons adapter.
- Session-start runs three-tier graduation in-process via `_register_and_promote`
  (`hooks/session-start.py`), fail-soft, with a `FORGE_NO_GRADUATE=1` escape hatch.
- A new `/forge:graduate` skill + thin CLI (`--dry-run` / `list` / force scan) exposes the
  same core — no second promotion path.
- Skill recall is a symlink — see **[ADR-009](009-skill-recall-symlink.md)**.
- Cross-machine **sync transport** of `~/.forge` stays the user's (git/rsync, per
  `docs/forge-sync.md`); this layer makes `~/.forge` durable + portable, not auto-synced.
- See **[`references/graduation-layer.md`](../../../references/graduation-layer.md)** for
  the tiers, gates, `~/.forge` layout, and the `/forge:graduate` surface.
