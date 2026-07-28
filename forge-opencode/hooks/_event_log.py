"""HMAC-chained append-only event log for .forge/events.jsonl (FR-DDB-002).

Every write to long-term memory produces one event line. Each line carries:
  - prev_hash: SHA256 of the previous raw line (chain integrity)
  - signature: HMAC-SHA256 of the event object without the signature field

Signing key is loaded from env FORGE_EVENT_LOG_KEY, falling back to a
per-project key file at .forge/event-log.key (created on first use).
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path


def _load_key(forge_dir: Path) -> bytes:
    env_key = os.environ.get("FORGE_EVENT_LOG_KEY", "")
    if env_key:
        return env_key.encode()
    key_path = forge_dir / "event-log.key"
    if key_path.exists():
        return key_path.read_bytes().strip()
    key = os.urandom(32).hex().encode()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key)
    return key


def _sign(key: bytes, event_without_sig: dict) -> str:
    """HMAC-SHA256 of the event's canonical (sort_keys) JSON."""
    canonical = json.dumps(event_without_sig, sort_keys=True)
    return hmac.new(key, canonical.encode(), hashlib.sha256).hexdigest()


def _line_hash(line: str) -> str:
    """SHA256 of a raw stored line — prev_hash for the next event."""
    return hashlib.sha256(line.encode()).hexdigest()


def _genesis_hash(key: bytes) -> str:
    return _sign(key, {"genesis": True})


def _read_lines(forge_dir: Path) -> list[str]:
    path = forge_dir / "events.jsonl"
    if not path.exists():
        return []
    return [ln for ln in path.read_text().splitlines() if ln.strip()]


def append(
    forge_dir: Path,
    event_type: str,
    session_id: str,
    stage: int,
    payload: dict,
    validator_outcome: str,
) -> None:
    """Append one HMAC-chained event to .forge/events.jsonl."""
    forge_dir.mkdir(parents=True, exist_ok=True)
    key = _load_key(forge_dir)
    lines = _read_lines(forge_dir)
    prev_hash = _line_hash(lines[-1]) if lines else _genesis_hash(key)

    event: dict = {
        "id": len(lines) + 1,
        "type": event_type,
        "session": session_id,
        "stage": stage,
        "payload": payload,
        "validator_outcome": validator_outcome,
        "occurred_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "prev_hash": prev_hash,
    }
    event["signature"] = _sign(key, event)

    path = forge_dir / "events.jsonl"
    with path.open("a") as f:
        f.write(json.dumps(event) + "\n")


def verify(forge_dir: Path) -> tuple[bool, str]:
    """Verify HMAC chain integrity. Returns (ok, reason)."""
    key = _load_key(forge_dir)
    lines = _read_lines(forge_dir)
    if not lines:
        return True, "no events"

    expected_prev = _genesis_hash(key)
    for i, line in enumerate(lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return False, f"line {i + 1}: invalid JSON"

        if event.get("prev_hash") != expected_prev:
            return False, f"line {i + 1}: prev_hash mismatch"

        sig = event.pop("signature", None)
        expected_sig = _sign(key, event)
        if sig != expected_sig:
            return False, f"line {i + 1}: signature mismatch"
        event["signature"] = sig

        expected_prev = _line_hash(line)

    return True, "ok"
