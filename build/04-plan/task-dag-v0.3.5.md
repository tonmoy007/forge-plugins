# Task DAG — Forge v0.3.5 (semantic skill mining + skill-creator)

> **Status**: **Ready to build** (2026-06-15). Derived from `build/01-srs/srs-v0.3.5.md`.
> Numbering continues from v0.3.3 (T-167..T-176); this is **T-177..T-184**.
>
> Format: `T-NNN [size] title` — Size: S (~30min), M (~2hr), L (~half-day).
>
> | Milestone | Tag | Gate |
> |-----------|-----|------|
> | M1 Semantic miner core | — | none — build first |
> | M2 Induction + authoring | — | M1 landed |
> | M3 Verify + curate | — | M2 landed |
> | M4 Migrate + release | v0.3.5 | M1–M3 landed |
>
> **Invariants** (every task): stdlib + PyYAML fail-soft; never-raises; cost + capability
> gating; `.forge/`-only writes for background work; TDD red-first; suite green per task; LLM
> steps degrade gracefully to the deterministic path when background is unavailable
> (REQ-NF-016..019). Reuses `_background_agent` (cheap model, `--json-schema`, `--max-budget-usd`),
> `_cost_cap`, `skill-approval`, ADR-006.

---

## Milestone 1: Semantic miner core (deterministic, stdlib)

### T-177 [L] Semantic enrichment + episode segmentation
- **Description**: New `scripts/_trace_semantics.py` (lib). Read `.forge/session-log.jsonl`;
  canonicalize each call to `(verb, args, outcome)` via a rule table mapping
  `(tool, arg-pattern, exit/result, stage) → verb` (REQ-SM-001). Segment the enriched stream into
  outcome-bounded **episodes**, splitting at outcome transitions (failure→fix the key boundary)
  (REQ-SM-002). Pure stdlib; unknown calls → generic verb; never raises.
- **Files**: `scripts/_trace_semantics.py`, `tests/unit/test_trace_semantics.py`
- **Done when**: a fixture session log yields the expected verb sequence and episode boundaries;
  malformed/empty log → `[]`, no raise; the failure→fix boundary is detected.
- **Depends on**: none
- **REQ-IDs**: REQ-SM-001, 002

### T-178 [L] Anti-unification motif miner + success gate
- **Description**: New `scripts/skill_miner_v2.py` (or evolve `mine-skills.py`). Over verb
  sequences from T-177, find ordered fragments recurring across **≥k distinct episodes** and
  **anti-unify** their instances — lift differing literals to named parameters; identical
  diverging values → same variable (REQ-SM-003). Promote a fragment **only if** anti-unification
  yields a coherent parameterized skeleton AND the source episodes are ≥k distinct and **ended in
  success** (REQ-SM-004). Deterministic; stdlib.
- **Files**: `scripts/skill_miner_v2.py`, `scripts/_antiunify.py`, `tests/unit/test_antiunify.py`,
  `tests/unit/test_skill_miner_v2.py`
- **Done when**: AC-SM-001/003/004 — parameterized candidate from 3 distinct successful episodes
  with differing names; nothing from incoherent co-occurrence; failed-only motif not promoted.
- **Depends on**: T-177
- **REQ-IDs**: REQ-SM-003, 004

---

## Milestone 2: Induction + authoring

### T-179 [M] LLM induction with de-specialization
- **Description**: For each candidate cluster, one cheap-model (`haiku`) background dispatch via
  `_background_agent` (structured output `--json-schema`, cost/budget/capability gated) producing
  a **named, parameterized procedure + one-line description + source-trace-line citations**
  (REQ-SM-005). **Degrade**: with no background/LLM (or `FORGE_NO_BACKGROUND=1`), emit the
  deterministic anti-unified skeleton from T-178 — never a hard failure.
- **Files**: `scripts/skill_miner_v2.py` (induction step), `tests/unit/test_skill_miner_v2.py`
- **Done when**: induction returns a structured procedure when available; clean fallback to the
  deterministic skeleton otherwise; never raises; budget-gated.
- **Depends on**: T-178
- **REQ-IDs**: REQ-SM-005, NF-017

### T-180 [L] `forge:skill-creator` skill + agentskills.io emission
- **Description**: Emit proposals as `.forge/proposed-skills/<slug>/SKILL.md` in the
  agentskills.io format (frontmatter `name`/`description` + *When to Use / Procedure / Pitfalls /
  Verification / Provenance*) — never unnamed (REQ-SM-006). New `skills/forge-skill-creator/SKILL.md`
  (`/forge:skill-creator`) that consumes a candidate and runs the author→test→optimize-description
  loop **in-session** (ADR-006), extending the existing `skill-approval` flow (REQ-SM-007).
- **Files**: `skills/forge-skill-creator/SKILL.md`, `scripts/skill_miner_v2.py` (renderer),
  `scripts/skill-approval.py` (extend), tests
- **Done when**: AC-SM-005/006/007 — valid SKILL.md with non-empty third-person description +
  provenance; `/forge:skill-creator` produces a tested skill; nothing installs without approval.
- **Depends on**: T-179
- **REQ-IDs**: REQ-SM-006, 007

---

## Milestone 3: Verify + curate

### T-181 [M] Replay verification before admit
- **Description**: Before admit/install, **replay** a candidate against its source episodes;
  admit only if it reproduces the successful outcome (coding oracle = test suite red→green);
  critic fallback when no runnable oracle (REQ-SM-008). Reuse gate infra.
- **Files**: `scripts/skill_verify.py`, `tests/unit/test_skill_verify.py`
- **Done when**: AC-SM-008 — a candidate that fails replay is not admitted; pass admits.
- **Depends on**: T-180
- **REQ-IDs**: REQ-SM-008

### T-182 [M] Library curation (voting + frequency trim + maintenance)
- **Description**: ExpeL voting on skills — ADD/UPVOTE/DOWNVOTE/EDIT, prune at weight 0 — plus a
  TroVE frequency trim, recorded in `.forge/skill-stats.jsonl`. A scheduled `/dream`-style
  maintenance pass (CLI command, capability/cost-gated) merges near-duplicate descriptions,
  prunes stale/never-used skills, and flags skills referencing missing files/commands
  (REQ-SM-009). `.forge`-only; never raises.
- **Files**: `scripts/skill_curate.py`, `tests/unit/test_skill_curate.py`
- **Done when**: AC-SM-009 — near-dupes merged; unused skill pruned; dangling-reference skill
  flagged; voting updates persisted.
- **Depends on**: T-180
- **REQ-IDs**: REQ-SM-009

---

## Milestone 4: Migrate + release

### T-183 [M] Retire n-gram path + docs
- **Description**: Switch the Stop-hook miner (`stop-reflect.py` / `skill_miner_bg.py`) to the v2
  pipeline; keep existing `proposed-skills/` + `skill-blacklist.txt` honored (REQ-SM-010). Fix the
  `agents/skill-miner.md` doc-drift (`proposals.jsonl` → `proposed-skills/<slug>/SKILL.md`). Update
  `references/` (a `skill-mining.md` like `rules-format.md`) + README.
- **Files**: `hooks/stop-reflect.py`, `scripts/skill_miner_bg.py`, `agents/skill-miner.md`,
  `references/skill-mining.md`, `README.md`, tests
- **Done when**: Stop hook drives v2; legacy artifacts honored; doc-drift fixed; suite green.
- **Depends on**: T-178, T-179
- **REQ-IDs**: REQ-SM-010

### T-184 [S] Release v0.3.5
- **Description**: `bump-version.py 0.3.5`; CHANGELOG `[0.3.5]`; ROADMAP/progress rows; refresh
  banner stats + **re-render `social-preview.png`** (coupled pair). Pre-release green;
  PR→develop→main→tag→mirror both remotes.
- **Files**: `.claude-plugin/*`, `CHANGELOG.md`, `ROADMAP.md`, `build/05-implementation/progress.md`,
  `README.md`, `assets/banner.svg`, `social-preview.png`
- **Done when**: suite green, validate 0, full-pipeline 12/12, manifests 0.3.5, tags on both remotes.
- **Depends on**: T-180, T-181, T-182, T-183
- **REQ-IDs**: (release)

---

## Critical path

```
T-177 → T-178 ─┬─→ T-179 → T-180 ─┬─→ T-181 ─┐
               │                   ├─→ T-182 ─┤
               └─────→ T-183 ──────┴──────────┴─→ T-184 (v0.3.5)
```

M1 (T-177/T-178) is the deterministic core and the highest-value, lowest-risk work — it alone
fixes the noise problem even with no LLM. M2 adds induction + authoring; M3 adds verification +
curation; M4 migrates and ships.

---

## Out of scope (future, v0.3.6+)

- Cross-project skill graduation via `~/.forge` (analogous to lesson promotion).
- Embedding/vector retrieval of skills (Claude's description-matching covers invocation today).
- Fully unattended skill installation (human approval is retained by design).
- RL / weight-level self-improvement (MiMo-model style) — Forge stays prompt/skill-level.
