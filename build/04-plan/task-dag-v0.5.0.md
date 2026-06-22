# Task DAG — Forge v0.5.0 (unified `~/.forge` graduation layer)

> **Status**: **Ready to build** (2026-06-22). Derived from `build/01-srs/srs-v0.5.0.md`.
> Numbering continues from v0.4.1 (T-202..T-206); this is **T-207..T-213**. A **new-capability**
> minor: generalize the T-022 lesson promoter into one tier-agnostic `~/.forge` graduation core, then
> add **skills** and **workflows** tiers behind per-tier gates, recalled with **project-wins**.
>
> Format: `T-NNN [size] title` — Size: S (~30min), M (~2hr), L (~half-day).
>
> | Milestone | Tag | Gate |
> |-----------|-----|------|
> | M1 Core + lessons adapter (behavior-preserving) | — | v0.4.1 landed |
> | M2 Skills + workflows tiers | — | M1 landed |
> | M3 Wiring + surface + docs | — | M2 landed |
> | M4 Release | v0.5.0 | M1–M3 landed |
>
> **Invariants** (every task): stdlib + PyYAML fail-soft; **never-raises** — a tier error degrades that
> tier to a no-op and never aborts the driver, a sibling tier, or session-start; **project-wins** recall
> in every tier; **`~/.forge`/`.forge`-only atomic writes** (the existing `_write_atomic`); the shared
> 30-day `is_stale` TTL governs decay-from-recall for all tiers; **behavior-preserving** — after the core
> extraction the `promote-lessons` CLI + `global-lessons.yaml` output + its full test set are unchanged,
> and that refactor is a **separate commit** from any new-tier behavior (REQ-NF-036); TDD red-first; full
> suite + `validate-plugin.py` 0 + `full-pipeline.sh` green per task. Reuses `scripts/promote-lessons.py`
> (registry · breadth+freq gate · merge · TTL · `_write_atomic`), `scripts/skill-approval.py`
> (`approve` dest path = "approved"), `.forge/skill-stats.jsonl` (ExpeL weight+use; T-182),
> `.forge/events.jsonl` (`workflow_run` records; T-203), `scripts/workflow_loader.py` (validate +
> enumerate), `hooks/session-start.py` `_register_and_promote`.

---

## Milestone 1: Core + lessons adapter

### T-207 [M] Shared graduation core `_graduation.py` + behavior-preserving lessons adapter
- **Description**: Extract the tier-agnostic core from `promote-lessons.py` into new
  `scripts/_graduation.py`: the registry (`~/.forge/projects.yaml`) `register`/`load`, `_write_atomic`,
  the 30-day `is_stale` TTL, an idempotent **merge** keyed by a tier-supplied conflict key, a `Tier`
  protocol (`collect`/`gate`/`key`/`promote`/`recall`), and a `graduate(global_dir, tiers, *, dry_run)`
  driver that loops `registered-projects × tiers` isolating each tier (fail-soft per tier, never-raises).
  Re-express `promote-lessons.py` as the **lessons `Tier`** over the core — same CLI
  (`--register`/`--promote`/`--global-dir`/`--threshold`/`--dry-run`), same breadth≥3 + freq≥2 gate, same
  trigger-similarity clustering, same `global-lessons.yaml` bytes. **The existing `promote-lessons` tests
  stay green untouched.** Commit the refactor **separately** from M2.
- **Files**: `scripts/_graduation.py` (new), `scripts/promote-lessons.py`, `tests/unit/test_graduation.py`
  (new), `tests/unit/test_promote_lessons.py` (must stay green)
- **Done when**: AC-GR-001 — `promote-lessons.py` emits byte-identical `global-lessons.yaml` for the same
  inputs; the full existing `promote-lessons` suite passes unchanged; the driver isolates a thrown tier so
  siblings still complete; new core unit tests cover registry, merge-idempotence, TTL, fail-soft.
- **Depends on**: none (v0.4.1 landed)
- **REQ-IDs**: REQ-GR-001, REQ-GR-002, NF-034, NF-035, NF-036

---

## Milestone 2: Skills + workflows tiers

### T-208 [M] Skills tier — gate + promote + global store/index + symlink recall (ADR-009)
- **Description**: A skills `Tier` over the core. **collect** a project's approved skills (present at the
  `skill-approval.py` install path `<plugin>/skills/<slug>/`) joined with that project's
  `.forge/skill-stats.jsonl` ExpeL ledger (fold ADD/UPVOTE/DOWNVOTE/EDIT → weight + use). **gate** =
  approved **AND** `weight > 0` **AND** `use ≥ _MIN_SKILL_USES` (default 2). **promote** = copy the skill
  dir to `~/.forge/skills/<slug>/` + upsert `~/.forge/global-skills.yaml` (`slug`, source `projects`,
  `weight`, `use`, `last_used`). **key** = `slug`. **recall** = **symlink** `~/.forge/skills/<slug>` into
  the discovered plugin `skills/` path, **only** when no same-slug project/plugin skill exists
  (project/plugin-wins); never clobber a real file; TTL-stale globals are not surfaced. Symlink-unsupported
  platform ⇒ guarded copy, fail-soft (ADR-009 fallback).
- **Files**: `scripts/_graduation.py` (skills adapter), `tests/unit/test_graduation_skills.py` (new)
- **Done when**: AC-GR-002 — two projects with an approved `<slug>` at weight>0/use≥2 promote it + index it;
  weight≤0, use<2, or *proposed-not-approved* do not promote; recall symlinks only with no same-slug
  project/plugin skill and never clobbers; idempotent on re-run.
- **Depends on**: T-207
- **REQ-IDs**: REQ-GR-003, REQ-GR-005, NF-035, NF-037

### T-209 [M] Workflows tier — gate via `events.jsonl` + promote + loader search-path recall
- **Description**: A workflows `Tier` over the core. **collect** `.forge/workflows/*.yaml`. **gate** =
  `workflow_loader.load_workflow_file(...).ok` (validates clean) **AND** ≥ `_MIN_WORKFLOW_RUNS` (default 2)
  successful runs, counted from `.forge/events.jsonl` `event:"workflow_run"` records matching `name`
  (success = ≥1 completed node and no failing verify verdict). **promote** = copy YAML to
  `~/.forge/workflows/<name>.yaml` + upsert `~/.forge/global-workflows.yaml` (`name`, `projects`, `runs`,
  `last_used`). **key** = `name`. **recall** = extend `workflow_loader` to enumerate/resolve
  `[project/.forge/workflows, ~/.forge/workflows]` with **project-wins on name**, so `/forge:flow` lists +
  loads both. TTL-stale globals are not surfaced.
- **Files**: `scripts/_graduation.py` (workflows adapter), `scripts/workflow_loader.py` (global search path),
  `tests/unit/test_graduation_workflows.py` (new), `tests/unit/test_workflow_loader.py`
- **Done when**: AC-GR-003 — a clean workflow with ≥2 successful `workflow_run` records promotes + indexes;
  invalid YAML or <2 successful runs do not; the loader lists/loads a graduated `<name>` in a different
  project; a project-local `<name>.yaml` shadows the global (project-wins).
- **Depends on**: T-207
- **REQ-IDs**: REQ-GR-004, REQ-GR-005, NF-035, NF-037

---

## Milestone 3: Wiring + surface + docs

### T-210 [M] Session-start graduation wiring (all three tiers, silent/bounded/fail-soft)
- **Description**: Extend `hooks/session-start.py _register_and_promote` to register the current project and
  call `graduate(...)` over the three tiers (replacing the lessons-only promote), then run skill-symlink
  recall (T-208) for the project. **Silent** (no new stdout/stderr beyond existing logging), **bounded**
  (within the current lesson-promote budget), **fail-soft** — any graduation/recall error is swallowed and
  never delays or blocks startup. A `FORGE_NO_GRADUATE=1` / existing quiet escape disables it.
- **Files**: `hooks/session-start.py`, `tests/unit/test_session_start.py`
- **Done when**: AC-GR-005 — session-start runs three-tier graduation silently; with an unwritable
  `~/.forge` + malformed `events.jsonl` + missing `skill-stats.jsonl` simultaneously, startup completes,
  no exception escapes, and each healthy tier still does its work.
- **Depends on**: T-208, T-209
- **REQ-IDs**: REQ-GR-006, NF-034, NF-037

### T-211 [S] `/forge:graduate` skill + thin CLI (dry-run / list / scan)
- **Description**: New `skills/forge-graduate/SKILL.md` + a thin CLI over `_graduation.py`: `--dry-run`
  previews each tier's would-promote set without writing; a `list` view enumerates the `~/.forge` global
  store per tier (lessons / skills / workflows) with counts + `last_used`; a force `--promote` runs an
  immediate scan. Reuses the core — **no second promotion path**. Register the skill (auto-discovered from
  `skills/`).
- **Files**: `skills/forge-graduate/SKILL.md` (new), `scripts/_graduation.py` (CLI `main`),
  `tests/unit/test_graduation_cli.py` (new)
- **Done when**: AC-GR-006 — `--dry-run` prints the per-tier preview + writes nothing; `list` reflects the
  real store; a forced scan promotes exactly the dry-run-predicted set; `validate-plugin.py` 0 (skill valid).
- **Depends on**: T-207, T-208, T-209
- **REQ-IDs**: REQ-GR-007

### T-212 [S] ADR-008 + ADR-009 + docs
- **Description**: Write `build/02-architecture/adr/008-graduation-layer.md` (shared core + per-tier gates +
  project-wins) and `009-skill-recall-symlink.md` (symlink over copy; project/plugin-wins; copy fallback).
  Add `references/graduation-layer.md` (the three tiers, gates, `~/.forge` layout, the `/forge:graduate`
  surface, project-wins). Update README (one section), ROADMAP, and `build/05-implementation/progress.md`
  + decisions log.
- **Files**: `build/02-architecture/adr/008-graduation-layer.md` (new),
  `build/02-architecture/adr/009-skill-recall-symlink.md` (new), `references/graduation-layer.md` (new),
  `README.md`, `ROADMAP.md`, `build/05-implementation/progress.md`, `build/05-implementation/decisions.md`
- **Done when**: both ADRs present + Accepted; `references/graduation-layer.md` documents the tiers/gates/
  layout/surface; README references it; full-pipeline traceability green.
- **Depends on**: T-208, T-209, T-210
- **REQ-IDs**: REQ-GR-001, REQ-GR-003, REQ-GR-004 (docs)

---

## Milestone 4: Release

### T-213 [S] Release v0.5.0
- **Description**: `bump-version.py 0.5.0`; CHANGELOG `[0.5.0]`; ROADMAP + progress rows. Banner/social-preview
  evergreen (no per-release stats) → no refresh. Pre-release green; PR→develop→main→tag `v0.5.0`→mirror both
  remotes→GitHub releases→delete branch.
- **Files**: `.claude-plugin/*`, `CHANGELOG.md`, `ROADMAP.md`, `build/05-implementation/progress.md`,
  `README.md`
- **Done when**: AC-GR-008 — suite green; `validate-plugin.py` 0; `full-pipeline.sh` passes; manifests 0.5.0;
  `v0.5.0` tagged on origin + polygon with GitHub releases; two-remote parity; ADR-008/009 present.
- **Depends on**: T-207..T-212
- **REQ-IDs**: REQ-GR-008

---

## Critical path

```
T-207 (core + lessons adapter)
      → ┌ T-208 (skills tier) ┐
        └ T-209 (workflows tier) ┘  (independent — different tiers/files; may parallelize or sequence)
      → T-210 (session-start wiring) → T-211 (/forge:graduate) ∥ T-212 (ADRs + docs) → T-213 (v0.5.0)
```

T-208 and T-209 are independent (separate tier adapters, plus workflows touches `workflow_loader.py`),
so they can run in parallel; if built in one session, sequence them to keep the shared `_graduation.py`
edits conflict-free (the v0.4.1 small-release discipline). T-210 needs both tiers wired; T-211 and T-212
both depend on the tiers and can overlap; T-213 ships.

---

## Acceptance gate (v0.5.0)

**AC-GR-008** is the release gate: full unit suite green; `validate-plugin.py` 0; `full-pipeline.sh` passes;
`v0.5.0` tagged on `origin` + `polygon` with GitHub releases; manifests at `0.5.0`; ADR-008 + ADR-009 present.
Plus the per-feature gates AC-GR-001..007 — in particular the **behavior-preserving** check (AC-GR-001:
`promote-lessons` byte-identical + tests unchanged) and the **project-wins** checks (AC-GR-002/003/004),
which together prove "new cross-project capability, zero regression to the lesson path."

---

## Risk register

| ID | Risk | Impact | Likelihood | Mitigation |
|----|------|--------|------------|------------|
| R-1 | Core extraction silently changes lesson-promotion output | H | M | REQ-NF-036: refactor is its own commit; AC-GR-001 asserts byte-identical `global-lessons.yaml` + the full existing `promote-lessons` suite green before any new-tier work. |
| R-2 | Skill symlink clobbers or shadows a real project/plugin skill | H | L | Project/plugin-wins: symlink only when no same-slug real entry exists; never overwrite a file; copy-fallback is also guarded (ADR-009); AC-GR-002 asserts no-clobber. |
| R-3 | `events.jsonl` parse drives the workflow gate wrong (over/under-promote) | M | M | Fail-soft per-line JSON parse; a malformed record is skipped, not fatal; explicit "successful run" definition; AC-GR-003 covers invalid-YAML and <N-runs boundaries. |
| R-4 | Session-start slows or breaks from graduation work | H | L | Bounded O(projects×tiers); fail-soft swallow; `FORGE_NO_GRADUATE=1` escape; AC-GR-005 runs startup with three simultaneous broken inputs and asserts no escape/no block. |
| R-5 | Non-idempotent re-scan churns `~/.forge` or duplicates symlinks | M | L | Idempotent keyed merge + byte-identical rewrite; symlink-if-absent; AC-GR-007 asserts a second no-new-artifact scan changes nothing on disk. |

---

## Out of scope (future)

The engine "made real" trio (session reuse · top-level generation · pipeline-as-WorkflowSpec) — now ≥ v0.5.1 /
v0.6 (srs-v0.5.0 §6). The cross-machine **sync transport** of `~/.forge` (git/rsync stays the user's, per
`docs/forge-sync.md`). Embedding / vector retrieval of skills or workflows — standing non-goal
(srs-v0.4.1 §5.4). No change to how skills are mined/approved or workflows are authored/run.
