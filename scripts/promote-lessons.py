#!/usr/bin/env python3
"""Promote cross-project lessons to ~/.forge/global-lessons.yaml.

Scans all registered Forge projects for lessons that appear (by trigger
similarity) in at least --threshold distinct projects and writes them to
the global lessons file read by session-start.py.

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
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1
_DEFAULT_THRESHOLD = 3
_SIMILARITY_RATIO = 0.8


# ---------------------------------------------------------------------------
# ~/.forge/ bootstrap
# ---------------------------------------------------------------------------


def ensure_global_dir(global_dir: Path) -> None:
    """Create ~/.forge/ scaffold if it does not exist."""
    global_dir.mkdir(parents=True, exist_ok=True)
    registry = global_dir / "projects.yaml"
    if not registry.exists():
        _write_atomic(registry, yaml.dump({"schema_version": 1, "projects": []}))
    global_yaml = global_dir / "global-lessons.yaml"
    if not global_yaml.exists():
        _write_atomic(
            global_yaml,
            yaml.dump({"schema_version": _SCHEMA_VERSION, "lessons": []}),
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def load_registry(global_dir: Path) -> list[str]:
    """Return list of registered project paths."""
    path = global_dir / "projects.yaml"
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return [str(p) for p in (data.get("projects") or [])]
    except Exception:  # noqa: BLE001
        return []


def register_project(global_dir: Path, project_path: Path) -> bool:
    """Add project_path to registry. Returns True if it was newly added."""
    ensure_global_dir(global_dir)
    canonical = str(project_path.resolve())
    projects = load_registry(global_dir)
    if canonical in projects:
        return False
    projects.append(canonical)
    _write_atomic(
        global_dir / "projects.yaml",
        yaml.dump({"schema_version": 1, "projects": projects}),
    )
    logger.info("registered project: %s", canonical)
    return True


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
# Merge with existing global lessons
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


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------


def _write_atomic(path: Path, content: str) -> None:
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
# Public API
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

    clusters = cluster_lessons(all_lessons)
    promotable = [c for c in clusters if len(_distinct_projects(c)) >= threshold]
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
        logger.info(
            "promoted %d lesson(s) from %d project(s) to global",
            len(new_records),
            len(projects),
        )

    return new_records


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
        register_project(args.global_dir, args.register)

    if args.promote:
        promote(args.global_dir, threshold=args.threshold, dry_run=args.dry_run)

    sys.exit(0)


if __name__ == "__main__":
    main()
