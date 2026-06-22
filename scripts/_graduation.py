#!/usr/bin/env python3
"""Tier-agnostic ``~/.forge`` graduation core (T-207, REQ-GR-001).

This module holds the cross-tier mechanics that used to live inside
``promote-lessons.py``: the project **registry** (``~/.forge/projects.yaml``),
the atomic store writer, the 30-day ``is_stale`` TTL, a generic idempotent
keyed **merge**, a ``Tier`` protocol, and the fail-soft ``graduate()`` driver.

A *tier* (lessons, skills, workflows) is a thin adapter answering five
questions — what a project contributes (``collect``), which contributions pass
the gate (``gate``), each record's conflict key (``key``), where they live
globally (``promote``), and how they are recalled (``recall``). The
``graduate()`` driver loops ``registered-projects × tiers`` and isolates each
tier so one tier's failure degrades **only** that tier (fail-soft per tier).
The driver **never raises** — graduation runs silently at session-start and must
never block or delay startup (REQ-NF-034).

stdlib + PyYAML only; every external read is guarded; all writes are atomic and
confined to ``~/.forge`` / the project's ``.forge`` (REQ-NF-035).
"""

from __future__ import annotations

import datetime
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, runtime_checkable

import yaml

logger = logging.getLogger(__name__)

# Global records older than this (by ``last_used``) decay out of recall. The
# single shared TTL governs decay-from-recall for every tier (REQ-NF-035).
_GLOBAL_TTL_DAYS = 30


# ---------------------------------------------------------------------------
# Atomic write (temp + os.replace) — REQ-NF-035
# ---------------------------------------------------------------------------


def write_atomic(path: Path, content: str) -> None:
    """Atomically write ``content`` to ``path`` (temp file + ``os.replace``)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, suffix=".tmp", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
        tmp = fh.name
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# 30-day TTL / staleness — shared by all tiers (EF-026)
# ---------------------------------------------------------------------------


def is_stale(
    last_used: Optional[str],
    *,
    today: Optional[datetime.date] = None,
    max_age_days: int = _GLOBAL_TTL_DAYS,
) -> bool:
    """True if ``last_used`` (YYYY-MM-DD or ISO) is older than ``max_age_days``.

    A missing/unparseable date is treated as NOT stale (kept) — we only decay
    entries we can positively date as old.
    """
    if not last_used:
        return False
    try:
        date = datetime.date.fromisoformat(str(last_used)[:10])
    except ValueError:
        return False
    today = today or datetime.date.today()
    return (today - date).days > max_age_days


# ---------------------------------------------------------------------------
# Registry (~/.forge/projects.yaml) — register / load
# ---------------------------------------------------------------------------


def ensure_registry(global_dir: Path) -> None:
    """Create ``~/.forge/`` + the ``projects.yaml`` registry scaffold if absent.

    Scope is the **registry only** — the per-tier global stores (e.g.
    ``global-lessons.yaml``) are scaffolded by their own adapters.
    """
    global_dir.mkdir(parents=True, exist_ok=True)
    registry = global_dir / "projects.yaml"
    if not registry.exists():
        write_atomic(registry, yaml.dump({"schema_version": 1, "projects": []}))


def load_registry(global_dir: Path) -> list[str]:
    """Return the list of registered project paths (fail-soft → ``[]``)."""
    path = global_dir / "projects.yaml"
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return [str(p) for p in (data.get("projects") or [])]
    except Exception:  # noqa: BLE001 — never raise from a guarded read
        return []


def register_project(global_dir: Path, project_path: Path) -> bool:
    """Add ``project_path`` to the registry. Returns True if newly added."""
    ensure_registry(global_dir)
    canonical = str(project_path.resolve())
    projects = load_registry(global_dir)
    if canonical in projects:
        return False
    projects.append(canonical)
    write_atomic(
        global_dir / "projects.yaml",
        yaml.dump({"schema_version": 1, "projects": projects}),
    )
    logger.info("registered project: %s", canonical)
    return True


# ---------------------------------------------------------------------------
# Generic idempotent keyed merge (exact-key upsert)
# ---------------------------------------------------------------------------


def merge_by_key(
    new_records: list[dict],
    existing: list[dict],
    key_fn: Callable[[dict], str],
    *,
    merge_fn: Optional[Callable[[dict, dict], dict]] = None,
) -> list[dict]:
    """Upsert ``new_records`` into ``existing`` keyed by ``key_fn`` (idempotent).

    On an exact-key collision the existing record is replaced by the new one,
    or — when ``merge_fn`` is given — by ``merge_fn(existing_record, new_record)``
    so a tier can accumulate fields (e.g. union the source ``projects``). New
    keys are appended in input order. Skills/workflows tiers key on slug/name;
    the lessons tier keeps its own trigger-similarity merge.
    """
    result = list(existing)
    index: dict[str, int] = {}
    for i, record in enumerate(result):
        try:
            index[key_fn(record)] = i
        except Exception:  # noqa: BLE001 — a malformed existing record is skipped
            continue
    for record in new_records:
        try:
            k = key_fn(record)
        except Exception:  # noqa: BLE001 — a malformed new record is skipped
            continue
        if k in index:
            i = index[k]
            result[i] = merge_fn(result[i], record) if merge_fn else record
        else:
            index[k] = len(result)
            result.append(record)
    return result


# ---------------------------------------------------------------------------
# Tier protocol + fail-soft graduate() driver
# ---------------------------------------------------------------------------


@runtime_checkable
class Tier(Protocol):
    """A graduation tier adapter over the shared core.

    ``name`` labels the tier in ``graduate()``'s result dict. The five methods
    answer: what a project contributes, which pass the gate, each record's
    conflict key, where promotables live globally, and how they are recalled.
    """

    name: str

    def collect(self, project_path: str) -> list: ...

    def gate(self, records: list) -> list: ...

    def key(self, record: Any) -> str: ...

    def promote(self, promotable: list, global_dir: Path, *, dry_run: bool = ...) -> list: ...

    def recall(self, global_dir: Path, project_path: str) -> None: ...


def _tier_name(tier: Tier) -> str:
    return getattr(tier, "name", None) or type(tier).__name__


def graduate(
    global_dir: Path,
    tiers: list[Tier],
    *,
    dry_run: bool = False,
    project_path: Optional[Path] = None,
) -> dict:
    """Run every tier over the registered projects, fail-soft per tier.

    For each tier: collect across the registry → gate → promote, then recall for
    ``project_path`` (the current project, if given). Each tier is wrapped so its
    exception degrades **only** that tier (its result becomes ``[]``) and never
    aborts the driver or a sibling tier. Returns ``{tier_name: new_records}``.
    The driver itself never raises (REQ-GR-001 / REQ-NF-034).
    """
    try:
        ensure_registry(global_dir)
    except Exception:  # noqa: BLE001 — degrade to empty registry, never raise
        logger.warning("graduate: registry scaffold failed for %s", global_dir)
    projects = load_registry(global_dir)

    results: dict[str, list] = {}
    for tier in tiers:
        name = _tier_name(tier)
        try:
            records: list = []
            for proj in projects:
                records.extend(tier.collect(proj) or [])
            promotable = tier.gate(records)
            new_records = tier.promote(promotable, global_dir, dry_run=dry_run)
            results[name] = list(new_records or [])
        except Exception as exc:  # noqa: BLE001 — isolate this tier only
            logger.warning("graduate: tier %r degraded to no-op: %s", name, exc)
            results[name] = []
        # Recall is best-effort and isolated from promotion failures.
        if project_path is not None and not dry_run:
            try:
                tier.recall(global_dir, str(project_path))
            except Exception as exc:  # noqa: BLE001 — recall never blocks startup
                logger.warning("graduate: tier %r recall degraded: %s", name, exc)
    return results


# ---------------------------------------------------------------------------
# CLI: the /forge:graduate surface lands in T-211 — import-only for now.
# ---------------------------------------------------------------------------


if __name__ == "__main__":  # pragma: no cover - thin CLI arrives in T-211
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    logger.info("_graduation is a library module; the /forge:graduate CLI lands in T-211")
