# Spike: Background Agents — Feasibility (v0.2 P0)

> **REQ-F-028.** Decide whether Claude Code's background-agent capability is
> usable by Forge before committing to the P1 daemon build-out. Run **before**
> Stage-3 architecture, to de-risk the dependency the whole daemon half rests on.

- **Date**: 2026-06-09
- **Environment**: `claude` CLI **v2.1.169**, repo `forge-plugin` @ `main` (v0.1.7)
- **Author**: Forge build session (empirical probe — no fabricated runs)

---

## Question

Can a Forge hook (a Python subprocess invoked by Claude Code) detect, list, and
ultimately dispatch background agents — reliably and within a cost cap — so the
v0.2 daemons (Observer/Dreamer/Health) are buildable?

---

## What was actually measured (and what was not)

| # | Probe | Result |
|---|-------|--------|
| 1 | Is the `claude` CLI present + what version? | ✅ `/home/tonmoy/.local/bin/claude`, **v2.1.169** |
| 2 | Does a background-agent surface exist? | ✅ `claude agents` — "Manage background agents" |
| 3 | Is listing **scriptable / headless** (no TTY)? | ✅ `claude agents --json` returns a JSON array, exit 0, `stdin=DEVNULL` |
| 4 | Per-project scoping? | ✅ `claude agents --json --cwd <path>` filters by project |
| 5 | Live capability from a Python subprocess (the real hook path)? | ✅ `detect_capability()` → `available=True`, **4 active sessions**, 1 under this repo |
| 6 | Graceful degradation on every failure mode? | ✅ `hooks/_background_agent.py` + 8 unit tests (no CLI / non-zero / non-JSON / non-array / timeout / not-found all → no-op, never raise) |
| 7 | Headless **dispatch** (spawn a *new* agent run from a hook)? | ✅ **RESOLVED 2026-06-10** — `claude -p --output-format json --max-turns N` runs headless (stdin=DEVNULL, no TTY, no permission prompt), exit 0, returns its own `session_id` + **actual `total_cost_usd`** + `usage`. See O-1 below. |
| 8 | Reliability over ≥5 real background runs + cost/session? | 🟡 **cost MEASURED** ($0.053 fresh / $0.005 resumed); **completion-rate still needs ≥5 real sessions** (P0, gates P1). See O-2 below. |

Evidence for #5 (live, unedited):

```
available      : True
reason         : background agents available via `claude agents`
active_sessions: 4
per-cwd (here) : 1 session(s) under this repo
```

---

## Headline finding: the dependency is *de-risked*, and the draft's API is stale

The original 2026-05-14 v0.2 draft assumed a **Research Preview** API surfaced as
`claude --bg` / `/bg` / `/tasks`, and treated "is this even usable?" as the gating
risk. Both assumptions are now wrong in Forge's favor:

1. **Background agents have shipped** — they're a first-class, documented command
   (`claude agents`) in v2.1.169, not a preview behind a flag.
2. **The surface is fully scriptable** from a hook: `claude agents --json [--cwd]`
   returns structured data headlessly. That directly powers the probe (REQ-F-001),
   the Observer session record (REQ-F-009), findings surfacing (REQ-F-012), and the
   Stage-9 status line (REQ-F-014) — **today, with no API gymnastics**.
3. The draft's assumed API name is dead. **`hooks/_background_agent.py` (REQ-F-002)
   is the one place this matters** — exactly the single-adapter discipline the SRS
   mandated — and it's already written against the real API.

So the central spike risk (**capability unusable → abandon daemons**) is **retired**.

---

## Open items (gate P1, not P0)

The capability is *available*; two things still need real-world measurement before
committing to the daemon build-out. Neither can be honestly simulated in one
session, so they are left OPEN rather than guessed:

- **O-1 — Headless dispatch. ✅ RESOLVED (2026-06-10).** The path is detached
  `claude -p "<prompt>" --output-format json --max-turns N` (NOT `claude agents`,
  which is an interactive TUI). Measured, live:
  - Runs fully headless: `stdin=DEVNULL`, no TTY, **no permission prompt** for a
    no-tool reply; exit 0; ~6.8s wall for a trivial haiku turn.
  - Returns a rich JSON envelope including **`session_id`**, **`total_cost_usd`
    (actual, API-reported)**, `usage` (input/output/cache tokens), `num_turns`,
    `is_error`, `result`, `uuid`.
  - **Correlation key = the returned `session_id`, captured from the dispatch's
    stdout** — *not* `claude agents --json`. Confirmed: a completed `-p` session
    does **not** appear in `claude agents --json` (that surface lists user-started
    background agents: keys `cwd/kind/name/pid/sessionId/startedAt/status`). Dispatch
    and monitor are **two distinct surfaces**; Forge tracks dispatched runs by the
    captured `session_id` in its own session record.
  - This unblocks REQ-F-008 (`/forge:watch`) and REQ-F-020 (nightly Dreamer).
- **O-2 — Reliability + cost.** **Cost half MEASURED (2026-06-10); completion-rate
  half still pending ≥5 real sessions.**
  - **Cost floor finding (material):** a *fresh* dispatch costs **~$0.053** even for a
    10-token prompt, because the ~42k-token system prompt is billed as
    `cache_creation_input_tokens` (`cache_read=0`) on every new session. At a naive
    15-min poll cadence (8h/day) that is **~$50/mo** — untenable, and only 1.9×
    under the $0.10/session gate.
  - **Mitigation MEASURED + VALIDATED — session reuse.** Resuming the same session
    (`--resume <session_id>`) turns the 42k tokens into a `cache_read`, dropping cost
    to **~$0.0046 — 9% of a fresh dispatch**. Design consequence: **each daemon
    reuses one persistent session**; only the first poll/day pays the cache-creation
    tax (~$0.05), subsequent polls are ~$0.005. At reuse, ~960 polls/mo ≈ **$4.4** —
    comfortably within the $0.50/day cap.
  - **Cost is API-reported, not estimated** (`total_cost_usd` in the JSON) — the
    ledger records actuals; the cost-cap pre-check uses a conservative floor constant
    (~$0.06 fresh / ~$0.01 resumed) only to gate *before* spend.
  - **Still open (P0, gates P1):** the **completion-rate** number (≥90% over ≥5 real
    sessions). Method unchanged: instrument the async skill-miner dispatch with the
    cost ledger (REQ-F-006), run 5 ordinary build sessions, read
    `.forge/cost-ledger.jsonl` + completion markers. Affordability is no longer in
    doubt; only reliability remains to be observed.

---

## Verdict

**PASS — GREEN to proceed with P0 foundation. O-1 RESOLVED; O-2 cost RESOLVED;
only O-2 completion-rate remains (measured inside P0).**

- ✅ Build out `hooks/_background_agent.py` — probe ✓ done; **dispatch half now
  specified by O-1** (detached `claude -p --output-format json`, capture
  `session_id`, **reuse the session via `--resume`** for cheap subsequent polls).
- ✅ Build `hooks/_cost_cap.py` recording **actual** `total_cost_usd`; wire the probe
  into `session-start.py` → `.forge/capabilities.json`.
- ⏸ **Do not start P1 daemons** until the O-2 **completion-rate** number clears
  (≥90% over ≥5 real sessions). Affordability is no longer a risk. If completion
  fails, ship `v0.2.0` as foundation-only (probe + adapter + cost cap), exactly as
  the SRS contingency states.
- ⚠️ **Cost-control is now a first-class design rule, not a nicety:** daemons MUST
  reuse one session (`--resume`) — naive fresh dispatch per poll is ~10× the cost
  and breaks the budget.

The expensive risk is gone; the remaining unknowns are bounded, measurable, and
sit safely inside P0.

---

## SRS impact

- `srs-v0.2.md` REQ-F-001/002/028: replace the assumed `claude --bg` / `/bg` /
  `/tasks` surface with the real **`claude agents`** (monitor) + **`claude -p`**
  (dispatch) APIs. *(Applied 2026-06-10.)*
- **OQ-008 — RESOLVED:** dispatch = detached `claude -p --output-format json`;
  correlate via the returned `session_id`; `claude agents --json` is monitor-only.
- **OQ-004 — RESOLVED:** cost is **API-reported** (`total_cost_usd`); ledger records
  actuals, the cap pre-check uses a conservative floor constant.
- **New design rule → REQ + ADR:** daemons reuse one session (`--resume`) to avoid
  the ~$0.05 per-fresh-dispatch cache-creation tax (≈10× cost). Reflected in
  REQ-F-004/006/020 and ADR-005/007.

---

## O-2 completion-rate — measurement harness (T-139, shipped 2026-06-10)

The cost half of O-2 is settled. The **completion-rate** half (≥90% over ≥5 real
sessions) is, by construction, data that **accrues over real use** — it cannot be
honestly produced in a single authoring session, so it is **instrumented now and
left to fill in**:

- `stop-reflect.py` Step 4 now offloads skill-mining to a background subagent via
  `scripts/skill_miner_bg.py` **when** `.forge/capabilities.json` reports background
  available (else the inline deterministic `mine-skills.py` fallback; `FORGE_NO_BACKGROUND`
  forces the fallback). Both paths are detached — the Stop hook never waits.
- Every background run appends one marker to `.forge/skill-miner-runs.jsonl`
  (`ts, session, status ∈ {completed,failed,skipped}, cost_usd`). `skipped` =
  deliberate cost-cap no-op (excluded from the rate).
- **Reader**: `skill_miner_bg.completion_stats(forge_dir)` →
  `{n, completed, failed, skipped, completion_rate, total_cost_usd, avg_cost_usd}`.

**Verdict — PENDING (accumulating).** Gate: `completion_rate ≥ 0.90` with `n ≥ 5`.
Re-read `completion_stats` after ~5 real Forge sessions; if it clears, P1 (M2 daemons)
unlocks. If it stalls below 0.90, ship `v0.2.0` as foundation-only (this is exactly
the SRS §6 contingency). **No run here is fabricated** — each marker is one real
dispatch recorded by a real session.
