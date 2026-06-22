# SRS — Forge v0.5.0 (unified `~/.forge` graduation layer: lessons + skills + workflows)

> **Status**: **Draft — ready for build** (2026-06-22). A **new-capability** minor release. Forge
> already promotes the best *lessons* across projects (`scripts/promote-lessons.py`, T-022): a project
> registry under `~/.forge/projects.yaml`, a frequency/breadth-gated scan, an idempotent merge into
> `~/.forge/global-lessons.yaml`, recalled at session-start with **project-lessons-win** on conflict.
> The other two memory tiers have no such path: **skills** are mined + curated + verified locally but
> never graduate beyond a machine's plugin install, and **workflows** (`.forge/workflows/*.yaml`) have
> **zero** cross-project sharing. The deferred backlog (srs-v0.4.1 §5.2) calls for one **unified
> graduation layer** serving all three tiers instead of three bespoke promoters.
>
> This release **generalizes the existing lesson promoter into a shared, tier-agnostic core** and adds
> two new tiers (skills, workflows) behind **per-tier promotion gates** matched to each artifact's
> nature: cross-project *breadth* for emergent lessons; *quality + approval* for deliberate skills and
> workflows. Project artifacts **always win on conflict**, in every tier. Promotion is automatic and
> silent at session-start; a new `/forge:graduate` skill exposes dry-run / list / force-scan.
>
> **Re-sequencing note**: srs-v0.4.1 §5 slotted this graduation layer *after* the v0.5.0 "engine made
> real" trio. That order is now reversed by decision (2026-06-22): the graduation layer is **v0.5.0**
> (lower-risk, generalizes built machinery, high cross-project leverage); the engine trio (session
> reuse · top-level generation · pipeline-as-WorkflowSpec) remains the subsequent engine work
> (≥ v0.5.1 / v0.6). §6 records the re-sequenced roadmap; the standing non-goals in srs-v0.4.1 §5.4 are
> unchanged and not re-listed here.
>
> **Grounding**: the T-022 lesson-promotion mechanism (registry · breadth+frequency gate · idempotent
> merge · 30-day TTL · atomic writes · fail-soft), reused verbatim as the lessons adapter; the
> skill subsystem's ExpeL voting ledger (`.forge/skill-stats.jsonl`, weight + use count; T-182
> `skill_curate.py`) and approval install path (`scripts/skill-approval.py` → `<plugin>/skills/<slug>/`);
> the v0.4.1 workflow audit record (`.forge/events.jsonl`, `event:"workflow_run"` with `name` +
> `completed`/`dropped` + `verdicts`; T-203) reused as the **workflow quality signal**; the
> `workflow_loader.py` enumerate/load path (REQ-WF-005); REQ-NF-024 stdlib-only / fail-soft discipline.

---

## 1. Overview

### 1.1 Problem

Forge accumulates three kinds of reusable memory inside a project's `.forge/`:

1. **Lessons** — corrections distilled to `trigger → rule` records (`.forge/lessons.yaml`).
2. **Skills** — mined, curated, human-approved `SKILL.md` workflows with an ExpeL reuse-quality ledger.
3. **Workflows** — declarative `.forge/workflows/*.yaml` DAGs run by the v0.4.0 engine.

Only lessons cross the project boundary. `promote-lessons.py` (T-022) registers every Forge project,
scans for lessons recurring across ≥ N projects, and merges them into `~/.forge/global-lessons.yaml`,
recalled at session-start in *any* project. Skills and workflows have **no equivalent**:

- A skill mined and approved in project A is invisible to project B. Approved skills do land in the
  shared plugin `skills/` dir (machine-wide), but that is **not durable across plugin reinstalls, not
  portable across machines, and not quality-curated** — it is an install-time side effect, not a
  promoted, gated, recallable global set.
- A battle-tested workflow YAML in project A cannot be reused in project B at all. There is no global
  workflow store and `workflow_loader` only ever looks in the current project's `.forge/workflows/`.

The deferred-backlog consolidation (srs-v0.4.1 §5.2) already decided the fix: **not** three bespoke
promoters, but **one `~/.forge` graduation layer** generalizing the lesson mechanism for all three
tiers, with the project-wins conflict rule preserved.

### 1.2 Objective

Ship one **unified graduation layer**: a shared, tier-agnostic core (registry · gate driver · idempotent
merge · TTL · atomic IO · project-wins recall) plus three **tier adapters** (lessons, skills, workflows),
each with a promotion gate matched to its artifact's nature. Promotion runs automatically and silently at
session-start (same budget as today's lesson promote); a new `/forge:graduate` skill exposes manual
dry-run / list / force-scan. **Zero regression** to the existing lesson promotion: `promote-lessons.py`'s
CLI, on-disk format, and tests are preserved by refactoring it into the lessons adapter over the new core.

### 1.3 Scope

**In scope.**

- A shared core module `scripts/_graduation.py` (extracted from `promote-lessons.py`): the registry,
  atomic writes, 30-day TTL/staleness, idempotent merge, and a `Tier` protocol + `graduate(...)` driver
  that loops `registered-projects × tiers`, fail-soft per tier, never-raising.
- **Lessons adapter** — `promote-lessons.py` re-expressed over the core; behavior-preserving.
- **Skills adapter** — gate = locally **approved** skill **AND** ExpeL `weight > 0` **AND** `use ≥ N`;
  global store `~/.forge/skills/<slug>/` (copied dir) + `~/.forge/global-skills.yaml` index; recall =
  **symlink** `~/.forge/skills/<slug>` into the discovered plugin `skills/` path at session-start.
- **Workflows adapter** — gate = **validates clean** (`workflow_loader.load_workflow_file`) **AND** ran
  successfully ≥ N times (counted from `.forge/events.jsonl`); global store `~/.forge/workflows/<name>.yaml`
  + `~/.forge/global-workflows.yaml` index; recall = extend the loader's search path to
  `[project/.forge/workflows, ~/.forge/workflows]`, project-wins on name; `/forge:flow` lists both.
- **Project-wins** recall conflict rule across all three tiers.
- **Automatic** session-start graduation (extend `hooks/session-start.py _register_and_promote`).
- A new **`/forge:graduate`** skill + thin CLI: `--dry-run`, list the global store per tier, force a scan.
- ADR-008 (graduation model) and ADR-009 (skill-recall = symlink). Tests + docs.

**Out of scope (this release).** The engine "made real" trio (session reuse · top-level generation ·
pipeline-as-WorkflowSpec) — §6. The actual cross-machine **sync transport** of `~/.forge` (git/rsync
remains the user's, per `docs/forge-sync.md`); we make `~/.forge` durable + portable, not auto-synced.
Embedding / vector retrieval of skills or workflows — standing non-goal (srs-v0.4.1 §5.4). Any change to
how skills are *mined/approved* or workflows are *authored/run* — graduation consumes those outputs, it
does not alter them.

### 1.4 Design principles

- **One core, three thin adapters.** All cross-tier mechanics (registry, merge, TTL, atomic IO, driver)
  live once in `_graduation.py`. A tier adapter answers only: *what does this project contribute, does it
  pass the gate, what is its conflict key, where does it live globally, how is it recalled.*
- **Per-tier gates matched to artifact nature.** Lessons are *emergent* (promote on cross-project
  breadth). Skills and workflows are *deliberate, single artifacts* (promote on quality + an existing
  human/validation gate) — a breadth gate would leave them dormant.
- **Project always wins.** A project's own lesson / skill / workflow shadows the global one with the same
  key. The global store is a **fallback library**, never an override.
- **Behavior-preserving generalization.** The lessons path is refactored, not rewritten: same CLI, same
  `global-lessons.yaml`, same tests green. The refactor is a separate commit from new-tier behavior
  (REQ-NF-036 split-determinism discipline).
- **Silent, bounded, never-raising.** Graduation at session-start adds no user-visible output and no more
  cost than today's lesson promote; any tier's failure degrades that tier to a no-op and never blocks
  session-start or a sibling tier.
- **`~/.forge`/`.forge`-only, stdlib + PyYAML, atomic.** No new dependency, no writes outside the two
  forge trees, every store write atomic (temp + `os.replace`).

---

## 2. Functional Requirements

### 2.1 Shared graduation core

- **REQ-GR-001** — `scripts/_graduation.py` provides a tier-agnostic core: (a) the project **registry**
  (`~/.forge/projects.yaml`, reused as-is) with `register` + `load`; (b) `_write_atomic` and the 30-day
  `is_stale` TTL helper, moved here and shared; (c) an idempotent **merge** primitive keyed by a
  tier-supplied conflict key; (d) a `Tier` protocol — `collect(project) → records`, `gate(records) →
  promotable`, `key(record) → str`, `promote(promotable, global_dir)`, `recall(global_dir, project)`;
  (e) a `graduate(global_dir, tiers, *, dry_run) ` driver that scans `registered-projects × tiers`,
  isolating each tier so one tier's exception degrades **only** that tier (fail-soft per tier). The driver
  **never raises**.

### 2.2 Lessons adapter (behavior-preserving)

- **REQ-GR-002** — `promote-lessons.py` is re-expressed as the lessons `Tier` over `_graduation.py`:
  source `.forge/lessons.yaml`; gate = breadth ≥ `--threshold` (default 3) distinct projects **AND**
  total frequency ≥ 2 (the EF-026 rule); cluster by trigger similarity; merge into
  `~/.forge/global-lessons.yaml`; recall = session-start injection, **project-lessons-win**. The CLI
  (`--register`, `--promote`, `--global-dir`, `--threshold`, `--dry-run`), the on-disk
  `global-lessons.yaml` schema, and all existing `promote-lessons` tests remain unchanged.

### 2.3 Skills tier (new)

- **REQ-GR-003** — A skills `Tier`: **collect** a project's locally-**approved** skills (those installed
  to the plugin `skills/<slug>/` via `skill-approval.py approve`, joined with their ExpeL ledger in the
  project's `.forge/skill-stats.jsonl`); **gate** = approved **AND** folded ExpeL `weight > 0` **AND**
  `use ≥ _MIN_SKILL_USES` (tunable, default 2); **promote** = copy the skill directory to
  `~/.forge/skills/<slug>/` and upsert a `~/.forge/global-skills.yaml` index record (`slug`, source
  `projects`, `weight`, `use`, `last_used`); **key** = `slug`; **recall** = at session-start, **symlink**
  each `~/.forge/skills/<slug>` into the discovered plugin `skills/` path **unless** a project/plugin skill
  of the same slug already exists (project/plugin-wins). Stale (TTL) global skills are dropped from recall.

### 2.4 Workflows tier (new)

- **REQ-GR-004** — A workflows `Tier`: **collect** a project's `.forge/workflows/*.yaml`; **gate** =
  `workflow_loader.load_workflow_file` returns `ok` (validates clean) **AND** the workflow ran successfully
  ≥ `_MIN_WORKFLOW_RUNS` times (tunable, default 2), where a successful run is a `.forge/events.jsonl`
  record with `event:"workflow_run"`, matching `name`, at least one completed node and no failing verify
  verdict; **promote** = copy the YAML to `~/.forge/workflows/<name>.yaml` and upsert a
  `~/.forge/global-workflows.yaml` index record (`name`, source `projects`, `runs`, `last_used`); **key** =
  `name`; **recall** = `workflow_loader` enumerates `[project/.forge/workflows, ~/.forge/workflows]` with
  **project-wins on name**, so `/forge:flow` lists and runs both project and graduated workflows.

### 2.5 Conflict rule

- **REQ-GR-005** — Recall is **project-wins** in every tier: a project artifact whose conflict key
  (lesson trigger-cluster · skill slug · workflow name) matches a global one shadows the global entry.
  The global store is a fallback library; it never overrides a project's own artifact.

### 2.6 Automatic session-start graduation

- **REQ-GR-006** — `hooks/session-start.py _register_and_promote` is extended to register the current
  project and run `graduate(...)` over all three tiers (replacing the lessons-only promote). It is
  **silent** (no stdout/stderr in the happy path beyond existing logging), **bounded** (work is
  O(registered-projects × tiers), within the existing lesson-promote time budget), and **fail-soft**: a
  graduation error never blocks or delays session startup and never raises into the hook.

### 2.7 Manual surface

- **REQ-GR-007** — A new **`/forge:graduate`** skill (`skills/forge-graduate/SKILL.md`) + a thin CLI over
  `_graduation.py`: `--dry-run` previews what each tier would promote without writing; a `list` view
  enumerates the current `~/.forge` global store per tier (lessons / skills / workflows) with counts and
  `last_used`; a `--promote`/force path runs an immediate scan. The CLI reuses the core; it adds no second
  promotion path.

### 2.8 Release

- **REQ-GR-008** — Release v0.5.0: `bump-version.py 0.5.0`; CHANGELOG `[0.5.0]`; ROADMAP + progress rows;
  ADR-008 + ADR-009 committed; banner/social-preview are evergreen (no per-release stats → no refresh).
  Pre-release gate green; PR→develop→main→tag `v0.5.0`→mirror both remotes→GitHub releases→delete branch.

---

## 3. Non-Functional Requirements

- **REQ-NF-034** — **Stdlib + PyYAML only; fail-soft; never-raises.** No third-party import in the core,
  adapters, or hook path (REQ-NF-024). Every external read (project `.forge/*`, `~/.forge/*`, the registry,
  `events.jsonl`, `skill-stats.jsonl`) is guarded; a missing/unreadable/malformed input degrades that tier
  to a no-op. A failure in one tier never aborts the driver, a sibling tier, or session-start.
- **REQ-NF-035** — **`~/.forge`/`.forge`-only, atomic, TTL-shared.** All store writes are atomic
  (temp + `os.replace`, the existing `_write_atomic`). Nothing is written outside `~/.forge` and the
  project's `.forge`. The single 30-day `is_stale` TTL governs decay-from-recall for all tiers; skill
  symlinks and workflow search entries for stale global records are not surfaced.
- **REQ-NF-036** — **Behavior-preserving refactor (split determinism).** Extracting the core from
  `promote-lessons.py` is committed **separately** from any new-tier behavior; after the refactor commit,
  the lessons CLI, `global-lessons.yaml` output, and the full existing test set are byte/behaviour
  unchanged. New tiers are additive and default-inert until a project actually has an approved skill /
  successful workflow to contribute.
- **REQ-NF-037** — **Bounded, idempotent, safe under repetition.** A second `graduate(...)` with no new
  qualifying artifacts is a no-op (idempotent merge; symlinks already present are left as-is; an existing
  global YAML is rewritten byte-identically). Recall symlinking never overwrites a real file and never
  follows into deleting a project/plugin skill. Session-start graduation adds no more wall-clock than the
  current lesson promote.

---

## 4. Acceptance Criteria

- **AC-GR-001** (REQ-GR-001/002, NF-036) — After the core extraction, `promote-lessons.py` produces a
  byte-identical `global-lessons.yaml` for the same inputs and the entire existing `promote-lessons` test
  suite passes unchanged; the core driver isolates a thrown tier so the other tiers still complete.
- **AC-GR-002** (REQ-GR-003) — Given two registered projects each with an approved skill `<slug>` at ExpeL
  `weight > 0`, `use ≥ 2`, a scan copies it to `~/.forge/skills/<slug>/` + indexes it; a skill at
  `weight ≤ 0` or `use < 2`, or one only *proposed* (not approved), is **not** promoted. At recall the
  global skill is symlinked into the plugin `skills/` path **only** when no same-slug project/plugin skill
  exists (project/plugin-wins), and the symlink never clobbers an existing file.
- **AC-GR-003** (REQ-GR-004) — Given a workflow `<name>.yaml` that validates clean and has ≥ 2 successful
  `workflow_run` records in `events.jsonl`, a scan copies it to `~/.forge/workflows/<name>.yaml` + indexes
  it; an invalid YAML or one with < 2 successful runs is not promoted. `workflow_loader` then lists/loads
  `<name>` in a *different* project, and a project-local `<name>.yaml` shadows the global one (project-wins).
- **AC-GR-004** (REQ-GR-005) — For each tier, a project artifact with the same conflict key as a global
  one is the one recalled; removing the project artifact surfaces the global fallback.
- **AC-GR-005** (REQ-GR-006/NF-034) — Session-start runs the three-tier graduation silently; with an
  unwritable `~/.forge`, a malformed `events.jsonl`, and a missing `skill-stats.jsonl` all present at once,
  startup completes normally, no exception escapes, and each healthy tier still does its work.
- **AC-GR-006** (REQ-GR-007) — `/forge:graduate --dry-run` prints the per-tier promotion preview and writes
  nothing; the `list` view reflects the real `~/.forge` store; a forced scan promotes the same set the
  dry-run predicted.
- **AC-GR-007** (REQ-NF-037) — Running graduation twice with no new qualifying artifacts changes no file
  on disk (idempotent) and adds/removes no symlink.
- **AC-GR-008** (REQ-GR-008) — Suite green; `validate-plugin.py` 0; `full-pipeline.sh` passes;
  manifests at `0.5.0`; `v0.5.0` tagged on origin + polygon with GitHub releases; ADR-008 + ADR-009 present.

---

## 5. Architecture notes (for ADR-008 / ADR-009)

- **ADR-008 — Unified graduation layer: shared core + per-tier gates.** One `_graduation.py` core; three
  thin adapters; project-wins recall. Decision: **per-tier gates** (breadth for emergent lessons; quality +
  existing approval/validation gate for deliberate skills/workflows) rather than a uniform breadth gate,
  because skills/workflows almost never recur independently across projects and a breadth gate would leave
  those tiers dormant. The driver is fail-soft per tier; the core owns all cross-tier mechanics so a fourth
  tier would be a new adapter, not a new pipeline.
- **ADR-009 — Skill recall is a symlink, not a copy.** Graduated skills are stored once under
  `~/.forge/skills/<slug>/` and **symlinked** into the discovered plugin `skills/` path at recall. Decision:
  symlink (chosen over copy) so there is a single source of truth, edits to a graduated skill propagate, and
  recall is cheap and reversible; project/plugin skills of the same slug always win and are never replaced.
  (Fallback if a platform cannot symlink: degrade to a guarded copy — fail-soft, never raise.)

---

## 6. Re-sequenced roadmap (supersedes srs-v0.4.1 §5.1 ordering)

This release realizes srs-v0.4.1 **§5.2** (the unified `~/.forge` graduation layer) as **v0.5.0**, ahead of
the engine trio. The remaining program order:

1. **v0.5.0 (this SRS)** — unified `~/.forge` graduation layer (lessons + skills + workflows).
2. **Engine "made real" trio** (srs-v0.4.1 §5.1), now ≥ v0.5.1 / v0.6, unchanged in content: session reuse
   across heterogeneous DAG nodes · top-level LLM-generated workflows · pipeline-as-WorkflowSpec.
3. **Managed-Agents track** (srs-v0.4.1 §5.3) — its own program, ≥ v0.6, independent of the above.

The **standing non-goals** (srs-v0.4.1 §5.4) are unchanged and authoritative — in particular **embedding /
vector retrieval of skills or workflows** remains a non-goal, so graduation gates on frequency/quality/breadth
and Claude's own description-matching, never on vector similarity.

---

## 7. Traceability

| REQ-ID | Tasks (assigned in task-dag-v0.5.0) |
|--------|-------------------------------------|
| REQ-GR-001 | core extraction |
| REQ-GR-002 | lessons adapter (behavior-preserving) |
| REQ-GR-003 | skills tier |
| REQ-GR-004 | workflows tier |
| REQ-GR-005 | conflict rule (recall, all tiers) |
| REQ-GR-006 | session-start wiring |
| REQ-GR-007 | `/forge:graduate` skill + CLI |
| REQ-GR-008 | release |
| REQ-NF-034..037 | every task (invariants) |
| ADR-008 / ADR-009 | core + skills-recall tasks |

---

## 8. References & provenance

### 8.1 Internal contracts reused

- **T-022 / `promote-lessons.py`** — registry, breadth+frequency gate (EF-026: `_MIN_FREQUENCY`),
  idempotent merge, 30-day `is_stale` TTL, `_write_atomic`, fail-soft loaders. The lessons adapter and the
  extracted core.
- **T-182 / `skill_curate.py` + `.forge/skill-stats.jsonl`** — ExpeL voting ledger (ADD/UPVOTE/DOWNVOTE/EDIT
  → weight + use). The skills-tier quality signal.
- **T-028 / `skill-approval.py`** — `approve()` installs `.forge/proposed-skills/<slug>/SKILL.md` →
  `<plugin>/skills/<slug>/`. Defines "approved" and the recall destination path.
- **T-203 (v0.4.1) / `.forge/events.jsonl`** — one `workflow_run` record per run (`name`, `completed`,
  `dropped`, `verdicts`). The workflows-tier success signal.
- **REQ-WF-005 / `workflow_loader.py`** — `load_workflow_file` (validate) + `list_workflows` (enumerate).
  Extended with the global search path for workflow recall.
- **REQ-NF-024** — stdlib-only / guarded-PyYAML / fail-soft discipline; the no-`pip` rule the embeddings
  non-goal also rests on.

### 8.2 Backlog provenance

- `build/01-srs/srs-v0.4.1.md:230-236` (§5.2) — "generalize the existing lesson-promotion mechanism into one
  `~/.forge` graduation layer serving lessons + skills + workflows"; sequenced after flows dogfooded — now
  pulled ahead to v0.5.0 by the 2026-06-22 re-sequencing decision (§6).
- `build/01-srs/srs-v0.4.1.md:249-264` (§5.4) — standing non-goals (embeddings, in-session Agent driving,
  resident process, repackaging, full policy DSL, RL/web UI), unchanged.
- `build/01-srs/srs-v0.3.5.md:55-57` — `~/.forge` *skill* graduation "analogous to lesson promotion" (origin
  of the skills tier).
- `build/01-srs/srs-v0.4.0.md` out-of-scope — `~/.forge` *workflow* sharing (origin of the workflows tier).
