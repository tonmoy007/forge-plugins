#!/usr/bin/env python3
"""Observer daemon (T-142, REQ-F-008..014) — the Stage-9 watcher.

`/forge:watch` starts the Observer as a **reused-session** background dispatch (one
`claude -p` session, resumed on every poll — the spike's cost rule: fresh dispatch is
~10× a resumed one). Each poll asks the agent for terse findings about recent project
activity and appends them to `.forge/observer-findings.jsonl`; `/forge:watch-stop`
stops the session while preserving its last output. Unread findings are surfaced at the
next session start (hooks/session-start.py) and summarized in `/forge:status`.

Boundaries (hard):
  - REQ-F-013: the Observer NEVER writes pipeline artifacts — only `.forge/`.
  - Cost rule: pins a cheap model (`OBSERVER_MODEL`) and reuses one session.
  - Capability-false → clean no-op. Never raises (it runs detached).

Mirrors the structure of `scripts/skill_miner_bg.py`; findings rotation reuses
`hooks/_error_log.py` (T-146).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Optional

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
import _background_agent  # noqa: E402  (the single background adapter)
import _error_log  # noqa: E402  (shared size-bounded log rotation, T-146)

try:
    import _event_log  # noqa: E402  (HMAC-chained audit log)
except Exception:  # noqa: BLE001 — audit logging is best-effort, never load-blocking
    _event_log = None  # type: ignore[assignment]

# Cost rule (spike O-2): daemons pin a cheap model + reuse one session. Override --model.
OBSERVER_MODEL = "haiku"

_SESSION_NAME = "observer-session.json"
_FINDINGS_NAME = "observer-findings.jsonl"
_READ_CURSOR_NAME = "observer-findings.read"
_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"
_DEFAULT_POLL_INTERVAL_MIN = 30
_FINDINGS_MAX_BYTES = 262_144  # 256 KiB before rotation (paired with T-146)
_OBSERVER_STAGE = 9
_VALID_SEVERITIES = ("low", "medium", "high")

_PROMPT = (
    "You are Forge's Observer (Stage 9). Inspect the current project's recent activity "
    "(working tree, recent commits, test/build state) for things worth flagging — "
    "risky changes, missing tests, drift from the plan. Reply with ONLY a compact JSON "
    "array of findings, each {\"severity\": \"low|medium|high\", \"source\": \"<short "
    "origin>\", \"message\": \"<one line>\"}. Empty array if nothing notable. No prose."
)


def _now(now: Optional[dt.datetime]) -> dt.datetime:
    return now if now is not None else dt.datetime.now(dt.timezone.utc)


def _parse_ts(value: object) -> Optional[dt.datetime]:
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.strptime(value, _TS_FMT).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


# --- capability -------------------------------------------------------------

def _capability_available(forge_dir: Path) -> bool:
    caps = _background_agent.read_capabilities(forge_dir)
    return bool(caps and caps.get("forge_background_available"))


# --- session record ---------------------------------------------------------

def _load_session(forge_dir: Path) -> Optional[dict]:
    try:
        data = json.loads((forge_dir / _SESSION_NAME).read_text())
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _save_session(forge_dir: Path, record: dict) -> None:
    try:
        forge_dir.mkdir(parents=True, exist_ok=True)
        (forge_dir / _SESSION_NAME).write_text(json.dumps(record))
    except OSError:
        return


def is_running(forge_dir: Path) -> bool:
    sess = _load_session(forge_dir)
    return bool(sess and sess.get("status") == "running")


# --- findings ---------------------------------------------------------------

def _parse_findings(result_text: object) -> list[dict]:
    """Extract a findings list from the agent's reply. Tolerant: accepts a bare JSON
    array or one embedded in surrounding text; anything unparseable yields []."""
    if not isinstance(result_text, str):
        return []
    candidates = [result_text.strip()]
    lo, hi = result_text.find("["), result_text.rfind("]")
    if 0 <= lo < hi:
        candidates.append(result_text[lo:hi + 1])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(data, list):
            return [_normalize_finding(f) for f in data if _normalize_finding(f)]
    return []


def _normalize_finding(raw: object) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    message = str(raw.get("message", "")).strip()
    if not message:
        return None
    severity = str(raw.get("severity", "low")).lower()
    if severity not in _VALID_SEVERITIES:
        severity = "low"
    source = str(raw.get("source", "observer")).strip() or "observer"
    return {"severity": severity, "source": source, "message": message}


def _record_findings(forge_dir: Path, findings: list[dict], now: dt.datetime) -> int:
    ts = now.strftime(_TS_FMT)
    written = 0
    for f in findings:
        entry = {"ts": ts, **f}
        if _error_log.append_jsonl(
            forge_dir / _FINDINGS_NAME, entry, max_bytes=_FINDINGS_MAX_BYTES
        ):
            written += 1
    return written


def read_findings(forge_dir: Path) -> list[dict]:
    path = forge_dir / _FINDINGS_NAME
    out: list[dict] = []
    try:
        lines = path.read_text().splitlines() if path.exists() else []
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _read_cursor(forge_dir: Path) -> int:
    try:
        return int((forge_dir / _READ_CURSOR_NAME).read_text().strip())
    except (OSError, ValueError):
        return 0


def _write_cursor(forge_dir: Path, value: int) -> None:
    try:
        forge_dir.mkdir(parents=True, exist_ok=True)
        (forge_dir / _READ_CURSOR_NAME).write_text(str(value))
    except OSError:
        return


def unread_count(forge_dir: Path) -> int:
    return max(0, len(read_findings(forge_dir)) - _read_cursor(forge_dir))


# --- audit event (best-effort) ---------------------------------------------

def _log_event(forge_dir: Path, action: str, session_id: str, detail: dict) -> None:
    if _event_log is None:
        return
    try:
        _event_log.append(
            forge_dir, f"observer_{action}", session_id, _OBSERVER_STAGE,
            detail, "observer",
        )
    except Exception:  # noqa: BLE001 — audit is best-effort; never break the daemon
        return


# --- dispatch ---------------------------------------------------------------

def _dispatch_poll(
    forge_dir: Path,
    *,
    resume: Optional[str],
    cwd: Optional[str],
    claude_bin: Optional[str],
    model: Optional[str],
):
    return _background_agent.dispatch(
        _PROMPT,
        forge_dir=forge_dir,
        feature="observer",
        resume=resume,
        model=model,
        cwd=cwd,
        claude_bin=claude_bin,
    )


def start(
    forge_dir: Path,
    cwd: Optional[str] = None,
    claude_bin: Optional[str] = None,
    model: Optional[str] = OBSERVER_MODEL,
    now: Optional[dt.datetime] = None,
) -> tuple[str, str]:
    """Start the Observer (idempotent). Returns (code, message). Never raises.

    code ∈ {unavailable, already_running, started, error}.
    """
    try:
        if not _capability_available(forge_dir):
            return ("unavailable", "background agents unavailable — Observer is a no-op")
        if is_running(forge_dir):
            sess = _load_session(forge_dir) or {}
            return ("already_running",
                    f"Observer already running (session {sess.get('session_id', '?')}) "
                    f"— /forge:watch-stop to stop")

        when = _now(now)
        res = _dispatch_poll(forge_dir, resume=None, cwd=cwd, claude_bin=claude_bin, model=model)
        if res.status != "ok" or (res.raw or {}).get("is_error"):
            return ("error", f"initial poll failed: {res.reason}")

        findings = _parse_findings(res.result if res.result is not None else (res.raw or {}).get("result"))
        _record_findings(forge_dir, findings, when)
        ts = when.strftime(_TS_FMT)
        _save_session(forge_dir, {
            "session_id": res.session_id or "",
            "status": "running",
            "started_at": ts,
            "last_poll_at": ts,
            "last_result": res.result or "",
        })
        _log_event(forge_dir, "started", res.session_id or "", {"findings": len(findings)})
        return ("started", f"Observer watching (session {res.session_id}); "
                           f"{len(findings)} finding(s) on first poll")
    except Exception:  # noqa: BLE001 — daemon entry must never raise
        return ("error", "unexpected error starting Observer")


def poll(
    forge_dir: Path,
    cwd: Optional[str] = None,
    claude_bin: Optional[str] = None,
    model: Optional[str] = OBSERVER_MODEL,
    now: Optional[dt.datetime] = None,
) -> str:
    """Run one poll, reusing the Observer's session. Returns a status string. No-op
    (\"skipped\") when not running or capability is absent. Never raises."""
    try:
        if not is_running(forge_dir) or not _capability_available(forge_dir):
            return "skipped"
        sess = _load_session(forge_dir) or {}
        prior = sess.get("session_id") or None
        when = _now(now)
        res = _dispatch_poll(forge_dir, resume=prior, cwd=cwd, claude_bin=claude_bin, model=model)
        if res.status == "skipped":
            return "skipped"
        if res.status != "ok" or (res.raw or {}).get("is_error"):
            return "error"
        findings = _parse_findings(res.result if res.result is not None else (res.raw or {}).get("result"))
        _record_findings(forge_dir, findings, when)
        sess.update({
            "session_id": res.session_id or prior or "",
            "last_poll_at": when.strftime(_TS_FMT),
            "last_result": res.result or "",
        })
        _save_session(forge_dir, sess)
        _log_event(forge_dir, "poll", sess["session_id"], {"findings": len(findings)})
        return "ok"
    except Exception:  # noqa: BLE001
        return "error"


def stop(forge_dir: Path, now: Optional[dt.datetime] = None) -> tuple[str, str]:
    """Stop the Observer, preserving the last poll output (REQ-F-010). Never raises."""
    try:
        sess = _load_session(forge_dir)
        if not sess or sess.get("status") != "running":
            return ("not_running", "Observer is not running")
        sess["status"] = "stopped"
        sess["stopped_at"] = _now(now).strftime(_TS_FMT)
        _save_session(forge_dir, sess)  # last_result left intact
        _log_event(forge_dir, "stopped", sess.get("session_id", ""), {})
        return ("stopped", "Observer stopped; last poll output preserved")
    except Exception:  # noqa: BLE001
        return ("error", "unexpected error stopping Observer")


def should_poll(
    forge_dir: Path,
    now: Optional[dt.datetime] = None,
    interval_min: int = _DEFAULT_POLL_INTERVAL_MIN,
) -> bool:
    """True when the Observer is running and the poll interval has elapsed (lazy,
    event-driven cadence — REQ-F-008). Never raises."""
    if not is_running(forge_dir):
        return False
    sess = _load_session(forge_dir) or {}
    last = _parse_ts(sess.get("last_poll_at"))
    if last is None:
        return True
    return (_now(now) - last) >= dt.timedelta(minutes=interval_min)


# --- status -----------------------------------------------------------------

def status(forge_dir: Path, now: Optional[dt.datetime] = None, mark_read: bool = False) -> dict:
    """Structured Observer status. When mark_read, advance the unread cursor to the
    current total (used when the user views /forge:status)."""
    sess = _load_session(forge_dir)
    total = len(read_findings(forge_dir))
    unread = unread_count(forge_dir)
    if mark_read:
        _write_cursor(forge_dir, total)
    return {
        "running": bool(sess and sess.get("status") == "running"),
        "status": (sess or {}).get("status", "never_started"),
        "last_poll_at": (sess or {}).get("last_poll_at"),
        "total_findings": total,
        "unread": unread,
    }


def _ago(last_poll_at: Optional[str], now: dt.datetime) -> str:
    last = _parse_ts(last_poll_at)
    if last is None:
        return "never"
    mins = int((now - last).total_seconds() // 60)
    if mins <= 0:
        return "just now"
    if mins < 60:
        return f"{mins}m ago"
    return f"{mins // 60}h ago"


def status_line(forge_dir: Path, now: Optional[dt.datetime] = None) -> str:
    """One compact line for /forge:status and the Stage-9 status surface."""
    st = status(forge_dir, now=now)
    when = _now(now)
    if st["running"]:
        return (f"Observer: running · last poll {_ago(st['last_poll_at'], when)} · "
                f"{st['unread']} unread finding(s)")
    if st["status"] == "stopped":
        return f"Observer: stopped · {st['total_findings']} finding(s) recorded"
    return "Observer: not running (/forge:watch to start)"


# --- CLI --------------------------------------------------------------------

def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="observer")
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--forge-dir", default=None,
                        help="defaults to <cwd>/.forge")
    parser.add_argument("--claude-bin", default=None)
    parser.add_argument("--model", default=OBSERVER_MODEL)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start", action="store_true")
    group.add_argument("--stop", action="store_true")
    group.add_argument("--poll", action="store_true")
    group.add_argument("--poll-if-stale", action="store_true")
    group.add_argument("--status", action="store_true")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    cwd = args.cwd
    forge_dir = Path(args.forge_dir) if args.forge_dir else Path(cwd or ".") / ".forge"

    if args.start:
        _, msg = start(forge_dir, cwd=cwd, claude_bin=args.claude_bin, model=args.model)
        print(msg)
    elif args.stop:
        _, msg = stop(forge_dir)
        print(msg)
    elif args.poll:
        print(poll(forge_dir, cwd=cwd, claude_bin=args.claude_bin, model=args.model))
    elif args.poll_if_stale:
        if should_poll(forge_dir):
            print(poll(forge_dir, cwd=cwd, claude_bin=args.claude_bin, model=args.model))
        else:
            print("skipped")
    elif args.status:
        print(status_line(forge_dir))
        status(forge_dir, mark_read=True)  # viewing status marks findings seen
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
