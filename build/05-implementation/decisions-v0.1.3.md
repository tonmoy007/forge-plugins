# Decisions — Forge v0.1.3

> Decision log for the v0.1.3 patch release. Composes with the v0.1.0 decisions
> log at `build/05-implementation/decisions.md`. Records non-obvious choices and
> their rationale so future sessions don't relitigate them.

---

## D-V13-1 — Hook resilience as a shared runner, not per-hook try/except

**Context**: REQ-RES-001..004 require every hook to be crash-safe and
time-bounded.

**Decision**: A single `scripts/_hook_runner.py` exposes `run_hook(main,
hook_name=...)`; each hook adds a 2-line wrap rather than its own error
handling.

**Why**: One barrier to audit and test; consistent exit-0/exit-2 semantics;
no logic duplication across 7 hooks. Forward-compatible with v0.2 long-lived
daemon hooks.

**Trade-off**: POSIX-only (SIGALRM/setitimer). Windows deferred to v0.2 —
documented in the module docstring and NFR-COMPAT-001.

## D-V13-2 — Blocking hooks never block on internal failure

**Decision**: Only an explicit `sys.exit(2)` from a hook's own logic propagates
as a block. Exceptions and timeouts always resolve to exit 0; accidental exit 2
from non-blocking hooks is suppressed and logged as `unexpected-exit-2`.

**Why**: A Forge bug must never prevent the user from saving a file or stopping.
Worst case is "skip this hook," never "user is stuck." (REQ-RES-003 rationale.)

## D-V13-3 — `/forge:force-advance` allows override but records a lesson

**Decision**: Overriding a blocker advances the stage but does **not** fix the
criteria — they stay failed on subsequent gate runs. `--reason` is mandatory
(≥ 10 chars) and is captured verbatim as a `force-advance` lesson.

**Why**: Gates should be honest negotiations, not jail. The lesson trail makes
repeated overrides on the same gate a visible signal to revisit the criterion
(surfaced in Stage 12 retro). Per-advancement, not per-criterion, keeps the
override auditable.

**Open**: OQ-1 (re-run gate after override?) — deferred; revisit after dogfood.

## D-V13-4 — `script` profile is `suggest_only`, never auto-assigned

**Decision**: The new 6th profile carries `suggest_only: true`. Detection
returns `suggested_profile`, not `assigned_profile`; the init SKILL must prompt
for confirmation before writing `state.md`. Confidence threshold raised to 0.75.

**Why**: Prevents the "I `/forge:init`'d my real project and got a stripped-down
4-stage pipeline" failure (R-V13-5). Other profiles keep auto-assigning until
dogfood shows a need to generalize the flag (OQ-4).

## D-V13-5 — Deterministic-only `/forge:why` and fix hints

**Decision**: `why.py` and the `format-gate-result.py` fix-hint table use
deterministic lookup (longest-prefix gate ID → check-type → universal
fallback). No LLM fallback for unknown IDs in v0.1.3.

**Why**: Predictable, testable, zero added latency (NFR-GATE-001). LLM fallback
is an explicit v0.2 candidate (OQ-3).

## D-V13-6 — Hook-error log: cap detail, defer rotation

**Decision**: `.forge/hook-errors.log` is JSONL with `detail` capped at 1000
chars per record. No rotation in v0.1.3.

**Why**: Cap + expected low frequency keeps the file small. Rotation is paired
with the v0.2 daemon-bus rotation policy to avoid building it twice (OQ-2 /
NFR-RES-002).

## D-V13-7 — T-103 SKILL.md as additive diff, not wholesale replacement

**Decision**: `init-pipeline.sh` was rewritten, but `skills/forge-init/SKILL.md`
changes are applied as additive steps rather than a drop-in replacement.

**Why**: Avoids clobbering existing init behaviors / local author changes
(R-V13-8). Requires reading current SKILL.md state before each edit.
