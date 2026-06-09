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
| 7 | Headless **dispatch** (spawn a *new* background agent from a hook)? | ⚠️ **NOT yet verified** — see Open Items |
| 8 | Reliability over ≥5 real background runs + cost/session? | ⚠️ **NOT measured** — see Open Items |

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

- **O-1 — Headless dispatch.** Listing/monitoring is proven. Spawning a *new*
  background agent from a hook still needs a probe: does `claude agents` dispatch
  non-interactively, or is the path `claude -p … &` (detached print mode), and what
  identifies the spawned session for later `--cwd`/`--json` correlation? This gates
  REQ-F-008 (`/forge:watch`) and REQ-F-020 (nightly Dreamer).
- **O-2 — Reliability + cost (the formal REQ-F-028 numbers).** Convert the
  `stop-reflect.py` skill-miner step to a dispatched background agent and run it
  over **≥5 real sessions**, recording completion rate and cost/session. Gate: ≥90%
  completion AND ≤$0.10/session typical. **Method**: instrument `_background_agent.py`
  dispatch with the cost ledger (REQ-F-006), then run 5 ordinary build sessions and
  read `.forge/cost-ledger.jsonl` + completion markers. This is P0 work (it builds
  the adapter's dispatch half + cost cap), measured before P1 daemons start.

---

## Verdict

**PASS (capability) — GREEN to proceed with P0 foundation.**

- ✅ Build out `hooks/_background_agent.py` (probe ✓ done; add dispatch once O-1 is
  probed), `hooks/_cost_cap.py`, and wire the probe into `session-start.py` →
  `.forge/capabilities.json`.
- ⏸ **Do not start P1 daemons** until O-1 (dispatch) and O-2 (≥5-session reliability
  + cost) clear. If O-2 fails, ship `v0.2.0` as foundation-only (probe + adapter +
  cost cap), exactly as the SRS contingency states.

The expensive risk is gone; the remaining unknowns are bounded, measurable, and
sit safely inside P0.

---

## SRS impact

- `srs-v0.2.md` REQ-F-001/002/028: replace the assumed `claude --bg` / `/bg` /
  `/tasks` surface with the real **`claude agents`** API.
- Add **OQ-008 (High)**: headless dispatch mechanism (O-1 above) — resolve in
  Stage-3 architecture / the O-1 probe.
