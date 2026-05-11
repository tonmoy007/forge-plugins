# Implementation Decisions Log

> Append-only log of decisions made during implementation.
> Every non-trivial choice gets an entry. Future sessions read this to understand why
> things are the way they are.

## Format

```markdown
## YYYY-MM-DD T-XXX — <decision title>

**Context**: <what we were doing, what choice came up>

**Decision**: <what we chose>

**Why**: <reasoning>

**Alternatives considered**: <what we didn't pick and why>

**Consequences**: <what this means for future work>
```

---

## Decisions

## 2026-05-11 T-009v2 — Proposal/Validator/Executor split for stop-reflect

**Context**: The T-009 prompt was hardened to v4.1 spec after initial implementation.
The original hook wrote directly to `state.md` and `lessons.md` with no intermediary.
The v4.1 SRS demands Proposal → Validator → Executor separation on the highest-risk
write path (all long-term memory writes).

**Decision**: Introduced five new helper modules: `_proposals.py` (Pydantic schemas),
`_session_meta.py` (loop + cost guards), `_event_log.py` (HMAC chain), `_validator.py`
(deterministic validation), `_executor.py` (atomic writes). `stop-reflect.py` is now
pure orchestration — it collects proposals, then validates and executes after gate check.

**Why**: Any write error or hallucination on the lesson-extraction path poisons every
future session via `session-start.py`. Separating proposal creation from execution means
gate check failures (exit 2) leave no partial writes. The event log makes every write
traceable and reversible by forensics.

**Alternatives considered**: Inline validation within the hook (simpler, but less testable
and easier to accidentally bypass); deferred to v0.2 (unacceptable — the risk is highest
before trust levels are established).

**Consequences**: `hooks/` now has 7 files instead of 2. Hook imports pydantic — added
to `requirements.txt`. Hooks are no longer strictly stdlib-only (acceptable per ADR-001's
"if possible" caveat when a safety property requires it).

---

## 2026-05-11 T-009v2 — Loop detection default: max 3 reflections/session

**Context**: FR-SEM-004 requires loop detection. Default needed to balance usefulness
(long sessions may legitimately Stop many times) vs. cost and latency.

**Decision**: `MAX_REFLECTIONS_DEFAULT = 3`. Stored in `.forge/session-meta/<session_id>.json`
so it persists across invocations within the same session ID.

**Why**: 3 is the FR-SEM-004 default. A typical work session rarely stops more than 3 times
while remaining in the same logical "session". Tunable via session-meta file for power users.

**Alternatives considered**: 5 (too permissive — allows runaway cost); 1 (too restrictive).

**Consequences**: Sessions with more than 3 Stops get a notice and skip reflection.
The reflection_count resets when session_id changes (new session).

---

## 2026-05-11 T-009v2 — Daily cost cap default: $1.00

**Context**: FR-COST-004 requires a daily cost cap for always-on hooks. Reflector +
Extractor + Gate + Miner = up to 4 LLM calls/Stop, but v0.1 uses no LLM calls.

**Decision**: `COST_CAP_DEFAULT_USD = 1.00`. Tracked in `.forge/cost-ledger.jsonl`
(append-only, one line per LLM call). Cost is summed at pre-flight using today's date.

**Why**: $1.00 matches the v4.1 FR-COST-004 spec "5% always-on envelope at
small-project scale." In v0.1 this cap is never actually hit (no LLM calls), but the
infrastructure is in place so adding LLM reflectors (T-016+) doesn't require retrofitting.

**Consequences**: `record_cost()` is wired but never called in v0.1. Cost ledger stays
empty until LLM components are added. Cap is tunable via `.forge/config.yaml` (future).

---

## 2026-05-11 T-009v2 — HMAC event log key strategy (file-based, not OS keyring)

**Context**: v4.1 FR-KEY-001 specifies OS keyring for the signing key. The `keyring`
package isn't installed and adds a non-trivial dependency.

**Decision**: Key loaded from env `FORGE_EVENT_LOG_KEY`, falling back to
`.forge/event-log.key` (random 64-char hex, created on first use). No `keyring` package.

**Why**: v4.1 FR-KEY-001 is tagged "Production tier." v0.1 goal is forensic traceability,
not cryptographic key management. A file-based key is auditable and sufficient for detecting
accidental corruption or naive tampering. Upgrading to OS keyring later is a drop-in change
to `_load_key()`.

**Alternatives considered**: Hardcoded key (unacceptable — trivially bypassed); OS keyring
(correct for production, overkill for v0.1 and adds install friction).

**Consequences**: `.forge/event-log.key` must be in `.gitignore`. The chain can be verified
on the same machine that created it. Cross-machine verification requires sharing the key file.

---

## 2026-05-11 T-009v2 — Writes deferred until after gate check (no partial state on exit 2)

**Context**: The original hook wrote the reflection immediately, then checked the gate.
If the gate failed with done_signal → exit 2, the reflection was already written.

**Decision**: All proposals are collected first (steps 1-3), gate exit-2 fires before any
write, executor runs only if gate passes (or no done_signal).

**Why**: "Hook exits cleanly on crash (no partial writes)" is an explicit done-when criterion.
A reflection written before an exit-2 is technically a partial write — the session state
reflects an aborted stage advance, not a completed reflection.

**Alternatives considered**: Write reflection first anyway (simpler, arguable that a
reflection of a blocked session is still useful); revert on exit-2 (complex rollback logic).

**Consequences**: Existing tests still pass because they don't assert on reflection content
when exit-2 occurs. Minor behavioral change: reflection is only written on successful Stop.

---

## 2026-05-10 T-003 — Normalize PyYAML datetime objects on state load

**Context**: `python-frontmatter` uses PyYAML under the hood. PyYAML automatically parses
bare ISO-8601 timestamps (e.g. `last_updated: 2026-05-07T12:00:00Z`) as Python `datetime`
objects. This caused `validate_frontmatter` (which requires `str` for `last_updated`) to
reject the round-trip `read_state → write_state` with "got datetime".

**Decision**: Added `_normalize_metadata(metadata)` in `_state_lib.py` that converts any
`datetime.datetime` or `datetime.date` values to ISO strings immediately after loading.
Applied in `read_state` and `write_state`.

**Why**: Callers always see `last_updated` as a string, matching the schema contract and
making the round-trip safe. The alternative (widening `REQUIRED_FIELDS["last_updated"]` to
accept both `str` and `datetime`) would leak the PyYAML implementation detail into the API.

**Alternatives considered**: Widening the type union — rejected because it would require
callers to handle two types. Using PyYAML's `safe_load` with a string-only loader — rejected
because `python-frontmatter` doesn't expose that easily.

**Consequences**: All consumers of `read_state` always receive strings. If a field is ever
intentionally typed as `datetime` in the schema, `_normalize_metadata` would need updating.
