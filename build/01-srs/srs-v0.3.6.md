# SRS — Forge v0.3.6 (context-aware autopilot: checkpoint → compact → continue)

> **Status**: **Draft — ready for build** (2026-06-16). Continues the v0.3 program.
> Adds context-pressure-aware checkpointing to autopilot so long hands-off runs survive
> a context/compaction boundary without losing "what was I doing / what's next."
>
> **Grounding**: derived from a 2026-06-16 research review of Claude Code compaction +
> hooks, the Claude Agent SDK / Messages-API context-management primitives, and industry
> long-run agent frameworks (Letta/MemGPT, OpenHands, Cline, Roo, LangGraph, Manus,
> Cognition/Devin, Slack, Anthropic's long-run-harness guidance). Key citations inlined in §6.

---

## 1. Overview

### 1.1 Problem

During a long hands-off **autopilot** run (driving the 12-stage pipeline, or a bounded
slice), the conversation context fills up. The user wants Forge to, at a **configurable
threshold**, automatically **add/update a checkpoint → compact → continue** so the run
resumes cleanly across the context boundary.

Two hard constraints from the platform shape what is buildable:

1. **No live context metric, no programmatic compaction (in-session).** Claude Code does
   not expose context-usage % to hooks/scripts, and hooks cannot *trigger* compaction —
   only the user (`/compact`) or the runtime (native auto-compact, ~95%) can. A
   configurable in-session threshold is an open upstream request (anthropics/claude-code
   #46695, #25689), not available today. The PreCompact hook can only act *before* a
   compaction that the runtime initiates; SessionStart with a `compact` matcher can
   re-inject state *after*.
2. **Background dispatches DO carry a usable signal.** `claude -p --resume` returns
   `usage.input_tokens` per turn in its JSON envelope (`hooks/_background_agent.py`); for a
   *resumed* session that figure approximates current context size — a real, deterministic
   context-pressure proxy Forge already receives.

Forge already bounds long runs via **session rotation** (`should_rotate_session`,
`scripts/autopilot.py`, T-170/REQ-HARNESS-004) — but keyed on *dispatch count*, not
context pressure.

### 1.2 Objective

Deliver "threshold → checkpoint → compact → continue" across **both** autopilot
substrates:

- **Background** (Forge-controlled): trigger on the real token signal — when a resumed
  dispatch's `input_tokens ≥ threshold% × window`, write a checkpoint and **rotate to a
  fresh session** (rotation *is* "compact → continue": the bloated session is discarded
  and a clean one is seeded by the checkpoint + run-log).
- **In-session** (ride the native lifecycle): a **PreCompact** hook writes a checkpoint
  *before* native compaction; **SessionStart(`compact`)** re-injects resume state *after*,
  so the loop continues without redoing completed stages.

A single, schema-versioned **checkpoint artifact** serves both; stage-level
**idempotency** reuses the existing run-log so resume never redoes work.

### 1.3 Scope

**In scope** — the opt-in config knobs, the token-pressure rotation trigger, the shared
checkpoint artifact + `checkpoint` CLI subcommand, the PreCompact hook, the
SessionStart(`compact`) resume injection, the autopilot SKILL.md loop integration, docs.
Reuses: `should_rotate_session` + `rotate⇒resume=None` rotation, `AutopilotConfig`/
`load_config` fail-soft coercion, `read_session`/`record_run` + run-log `--resume`
idempotency, the dispatch envelope `usage`, `_error_log.append_jsonl` + atomic writer, the
session-start injection budget and capability-upkeep idiom.

**Out of scope (future)** — a true in-session configurable-% trigger (blocked upstream:
#46695/#25689/a `ContextThreshold` hook); programmatic API-level compaction
(`context_management: compact_20260112` — `claude -p` manages its own compaction, not
injectable via the CLI); sub-stage/step-level checkpoints; semantic summarization of the
work itself (the planner + run-log already encode "what's next").

### 1.4 Design principles (from the research)

- **Checkpoint *before* compaction, not after.** Native auto-compact gives no warning the
  model can act on; write durable state at the PreCompact boundary (Cognition/Devin,
  OpenClaw, Hermes #17344). For background, write the checkpoint immediately before rotating.
- **Persist task state, not transcript.** Store current stage, remaining plan, next action,
  session id, dispatch/token counters — not message history (Anthropic long-run harness:
  state artifacts bridge windows; Slack: structured journal, not history).
- **Idempotent resume.** Completed stages are recorded in `autopilot-runs.jsonl`; resume
  must skip them and **never redo** (guards the post-compaction re-execution bug, Hermes #17344).
- **Threshold below the cliff.** Industry consensus rotates/compacts at ~80% (Cline, Roo,
  OpenHands), reserving headroom; performance degrades well before advertised limits (Chroma).
- **Opt-in, fail-soft, never-raises.** No behavior change unless the user sets a window size;
  every new path degrades to today's behavior and never breaks a hook or a run.

---

## 2. Functional Requirements

### 2.1 Config + signal

- **REQ-CTX-001 — Opt-in threshold config.** `.forge/config.yaml` `autopilot:` gains
  `context_threshold_percent` (default 80) and `context_window_size` (no default — the
  feature is **off** until set; Forge cannot auto-detect the model window). Loaded fail-soft
  in `AutopilotConfig`/`load_config`, mirroring existing coercion; invalid values ignored.
- **REQ-CTX-002 — Context-pressure signal (background).** `_background_agent.dispatch`
  surfaces the envelope `usage.input_tokens`; autopilot threads the last dispatch's
  `input_tokens` into the loop. For a resumed session this approximates current context size.

### 2.2 Background path

- **REQ-CTX-003 — Token-pressure rotation trigger.** `should_rotate_for_context(
  last_input_tokens, config) -> bool` returns true when `context_window_size` is set and
  `last_input_tokens ≥ context_threshold_percent% × context_window_size`. The loop rotates
  when this **OR** the existing count-based `should_rotate_session` is true. Rotation reuses
  the existing `rotate=True ⇒ resume=None` mechanism (fresh session = compact+continue).
  Never raises; no-op when window unset.

### 2.3 Shared checkpoint

- **REQ-CTX-004 — Checkpoint artifact.** `.forge/autopilot-checkpoint.json`: single current
  checkpoint, **atomic** (temp-then-rename), `schema_version`, fail-soft read (missing/
  malformed ⇒ treated as absent, never raises). Fields: `schema_version`, `run_started_at`,
  `current_stage`, `remaining_stages`, `dispatch_count`, `last_input_tokens`,
  `last_session_id`, `next_action` (human-readable), `ts`.
- **REQ-CTX-005 — Checkpoint write points + CLI.** An `autopilot.py checkpoint` subcommand
  writes/refreshes the artifact. It is invoked before a rotation and on each stage advance.
- **REQ-CTX-008 — Idempotent resume.** Resume relies on the existing
  `record_run`→`autopilot-runs.jsonl` + `--resume` skip of completed stages; the checkpoint
  references it and adds the next-action pointer. No completed stage is ever re-run.

### 2.4 In-session path

- **REQ-CTX-006 — PreCompact checkpoint.** New `hooks/pre-compact.py` (stdlib,
  never-raises, **never blocks** — always exit 0). When an autopilot run is active
  (`.forge/autopilot-session.json` present/active), it writes/refreshes the REQ-CTX-004
  checkpoint before native compaction. Registered as `PreCompact` in the plugin manifest.
  No-op (clean exit) when no run is active.
- **REQ-CTX-007 — Post-compaction resume injection.** `hooks/session-start.py`, when
  `source == "compact"` **and** an autopilot run is active, injects a concise resume block
  within the existing ≤2000-token budget: current stage, next action, and an explicit
  "completed stages are in autopilot-runs.jsonl — do **not** redo them." Registered via a
  `compact` matcher on SessionStart. No-op otherwise.

### 2.5 Integration

- **REQ-CTX-009 — Autopilot loop + docs.** `skills/forge-autopilot/SKILL.md` gains a
  context-check step between gate-check and the next dispatch: read the last dispatch's
  `input_tokens`; on threshold-cross call `autopilot.py checkpoint` then rotate the next
  dispatch. Documents the in-session checkpoint-before / resume-after behavior and the
  config knobs. A `references/autopilot-context.md` reference doc is added.

---

## 3. Non-Functional Requirements

- **REQ-NF-020 — Stdlib + PyYAML fail-soft; never-raises.** All new code (hook, library,
  CLI) is stdlib + fail-soft PyYAML; the PreCompact hook and the background path must never
  raise and the hook must never block.
- **REQ-NF-021 — Opt-in / zero-change default.** With `context_window_size` unset, behavior
  is identical to v0.3.5 (no checkpoint-on-context, count-based rotation only).
- **REQ-NF-022 — Bounded & gated.** Reuses the existing cost/capability gates and the full
  autopilot safety envelope (max_stages, max_budget_usd, kill switch, stop flag); `.forge`-
  only writes; atomic checkpoint writes.
- **REQ-NF-023 — Resumable across the boundary.** A checkpoint + run-log is sufficient to
  resume a run after either a session rotation (background) or a native compaction
  (in-session) with no duplicated work.
- Inherited: ≤2000-token session-start budget, two-remote parity, `python3`, TDD red-first.

---

## 4. Acceptance Criteria

- **AC-CTX-001** — With `context_window_size: 200000`, `context_threshold_percent: 80`, a
  dispatch reporting `input_tokens = 170000` (≥160000) flips rotation on; `150000` does not;
  with `context_window_size` unset, rotation never flips regardless of tokens.
- **AC-CTX-002** — `should_rotate_for_context` returns true at the threshold and above, false
  below; OR-combines with `should_rotate_session`; never raises on garbage input.
- **AC-CTX-003** — The checkpoint artifact round-trips (write → read) with all fields and a
  `schema_version`; a malformed/empty file reads as absent without raising; writes are atomic.
- **AC-CTX-004** — `autopilot.py checkpoint` creates/refreshes `.forge/autopilot-checkpoint.json`.
- **AC-CTX-005** — The PreCompact hook writes a checkpoint **only** when a run is active,
  exits 0 in all cases (active, inactive, malformed state, missing `.forge`), and never blocks.
- **AC-CTX-006** — On `source=compact` with an active run, session-start injects a resume
  block containing the current stage and a do-not-redo instruction, within the token budget;
  on `source=compact` with no active run (or other sources) it injects nothing new.
- **AC-CTX-007** — `--resume` after a rotation/compaction skips stages already in
  `autopilot-runs.jsonl` (no re-run).
- **AC-CTX-008** — Full suite green, `validate-plugin.py` 0, `full-pipeline.sh` 12/12 with the
  feature both off (default) and on.

---

## 5. Traceability

| REQ-ID | Task |
|--------|------|
| REQ-CTX-001, 002, 003 | T-185 |
| REQ-CTX-004, 005, 008 | T-186 |
| REQ-CTX-006 | T-187 |
| REQ-CTX-007 | T-188 |
| REQ-CTX-009 | T-188 (loop) / T-189 (docs) |
| (release) | T-190 |

---

## 6. Key citations (research, 2026-06-16)

- **Claude Code hooks** — PreCompact/PostCompact, SessionStart `compact` matcher, no
  programmatic compaction, no context-% to hooks: code.claude.com/docs/en/hooks;
  anthropics/claude-code #46695 (context_threshold setting), #25689 (ContextThreshold hook),
  #15174 (SessionStart compact injection), #43733 (PreCompact pre-actions).
- **API/SDK context management** — compaction `compact_20260112` (default 150k trigger),
  tool-result clearing `clear_tool_uses_20250919`, memory tool:
  platform.claude.com/docs/en/build-with-claude/compaction; Claude cookbook context-engineering.
- **Industry thresholds & checkpoint-before-compact** — Cline (~80% auto-compact), Roo
  (configurable %), OpenHands LLMSummarizingCondenser (~50% cost cut), Letta/MemGPT
  (recursive summarization at pressure), Manus (externalized memory, KV-cache), Slack
  (structured journal not history), Cognition/Devin (checkpoint→compact→re-seed), Anthropic
  "Effective harnesses for long-running agents" (state artifacts bridge windows), Chroma
  (degradation before limits), Hermes #17344 (post-compaction re-execution bug).
