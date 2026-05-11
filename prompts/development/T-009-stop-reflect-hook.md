# T-009 — `stop-reflect.py` Hook (v4.1-hardened)

> **Replaces** the original `prompts/development/T-009-stop-reflect-hook.md`.
> The four-step Stop pipeline is the single biggest source of *quiet* failure in Forge:
> a hallucinated lesson here poisons every future session. This prompt bakes in the
> v4.1 SRS hardening (Proposal/Validator/Executor lite, loop detection, trust levels,
> replay-determinism guards, atomic writes, latency + cost budgets) before any code.
>
> Read this prompt in full. Then read `references/hooks.md`, `build/02-architecture/stop-pipeline.md`,
> `build/01-srs/srs.md` (REQ-034, REQ-050–052), and the v4.1 SRS sections referenced below.
> Then start.

---

## Context

`stop-reflect.py` runs on every Claude Code `Stop` event. It is the only hook that **writes
to long-term memory** — `tasks/lessons.md`, `.forge/lessons.yaml`, `pipeline/state.md`'s
reflection section, and (asynchronously) `.forge/skill-candidates/*.md`.

That makes it the **single highest-leverage failure point** in the plugin. A wrong lesson
gets injected into every future session by `session-start.py` and silently steers Claude
in the wrong direction. The damage is invisible until cumulative.

This task implements the hook with **v4.1-grade safety rails** — even though Forge v0.1
does not implement the full Event Store / Validator / Executor stack, it implements a
**lite** version of those boundaries here so the riskiest write path is bounded.

## What v4.1 demands of this hook

The v4.1 SRS introduces five guarantees that this hook MUST honor:

| v4.1 requirement | What it means here |
|---|---|
| **FR-DET-001/002/003** Proposal → Validator → Executor | Reflector / Lesson Extractor / Skill Miner output **proposals**, never direct writes. A deterministic validator approves or rejects. The executor performs the file write. |
| **FR-NEG-002 / FR-NEG-004** Trust levels + anti-pattern poisoning prevention | Every newly extracted lesson is born `ephemeral`. Promotion to `semi_trusted` requires N successful uses; promotion to `trusted` requires HITL approval. No LLM-extracted lesson can be `trusted` on creation. |
| **FR-SEM-004** Loop detection | Track per-session reflection depth. If the Stop hook fires more than `max_reflections_per_session` (default 3), short-circuit with a notice. |
| **FR-DDB-002** Non-deterministic component recording | The reflector's prose output and the lesson extractor's proposed lessons are non-deterministic. Each MUST be recorded once, with model + prompt-hash + temperature, in `.forge/events.jsonl` so future replays don't re-invoke the model. |
| **FR-COST-004** Always-on cost cap | Reflector + Extractor + Gate-Checker + Skill-Miner = up to 4 LLM calls per Stop. Track the per-Stop cost and per-day cumulative cost; throttle when approaching the daily cap. |

## Deliverable

A `command`-type Stop hook with the following pipeline, in this order, with these guarantees.

```
Stop event
  │
  ▼
┌────────────────────────────────────────────────────────────────────┐
│ 0. Pre-flight (deterministic, no LLM, < 50ms)                       │
│    ├── Read pipeline/state.md frontmatter                           │
│    ├── Increment session reflection depth in .forge/session-meta    │
│    ├── If depth > max_reflections_per_session → log + exit 0        │
│    ├── Detect "done signal" in last user prompt (heuristic)         │
│    ├── Compute cost-budget remaining for today                      │
│    └── If cost-budget exhausted → log + exit 0 with notice          │
├────────────────────────────────────────────────────────────────────┤
│ 1. Reflector (LLM, sequential)                                      │
│    ├── Invoke `reflector` subagent with stage + recent transcript   │
│    ├── Wrap output as ReflectionProposal{stage, score, gaps, prose} │
│    ├── Validate (schema + non-empty + length cap)                   │
│    ├── On reject: log validation failure, skip to step 2            │
│    └── On accept: enqueue for executor                              │
├────────────────────────────────────────────────────────────────────┤
│ 2. Lesson Extractor (LLM, sequential, only if corrections flagged)  │
│    ├── Read .forge/correction-flags.jsonl from this session         │
│    ├── If empty → skip                                              │
│    ├── Invoke `lesson-extractor` subagent                           │
│    ├── Wrap output as List[LessonProposal]                          │
│    ├── For each lesson: trust = "ephemeral", source = session_id    │
│    ├── Validate (schema, dedup against existing LKG, conflict check)│
│    └── Enqueue accepted proposals for executor                      │
├────────────────────────────────────────────────────────────────────┤
│ 3. Gate Check (deterministic, no LLM)                               │
│    ├── If done_signal detected: invoke `scripts/check-gate.py`      │
│    ├── Wrap output as GateProposal{stage, passed, blockers}         │
│    ├── If passed → enqueue StageAdvanceProposal                     │
│    ├── If failed and done_signal → exit 2 with blockers (block stop)│
│    └── If failed and !done_signal → log nudge, do not block         │
├────────────────────────────────────────────────────────────────────┤
│ 4. Skill Miner (LLM, ASYNC, fire-and-forget)                        │
│    ├── Read .forge/patterns.jsonl pattern frequency                 │
│    ├── If any pattern hit ≥ 3 → spawn skill-miner in background     │
│    ├── Output goes to .forge/skill-candidates/, never auto-installed│
│    └── Hook returns immediately; skill-miner finishes off-thread    │
├────────────────────────────────────────────────────────────────────┤
│ 5. Validator (deterministic, all proposals from steps 1-3)          │
│    ├── Schema check (Pydantic models)                               │
│    ├── Policy check (does this stage allow this kind of write?)     │
│    ├── Conflict check (lesson contradicts existing trusted lesson?) │
│    └── Reject with reason → reason recorded in .forge/events.jsonl  │
├────────────────────────────────────────────────────────────────────┤
│ 6. Executor (deterministic, atomic, write-to-temp-then-rename)      │
│    ├── Append event to .forge/events.jsonl (HMAC-chained, see below)│
│    ├── Update tasks/lessons.md (human) + .forge/lessons.yaml (machine) │
│    ├── Update pipeline/state.md reflection section                  │
│    └── On any IO failure → roll back, log, exit 0 (never crash)     │
└────────────────────────────────────────────────────────────────────┘
```

### File deliverables

```
hooks/stop-reflect.py            # main hook entry point
hooks/_invoke_agent.py           # subagent invocation helper (already planned)
hooks/_proposals.py              # NEW — Pydantic models for the 4 proposal types
hooks/_validator.py              # NEW — deterministic validator
hooks/_executor.py               # NEW — atomic writer + event log appender
hooks/_event_log.py              # NEW — HMAC-chained .forge/events.jsonl writer
hooks/_session_meta.py           # NEW — per-session reflection depth, cost tracking
tests/unit/test_stop_reflect.py
tests/unit/test_proposals.py
tests/unit/test_validator.py
tests/unit/test_executor.py
tests/unit/test_event_log.py
tests/integration/test_stop_pipeline.py
```

### Proposal schemas (sketch — refine in `hooks/_proposals.py`)

```python
from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime

class ReflectionProposal(BaseModel):
    stage: int
    score: int = Field(ge=1, le=10)
    gaps: list[str] = Field(max_length=10)
    prose: str = Field(max_length=4000)
    model: str
    prompt_hash: str
    temperature: float
    created_at: datetime

class LessonProposal(BaseModel):
    trigger: str = Field(max_length=200)
    rule: str = Field(max_length=500)
    why: str = Field(max_length=500)
    stage_tags: list[int]
    trust: Literal["ephemeral"] = "ephemeral"   # cannot be set higher on creation
    source_session: str
    source_corrections: list[str]               # references to correction-flags
    model: str
    prompt_hash: str
    temperature: float
    created_at: datetime

class GateProposal(BaseModel):
    stage: int
    passed: bool
    blockers: list[str]
    advance_to: int | None
    checked_at: datetime

class StageAdvanceProposal(BaseModel):
    from_stage: int
    to_stage: int
    triggered_by: Literal["done_signal_with_passing_gate"]
    created_at: datetime
```

### Event log format (`.forge/events.jsonl`)

Every line is a JSON object. Each line's `prev_hash` is the HMAC of the previous line.
The HMAC root key lives in the OS keyring (use `keyring` package — same as Forge v4.1
FR-KEY-001 MVP tier).

```json
{
  "id": 1234,
  "type": "ReflectionRecorded",
  "session": "abc-123",
  "stage": 6,
  "payload": { ... ReflectionProposal as JSON ... },
  "validator_outcome": "accepted",
  "occurred_at": "2026-05-10T14:32:00Z",
  "prev_hash": "f3c1...",
  "signature": "9a2e..."
}
```

Why an event log even in v0.1 when v4.1 wouldn't ship it until Production tier? Because
the *write path that has the highest hallucination risk* needs replay forensics from day
one. If a bad lesson gets in, you need to be able to find it. `events.jsonl` makes every
write to memory traceable.

### Loop detection — `.forge/session-meta/<session_id>.json`

```json
{
  "session_id": "abc-123",
  "started_at": "2026-05-10T13:15:00Z",
  "reflection_count": 2,
  "max_reflections_per_session": 3,
  "cost_today_usd": 0.12,
  "cost_cap_today_usd": 1.00
}
```

`max_reflections_per_session` defaults to **3** (v4.1 FR-SEM-004 default).

### Cost tracking

After each LLM call, write the token usage to `.forge/cost-ledger.jsonl`. At the start of
the hook, sum today's entries. If cumulative ≥ cap, exit early with a notice in stderr.
Default daily cap: **$1.00** for the always-on hooks (matches v4.1 FR-COST-004 5%
"always-on" envelope at small-project scale; tunable in `.forge/config.yaml`).

### Latency budget

| Step | Budget | Notes |
|---|---|---|
| 0 (pre-flight) | < 50 ms | All filesystem and arithmetic |
| 1 (reflector) | < 15 s | LLM call; one of these per Stop |
| 2 (lesson extractor) | < 10 s | LLM call; only if corrections flagged |
| 3 (gate check) | < 2 s | `check-gate.py`; deterministic |
| 4 (skill miner) | **async**, no budget | Detached; writes to `skill-candidates/` |
| 5 (validator) | < 200 ms | Pure Python |
| 6 (executor) | < 500 ms | Atomic file ops + event log append |
| **Total p95 (sync)** | **< 30 s** | Steps 0-3 + 5-6 |

If the total exceeds 30 s in p95 over the last 7 days, the hook itself emits a warning
proposal asking for tuning.

## Test coverage

### Unit tests (`tests/unit/`)

- `test_stop_reflect.py`
  - Happy path: all 4 steps complete, all proposals accepted, lessons.md updated
  - Loop guard: 4th invocation in same session → exits 0 with notice
  - Cost guard: cap exceeded → exits 0 with notice
  - Done signal + failing gate → exits 2 with blockers
  - Done signal + passing gate → emits StageAdvanceProposal
  - No corrections → lesson extractor skipped
  - Hook crash mid-step → no partial write to lessons.md or state.md

- `test_proposals.py`
  - Trust = "ephemeral" cannot be overridden on construction
  - Length caps enforced
  - Schema rejects malformed proposals

- `test_validator.py`
  - Conflict detection: new lesson contradicts existing `trusted` lesson → reject
  - Dedup: near-identical lesson already exists → reject
  - Stage-policy: a lesson tagged for a stage the agent isn't allowed to write → reject

- `test_executor.py`
  - Atomic write: process killed mid-write → file is either old or new, never corrupt
  - Event log: each append produces correct HMAC chain
  - Roll back: validator-accepted but FS-write-failed → no event log entry, no state change

- `test_event_log.py`
  - Chain integrity: tamper any line → `verify()` fails
  - Verify across rotations (v4.1 FR-KEY-002 simplified)

### Integration tests (`tests/integration/`)

- `test_stop_pipeline.py`
  - Synthetic session with 3 reflections + 2 corrections + a passed gate → run end-to-end → assert lessons.md, state.md, events.jsonl, cost-ledger all consistent
  - Inject a hallucinated lesson via mocked LLM → assert it lands as `ephemeral`, not used by next session-start
  - Loop trigger: simulate 4 rapid Stop events → assert 4th is short-circuited

## Update trail (do this at end of task)

1. `build/05-implementation/progress.md` → mark T-009 ✅, set current → T-010
2. `tasks/todo.md` → archive T-009, activate T-010
3. `tasks/lessons.md` → record what you learned about Claude Code subagent invocation, hook
   exit codes, and event-log HMAC chains
4. `build/05-implementation/decisions.md` → ADR for: proposal schema choices, loop-depth
   default, cost-cap default, sync-vs-async split, atomic-write strategy
5. `.forge/events.jsonl` → write a `TaskCompleted{T-009}` event (eat your own dogfood)

## Notes / tradeoffs / fallbacks

- **The subagent invocation API is the part with the most unknowns.** Spend research time on
  it before writing code. If Claude Code's subagent API is too restrictive for parallel
  invocation, fall back to **sequential** invocation for steps 1–3 (skill miner stays
  async). Document the choice in decisions.md.

- **The reflector's output format is not your problem here.** That's T-016 (the reflector
  agent persona). T-009 only needs to *call* the reflector and wrap its output as a
  proposal. Resist the urge to perfect the reflector here.

- **The "done signal" detection is heuristic.** Start conservative — only obvious phrases
  like "ship it", "advance to next stage", "we're done with stage N", "let's move on".
  False positives block the user; false negatives just mean they need to be more explicit.
  Log every detection (positive or negative) so you can tune the heuristics later.

- **If T-019 (extract-lessons.py) or T-006 (check-gate.py) interfaces don't match what this
  hook needs, STOP and fix the upstream task** rather than working around it. Workarounds
  compound silently.

- **Don't ship trust=`semi_trusted` or `trusted` from this hook.** Ever. Even if the LLM is
  confident. Promotion happens in T-020 (lesson injection / promotion logic) under
  conditions that aren't available at proposal time.

- **The event log is small in v0.1 — only the writes from this hook.** It is NOT the v4.1
  Event Store. It's a forensic log scoped to the highest-risk write path. Don't let it
  grow into a parallel state machine; that's a v0.2+ decision.

- **If you find yourself writing more than ~600 lines for the hook itself, stop and look
  for what should be in `_executor.py` or `_validator.py` instead.** The hook is glue;
  the components do the work.

## REQ refs

- v0.1 plugin: REQ-034 (auto-reflection), REQ-050 (lesson extraction), REQ-051 (gate
  enforcement at Stop), REQ-052 (skill mining)
- v4.1 SRS upstream: FR-DET-001/002/003, FR-NEG-002/004, FR-SEM-004, FR-DDB-002, FR-COST-004,
  FR-KEY-001 (MVP)

---

**Done when:**

- [ ] All unit tests pass
- [ ] Integration test passes including the hallucinated-lesson and loop-trigger cases
- [ ] Hook exits cleanly on crash (no partial writes)
- [ ] p95 sync latency < 30 s on the test corpus
- [ ] Event log verifies via `forge audit verify` (or its v0.1 equivalent)
- [ ] No newly-extracted lesson is anything other than `ephemeral`
- [ ] `tasks/lessons.md` and `.forge/lessons.yaml` stay in sync after the hook runs
- [ ] Update trail (above) completed