#!/usr/bin/env python3
"""Promote cross-project lessons to ~/.forge/global-lessons.yaml.

Scans all registered Forge projects for lessons that appear (by trigger
similarity) in at least --threshold distinct projects and writes them to
the global lessons file read by session-start.py.

This is the **lessons tier** of the unified ``~/.forge`` graduation layer
(T-207): the cross-tier mechanics — registry, atomic IO, 30-day ``is_stale``
TTL, the generic keyed merge, the ``Tier`` protocol, and the fail-soft
``graduate()`` driver — live in ``scripts/_graduation.py``. This file keeps the
lesson-specific logic (trigger-similarity clustering, breadth+frequency gate,
similarity merge) and the original CLI, byte-for-byte unchanged (REQ-GR-002,
REQ-NF-036). ``LessonTier`` re-expresses that logic as a ``Tier`` so the unified
driver runs lessons through the exact same path as the legacy ``promote()``.

Usage:
  promote-lessons.py --register PATH              # add project to registry
  promote-lessons.py --promote                    # scan and promote
  promote-lessons.py --register PATH --promote    # register then promote
  promote-lessons.py --global-dir PATH ...        # override ~/.forge dir
  promote-lessons.py --dry-run                    # print; do not write
"""

from __future__ import annotations

import argparse
import difflib
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

# Sibling import idiom (hyphenated CLI files share the core via scripts/ on path).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _graduation import (  # noqa: E402
    is_stale,
    load_registry,
    merge_by_key,
    register_project,
)
from _graduation import Tier  # noqa: E402,F401  (LessonTier implements this protocol)
from _graduation import write_atomic as _write_atomic  # noqa: E402

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1
_DEFAULT_THRESHOLD = 3
_SIMILARITY_RATIO = 0.8
# EF-026 global-store hygiene: a concept must have fired at least this many times
# (summed across the cluster) before it reaches the global store — a one-shot
# test artifact (frequency 1) never gets promoted.
_MIN_FREQUENCY = 2

# Re-exported for callers/tests that referenced these from this module historically.
__all__ = [
    "ensure_global_dir",
    "load_registry",
    "register_project",
    "load_project_lessons",
    "cluster_lessons",
    "promote",
    "merge_global",
    "is_stale",
    "ProjectLesson",
    "LessonTier",
]


# ---------------------------------------------------------------------------
# ~/.forge/ bootstrap (lessons store scaffold)
# ---------------------------------------------------------------------------


def ensure_global_dir(global_dir: Path) -> None:
    """Create ~/.forge/ scaffold (registry + global-lessons.yaml) if absent."""
    # Registry scaffold is owned by the shared core; the lessons store is ours.
    from _graduation import ensure_registry  # noqa: E402 — local to avoid cycle noise

    ensure_registry(global_dir)
    global_yaml = global_dir / "global-lessons.yaml"
    if not global_yaml.exists():
        _write_atomic(
            global_yaml,
            yaml.dump({"schema_version": _SCHEMA_VERSION, "lessons": []}),
        )


# ---------------------------------------------------------------------------
# Lesson loading
# ---------------------------------------------------------------------------


@dataclass
class ProjectLesson:
    lesson: dict
    project: str


def load_project_lessons(project_path: str) -> list[ProjectLesson]:
    """Load .forge/lessons.yaml from a registered project."""
    lessons_yaml = Path(project_path) / ".forge" / "lessons.yaml"
    if not lessons_yaml.exists():
        return []
    try:
        data = yaml.safe_load(lessons_yaml.read_text(encoding="utf-8")) or {}
        lessons = data.get("lessons") or []
        return [ProjectLesson(lesson=l, project=project_path) for l in lessons if l]
    except Exception as exc:  # noqa: BLE001
        logger.warning("skipping %s: %s", project_path, exc)
        return []


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


def _similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= _SIMILARITY_RATIO


def cluster_lessons(all_lessons: list[ProjectLesson]) -> list[list[ProjectLesson]]:
    """Group lessons by trigger similarity. Each cluster is one concept."""
    clusters: list[list[ProjectLesson]] = []
    for item in all_lessons:
        trigger = item.lesson.get("trigger", "")
        placed = False
        for cluster in clusters:
            rep_trigger = cluster[0].lesson.get("trigger", "")
            if _similar(trigger, rep_trigger):
                cluster.append(item)
                placed = True
                break
        if not placed:
            clusters.append([item])
    return clusters


def _distinct_projects(cluster: list[ProjectLesson]) -> set[str]:
    return {item.project for item in cluster}


def _cluster_freq(cluster: list[ProjectLesson]) -> int:
    return sum(x.lesson.get("frequency", 0) or 0 for x in cluster)


def _gate_clusters(
    all_lessons: list[ProjectLesson], threshold: int
) -> list[list[ProjectLesson]]:
    """EF-026: require both cross-project breadth AND that the concept fired ≥2×."""
    clusters = cluster_lessons(all_lessons)
    return [
        c
        for c in clusters
        if len(_distinct_projects(c)) >= threshold and _cluster_freq(c) >= _MIN_FREQUENCY
    ]


def _make_global_record(cluster: list[ProjectLesson]) -> dict:
    """Build a global lesson record from a cluster of matching lessons."""
    rep = max(cluster, key=lambda x: x.lesson.get("frequency", 0))
    projects = sorted(_distinct_projects(cluster))
    total_freq = sum(x.lesson.get("frequency", 0) for x in cluster)
    raw_dates = [x.lesson.get("last_used") or "" for x in cluster]
    last_used: Optional[str] = max(raw_dates) if any(raw_dates) else None
    if last_used == "":
        last_used = None
    return {
        "id": rep.lesson.get("id", ""),
        "date": rep.lesson.get("date", ""),
        "title": rep.lesson.get("title", ""),
        "trigger": rep.lesson.get("trigger", ""),
        "rule": rep.lesson.get("rule", ""),
        "why": rep.lesson.get("why", ""),
        "tags": rep.lesson.get("tags", []),
        "stage": rep.lesson.get("stage", []),
        "project_types": rep.lesson.get("project_types", []),
        "frequency": total_freq,
        "last_used": last_used,
        "projects": projects,
    }


# ---------------------------------------------------------------------------
# Merge with existing global lessons (trigger-similarity, lesson-specific)
# ---------------------------------------------------------------------------


def _load_global(global_dir: Path) -> list[dict]:
    path = global_dir / "global-lessons.yaml"
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data.get("lessons") or []
    except Exception:  # noqa: BLE001
        return []


def _find_global_match(record: dict, existing: list[dict]) -> Optional[dict]:
    trigger = record.get("trigger", "")
    for ex in existing:
        if _similar(trigger, ex.get("trigger", "")):
            return ex
    return None


def merge_global(new_records: list[dict], existing: list[dict]) -> list[dict]:
    """Merge new promoted records into existing global lessons."""
    result = list(existing)
    for record in new_records:
        ex = _find_global_match(record, result)
        if ex:
            # Update in place: refresh content fields, accumulate projects
            idx = result.index(ex)
            merged_projects = sorted(
                set(ex.get("projects", [])) | set(record.get("projects", []))
            )
            result[idx] = {**record, "projects": merged_projects}
        else:
            result.append(record)
    return result


def _emit_lessons(
    global_dir: Path, promotable: list[list[ProjectLesson]], *, dry_run: bool
) -> list[dict]:
    """Make global records from promotable clusters, merge, write/print.

    The single load→make→merge→write body shared by the legacy ``promote()`` CLI
    and ``LessonTier.promote`` so the two entry points cannot diverge — same
    records, same merge, same byte output (AC-GR-001).
    """
    new_records = [_make_global_record(c) for c in promotable]
    existing = _load_global(global_dir)
    merged = merge_global(new_records, existing)
    output = yaml.dump(
        {"schema_version": _SCHEMA_VERSION, "lessons": merged},
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    if dry_run:
        print(output, end="")
    else:
        _write_atomic(global_dir / "global-lessons.yaml", output)
    return new_records


# ---------------------------------------------------------------------------
# Public API — legacy CLI entry (behavior-preserving)
# ---------------------------------------------------------------------------


def promote(
    global_dir: Path,
    *,
    threshold: int = _DEFAULT_THRESHOLD,
    dry_run: bool = False,
) -> list[dict]:
    """Scan registered projects; promote lessons appearing in threshold+ projects.

    Returns the list of newly promoted records.
    """
    ensure_global_dir(global_dir)
    projects = load_registry(global_dir)
    if not projects:
        logger.info("no projects registered — nothing to promote")
        return []

    all_lessons: list[ProjectLesson] = []
    for proj in projects:
        all_lessons.extend(load_project_lessons(proj))

    promotable = _gate_clusters(all_lessons, threshold)
    new_records = _emit_lessons(global_dir, promotable, dry_run=dry_run)

    if not dry_run:
        logger.info(
            "promoted %d lesson(s) from %d project(s) to global",
            len(new_records),
            len(projects),
        )

    return new_records


# ---------------------------------------------------------------------------
# Lessons tier adapter (the new graduate() entry point)
# ---------------------------------------------------------------------------


class LessonTier:
    """The lessons tier over ``_graduation`` — same logic as legacy ``promote()``.

    ``collect`` loads a project's lessons; ``gate`` clusters all collected
    lessons and applies the breadth≥threshold + freq≥2 rule; ``promote`` writes
    the merged ``global-lessons.yaml`` via the shared ``_emit_lessons`` body.
    Recall is handled by session-start injection (project-lessons-win), so the
    tier's ``recall`` is a no-op here (REQ-GR-005).
    """

    name = "lessons"

    def __init__(self, threshold: int = _DEFAULT_THRESHOLD) -> None:
        self.threshold = threshold

    def collect(self, project_path: str) -> list[ProjectLesson]:
        return load_project_lessons(project_path)

    def gate(self, records: list[ProjectLesson]) -> list[list[ProjectLesson]]:
        return _gate_clusters(records, self.threshold)

    def key(self, record: dict) -> str:
        return record.get("trigger", "")

    def promote(
        self,
        promotable: list[list[ProjectLesson]],
        global_dir: Path,
        *,
        dry_run: bool = False,
    ) -> list[dict]:
        ensure_global_dir(global_dir)
        return _emit_lessons(global_dir, promotable, dry_run=dry_run)

    def recall(self, global_dir: Path, project_path: str) -> None:
        # Lesson recall is performed by session-start.py (project-lessons-win).
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--register",
        type=Path,
        metavar="PATH",
        help="register a project path",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="scan registered projects and promote cross-project lessons",
    )
    parser.add_argument(
        "--global-dir",
        type=Path,
        default=Path.home() / ".forge",
        help="override ~/.forge directory (default: ~/.forge)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=_DEFAULT_THRESHOLD,
        help=f"number of projects required for promotion (default: {_DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be written; do not write",
    )
    args = parser.parse_args()

    if not args.register and not args.promote:
        parser.print_help()
        sys.exit(1)

    if args.register:
        # Eagerly scaffold the lessons store on --register so the CLI is
        # observably behavior-preserving vs the pre-T-207 path (the shared core's
        # register_project only scaffolds the registry). Keeps the core clean.
        ensure_global_dir(args.global_dir)
        register_project(args.global_dir, args.register)

    if args.promote:
        promote(args.global_dir, threshold=args.threshold, dry_run=args.dry_run)

    sys.exit(0)


if __name__ == "__main__":
    main()
