# SRS — Forge v0.3 (program scope, phased)

> **Status**: **Draft — ready for build** (2026-06-15). Composes additively with
> `srs.md` and the v0.1.x / v0.2.x deltas. Derived from the approved plan
> "Autopilot Mode + Rules Setup" (`~/.claude/plans/tidy-roaming-piglet.md`).
>
> **Baseline**: Forge **v0.2.3** is released — `main` at `2f54489`, 1124+ tests green,
> 10 project-type profiles, background daemons (Observer/Dreamer/Health), orchestration
> primitive, brownfield adopt, cost cap + ledger, `bump-version.py`. v0.3 builds on that.
>
> **Theme**: move Forge from *a system that works alongside you* to one you can
> **hand the wheel to, under your rules** — autonomous cross-stage execution with
> safety rails (Autopilot) and a user-authored constraints surface that steers every
> agent (Rules).

---

## 1. Overview

### 1.1 Objective

Add two capability areas on top of v0.2, **without breaking any v0.1/v0.2 behavior** and
**without making either mandatory**: (a) a user-authored **Rules** surface, and (b) an
**Autopilot** that drives the 12-stage pipeline hands-off within bounds. Everything
degrades to a clean no-op when unused (no rules dir → no rules; no autopilot invocation →
the pipeline behaves exactly as today).

### 1.2 Phasing

v0.3 ships as two phased sub-releases, each its own tag, each independently green
(full suite + `validate-plugin.py` exit 0 + `full-pipeline.sh` 12/12):

| Phase | Tag | Scope | Gate |
|-------|-----|-------|------|
| **P1 Rules (governance)** | v0.3.0 | `.forge/rules/*.md`, loader, `/forge:rules`, session-start + pre-tool-write injection | none — build now |
| **P2 Autopilot (autonomy)** | v0.3.1 | cross-stage loop skill + planner, both execution substrates, cancel/resume | P1 lands first (autopilot consults rules) |

Rules ship first because Autopilot **consults** them (a user rule can bound autopilot).

### 1.3 Scope

**In scope** — the two areas above + their docs, references, and tests.

**Out of scope (v0.4+)** — Python package extraction; multi-tenant; standalone CLI;
a full policy DSL / blocking rule enforcement (rules are advisory in v0.3, matching the
existing design-system check); per-rule LLM "agent-requested" retrieval beyond a `manual`
scope marker.

### 1.4 Provenance

Net-new capability (not in `srs-v0.2.md`). Relationship to existing features:
- **Autopilot** generalizes `force-advance` (one gated advance) and `build-batch`
  (within-stage task batch) to a **cross-stage** loop.
- **Rules** generalizes the `pre-tool-write` design-system check (hardcoded rules) into a
  **user-authored** surface, reusing the lessons-injection mechanics.

---

## 2. Functional Requirements

### 2.1 Rules — storage & loader (P1)

- **REQ-RULES-001 — Rules surface.** A project may define user rules as Markdown files
  under `.forge/rules/*.md`. Each file has YAML frontmatter
  `{description, scope, stages?, globs?, priority?}` + a Markdown body (the rule text).
  Absent directory ⇒ feature is a silent no-op.
- **REQ-RULES-002 — Scope model.** `scope ∈ {always, stage, glob, manual}`:
  `always` (every session), `stage` (only when `current_stage ∈ stages`), `glob`
  (only on writes to files matching `globs`), `manual` (loaded only when explicitly
  referenced; never auto-injected).
- **REQ-RULES-003 — Loader.** `scripts/rules.py` exposes `load_rules(forge_dir)`,
  `select(rules, *, stage, file_path, scope)`, and `render(rules, max_chars)`. It parses
  frontmatter with the in-repo `_state_lib._split_frontmatter` helper + PyYAML — **no
  third-party `frontmatter` dependency** (lesson 2026-05-24). Malformed files are skipped
  fail-soft; the loader **never raises**.
- **REQ-RULES-004 — Glob matching.** `glob`-scoped rules match `file_path` via stdlib
  `fnmatch`/`pathlib` (e.g. `**/*.tsx`).

### 2.2 Rules — authoring skill (P1)

- **REQ-RULES-005 — `/forge:rules`.** A skill (`skills/forge-rules/`, `name: rules`)
  with subcommands `init | list | add <name> | validate`.
- **REQ-RULES-006 — `init` scaffold.** Creates `.forge/rules/` with a short `README.md`,
  a commented example, and a `00-style.md` template, idempotently (warns, never clobbers).
- **REQ-RULES-007 — `validate`.** Reports malformed frontmatter / unknown scope / empty
  body without raising; exit non-zero only on a usage error.
- **REQ-RULES-008 — Format reference.** `references/rules-format.md` documents the schema
  and scope model (loaded on demand, like `daemon-bus.md`).

### 2.3 Rules — injection & enforcement (P1)

- **REQ-RULES-009 — Session-start injection.** `hooks/session-start.py` injects
  `always` + `stage`(=current_stage) rules into the context block, **within the existing
  ≤2000-token budget** (REQ-NF-011): rules are trimmed before lessons to stay under budget.
- **REQ-RULES-010 — Write-time injection.** `hooks/pre-tool-write.py` appends
  `glob`-matching rule text to its advisory `additionalContext` (alongside design-system
  feedback). **Never blocks** the write (exit 0). Active only when `.forge/rules/` exists.
- **REQ-RULES-011 — No state mutation.** Rule injection is read-only context; it does not
  write pipeline state and needs no proposal/validator/executor path. `/forge:rules add`
  is a direct user-authoring write (like editing `tasks/lessons.md`).

### 2.4 Autopilot — planner (P2)

- **REQ-AP-001 — Deterministic planner.** `scripts/autopilot.py` (no LLM) reads
  `pipeline/state.md` + `_stage_table` and emits the ordered stage plan, honoring the
  cycle entry/exit and `bounds` (cycle-wrap), with **no side effects** under `--dry-run`.
- **REQ-AP-002 — Bounds & targets.** Targets `--to N`, `--stages K`, `--until-gate`;
  plus an optional `.forge/config.yaml` → `autopilot:` block
  (`max_stages`, `stop_before`, `checkpoint: every|gate|never`, `allow_force: false`),
  read **fail-soft** like `cost_cap`.
- **REQ-AP-003 — Resume & idempotency.** `--resume` skips stages already completed in
  `.forge/autopilot-runs.jsonl`; the run/stop record lives in
  `.forge/autopilot-session.json`. Logs rotate via `_error_log.append_jsonl`. `.forge/`
  is the only write boundary.

### 2.5 Autopilot — execution (P2)

- **REQ-AP-004 — Skill-driven loop.** `skills/forge-autopilot/` (`name: autopilot`)
  drives, per planned stage: run the stage agent → `check-gate.py` → on **pass**
  `state-manager advance`; on **blocker STOP** and surface (default), never auto-forcing.
  (ADR-006: a script cannot drive the in-session Agent tool, so the loop is skill-driven.)
- **REQ-AP-005 — Stop-on-gate (safety).** Autopilot **never** force-advances past a
  blocking gate unless `autopilot.allow_force: true` AND an explicit reason is supplied;
  otherwise it stops and points the user to `/forge:force-advance` (REQ-NF-012).
- **REQ-AP-006 — Dual substrate via `--mode`.** `in-session` (default; reuses stage
  agents in the user's session; no extra spend) **or** `background` (each stage via
  `_background_agent.dispatch`: cost-gated, capability-gated, session-reuse,
  never-raises; clean no-op when capability absent or `FORGE_NO_BACKGROUND=1`).
- **REQ-AP-007 — Cancel.** `/forge:autopilot-stop` writes a stop flag the loop checks
  between stages; start is idempotent (warns if already running) — Observer-daemon idiom.
- **REQ-AP-008 — Rules-aware & interactive-aware.** Autopilot surfaces `always` rules to
  the loop and respects stages' CLARIFY/CONFIRM interactivity (stages 1/4/5).
- **REQ-AP-009 — Narration.** Each step narrates `[Forge] autopilot: stage N → …`
  (build-batch stderr idiom) and appends a run-log row.

---

## 3. Non-Functional Requirements

> Reuses the v0.2 NFR set (REQ-NF-001..010); adds two.

- **REQ-NF-011 — Rules within token budget.** Session-start context (state + lessons +
  rules) stays ≤ 2000 tokens; rules trim first.
- **REQ-NF-012 — Autopilot is bounded & reversible.** Default stop-on-gate; never an
  unbounded run; every advance goes through the sanctioned `advance_stage` path and is
  recorded; the kill switch and cost cap apply to the background substrate.
- Inherited (must hold): stdlib-only hooks (PyYAML sole dep, **fail-soft**),
  **never-raises** in hooks/background, capability + cost gating, `.forge/`-only writes
  for background features, one adapter per host mechanism, two-remote parity, `python3`.

---

## 4. Acceptance Criteria

- **AC-RULES-001** — With `.forge/rules/00-style.md` (`scope: glob, globs:["**/*.tsx"]`),
  a `Write` to `app/Button.tsx` surfaces the rule via `additionalContext`; a write to
  `README.md` does not. No write is ever blocked.
- **AC-RULES-002** — A `scope: stage, stages:[6]` rule appears in the session-start block
  only when `current_stage == 6`, and total context stays ≤ 2000 tokens.
- **AC-RULES-003** — No `.forge/rules/` ⇒ session-start and pre-tool-write behave exactly
  as v0.2 (no new output); a malformed rule file is skipped without error.
- **AC-AP-001** — `autopilot.py --dry-run --to 6` prints the correct ordered stage plan
  with no file changes.
- **AC-AP-002** — With a forced blocking gate at the current stage, the loop **STOPS**
  (does not advance) and surfaces the blocker; with `allow_force:false` it never forces.
- **AC-AP-003** — `--mode background` with `FORGE_NO_BACKGROUND=1` (or capability absent)
  is a clean no-op; `--resume` skips stages already in `autopilot-runs.jsonl`.

---

## 5. Traceability

| REQ-ID | Task |
|--------|------|
| REQ-RULES-001..004 | T-157 |
| REQ-RULES-005..008 | T-158 |
| REQ-RULES-009, NF-011 | T-159 |
| REQ-RULES-010, 011 | T-160 |
| (P1 docs + release) | T-161 |
| REQ-AP-001..003 | T-162 |
| REQ-AP-004, 005, 008, 009, NF-012 | T-163 |
| REQ-AP-006 | T-164 |
| REQ-AP-007 | T-165 |
| (P2 docs + release) | T-166 |
