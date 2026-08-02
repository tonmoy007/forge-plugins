#!/usr/bin/env python3
"""Sync tasks/lessons.md → .forge/lessons.yaml.

Parses structured lesson entries from the markdown file and writes them
as YAML for session-start.py's _load_lessons(). Merges with any existing
lessons.yaml to preserve stage, project_types, frequency, and last_used.

Usage:
  sync-lessons.py --cwd PATH [--dry-run]
  sync-lessons.py --input PATH --output PATH [--dry-run]
"""

from __future__ import annotations

import argparse
import difflib
import logging
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1
_HEADING_RE = re.compile(r"^###\s+(\d{4}-\d{2}-\d{2})\s+[—\-]+\s+(.+)$")
_FIELD_RE = re.compile(r"^-\s+\*\*(\w+)\*\*:\s*(.+)$")
_TAGS_RE = re.compile(r"\[([^\]]*)\]")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class LessonEntry:
    id: str
    date: str
    title: str
    trigger: str
    rule: str
    why: str
    tags: list[str] = field(default_factory=list)
    stage: list[int] = field(default_factory=list)
    project_types: list[str] = field(default_factory=list)
    frequency: int = 0
    last_used: Optional[str] = None


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _parse_tags(text: str) -> list[str]:
    m = _TAGS_RE.search(text)
    inner = m.group(1) if m else text
    return [t.strip() for t in inner.split(",") if t.strip()]


def _slug(title: str) -> str:
    s = title.lower()
    s = re.sub(r"[`'\"()]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s[:40].strip("-")


def parse_lessons_md(path: Path) -> list[LessonEntry]:
    """Parse lesson entries from a lessons.md file. Returns [] on any failure."""
    if not path.exists():
        return []
    entries: list[LessonEntry] = []
    current: dict = {}
    seen_slugs: dict[str, int] = {}

    def _flush() -> None:
        if not current.get("title") or not current.get("trigger"):
            return
        slug = _slug(current["title"])
        count = seen_slugs.get(slug, 0)
        seen_slugs[slug] = count + 1
        uid = f"L-{slug}" if count == 0 else f"L-{slug}-{count}"
        entries.append(
            LessonEntry(
                id=uid,
                date=current.get("date", ""),
                title=current["title"],
                trigger=current.get("trigger", ""),
                rule=current.get("rule", ""),
                why=current.get("why", ""),
                tags=current.get("tags", []),
            )
        )

    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            h = _HEADING_RE.match(line)
            if h:
                _flush()
                current = {"date": h.group(1), "title": h.group(2).strip()}
                continue
            if not current:
                continue
            f = _FIELD_RE.match(line)
            if f:
                key = f.group(1).lower()
                val = f.group(2).strip()
                current["tags" if key == "tags" else key] = (
                    _parse_tags(val) if key == "tags" else val
                )
        _flush()
    except Exception as exc:  # noqa: BLE001
        logger.warning("parse_lessons_md: %s", exc)

    return entries


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def _similar(a: str, b: str) -> bool:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.8


def _load_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data.get("lessons", []) or []
    except Exception:  # noqa: BLE001
        return []


def _find_existing(entry: LessonEntry, existing: list[dict]) -> Optional[dict]:
    for ex in existing:
        if _similar(entry.title, ex.get("title", "")) or _similar(
            entry.trigger, ex.get("trigger", "")
        ):
            return ex
    return None


def merge(entries: list[LessonEntry], existing: list[dict]) -> list[dict]:
    """Merge parsed entries with existing records, preserving enrichment fields."""
    result: list[dict] = []
    for entry in entries:
        ex = _find_existing(entry, existing)
        result.append(
            {
                "id": entry.id,
                "date": entry.date,
                "title": entry.title,
                "trigger": entry.trigger,
                "rule": entry.rule,
                "why": entry.why,
                "tags": entry.tags,
                "stage": ex["stage"] if ex and ex.get("stage") is not None else [],
                "project_types": (
                    ex["project_types"]
                    if ex and ex.get("project_types") is not None
                    else []
                ),
                "frequency": (
                    ex["frequency"] if ex and ex.get("frequency") is not None else 0
                ),
                "last_used": (
                    ex["last_used"] if ex and ex.get("last_used") is not None else None
                ),
            }
        )
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


def sync(
    lessons_md: Path,
    lessons_yaml: Path,
    *,
    dry_run: bool = False,
) -> list[dict]:
    """Parse lessons_md, merge with existing lessons_yaml, write result.

    Returns the list of merged records.
    """
    entries = parse_lessons_md(lessons_md)
    existing = _load_existing(lessons_yaml)
    records = merge(entries, existing)
    output = yaml.dump(
        {"schema_version": _SCHEMA_VERSION, "lessons": records},
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    if dry_run:
        print(output, end="")
    else:
        _write_atomic(lessons_yaml, output)
        logger.info("wrote %d lessons to %s", len(records), lessons_yaml)
    return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="project root")
    parser.add_argument(
        "--input", type=Path, help="lessons.md path (overrides --cwd discovery)"
    )
    parser.add_argument(
        "--output", type=Path, help="lessons.yaml path (overrides --cwd discovery)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print YAML to stdout, do not write"
    )
    args = parser.parse_args()

    lessons_md: Path = args.input or (args.cwd / "tasks" / "lessons.md")
    lessons_yaml: Path = args.output or (args.cwd / ".forge" / "lessons.yaml")

    if not lessons_md.exists():
        logger.warning("lessons.md not found: %s", lessons_md)
        sys.exit(0)

    sync(lessons_md, lessons_yaml, dry_run=args.dry_run)
    sys.exit(0)


if __name__ == "__main__":
    main()
