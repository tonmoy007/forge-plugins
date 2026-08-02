#!/usr/bin/env python3
"""Opt-in, local-only skill-mining telemetry (REQ-F-053, v0.3.4 / M4).

Forge records **nothing** by default. When a user explicitly opts in, lightweight
skill-mining signals (a skill mined, a proposal shown/accepted) are appended to
`.forge/telemetry.jsonl` **on the local machine only** — they are never transmitted
anywhere. The data leaves the machine solely through an explicit `export` the user runs.

  telemetry.py status  [--cwd .]
  telemetry.py enable  [--cwd .]          # opt in (writes .forge/telemetry-enabled)
  telemetry.py disable [--cwd .]          # opt out
  telemetry.py record  --event E [--cwd .] [--field k=v ...]   # no-op unless enabled
  telemetry.py summary [--cwd .]          # local counts by event
  telemetry.py export  [--cwd .]          # print the raw local JSONL (explicit)

Opt-in is signalled by the marker file `.forge/telemetry-enabled` (managed by
enable/disable) OR `telemetry.enabled: true` in `.forge/config.yaml`. Stdlib + PyYAML
(fail-soft); never raises into a caller (it may be invoked from the skill-mining path).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Optional

_MARKER = "telemetry-enabled"
_DATA = "telemetry.jsonl"
_CONFIG = "config.yaml"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _config_opt_in(forge_dir: Path) -> bool:
    """True iff `.forge/config.yaml` has `telemetry.enabled: true`. Fail-soft."""
    path = Path(forge_dir) / _CONFIG
    try:
        if not path.exists():
            return False
        import yaml  # noqa: F401
        data = yaml.safe_load(path.read_text())
    except Exception:  # noqa: BLE001 — missing PyYAML / bad YAML / OSError → not enabled
        return False
    section = data.get("telemetry") if isinstance(data, dict) else None
    return isinstance(section, dict) and section.get("enabled") is True


def is_enabled(forge_dir) -> bool:
    """True only when the user has opted in (marker file or config flag). Never raises."""
    try:
        if (Path(forge_dir) / _MARKER).exists():
            return True
    except OSError:
        return False
    return _config_opt_in(Path(forge_dir))


def enable(forge_dir) -> bool:
    """Opt in by writing the marker file. Returns True on success. Never raises."""
    forge = Path(forge_dir)
    try:
        forge.mkdir(parents=True, exist_ok=True)
        (forge / _MARKER).write_text(_now_iso() + "\n")
        return True
    except OSError:
        return False


def disable(forge_dir) -> bool:
    """Opt out by removing the marker file. Returns True (idempotent). Never raises."""
    try:
        (Path(forge_dir) / _MARKER).unlink(missing_ok=True)
        return True
    except OSError:
        return False


def record(forge_dir, event: str, **fields) -> bool:
    """Append one telemetry event to `.forge/telemetry.jsonl` — but ONLY if the user has
    opted in. Returns False (a clean no-op) when disabled. Local-only; never transmits.
    Never raises (safe to call from the skill-mining hot path).
    """
    forge = Path(forge_dir)
    if not is_enabled(forge):
        return False
    entry = {"ts": _now_iso(), "event": str(event)}
    for k, v in fields.items():
        entry[k] = v
    try:
        forge.mkdir(parents=True, exist_ok=True)
        with open(forge / _DATA, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return True
    except OSError:
        return False


def _read_rows(forge_dir: Path) -> list:
    rows: list = []
    try:
        text = (Path(forge_dir) / _DATA).read_text()
    except OSError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def summary(forge_dir) -> dict:
    """Local count of recorded events keyed by event name. Never raises."""
    counts: dict = {}
    for row in _read_rows(Path(forge_dir)):
        ev = str(row.get("event", "unknown"))
        counts[ev] = counts.get(ev, 0) + 1
    return counts


def export_data(forge_dir) -> str:
    """Return the raw local telemetry JSONL text ('' when none). The ONLY way data leaves
    the machine — and only because the user explicitly ran it. Never raises.
    """
    try:
        return (Path(forge_dir) / _DATA).read_text()
    except OSError:
        return ""


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _forge(cwd: str) -> Path:
    return Path(cwd) / ".forge"


def _parse_fields(pairs: Optional[list]) -> dict:
    out: dict = {}
    for item in pairs or []:
        if "=" in item:
            k, v = item.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="telemetry.py",
        description="Opt-in, local-only skill-mining telemetry (default off).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "enable", "disable", "summary", "export"):
        p = sub.add_parser(name)
        p.add_argument("--cwd", default=".")
    p_rec = sub.add_parser("record")
    p_rec.add_argument("--cwd", default=".")
    p_rec.add_argument("--event", required=True)
    p_rec.add_argument("--field", action="append", default=[], metavar="k=v",
                       help="extra key=value field (repeatable)")
    args = parser.parse_args(argv)
    forge = _forge(args.cwd)

    if args.command == "status":
        on = is_enabled(forge)
        print(f"telemetry: {'enabled' if on else 'disabled (default)'}")
        print(f"  data (local-only): {forge / _DATA}")
        if on:
            print(f"  events recorded: {sum(summary(forge).values())}")
        print("  Forge never transmits telemetry; `export` is the only way out.")
        return 0
    if args.command == "enable":
        ok = enable(forge)
        print("telemetry enabled — events recorded locally to "
              f"{forge / _DATA} (never transmitted)." if ok
              else "could not enable telemetry (write failed)", file=sys.stderr if not ok else sys.stdout)
        return 0 if ok else 1
    if args.command == "disable":
        disable(forge)
        print("telemetry disabled.")
        return 0
    if args.command == "record":
        record(forge, args.event, **_parse_fields(args.field))
        return 0  # silent no-op when disabled — never an error
    if args.command == "summary":
        counts = summary(forge)
        if not counts:
            print("no telemetry recorded (telemetry is opt-in; `telemetry.py enable`).")
            return 0
        for ev, n in sorted(counts.items()):
            print(f"{ev}: {n}")
        return 0
    if args.command == "export":
        out = export_data(forge)
        if out:
            sys.stdout.write(out)
        else:
            print("no telemetry to export.", file=sys.stderr)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
