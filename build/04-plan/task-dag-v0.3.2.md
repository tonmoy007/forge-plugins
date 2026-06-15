# Task DAG — Forge v0.3.2 + v0.3.3 (autonomy + modernized harness)

> **Status**: **Ready to build** (2026-06-15). Derived from `build/01-srs/srs-v0.3.2.md`.
> Numbering continues from v0.3.1 (T-157..T-166); this is **T-167..T-176**.
>
> Format: `T-NNN [size] title` — Size: S (~30min), M (~2hr), L (~half-day).
>
> | Milestone | Tag | Gate |
> |-----------|-----|------|
> | M1 Modernized harness | v0.3.2 | none — build now |
> | M2 Complete autonomy | v0.3.3 | M1 landed |
>
> **Invariants** (every task): stdlib + PyYAML fail-soft; never-raises; capability + cost
> gating; `.forge/`-only writes for background work; TDD red-first; suite green per task
> (REQ-NF-013..015). **Harness tasks additionally: verify the current Claude API/Code
> surface before implementing, and degrade to today's behavior when the primitive is
> absent** (REQ-NF-013).

---

## Milestone 1: Modernized harness (v0.3.2)

### T-167 [M] Structured outputs in `_orchestrate`
- **Description**: Request schema-constrained JSON for orchestrated dispatches (reviewers,
  extractors) via the current structured-outputs API; keep the parse/retry/drop path as a
  fallback when unavailable. **Verify the current `output_config.format` / `messages.parse`
  surface first.**
- **Files**: `scripts/_orchestrate.py`, `hooks/_background_agent.py` (pass-through),
  `tests/unit/test_orchestrate.py`
- **Done when**: a malformed dimension is re-requested via schema and parsed; fallback path
  intact when structured outputs are off; never-raises.
- **Depends on**: none
- **REQ-IDs**: REQ-HARNESS-001, NF-013

### T-168 [M] Run-level task budget on dispatch
- **Description**: `_background_agent.dispatch` accepts an optional token **task budget**
  (model self-moderates) alongside the `_cost_cap` $ gate; autopilot threads a per-run
  budget. **Verify the current task-budget beta** first; degrade to cost-cap-only when
  absent.
- **Files**: `hooks/_background_agent.py`, `scripts/autopilot.py`,
  `tests/unit/test_background_agent.py`, `tests/unit/test_autopilot.py`
- **Done when**: budget passed through when available; cost-cap-only fallback verified;
  over-budget stops cleanly; never-raises.
- **Depends on**: none
- **REQ-IDs**: REQ-HARNESS-002, NF-013, NF-014

### T-169 [S] Per-stage model routing
- **Description**: `.forge/config.yaml` → `autopilot.models` maps stages/classes to models
  (capable for build/arch, cheap for gate-check/narration); read fail-soft; absent ⇒
  single-model behavior.
- **Files**: `scripts/autopilot.py`, `tests/unit/test_autopilot.py`
- **Done when**: mapped model used per stage; absent config unchanged; invalid entries
  ignored fail-soft.
- **Depends on**: T-168
- **REQ-IDs**: REQ-HARNESS-003

### T-170 [M] Long-run context management (compaction)
- **Description**: Enable compaction / context editing for long background autopilot
  dispatches so unattended runs don't exhaust context. **Verify the current compaction beta**;
  no-op/fallback when unavailable.
- **Files**: `hooks/_background_agent.py`, `tests/unit/test_background_agent.py`
- **Done when**: compaction enabled when available; clean fallback otherwise; never-raises.
- **Depends on**: T-168
- **REQ-IDs**: REQ-HARNESS-004, NF-013

### T-171 [S] Release v0.3.2
- **Description**: README harness/config notes; `bump-version.py 0.3.2`; CHANGELOG
  `[0.3.2]`; ROADMAP/progress rows. Pre-release green; PR→develop→main→tag→mirror.
- **Files**: `README.md`, `CHANGELOG.md`, `ROADMAP.md`, `build/05-implementation/progress.md`, `.claude-plugin/*`
- **Done when**: suite green, validate 0, full-pipeline 12/12, manifests 0.3.2, tag on both remotes.
- **Depends on**: T-167, T-168, T-169, T-170
- **REQ-IDs**: (release)

---

## Milestone 2: Complete autonomy (v0.3.3)

### T-172 [L] Self-heal loop (blocker → resolve → re-gate)
- **Description**: On a blocking gate failure, autopilot dispatches a **bounded**
  `/forge:resolve` fix (cost+budget gated), re-runs `check-gate`, advances on pass; capped
  by `autopilot.max_heal_attempts` (default 1; 0 = stop-on-gate); on exhaustion STOPS and
  surfaces blockers — never force unless `allow_force`+reason.
- **Files**: `scripts/autopilot.py`, `skills/forge-autopilot/SKILL.md`,
  `tests/unit/test_autopilot.py`
- **Done when**: one heal attempt by default; advance on heal-then-pass; STOP after cap;
  `max_heal_attempts:0` == v0.3.1; never-raises.
- **Depends on**: T-171
- **REQ-IDs**: REQ-AUTO-001, 002, NF-014

### T-173 [M] Self-verification (verifier subagents)
- **Description**: After a gate passes, optionally run an independent fresh-context verifier
  (structured verdict) checking the artifact against stage intent; a fail is treated like a
  blocker (heal/stop). Bounded + budget-gated. **Verify current subagent/Task surface.**
- **Files**: `skills/forge-autopilot/SKILL.md`, `scripts/autopilot.py` (verdict plumbing),
  `tests/unit/test_autopilot.py`
- **Done when**: verifier runs when enabled; fail routes to heal/stop; disabled ⇒ unchanged;
  bounded.
- **Depends on**: T-172
- **REQ-IDs**: REQ-AUTO-003, NF-013, NF-014

### T-174 [M] `--unattended` mode
- **Description**: No per-stage checkpoints; interactive stages use
  `.forge/autopilot-answers.*` or record reasonable defaults as assumptions in the run-log
  (never a silent guess); bounded by the full safety envelope (task budget, cost cap,
  max_heal, max_stages, kill switch, stop flag); clean STOP + resumable state on any bound.
- **Files**: `scripts/autopilot.py`, `skills/forge-autopilot/SKILL.md`,
  `tests/unit/test_autopilot.py`
- **Done when**: runs checkpoint-free; assumptions recorded; STOPS cleanly at any bound;
  `--resume` continues.
- **Depends on**: T-172
- **REQ-IDs**: REQ-AUTO-004, 005, NF-014

### T-175 [M] Enforcing rules (unattended guardrail)
- **Description**: Extend v0.3.0 rules with `enforce: true` (+ `severity`); an enforcing
  `glob` rule blocks a violating write via `pre-tool-write` (exit 2). Advisory stays the
  default; non-enforcing/non-matching unchanged. Update `rules.py`, `references/rules-format.md`.
- **Files**: `scripts/rules.py`, `hooks/pre-tool-write.py`, `references/rules-format.md`,
  `tests/unit/test_rules.py`, `tests/unit/test_pre_tool_write.py`
- **Done when**: enforcing rule blocks (exit 2) on match; advisory + non-match unaffected;
  fail-soft when rules dir absent.
- **Depends on**: T-171
- **REQ-IDs**: REQ-AUTO-006, NF-014

### T-176 [S] Release v0.3.3
- **Description**: README autonomy section; `bump-version.py 0.3.3`; CHANGELOG `[0.3.3]`;
  ROADMAP/progress rows. Pre-release green; PR→develop→main→tag→mirror.
- **Files**: `README.md`, `CHANGELOG.md`, `ROADMAP.md`, `build/05-implementation/progress.md`, `.claude-plugin/*`
- **Done when**: suite green, validate 0, full-pipeline 12/12, manifests 0.3.3, tag on both remotes.
- **Depends on**: T-172, T-173, T-174, T-175
- **REQ-IDs**: (release)

---

## Critical path

```
T-167 ─┐
T-168 ─┼─→ T-169 ─┐
       └─→ T-170 ─┤
                  └─→ T-171 (v0.3.2) ─┬─→ T-172 ─┬─→ T-173 ─┐
                                      │          └─→ T-174 ─┤
                                      └─→ T-175 ───────────┴─→ T-176 (v0.3.3)
```

M1 tasks T-167/T-168 are independent and parallelizable; T-169/T-170 build on T-168.
T-171 ships v0.3.2. The autonomy chain (T-172 self-heal → T-173 verify / T-174 unattended,
plus T-175 enforcing rules) ships as v0.3.3.

---

## Out of scope (future)

- **v0.3.4+ — Hosted autonomy (Managed Agents):** `--mode managed` (Anthropic-run loop +
  container), gate-derived Outcome rubric, scheduled deployments. Deferred per the v0.3.2
  scoping decision (local-only autonomy first).
