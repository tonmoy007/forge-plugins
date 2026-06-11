"""Size-bounded rotation for append-only `.forge` logs (T-146, REQ-F-049).

Hook error logs (`hook-errors.log`) and daemon findings logs grow without bound
otherwise. This is the one rotation primitive both paths share: when a log reaches a
byte ceiling, roll it to numbered backups (`.1`, `.2`, …) and start fresh, keeping at
most `keep` backups. Each step is a single `os.replace` (atomic on POSIX), so a crash
mid-rotation never loses or corrupts a line.

Stdlib-only; never raises — these run on the hot hook path and must fail soft.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_MAX_BYTES = 1_048_576  # 1 MiB
DEFAULT_KEEP = 2


def _backup(path: Path, index: int) -> Path:
    """The Nth rotated backup path: `<path>.<index>`."""
    return path.with_name(f"{path.name}.{index}")


def rotate_if_needed(
    path: Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    keep: int = DEFAULT_KEEP,
) -> bool:
    """Roll `path` to numbered backups if it is at/over `max_bytes`.

    Drops the oldest backup, shifts `.{i}` → `.{i+1}`, then moves the live log to `.1`
    (or just removes it when ``keep <= 0``), leaving `path` absent so the next append
    starts a fresh file. Returns True iff a rotation happened. Never raises.

    ``max_bytes <= 0`` disables rotation (returns False).
    """
    try:
        if max_bytes <= 0 or not path.is_file():
            return False
        if path.stat().st_size < max_bytes:
            return False

        if keep <= 0:
            path.unlink()
            return True

        # Drop the oldest slot, then cascade .{i} -> .{i+1} down to the live log.
        oldest = _backup(path, keep)
        if oldest.exists():
            oldest.unlink()
        for i in range(keep - 1, 0, -1):
            src = _backup(path, i)
            if src.exists():
                os.replace(src, _backup(path, i + 1))
        os.replace(path, _backup(path, 1))
        return True
    except OSError:
        return False


def append_jsonl(
    path: Path,
    record: Any,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    keep: int = DEFAULT_KEEP,
) -> bool:
    """Rotate `path` if needed, then append `record` as one JSON line.

    Returns True if the record was written. Never raises — a write failure is swallowed
    (callers are best-effort loggers that must not crash their host).
    """
    try:
        rotate_if_needed(path, max_bytes=max_bytes, keep=keep)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(json.dumps(record) + "\n")
        return True
    except (OSError, TypeError, ValueError):
        return False
