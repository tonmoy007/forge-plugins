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
import sys
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
# CLI: the /forge:graduate surface (T-211, REQ-GR-007 / AC-GR-006).
#
# A thin argparse front end over the SAME ``graduate()`` driver the session-start
# hook uses — there is no second promotion path. The three adapter tiers are
# lazy-imported INSIDE ``main()`` so this module stays import-clean as a library
# (a tier import fault degrades the CLI to a clean message, never a hard crash).
# ---------------------------------------------------------------------------

# The plugin root (…/forge-plugin); ``<root>/skills`` is where approved skills
# install to and where the SkillTier recalls graduated skills into.
_PLUGIN_DIR = Path(__file__).resolve().parent.parent

# Per-tier global stores enumerated by the ``list`` view (tier label → file/key).
_STORE_FILES: tuple[tuple[str, str, str], ...] = (
    ("lessons", "global-lessons.yaml", "lessons"),
    ("skills", "global-skills.yaml", "skills"),
    ("workflows", "global-workflows.yaml", "workflows"),
)


def _build_tiers() -> list:
    """Assemble the three graduation tiers (mirrors session-start's assembly).

    The lessons tier lives in the hyphenated ``promote-lessons.py``; it is loaded
    via importlib and registered in ``sys.modules`` BEFORE ``exec_module`` so its
    ``@dataclass`` string annotations resolve. Imports are local to keep the core
    import-clean. Any import fault propagates to ``main()``'s guard.
    """
    import importlib.util

    # Make the sibling adapters importable whether this module was run as a
    # script or loaded via importlib (tests) — mirrors the sibling-import idiom.
    scripts_dir = str(_PLUGIN_DIR / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from _graduation_skills import SkillTier
    from _graduation_workflows import WorkflowTier

    promote_lessons = sys.modules.get("promote_lessons")
    if promote_lessons is None:
        spec = importlib.util.spec_from_file_location(
            "promote_lessons", _PLUGIN_DIR / "scripts" / "promote-lessons.py"
        )
        promote_lessons = importlib.util.module_from_spec(spec)
        sys.modules["promote_lessons"] = promote_lessons
        spec.loader.exec_module(promote_lessons)

    return [
        promote_lessons.LessonTier(),
        SkillTier(_PLUGIN_DIR / "skills"),
        WorkflowTier(),
    ]


def _load_store_entries(path: Path, list_key: str) -> list[dict]:
    """Read a per-tier global store → its list of entries (fail-soft → [])."""
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return [r for r in (data.get(list_key) or []) if isinstance(r, dict)]
    except Exception:  # noqa: BLE001 — a missing/garbled store reads as empty
        return []


def _entry_key(entry: dict) -> str:
    """The human-facing identifier of a store entry across tiers."""
    return str(entry.get("slug") or entry.get("name") or entry.get("trigger") or "?")


def _print_promotion_summary(results: dict, *, dry_run: bool) -> None:
    """Print a per-tier promoted (or would-promote) summary from ``graduate()``."""
    verb = "Would promote" if dry_run else "Promoted"
    header = "Dry-run graduation preview (nothing written):" if dry_run else "Graduation scan complete:"
    print(header)
    for name, records in sorted(results.items()):
        records = records or []
        if not records:
            print(f"  {name}: nothing to promote")
            continue
        keys = ", ".join(_entry_key(r) for r in records)
        print(f"  {name}: {verb} {len(records)} — {keys}")


def _print_store_listing(global_dir: Path) -> None:
    """Enumerate the global store per tier: entry count + each key's last_used."""
    print(f"Global store at {global_dir}:")
    for tier_name, filename, list_key in _STORE_FILES:
        entries = _load_store_entries(global_dir / filename, list_key)
        print(f"  {tier_name}: {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}")
        for entry in entries:
            print(f"    - {_entry_key(entry)} (last_used: {entry.get('last_used') or 'n/a'})")


def main(argv: Optional[list[str]] = None) -> int:
    """Thin ``/forge:graduate`` CLI over ``graduate()``. Never raises.

    Default action runs a real scan and promotes; ``--dry-run`` previews without
    writing; ``list`` (subcommand or ``--list``) enumerates the global store.
    Returns a process exit code (0 = ok, 2 = argparse usage error).
    """
    import argparse

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        prog="forge-graduate",
        description="Promote proven lessons, skills, and workflows to ~/.forge "
        "(the shared graduation store), or list/preview what is there.",
    )
    parser.add_argument(
        "--global-dir",
        type=Path,
        default=Path.home() / ".forge",
        help="override ~/.forge directory (default: ~/.forge)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview what would be promoted; write nothing",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list the current global store per tier and exit",
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=["scan", "list"],
        default="scan",
        help="'scan' (default) to graduate, or 'list' to enumerate the store",
    )
    # argparse exits 2 on a usage error before we reach the guard below — that is
    # the one sanctioned nonzero exit (a true CLI misuse), not a runtime fault.
    args = parser.parse_args(argv)

    try:
        global_dir = args.global_dir
        if args.list or args.action == "list":
            _print_store_listing(global_dir)
            return 0

        tiers = _build_tiers()
        results = graduate(global_dir, tiers, dry_run=args.dry_run)
        _print_promotion_summary(results, dry_run=args.dry_run)
        return 0
    except Exception as exc:  # noqa: BLE001 — the CLI must never raise out
        logger.warning("graduate CLI degraded: %s", exc)
        print(f"forge:graduate could not complete cleanly: {exc}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
