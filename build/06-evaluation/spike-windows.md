# Spike — Windows support (T-155 / REQ-F-054 / NFR-COMPAT-001)

> **Status: RESOLVED — 2026-06-15.** Outcome: a targeted **graceful-degradation fix** for
> the one hard blocker (the POSIX-only hook-timeout), plus a documented support boundary
> for the rest. Forge's Python hooks/scripts now **run on Windows without crashing**;
> hook *timeouts* remain POSIX-only by design (with a clear rationale + workaround).

---

## Question

NFR-COMPAT-001 asks whether Forge runs on Windows. The hook resilience wrapper
(`scripts/_hook_runner.py`) used `signal.SIGALRM` + `signal.setitimer`, which **do not
exist on Windows** — so importing/running it there raised `AttributeError` and would crash
the user's Claude Code session on the very first hook event. Fix it cross-platform, or
document the limitation precisely?

## Findings (what actually blocks Windows)

A sweep of `hooks/` and `scripts/` for platform-specific assumptions:

| Area | Windows status | Notes |
| --- | --- | --- |
| `signal.SIGALRM` / `setitimer` in `_hook_runner.py` | ❌ **hard crash** | The only true blocker — fixed below. |
| Atomic writes (`os.replace`, temp + rename) | ✅ OK | `os.replace` is atomic on Windows too. Used widely (state, ledger, lessons, run-logs). |
| `subprocess.run(..., stdin=DEVNULL)` for `claude -p` / `claude agents` | ✅ OK | `subprocess.DEVNULL` is cross-platform. Background features are capability-gated anyway. |
| Path handling | ✅ OK | `pathlib.Path` throughout; globs normalize separators. |
| `init-pipeline.sh`, `tests/integration/*.sh` | ⚠️ needs a POSIX shell | Bash scaffold/integration scripts need **Git Bash or WSL** on Windows. The Python hooks/skills themselves do not. |

So **one** code path crashed; everything else is portable or shell-only.

## Decision

**Both halves of the task's "done when": a fix lands AND the residual limitation is documented.**

1. **Fix the crash (graceful degradation).** `_hook_runner` now checks for the interval
   timer at call time and degrades when it is absent:
   - `_supports_itimer()` → `hasattr(signal, "setitimer") and hasattr(signal, "SIGALRM")`.
   - `_install_timeout()` returns `None` (no timer) on Windows or if the timer can't be
     installed (e.g. not the main thread); `_cancel_timeout()` is a matching no-op.
   - `run_hook()` therefore runs the hook **without a wall-clock kill** on Windows instead
     of crashing. **All other guarantees hold** — uncaught exceptions are still isolated
     (exit 0), and an explicit `sys.exit(2)` from a blocking hook still propagates.
   - Covered by `tests/unit/test_hook_runner.py::TestNoSigalrmPlatform` (simulates Windows
     on POSIX by removing the `signal` attrs at runtime).

2. **Document the residual limitation (this file + the module docstring).**

### Why not a thread-based cross-platform timeout?

A `threading.Timer` watchdog cannot interrupt synchronous Python running in the main thread
(there is no portable "kill this thread"), so it could not actually enforce the budget — it
would only *log* a late warning while the hook kept running. That is strictly worse than an
honest "no hard timeout on Windows": more code, more surface, no real guarantee. The hook
budget is a **safety net** (catch a pathological hang), not a correctness mechanism — every
hook is already exception-isolated and the budgets are sub-second by design.

## Residual limitations on Windows (and workarounds)

- **No hook wall-clock timeout.** A hook that genuinely hangs will not be force-killed on
  Windows. Mitigation: hooks are stdlib-only, do minimal work, and are exception-isolated;
  a hang requires a pathological bug. Workaround for parity: run Claude Code under **WSL2**,
  where the POSIX timer (and the timeout) is fully active.
- **Shell scaffolding needs a POSIX shell.** `scripts/init-pipeline.sh` and the
  `tests/integration/*.sh` harness require **Git Bash or WSL**. The runtime plugin (hooks,
  skills, Python scripts) does not.

## Recommendation

Ship the degradation fix (done). Treat **WSL2** as the first-class Windows story for full
parity, and **native Windows** as supported for the Python runtime with the one documented
caveat (no hook timeout). Re-evaluate a real cross-platform timeout only if a concrete hung
-hook report appears on native Windows — unlikely given the exception isolation already in
place.
