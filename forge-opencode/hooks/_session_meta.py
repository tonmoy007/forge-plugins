"""Per-session reflection depth and daily cost tracking (FR-SEM-004, FR-COST-004).

Stored in .forge/session-meta/<session_id>.json (atomic write).
Cost ledger in .forge/cost-ledger.jsonl (append-only).
"""
from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass
from pathlib import Path

MAX_REFLECTIONS_DEFAULT: int = 3
COST_CAP_DEFAULT_USD: float = 1.00


@dataclass
class SessionMeta:
    session_id: str
    started_at: str
    reflection_count: int
    max_reflections_per_session: int
    cost_today_usd: float
    cost_cap_today_usd: float


def _meta_path(forge_dir: Path, session_id: str) -> Path:
    return forge_dir / "session-meta" / f"{session_id}.json"


def _cost_ledger_path(forge_dir: Path) -> Path:
    return forge_dir / "cost-ledger.jsonl"


def _sum_cost_today(forge_dir: Path) -> float:
    path = _cost_ledger_path(forge_dir)
    if not path.exists():
        return 0.0
    today = datetime.date.today().isoformat()
    total = 0.0
    try:
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("date") == today:
                total += float(entry.get("cost_usd", 0))
    except Exception:
        pass
    return total


def load(forge_dir: Path, session_id: str) -> SessionMeta:
    """Load existing session meta or initialise fresh."""
    path = _meta_path(forge_dir, session_id)
    if path.exists():
        try:
            data = json.loads(path.read_text())
            fields = SessionMeta.__dataclass_fields__
            return SessionMeta(**{k: data[k] for k in fields if k in data})
        except Exception:
            pass
    return SessionMeta(
        session_id=session_id,
        started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        reflection_count=0,
        max_reflections_per_session=MAX_REFLECTIONS_DEFAULT,
        cost_today_usd=_sum_cost_today(forge_dir),
        cost_cap_today_usd=COST_CAP_DEFAULT_USD,
    )


def save(forge_dir: Path, meta: SessionMeta) -> None:
    path = _meta_path(forge_dir, meta.session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(meta), indent=2))
    tmp.replace(path)


def increment_reflection(forge_dir: Path, meta: SessionMeta) -> SessionMeta:
    meta.reflection_count += 1
    save(forge_dir, meta)
    return meta


def is_loop_detected(meta: SessionMeta) -> bool:
    """True when reflection count exceeds the per-session limit."""
    return meta.reflection_count > meta.max_reflections_per_session


def is_cost_exceeded(meta: SessionMeta) -> bool:
    """True when today's cumulative cost meets or exceeds the daily cap."""
    return meta.cost_today_usd >= meta.cost_cap_today_usd


def record_cost(
    forge_dir: Path, session_id: str, cost_usd: float, component: str
) -> None:
    """Append one cost entry to cost-ledger.jsonl."""
    path = _cost_ledger_path(forge_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = json.dumps({
        "date": datetime.date.today().isoformat(),
        "session": session_id,
        "component": component,
        "cost_usd": cost_usd,
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    with path.open("a") as f:
        f.write(entry + "\n")
