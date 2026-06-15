# Task DAG — Forge v0.3 (program, phased)

> **Status**: **Ready to build** (2026-06-15). Derived from `build/01-srs/srs-v0.3.md`.
> Numbering continues from v0.2 (T-136..T-156); v0.3 is **T-157..T-166**.
>
> Format: `T-NNN [size] title` — Size: S (~30min), M (~2hr), L (~half-day).
>
> **Phased shipping** — each milestone is its own tag, each independently green
> (full suite + `validate-plugin.py` exit 0 + `full-pipeline.sh` 12/12):
>
> | Milestone | Tag | Gate |
> |-----------|-----|------|
> | M1 Rules (governance) | v0.3.0 | none — build now |
> | M2 Autopilot (autonomy) | v0.3.1 | M1 landed (autopilot consults rules) |
>
> **Invariants** (every task): stdlib-only hooks (PyYAML fail-soft), never-raises,
> capability + cost gating for background work, `.forge/`-only writes, one adapter per
> host mechanism, TDD red-first, suite green after each task (REQ-NF-001..012).

---

## Milestone 1: Rules — governance surface (v0.3.0)

### T-157 [M] Rules loader — `scripts/rules.py`
- **Description**: Parse `.forge/rules/*.md` (frontmatter via
  `_state_lib._split_frontmatter` + PyYAML — no `frontmatter` dep). `load_rules`,
  `select(stage/file_path/scope)` with `fnmatch` globs, `render(max_chars)`. Stdlib +
  PyYAML fail-soft, never-raises. Thin CLI (`list`, `validate`) with argparse `SUPPRESS`
  for shared `--cwd`.
- **Files**: `scripts/rules.py`, `tests/unit/test_rules.py`
- **Done when**: parse + scope filtering + glob match covered; malformed file skipped
  (no raise); absent dir → empty result; CLI `validate` exits 0 on a clean dir.
- **Depends on**: none
- **REQ-IDs**: REQ-RULES-001, 002, 003, 004

### T-158 [M] `/forge:rules` skill + format reference
- **Description**: `skills/forge-rules/SKILL.md` (`name: rules`) — `init|list|add|validate`.
  `init` scaffolds `.forge/rules/` (README + commented example + `00-style.md`),
  idempotent. `references/rules-format.md` documents the schema + scope model.
- **Files**: `skills/forge-rules/SKILL.md`, `references/rules-format.md`,
  `tests/unit/test_rules_skill.py` (structural)
- **Done when**: skill frontmatter valid (`/forge:rules` registers); `init` is idempotent;
  reference documents all four scopes.
- **Depends on**: T-157
- **REQ-IDs**: REQ-RULES-005, 006, 007, 008

### T-159 [M] Session-start injection of always/stage rules
- **Description**: In `hooks/session-start.py`, after lessons, inject `always` +
  `stage`(=current_stage) rules within the ≤2000-token budget (trim rules before lessons).
  New helper beside `_load_lessons`/`_compose`.
- **Files**: `hooks/session-start.py`, `tests/unit/test_session_start.py`
- **Done when**: stage rule appears only at its stage; budget held; absent dir = silent
  no-op; malformed file ignored.
- **Depends on**: T-157
- **REQ-IDs**: REQ-RULES-009, REQ-NF-011

### T-160 [M] Pre-tool-write glob-scoped rule injection
- **Description**: In `hooks/pre-tool-write.py`, append `glob`-matching rule text to the
  advisory `additionalContext` next to design-system feedback. Never block (exit 0). Only
  when `.forge/rules/` exists.
- **Files**: `hooks/pre-tool-write.py`, `tests/unit/test_pre_tool_write.py`
- **Done when**: matching glob surfaces the rule; non-match silent; write never blocked;
  no rules dir = unchanged behavior.
- **Depends on**: T-157
- **REQ-IDs**: REQ-RULES-010, 011

### T-161 [S] Release v0.3.0
- **Description**: README rules section; `progress.md` rows; ROADMAP row; `bump-version.py
  0.3.0`; fill CHANGELOG `[0.3.0]`. Pre-release green. PR→develop→main→tag→mirror.
- **Files**: `README.md`, `CHANGELOG.md`, `ROADMAP.md`,
  `build/05-implementation/progress.md`, `.claude-plugin/*` (via bump)
- **Done when**: suite green, validate 0, full-pipeline 12/12, manifests 0.3.0, tag
  `v0.3.0` on both remotes.
- **Depends on**: T-158, T-159, T-160
- **REQ-IDs**: (release)

---

## Milestone 2: Autopilot — autonomy (v0.3.1)

### T-162 [M] Autopilot planner — `scripts/autopilot.py`
- **Description**: Deterministic (no LLM) stage-plan generator from `_stage_table` +
  state; targets `--to/--stages/--until-gate`; cycle-wrap aware; `--dry-run` (no side
  effects); `--mode in-session|background`; `--resume` from `.forge/autopilot-runs.jsonl`;
  reads `autopilot:` config fail-soft.
- **Files**: `scripts/autopilot.py`, `tests/unit/test_autopilot.py`
- **Done when**: `--dry-run --to N` prints correct ordered plan; bounds/targets honored;
  resume skips logged stages; never raises on missing/odd state.
- **Depends on**: T-161
- **REQ-IDs**: REQ-AP-001, 002, 003

### T-163 [M] `/forge:autopilot` skill (in-session loop)
- **Description**: Skill (`name: autopilot`) walks the planner output: stage agent →
  check-gate → advance on pass / STOP on blocker (no auto-force unless `allow_force` +
  reason). Surfaces `always` rules; respects CLARIFY/CONFIRM; narrates + logs each step.
- **Files**: `skills/forge-autopilot/SKILL.md`, `tests/unit/test_autopilot_skill.py`
- **Done when**: loop advances on pass, stops on blocker, never forces by default; rules
  consulted; narration emitted.
- **Depends on**: T-162
- **REQ-IDs**: REQ-AP-004, 005, 008, 009, REQ-NF-012

### T-164 [M] Background substrate (`--mode background`)
- **Description**: Per-stage dispatch via `_background_agent.dispatch` (cost + capability
  gated, session-reuse, never-raises); clean no-op when unavailable / kill-switched.
- **Files**: `scripts/autopilot.py` (mode branch), `tests/unit/test_autopilot.py`
- **Done when**: background path cost/capability-gated; `FORGE_NO_BACKGROUND=1` = no-op;
  in-session path unaffected.
- **Depends on**: T-163
- **REQ-IDs**: REQ-AP-006

### T-165 [S] `/forge:autopilot-stop` + cancel/idempotency
- **Description**: `skills/forge-autopilot-stop/` writes a stop flag in
  `.forge/autopilot-session.json`; loop checks it between stages; idempotent start.
- **Files**: `skills/forge-autopilot-stop/SKILL.md`, `tests/unit/test_autopilot.py`
- **Done when**: stop flag halts the loop at the next boundary; double-start warns.
- **Depends on**: T-163
- **REQ-IDs**: REQ-AP-007

### T-166 [S] Release v0.3.1
- **Description**: README autopilot section; progress/ROADMAP rows; `bump-version.py
  0.3.1`; CHANGELOG `[0.3.1]`. Pre-release green. PR→develop→main→tag→mirror.
- **Files**: `README.md`, `CHANGELOG.md`, `ROADMAP.md`,
  `build/05-implementation/progress.md`, `.claude-plugin/*` (via bump)
- **Done when**: suite green, validate 0, full-pipeline 12/12, manifests 0.3.1, tag
  `v0.3.1` on both remotes.
- **Depends on**: T-162, T-163, T-164, T-165
- **REQ-IDs**: (release)

---

## Critical path

```
T-157 ─┬─→ T-158 ─┐
       ├─→ T-159 ─┼─→ T-161 (v0.3.0) ─→ T-162 ─→ T-163 ─┬─→ T-164 ─┐
       └─→ T-160 ─┘                                      └─→ T-165 ─┴─→ T-166 (v0.3.1)
```

T-157 unblocks the three P1 integrations (parallelizable); T-161 ships v0.3.0; the
autopilot chain follows.
