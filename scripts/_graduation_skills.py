#!/usr/bin/env python3
"""Skills graduation tier over the shared ``~/.forge`` core (T-208, REQ-GR-003).

A project's deliberately-mined, human-**approved** skills are promoted to a
durable, quality-curated global store and recalled into other projects:

- **collect** — fold the project's ExpeL ledger (``.forge/skill-stats.jsonl``,
  reusing ``skill_curate.aggregate_stats`` — the ADD/UPVOTE/DOWNVOTE/EDIT fold,
  not reimplemented) and, for every slug that is also **approved** (installed at
  ``<plugin>/skills/<slug>/`` by ``skill-approval.py approve``), emit a record.
- **gate** — approved **AND** ExpeL ``weight > 0`` **AND** ``use >= _MIN_SKILL_USES``
  (default 2). A breadth gate is wrong for skills: they are single deliberate
  artifacts, rarely recurring independently across projects (ADR-008).
- **promote** — copy ``<plugin>/skills/<slug>/`` → ``~/.forge/skills/<slug>/`` and
  upsert ``~/.forge/global-skills.yaml`` (``slug``, source ``projects``, ``weight``,
  ``use``, ``last_used``) via the core's idempotent ``merge_by_key``.
- **recall** — **symlink** ``~/.forge/skills/<slug>`` into the plugin ``skills/``
  path, **only** when no same-slug skill already exists there (project/plugin-wins)
  and never clobbering a real entry; TTL-stale globals are skipped; a platform that
  cannot symlink degrades to a guarded copy (ADR-009). Never raises.

stdlib + PyYAML only; atomic writes; ``~/.forge``/``.forge``-only (REQ-NF-034/035).
"""

from __future__ import annotations

import datetime
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

# Sibling import idiom — share the core + the ExpeL fold across scripts/.
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_curate  # noqa: E402  (aggregate_stats — the ExpeL fold; reused, not reimplemented)
from _graduation import is_stale, merge_by_key, write_atomic  # noqa: E402

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1
# A skill must have been reused at least this many times before it graduates.
_MIN_SKILL_USES = 2
# Stable key order for index records → deterministic, byte-idempotent YAML.
_INDEX_KEYS = ("slug", "projects", "weight", "use", "last_used")


@dataclass
class SkillRecord:
    """One project's contribution of an approved, ExpeL-scored skill."""

    slug: str
    weight: int
    use: int
    last_used: Optional[str]
    project: str
    skill_dir: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dir_mtime_date(path: Path) -> Optional[str]:
    """ISO date of ``path``'s mtime — the skill's recency signal. None on error."""
    try:
        return datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()
    except Exception:  # noqa: BLE001 — never raise from a guarded stat
        return None


def _max_date(a: Optional[str], b: Optional[str]) -> Optional[str]:
    """Lexicographically-latest ISO date string (ISO sorts chronologically)."""
    candidates = [d for d in (a, b) if d]
    return max(candidates) if candidates else None


def _ordered(record: dict) -> dict:
    """Project a record onto the stable index key order for deterministic dumps."""
    return {k: record.get(k) for k in _INDEX_KEYS}


def _merge_skill(old: dict, new: dict) -> dict:
    """Accumulate two index records for the same slug (used by merge_by_key)."""
    return _ordered({
        "slug": new.get("slug") or old.get("slug"),
        "projects": sorted(set(old.get("projects") or []) | set(new.get("projects") or [])),
        "weight": max(int(old.get("weight") or 0), int(new.get("weight") or 0)),
        "use": max(int(old.get("use") or 0), int(new.get("use") or 0)),
        "last_used": _max_date(old.get("last_used"), new.get("last_used")),
    })


def _load_index(global_dir: Path) -> list[dict]:
    """Read ``global-skills.yaml`` → list of index records (fail-soft → [])."""
    path = global_dir / "global-skills.yaml"
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return [r for r in (data.get("skills") or []) if isinstance(r, dict)]
    except Exception:  # noqa: BLE001
        return []


def _aggregate_promotable(promotable: list[SkillRecord]) -> list[dict]:
    """Fold per-project promotable records into one index record per slug."""
    by_slug: dict[str, dict] = {}
    for r in promotable:
        rec = by_slug.get(r.slug)
        if rec is None:
            by_slug[r.slug] = {
                "slug": r.slug,
                "projects": [r.project],
                "weight": r.weight,
                "use": r.use,
                "last_used": r.last_used,
            }
        else:
            rec["projects"] = sorted(set(rec["projects"]) | {r.project})
            rec["weight"] = max(rec["weight"], r.weight)
            rec["use"] = max(rec["use"], r.use)
            rec["last_used"] = _max_date(rec["last_used"], r.last_used)
    records = [_ordered({**v, "projects": sorted(set(v["projects"]))}) for v in by_slug.values()]
    records.sort(key=lambda x: x["slug"])
    return records


def _copy_tree_if_absent(src: Path, dst: Path) -> None:
    """Copy ``src`` → ``dst`` only if ``dst`` is absent (idempotent, never raises)."""
    if dst.exists():
        return
    try:
        shutil.copytree(src, dst)
    except Exception as exc:  # noqa: BLE001 — a copy failure degrades that skill only
        logger.warning("skills: copy %s → %s failed: %s", src, dst, exc)


# ---------------------------------------------------------------------------
# The tier
# ---------------------------------------------------------------------------


class SkillTier:
    """Skills graduation tier over ``_graduation`` (the ``Tier`` protocol)."""

    name = "skills"

    def __init__(
        self,
        plugin_skills_dir,
        *,
        min_uses: int = _MIN_SKILL_USES,
        today: Optional[datetime.date] = None,
    ) -> None:
        # The machine-wide plugin ``skills/`` path: where approved skills install
        # to and where graduated skills are recalled (symlinked) into.
        self.plugin_skills_dir = Path(plugin_skills_dir)
        self.min_uses = min_uses
        self.today = today  # injectable for deterministic TTL tests

    # -- collect ----------------------------------------------------------

    def _is_approved(self, slug: str) -> bool:
        """Approved == installed at ``<plugin>/skills/<slug>/`` (skill-approval path)."""
        try:
            return (self.plugin_skills_dir / slug).is_dir()
        except OSError:
            return False

    def collect(self, project_path: str) -> list[SkillRecord]:
        forge_dir = Path(project_path) / ".forge"
        try:
            stats = skill_curate.aggregate_stats(forge_dir)
        except Exception as exc:  # noqa: BLE001 — fold must never crash the driver
            logger.warning("skills: stats fold failed for %s: %s", project_path, exc)
            return []
        out: list[SkillRecord] = []
        for slug, st in stats.items():
            if not self._is_approved(slug):
                continue  # proposed-but-not-approved (or absent) → not a candidate
            skill_dir = self.plugin_skills_dir / slug
            out.append(
                SkillRecord(
                    slug=slug,
                    weight=int(getattr(st, "weight", 0) or 0),
                    use=int(getattr(st, "uses", 0) or 0),
                    last_used=_dir_mtime_date(skill_dir),
                    project=str(project_path),
                    skill_dir=str(skill_dir),
                )
            )
        return out

    # -- gate -------------------------------------------------------------

    def gate(self, records: list[SkillRecord]) -> list[SkillRecord]:
        return [
            r
            for r in records
            if r.weight > 0 and r.use >= self.min_uses and self._is_approved(r.slug)
        ]

    # -- key --------------------------------------------------------------

    def key(self, record) -> str:
        if isinstance(record, SkillRecord):
            return record.slug
        return record.get("slug", "")

    # -- promote ----------------------------------------------------------

    def promote(
        self, promotable: list[SkillRecord], global_dir: Path, *, dry_run: bool = False
    ) -> list[dict]:
        new_records = _aggregate_promotable(promotable)
        if dry_run or not new_records:
            return new_records

        skills_root = Path(global_dir) / "skills"
        for r in promotable:
            _copy_tree_if_absent(Path(r.skill_dir), skills_root / r.slug)

        existing = _load_index(Path(global_dir))
        merged = merge_by_key(
            new_records, existing, lambda x: x.get("slug", ""), merge_fn=_merge_skill
        )
        merged = [_ordered(r) for r in merged]
        merged.sort(key=lambda x: x.get("slug") or "")
        write_atomic(
            Path(global_dir) / "global-skills.yaml",
            yaml.dump(
                {"schema_version": _SCHEMA_VERSION, "skills": merged},
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            ),
        )
        return new_records

    # -- recall -----------------------------------------------------------

    def recall(self, global_dir: Path, project_path: str) -> None:
        """Symlink fresh global skills into the plugin path (project/plugin-wins)."""
        skills_root = Path(global_dir) / "skills"
        for rec in _load_index(Path(global_dir)):
            slug = rec.get("slug")
            if not slug:
                continue
            if is_stale(rec.get("last_used"), today=self.today):
                continue  # TTL-stale globals are not surfaced (NF-035)
            src = skills_root / slug
            if not src.exists():
                continue
            dest = self.plugin_skills_dir / slug
            # project/plugin-wins + idempotent: never clobber a real entry and
            # leave an already-recalled symlink in place.
            if dest.is_symlink() or dest.exists():
                continue
            try:
                self.plugin_skills_dir.mkdir(parents=True, exist_ok=True)
                os.symlink(src, dest, target_is_directory=True)
            except (OSError, NotImplementedError, ValueError):
                # ADR-009 fallback: a platform that cannot symlink gets a copy.
                try:
                    shutil.copytree(src, dest)
                except Exception as exc:  # noqa: BLE001 — recall never raises
                    logger.warning("skills: recall %s failed: %s", slug, exc)
