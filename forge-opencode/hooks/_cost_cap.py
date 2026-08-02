#!/usr/bin/env python3
"""Daily/monthly cost cap + ledger — the hard-prerequisite spend gate (REQ-F-004
..007, ADR-007).

Every background/orchestration dispatch is billable and happens off the
foreground, so spend must be bounded *before* it occurs. This module is the only
gate: the adapters (`_background_agent.py`, `_orchestrate.py`) call `precheck()`
before dispatch and `record()` after, and `note_skip()` when the cap blocks.

Design rules:
  - **Never raises** (REQ-NF-006): missing/corrupt config or ledger degrades to a
    safe default (defaults caps; ignore unreadable ledger lines). A cost gate that
    crashes a hook would be worse than the spend it guards.
  - Cost is **API-reported**: `actual_usd` is the dispatch's `total_cost_usd`;
    `estimated_usd` is a conservative pre-dispatch floor used only to gate before
    the run. The running sum uses `actual_usd` where present, else `estimated_usd`.
  - Stdlib only; PyYAML is read fail-soft (defaults when absent/unparseable).
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
import _event_log as event_log  # noqa: E402  (sibling hooks/ module)

DEFAULT_DAILY_USD = 0.50
MONTHLY_WINDOW_DAYS = 30
_LEDGER_NAME = "cost-ledger.jsonl"
_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"


# --------------------------------------------------------------------------- #
# Caps
# --------------------------------------------------------------------------- #
@dataclass
class Caps:
    daily_usd: float
    monthly_usd: Optional[float]


def _safe_yaml_load(text: str) -> Optional[dict]:
    """Parse YAML, returning None on any failure (incl. PyYAML absent)."""
    try:
        import yaml  # noqa: F401
    except ImportError:
        return None
    try:
        data = yaml.safe_load(text)
    except Exception:  # noqa: BLE001 — malformed config must not crash the gate
        return None
    return data if isinstance(data, dict) else None


def _coerce_float(value: object, default: Optional[float]) -> Optional[float]:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def load_caps(forge_dir: Path) -> Caps:
    """Read caps from `<forge_dir>/config.yaml`; fail-soft to defaults."""
    cfg_path = forge_dir / "config.yaml"
    if not cfg_path.exists():
        return Caps(DEFAULT_DAILY_USD, None)
    data = _safe_yaml_load(_read_text(cfg_path))
    section = data.get("cost_cap") if data else None
    if not isinstance(section, dict):
        return Caps(DEFAULT_DAILY_USD, None)
    daily = _coerce_float(section.get("daily_usd"), DEFAULT_DAILY_USD) or DEFAULT_DAILY_USD
    monthly = _coerce_float(section.get("monthly_usd"), None)
    return Caps(daily, monthly)


# --------------------------------------------------------------------------- #
# Ledger
# --------------------------------------------------------------------------- #
@dataclass
class Decision:
    allowed: bool
    reason: str
    spent_today: float
    spent_month: float
    caps: Caps


def _read_text(path: Path) -> str:
    try:
        return path.read_text()
    except OSError:
        return ""


def _now(now: Optional[dt.datetime]) -> dt.datetime:
    return now if now is not None else dt.datetime.now(dt.timezone.utc)


def _parse_ts(value: object) -> Optional[dt.datetime]:
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.strptime(value, _TS_FMT).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _entry_cost(row: dict) -> float:
    """actual_usd where present, else estimated_usd, else 0.0."""
    actual = row.get("actual_usd")
    chosen = actual if actual is not None else row.get("estimated_usd")
    val = _coerce_float(chosen, 0.0)
    return val if val is not None else 0.0


def _read_ledger(forge_dir: Path) -> list[dict]:
    """Return ledger rows, silently skipping unreadable/corrupt lines."""
    rows: list[dict] = []
    for line in _read_text(forge_dir / _LEDGER_NAME).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _spend(rows: list[dict], now: dt.datetime) -> tuple[float, float]:
    """(spent_today, spent_rolling_30d) in USD."""
    today = now.date()
    month_start = now - dt.timedelta(days=MONTHLY_WINDOW_DAYS)
    day_sum = 0.0
    month_sum = 0.0
    for row in rows:
        ts = _parse_ts(row.get("ts"))
        if ts is None:
            continue
        cost = _entry_cost(row)
        if ts.date() == today:
            day_sum += cost
        if ts >= month_start:
            month_sum += cost
    return day_sum, month_sum


def precheck(forge_dir: Path, floor_usd: float, *, now: Optional[dt.datetime] = None) -> Decision:
    """Gate a dispatch *before* it spends. Allowed iff `spent + floor` stays within
    the daily cap and (if configured) the rolling-30-day monthly cap. Never raises.
    """
    when = _now(now)
    caps = load_caps(forge_dir)
    spent_today, spent_month = _spend(_read_ledger(forge_dir), when)

    if spent_today + floor_usd > caps.daily_usd:
        return Decision(
            False,
            f"daily cap reached (${spent_today:.4f} + ${floor_usd:.4f} > ${caps.daily_usd:.2f})",
            spent_today, spent_month, caps,
        )
    if caps.monthly_usd is not None and spent_month + floor_usd > caps.monthly_usd:
        return Decision(
            False,
            f"monthly cap reached (${spent_month:.4f} + ${floor_usd:.4f} > ${caps.monthly_usd:.2f})",
            spent_today, spent_month, caps,
        )
    return Decision(True, "within budget", spent_today, spent_month, caps)


def record(
    forge_dir: Path,
    *,
    feature: str,
    session_id: str,
    input_tokens: int,
    output_tokens: int,
    estimated_usd: float,
    actual_usd: Optional[float],
    now: Optional[dt.datetime] = None,
) -> None:
    """Append one ledger entry (REQ-F-006). `actual_usd` is the API-reported
    `total_cost_usd`; pass None until the dispatch returns. Never raises.
    """
    when = _now(now)
    entry = {
        "ts": when.strftime(_TS_FMT),
        "feature": feature,
        "session_id": session_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_usd": estimated_usd,
        "actual_usd": actual_usd,
    }
    try:
        forge_dir.mkdir(parents=True, exist_ok=True)
        with (forge_dir / _LEDGER_NAME).open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        return  # ledger is advisory — never crash the caller


def note_skip(forge_dir: Path, *, feature: str, session_id: str, reason: str) -> None:
    """Log an over-cap skip to .forge/events.jsonl (REQ-F-026 surfacing). Never raises."""
    try:
        event_log.append(
            forge_dir,
            "cost_cap_exceeded",
            session_id,
            0,
            {"feature": feature, "reason": reason},
            "skipped",
        )
    except Exception:  # noqa: BLE001 — logging the skip must not crash the caller
        return
