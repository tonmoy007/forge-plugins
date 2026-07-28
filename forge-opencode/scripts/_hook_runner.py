"""Hook runner — wraps Forge hook entry points with resilience guarantees.

Every Forge hook calls ``run_hook()`` in its ``if __name__ == "__main__"`` block.
Guarantees:

  1. An uncaught exception NEVER crashes the user's Claude Code session.
  2. A hung hook is killed at the configured timeout.
  3. All errors are logged to ``<cwd>/.forge/hook-errors.log`` as JSONL with
     timestamp, hook name, error kind, and detail (capped at 1000 chars).
  4. Blocking hooks (PreToolUse/Stop/SubagentStop) NEVER block on internal
     errors — only an explicit ``sys.exit(2)`` from the hook propagates.

Environment overrides:

  - ``FORGE_HOOK_TIMEOUT``                 — global timeout in seconds (float)
  - ``FORGE_HOOK_TIMEOUT_<HOOK_NAME>``     — per-hook override, e.g.
    ``FORGE_HOOK_TIMEOUT_SESSION_START=5``

The wall-clock timeout uses ``SIGALRM``/``setitimer`` (POSIX). On platforms without
them (Windows), the runner degrades to **no hard timeout** — the hook still runs and
stays exception-isolated; only the watchdog kill is unavailable (T-155 / NFR-COMPAT-001;
see ``build/06-evaluation/spike-windows.md``). Stdlib-only.

Ref: T-100, T-155
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import signal
import sys
import traceback
from pathlib import Path
from typing import Callable, NoReturn, Optional

# Per-hook default timeouts in seconds. SessionStart and SessionEnd are
# once-per-session and may do file I/O + subprocess work (sync-lessons,
# promote-lessons). The rest are per-event and must stay snappy: the Claude
# Code hook reference recommends < 200 ms cumulative across all hooks per
# event, so per-turn hooks budget ≤ 1-2 s as a hard ceiling.
_DEFAULT_TIMEOUTS: dict[str, float] = {
    "session-start":  30.0,
    "session-end":    30.0,
    "stop-reflect":   10.0,
    "subagent-stop":   5.0,
    "post-tool-use":   2.0,
    "pre-tool-write":  1.0,
    "prompt-submit":   1.0,
}

# Hooks that may legitimately block via exit code 2. For any other hook,
# an exit code of 2 is suppressed to 0 — non-blocking hooks shouldn't
# accidentally block tools or stops just because of a logic bug.
_BLOCKING_HOOKS: frozenset[str] = frozenset({
    "pre-tool-write",
    "stop-reflect",
    "subagent-stop",
})

_LOG_FILENAME = "hook-errors.log"
_DETAIL_CAP = 1000

# Size-bounded rotation for hook-errors.log (T-146, REQ-F-049). Default 1 MiB / 2
# backups; override the ceiling with FORGE_LOG_MAX_BYTES (0 disables rotation).
_LOG_MAX_BYTES_DEFAULT = 1_048_576
_LOG_KEEP = 2

# Shared rotation primitive lives in hooks/. Import it best-effort: if it is somehow
# unavailable, the runner still logs (unrotated) rather than failing.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
try:
    import _error_log  # noqa: E402
except Exception:  # noqa: BLE001 — never let an import break the universal runner
    _error_log = None  # type: ignore[assignment]


def _log_max_bytes() -> int:
    raw = os.environ.get("FORGE_LOG_MAX_BYTES")
    if raw is None:
        return _LOG_MAX_BYTES_DEFAULT
    try:
        return int(raw)
    except ValueError:
        return _LOG_MAX_BYTES_DEFAULT


def _resolve_timeout(hook_name: str) -> float:
    """Resolve hook timeout from env overrides, then defaults."""
    per_hook = f"FORGE_HOOK_TIMEOUT_{hook_name.upper().replace('-', '_')}"
    if per_hook in os.environ:
        try:
            return float(os.environ[per_hook])
        except ValueError:
            pass
    if "FORGE_HOOK_TIMEOUT" in os.environ:
        try:
            return float(os.environ["FORGE_HOOK_TIMEOUT"])
        except ValueError:
            pass
    return _DEFAULT_TIMEOUTS.get(hook_name, 5.0)


def _resolve_log_dir(cwd: Optional[Path] = None) -> Path:
    """Find the directory that should contain hook-errors.log.

    Order: explicit cwd arg, then CLAUDE_PROJECT_DIR env, then os.getcwd().
    """
    if cwd is not None:
        base = cwd
    else:
        env = os.environ.get("CLAUDE_PROJECT_DIR")
        base = Path(env) if env else Path(os.getcwd())
    return base / ".forge"


def _emit_error(
    hook_name: str,
    kind: str,
    detail: str,
    cwd: Optional[Path] = None,
) -> None:
    """Append a JSONL error record. Best-effort; never raises."""
    record = {
        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "hook": hook_name,
        "kind": kind,
        "detail": detail[:_DETAIL_CAP],
    }
    try:
        log_dir = _resolve_log_dir(cwd)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / _LOG_FILENAME
        if _error_log is not None:
            _error_log.rotate_if_needed(
                log_path, max_bytes=_log_max_bytes(), keep=_LOG_KEEP
            )
        with open(log_path, "a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        # Last resort: stderr. Never let the error-logger itself crash.
        try:
            sys.stderr.write(
                f"forge:hook-error[{kind}] {hook_name}: {detail[:200]}\n"
            )
        except Exception:  # noqa: BLE001
            pass  # Truly nothing we can do.


class _Timeout(Exception):
    """Raised by SIGALRM handler when the hook exceeds its budget."""


def _timeout_handler(signum, frame):  # type: ignore[no-untyped-def]
    raise _Timeout()


def _supports_itimer() -> bool:
    """True only on platforms with the POSIX interval timer (SIGALRM + setitimer).

    Windows has neither, so the wall-clock kill is unavailable there (T-155 /
    REQ-F-054 / NFR-COMPAT-001). Checked at call time so it can be exercised on POSIX.
    """
    return hasattr(signal, "setitimer") and hasattr(signal, "SIGALRM")


def _install_timeout(timeout: float):
    """Arm a wall-clock SIGALRM and return the previous handler, or None when the timer
    is unavailable (Windows) or cannot be installed (e.g. not the main thread). When None,
    the hook runs WITHOUT a hard timeout — it is still exception-isolated. Never raises.
    """
    if not _supports_itimer():
        return None
    try:
        previous = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        return previous
    except (ValueError, OSError, AttributeError):
        # ValueError: not in main thread. AttributeError: partial signal support.
        return None


def _cancel_timeout(previous) -> None:
    """Disarm the interval timer and restore the previous handler. Never raises."""
    if not _supports_itimer():
        return
    try:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if previous is not None:
            signal.signal(signal.SIGALRM, previous)
    except (TypeError, ValueError, OSError, AttributeError):
        pass


def run_hook(
    fn: Callable[[], None],
    *,
    hook_name: str,
    blocking: Optional[bool] = None,
    timeout: Optional[float] = None,
) -> NoReturn:
    """Run a hook's main function with resilience guarantees.

    Args:
        fn: The hook's main function. Takes no args; reads stdin internally;
            writes stdout internally; calls sys.exit at the end.
        hook_name: One of the seven known hook names (used for logging and
            timeout resolution). Custom hooks may pass any string.
        blocking: Override blocking-hook detection. If None, auto-detected
            from ``hook_name``.
        timeout: Wall-clock budget in seconds. If None, resolved from
            environment then defaults.

    Behavior:
        - fn() called inside try/except.
        - On exception: traceback logged, exit 0.
        - On timeout: log "timeout", exit 0 (even for blocking hooks — a
          timeout should not block the user's tool calls or stops).
        - On explicit ``sys.exit(N)`` from fn():
            * If N == 2 and hook is non-blocking, suppressed to 0 with log.
            * Otherwise propagated.
        - On clean return without sys.exit: treated as exit 0.

    Never returns — always calls sys.exit.
    """
    if blocking is None:
        blocking = hook_name in _BLOCKING_HOOKS
    if timeout is None:
        timeout = _resolve_timeout(hook_name)

    # Cache cwd before fn() runs in case fn() chdirs or crashes mid-execution.
    cwd_for_log: Optional[Path] = None
    env_cwd = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_cwd:
        try:
            cwd_for_log = Path(env_cwd)
        except (TypeError, ValueError):
            cwd_for_log = None

    # Install timeout. setitimer with ITIMER_REAL supports float seconds, unlike
    # signal.alarm which only takes int seconds. On platforms without SIGALRM/setitimer
    # (Windows), this degrades to no wall-clock kill — the hook still runs and stays
    # exception-isolated (T-155 / NFR-COMPAT-001).
    previous = _install_timeout(timeout)

    try:
        fn()
        sys.exit(0)
    except SystemExit as e:
        code: int
        if isinstance(e.code, int):
            code = e.code
        elif e.code is None or e.code == "":
            code = 0
        else:
            code = 1
        if not blocking and code == 2:
            _emit_error(
                hook_name,
                "unexpected-exit-2",
                f"Non-blocking hook {hook_name!r} returned exit 2; suppressed to 0.",
                cwd_for_log,
            )
            sys.exit(0)
        sys.exit(code)
    except _Timeout:
        _emit_error(
            hook_name,
            "timeout",
            f"Hook exceeded {timeout}s budget and was killed.",
            cwd_for_log,
        )
        sys.exit(0)
    except BaseException as exc:  # noqa: BLE001
        # Includes KeyboardInterrupt, MemoryError, etc. We must NEVER let
        # an internal error bubble up to Claude Code; that would manifest
        # as the user's session breaking on a Forge bug.
        tb = traceback.format_exc()
        _emit_error(hook_name, type(exc).__name__, tb, cwd_for_log)
        sys.exit(0)
    finally:
        _cancel_timeout(previous)


__all__ = ["run_hook"]