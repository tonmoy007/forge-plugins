# Task DAG — Forge v0.3.6 (context-aware autopilot)

> **Status**: **Ready to build** (2026-06-16). Derived from `build/01-srs/srs-v0.3.6.md`.
> Numbering continues from v0.3.5 (T-177..T-184); this is **T-185..T-190**.
>
> Format: `T-NNN [size] title` — Size: S (~30min), M (~2hr), L (~half-day).
>
> | Milestone | Tag | Gate |
> |-----------|-----|------|
> | M1 Background path | — | none — build first |
> | M2 In-session path | — | M1 landed (shared checkpoint) |
> | M3 Docs + release | v0.3.6 | M1–M2 landed |
>
> **Invariants** (every task): stdlib + PyYAML fail-soft; **never-raises** (hooks +
> background path); the PreCompact hook **never blocks** (exit 0); opt-in — zero behavior
> change when `context_window_size` is unset; capability/cost gating + full autopilot safety
> envelope preserved; `.forge/`-only **atomic** writes; TDD red-first; full suite +
> `validate-plugin.py` 0 + `full-pipeline.sh` 12/12 green per task. Reuses `should_rotate_session`
> + `rotate⇒resume=None`, `AutopilotConfig`/`load_config`, `record_run` + run-log `--resume`,
> the dispatch envelope `usage`, `_error_log.append_jsonl` + atomic writer, session-start
> injection budget + capability-upkeep idiom.

---

## Milestone 1: Background path (precise, Forge-controlled)

### T-185 [M] Token-pressure rotation trigger + opt-in config
- **Description**: Add `context_threshold_percent` (default 80) and `context_window_size`
  (no default ⇒ feature off) to `AutopilotConfig` + `load_config` (fail-soft coercion,
  invalid ignored). Surface `usage.input_tokens` out of `_background_agent.dispatch` and
  thread the last dispatch's `input_tokens` into the loop/dispatch path. Add
  `should_rotate_for_context(last_input_tokens, config) -> bool` (true iff window set and
  `input_tokens ≥ threshold% × window`); the rotate decision OR-combines it with the existing
  count-based `should_rotate_session`. Reuse the `rotate=True ⇒ resume=None` rotation.
- **Files**: `scripts/autopilot.py`, `hooks/_background_agent.py` (pass-through),
  `tests/unit/test_autopilot.py`, `tests/unit/test_background_agent.py`
- **Done when**: AC-CTX-001/002 — threshold boundary flips rotation; window-unset ⇒ never;
  OR-combine verified; never raises on garbage. Config round-trips fail-soft.
- **Depends on**: none
- **REQ-IDs**: REQ-CTX-001, 002, 003, NF-021

### T-186 [M] Shared checkpoint artifact + `checkpoint` subcommand
- **Description**: Implement `.forge/autopilot-checkpoint.json` — atomic (temp-then-rename),
  `schema_version`, fail-soft read, fields per REQ-CTX-004. Add an `autopilot.py checkpoint`
  CLI subcommand that writes/refreshes it; call it before a rotation and on stage advance.
  Idempotency stays in the existing run-log (`record_run` + `--resume`); the checkpoint adds
  the `next_action` pointer. Reuse `_error_log.append_jsonl` / the existing atomic writer.
- **Files**: `scripts/autopilot.py`, `tests/unit/test_autopilot.py`
- **Done when**: AC-CTX-003/004/007 — round-trip with schema; malformed ⇒ absent, no raise;
  atomic; `checkpoint` subcommand writes/refreshes; `--resume` still skips completed stages.
- **Depends on**: T-185
- **REQ-IDs**: REQ-CTX-004, 005, 008, NF-023

---

## Milestone 2: In-session path (ride native compaction)

### T-187 [M] PreCompact hook (checkpoint before compaction)
- **Description**: New `hooks/pre-compact.py` — stdlib, never-raises, **never blocks**
  (always exit 0). When an autopilot run is active (`.forge/autopilot-session.json`),
  write/refresh the T-186 checkpoint before native compaction; clean no-op otherwise.
  Register a `PreCompact` event in `.claude-plugin/plugin.json` (short timeout).
- **Files**: `hooks/pre-compact.py`, `.claude-plugin/plugin.json`,
  `tests/unit/test_pre_compact.py`
- **Done when**: AC-CTX-005 — writes a checkpoint only when a run is active; exits 0 for
  active/inactive/malformed-state/missing-`.forge`; never blocks. `validate-plugin.py` 0 with
  the new hook registered.
- **Depends on**: T-186
- **REQ-IDs**: REQ-CTX-006, NF-020

### T-188 [M] SessionStart(`compact`) resume injection + SKILL.md loop
- **Description**: Enhance `hooks/session-start.py` to detect `source == "compact"` + an
  active run and inject a concise resume block (current stage, next action, explicit
  do-not-redo) within the ≤2000-token budget; add the `compact` matcher to the SessionStart
  registration in the manifest. Update `skills/forge-autopilot/SKILL.md`: insert the
  context-check step between gate-check and next dispatch (read last `input_tokens` →
  on cross, `autopilot.py checkpoint` then rotate next dispatch); document the in-session
  checkpoint-before/resume-after behavior and the config knobs.
- **Files**: `hooks/session-start.py`, `.claude-plugin/plugin.json`,
  `skills/forge-autopilot/SKILL.md`, `tests/unit/test_session_start.py`
- **Done when**: AC-CTX-006 — injects resume only on `source=compact` + active run, within
  budget, with the do-not-redo guard; no-op otherwise; SKILL.md documents the loop step.
- **Depends on**: T-186
- **REQ-IDs**: REQ-CTX-007, 009, NF-020

---

## Milestone 3: Docs + release

### T-189 [S] Reference doc + README
- **Description**: `references/autopilot-context.md` (threshold/checkpoint/rotation model,
  in-session vs background, the config knobs, the upstream limitation). README autopilot section.
- **Files**: `references/autopilot-context.md`, `README.md`
- **Done when**: doc explains both substrates + config; README updated; suite green.
- **Depends on**: T-187, T-188
- **REQ-IDs**: REQ-CTX-009

### T-190 [S] Release v0.3.6
- **Description**: `bump-version.py 0.3.6`; CHANGELOG `[0.3.6]`; ROADMAP + progress rows;
  refresh banner stats + **re-render `social-preview.png`** (coupled pair). Pre-release green;
  PR→develop→main→tag `v0.3.6`→mirror both remotes→GitHub releases→delete branch.
- **Files**: `.claude-plugin/*`, `CHANGELOG.md`, `ROADMAP.md`,
  `build/05-implementation/progress.md`, `README.md`, `assets/banner.svg`, `social-preview.png`
- **Done when**: suite green, validate 0, full-pipeline 12/12, manifests 0.3.6, tags on both remotes.
- **Depends on**: T-185, T-186, T-187, T-188, T-189
- **REQ-IDs**: (release)

---

## Critical path

```
T-185 → T-186 ─┬─→ T-187 ─┐
               └─→ T-188 ─┴─→ T-189 → T-190 (v0.3.6)
```

T-185 (signal + trigger + config) is the foundation; T-186 (checkpoint) builds on it and is
the shared artifact both substrate tasks need. T-187 (PreCompact) and T-188
(SessionStart-resume + loop) are independent and parallelizable once T-186 lands. T-189 docs,
T-190 ships.

---

## Out of scope (future, v0.3.7+)

- True in-session configurable-% trigger (blocked on upstream Claude Code: #46695 / #25689 /
  a `ContextThreshold` hook event).
- Programmatic API-level compaction (`context_management: compact_20260112`) — not injectable
  via `claude -p`.
- Sub-stage/step-level checkpoints; semantic summarization of the work itself.
