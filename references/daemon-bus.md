# Daemon Bus — findings schemas & poll contract (M2)

> Loaded on demand. Defines the shared contract the background daemons
> (Observer / Dreamer / Health, T-142–T-144) use to record state and findings under
> `.forge/`. Daemons write **only** here — never to `pipeline/` artifacts (REQ-F-013).

## Cost & session rules (non-negotiable)

Every daemon poll goes through `hooks/_background_agent.dispatch` and **must**:

1. **Reuse one session** per daemon (`--resume <session_id>`). A fresh dispatch pays the
   ~42k-token cache-creation tax (~$0.05); a resumed one is a cache read (~$0.005). The
   session id is the one returned by the first dispatch, persisted in the daemon's
   session record.
2. **Pin a cheap model** (`--model haiku` via the daemon's `*_MODEL` constant).
   Real-usage testing showed the unpinned default (Opus-class) costs ~$1/run — ~20× the
   budget (see `build/06-evaluation/spike-background-agents.md`, O-2).
3. Be **cost-gated** (the dispatch pre-checks `_cost_cap`) and **capability-gated**
   (no-op when `.forge/capabilities.json` reports background unavailable).
4. **Never raise** — daemons run detached; failures are recorded, not thrown.

## Observer (T-142, Stage 9)

| File | Shape | Notes |
| --- | --- | --- |
| `.forge/observer-session.json` | `{session_id, status: running\|stopped, started_at, last_poll_at, last_result, stopped_at?}` | One session, reused via `--resume`. `status` drives idempotency (`/forge:watch` warns if already running) and the lazy poll trigger. |
| `.forge/observer-findings.jsonl` | one finding per line: `{ts, severity: low\|medium\|high, source, message}` | Append-only; size-bounded via `hooks/_error_log.append_jsonl` (256 KiB, 2 backups). |
| `.forge/observer-findings.read` | integer | Read cursor. `unread = total − cursor`. Advanced when the user views `/forge:status`. |

**Poll contract.** The dispatched agent replies with **only** a JSON array of findings
(`[{severity, source, message}, …]`, empty if nothing notable). `observer.py` parses it
tolerantly (bare array or embedded), normalizes severity/source, stamps `ts`, and
appends. Unparseable replies yield zero findings — never an error.

**Cadence.** Lazy / event-driven (default 30 min, `should_poll`). `hooks/session-start.py`
fires a detached `observer.py --poll-if-stale` when a session is running and the
capability cache is positive — it never blocks startup (NF-004), and the kill switch
`FORGE_NO_BACKGROUND=1` disables it.

## Surfacing

- **Session start** (`hooks/session-start.py`): one line — `[Forge] N unread Observer
  finding(s) — see /forge:status` — when `unread > 0`. Read-only; does not mark read.
- **`/forge:status`**: shows the Observer status line and marks findings read (advances
  the cursor).

## Audit

State transitions (started / poll / stopped) append a best-effort `observer_*` event to
the HMAC-chained `.forge/events.jsonl` via `hooks/_event_log.append`. Audit failures are
swallowed — they never break a poll.

## Rotation policy

All append-only daemon logs use `hooks/_error_log` rotation (T-146, REQ-F-049): roll to
numbered backups (`.1`, `.2`) at the byte ceiling, each step a single atomic
`os.replace`, so a crash mid-rotation loses no line. Ceiling overridable per call;
hook-errors.log honors `FORGE_LOG_MAX_BYTES`.
