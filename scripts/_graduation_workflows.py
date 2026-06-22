#!/usr/bin/env python3
"""Workflows graduation tier over the shared ``~/.forge`` core (T-209, REQ-GR-004).

A project's declarative ``.forge/workflows/<name>.yaml`` flows that **validate
clean** and have proven themselves (``>= _MIN_WORKFLOW_RUNS`` successful runs in
``.forge/events.jsonl``) are promoted to a durable global store and recalled
into other projects via the loader search path:

- **collect** — for every ``.forge/workflows/*.yaml``, mark ``valid`` via
  ``workflow_loader.load_workflow_file(path).ok`` and count its **successful**
  ``workflow_run`` records in ``.forge/events.jsonl``. A run is successful when
  it names the workflow, completed ≥1 node, and carries no failing verify verdict.
- **gate** — ``valid AND runs >= _MIN_WORKFLOW_RUNS`` (default 2). Unlike skills,
  workflows are reusable declarative artifacts, so a run-count gate is apt.
- **promote** — copy ``<project>/.forge/workflows/<name>.yaml`` →
  ``~/.forge/workflows/<name>.yaml`` and upsert ``~/.forge/global-workflows.yaml``
  (``name``, source ``projects``, ``runs``, ``last_used``) via the core's
  idempotent ``merge_by_key``. The same flow run across N projects MERGES: union
  ``projects``, SUM ``runs``, latest ``last_used``.
- **recall** — a NO-OP: workflow recall is the loader search path
  (``workflow_loader.resolve_workflows``), not a per-project filesystem action.

stdlib + PyYAML only; atomic writes; ``~/.forge``/``.forge``-only (REQ-NF-034/035).
"""

from __future__ import annotations

import datetime
import json
import logging
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

# Sibling import idiom — share the core + the workflow loader across scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import workflow_loader  # noqa: E402  (load_workflow_file — validity probe; reused, not reimplemented)
from _graduation import is_stale, merge_by_key, write_atomic  # noqa: E402

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1
# A workflow must have this many successful runs before it graduates (tunable).
_MIN_WORKFLOW_RUNS = 2
# Stable key order for index records → deterministic, byte-idempotent YAML.
_INDEX_KEYS = ("name", "projects", "runs", "last_used")


@dataclass
class WorkflowRecord:
    """One project's contribution of a validated, run-proven workflow."""

    name: str
    path: str
    runs: int
    last_used: Optional[str]
    project: str
    valid: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _max_date(a: Optional[str], b: Optional[str]) -> Optional[str]:
    """Lexicographically-latest ISO timestamp (ISO sorts chronologically)."""
    candidates = [d for d in (a, b) if d]
    return max(candidates) if candidates else None


def _ordered(record: dict) -> dict:
    """Project a record onto the stable index key order for deterministic dumps."""
    return {k: record.get(k) for k in _INDEX_KEYS}


def _is_successful_run(rec: dict, name: str) -> bool:
    """A ``workflow_run`` for ``name`` that completed ≥1 node with no failing verdict."""
    if not isinstance(rec, dict):
        return False
    if rec.get("event") != "workflow_run" or rec.get("name") != name:
        return False
    completed = rec.get("completed")
    if not isinstance(completed, list) or not completed:
        return False  # no node completed → not a success
    verdicts = rec.get("verdicts")
    if isinstance(verdicts, dict) and any(v == "fail" for v in verdicts.values()):
        return False  # any failing verify verdict disqualifies the run
    return True


def _scan_runs(events_path: Path, name: str) -> tuple[int, Optional[str]]:
    """Count successful runs of ``name`` in ``events.jsonl`` + their latest ``ts``.

    Per-line fail-soft: a malformed/unparseable line is skipped; a totally
    unreadable file degrades to ``(0, None)``. Never raises (REQ-NF-034)."""
    try:
        text = events_path.read_text(encoding="utf-8")
    except OSError:
        return 0, None
    runs = 0
    last_used: Optional[str] = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except (ValueError, TypeError):
            continue  # malformed line → skipped, good lines still counted
        if _is_successful_run(rec, name):
            runs += 1
            ts = rec.get("ts")
            if isinstance(ts, str):
                last_used = _max_date(last_used, ts)
    return runs, last_used


def _load_index(global_dir: Path) -> list[dict]:
    """Read ``global-workflows.yaml`` → list of index records (fail-soft → [])."""
    path = Path(global_dir) / "global-workflows.yaml"
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return [r for r in (data.get("workflows") or []) if isinstance(r, dict)]
    except Exception:  # noqa: BLE001 — never raise from a guarded read
        return []


def _merge_workflow(old: dict, new: dict) -> dict:
    """Reconcile an existing index record with a fresh full-rescan record.

    ``new`` is a complete recomputation over *all currently-registered* projects
    (the driver re-collects every project each scan), so its ``runs`` /
    ``last_used`` are authoritative — re-scanning must be byte-idempotent (NF-037)
    and not double-count. We keep ``new``'s totals and only UNION ``projects`` so
    a project still recorded globally but absent from the live registry is not
    silently dropped from the provenance list."""
    return _ordered({
        "name": new.get("name") or old.get("name"),
        "projects": sorted(set(old.get("projects") or []) | set(new.get("projects") or [])),
        "runs": int(new.get("runs") or 0),
        "last_used": _max_date(old.get("last_used"), new.get("last_used")),
    })


def _aggregate_promotable(promotable: list[WorkflowRecord]) -> list[dict]:
    """Fold per-project promotable records into one index record per workflow name.

    Several promotable records sharing a name (same flow across projects) MERGE:
    union ``projects``, SUM ``runs``, take the latest ``last_used``."""
    by_name: dict[str, dict] = {}
    for r in promotable:
        rec = by_name.get(r.name)
        if rec is None:
            by_name[r.name] = {
                "name": r.name,
                "projects": [str(Path(r.project).resolve())],
                "runs": int(r.runs),
                "last_used": r.last_used,
            }
        else:
            rec["projects"] = sorted(
                set(rec["projects"]) | {str(Path(r.project).resolve())}
            )
            rec["runs"] += int(r.runs)
            rec["last_used"] = _max_date(rec["last_used"], r.last_used)
    records = [_ordered({**v, "projects": sorted(set(v["projects"]))}) for v in by_name.values()]
    records.sort(key=lambda x: x["name"] or "")
    return records


def _copy_file_if_absent(src: Path, dst: Path) -> None:
    """Copy ``src`` → ``dst`` only if ``dst`` is absent (idempotent, never raises)."""
    if dst.exists():
        return
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except Exception as exc:  # noqa: BLE001 — a copy failure degrades that flow only
        logger.warning("workflows: copy %s → %s failed: %s", src, dst, exc)


# ---------------------------------------------------------------------------
# The tier
# ---------------------------------------------------------------------------


class WorkflowTier:
    """Workflows graduation tier over ``_graduation`` (the ``Tier`` protocol)."""

    name = "workflows"

    def __init__(
        self,
        *,
        min_runs: int = _MIN_WORKFLOW_RUNS,
        today: Optional[datetime.date] = None,
    ) -> None:
        self.min_runs = min_runs
        self.today = today  # injectable for deterministic TTL tests

    # -- collect ----------------------------------------------------------

    def collect(self, project_path: str) -> list[WorkflowRecord]:
        forge_dir = Path(project_path) / ".forge"
        workflows_dir = forge_dir / "workflows"
        events_path = forge_dir / "events.jsonl"
        out: list[WorkflowRecord] = []
        for wf_path in workflow_loader.list_workflows(workflows_dir):
            try:
                valid = bool(workflow_loader.load_workflow_file(wf_path).ok)
            except Exception:  # noqa: BLE001 — loader is fail-soft, but guard anyway
                valid = False
            name = wf_path.stem
            runs, last_used = _scan_runs(events_path, name)
            out.append(
                WorkflowRecord(
                    name=name,
                    path=str(wf_path),
                    runs=runs,
                    last_used=last_used,
                    project=str(project_path),
                    valid=valid,
                )
            )
        return out

    # -- gate -------------------------------------------------------------

    def gate(self, records: list[WorkflowRecord]) -> list[WorkflowRecord]:
        return [r for r in records if r.valid and r.runs >= self.min_runs]

    # -- key --------------------------------------------------------------

    def key(self, record) -> str:
        if isinstance(record, WorkflowRecord):
            return record.name
        return record.get("name", "")

    # -- promote ----------------------------------------------------------

    def promote(
        self, promotable: list[WorkflowRecord], global_dir: Path, *, dry_run: bool = False
    ) -> list[dict]:
        new_records = _aggregate_promotable(promotable)
        if dry_run or not new_records:
            return new_records

        workflows_root = Path(global_dir) / "workflows"
        for r in promotable:
            _copy_file_if_absent(Path(r.path), workflows_root / f"{r.name}.yaml")

        existing = _load_index(Path(global_dir))
        merged = merge_by_key(
            new_records, existing, lambda x: x.get("name", ""), merge_fn=_merge_workflow
        )
        merged = [_ordered(r) for r in merged]
        merged.sort(key=lambda x: x.get("name") or "")
        write_atomic(
            Path(global_dir) / "global-workflows.yaml",
            yaml.dump(
                {"schema_version": _SCHEMA_VERSION, "workflows": merged},
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            ),
        )
        return new_records

    # -- recall -----------------------------------------------------------

    def recall(self, global_dir: Path, project_path: str) -> None:
        """No-op: workflow recall is the loader search path, not an fs action.

        ``workflow_loader.resolve_workflows`` overlays the global store at load
        time (project-wins on name, TTL-filtered via ``fresh_global_names``), so
        there is nothing to materialise per-project here. Returns None, never raises."""
        return None

    # -- TTL surface for the loader ---------------------------------------

    def fresh_global_names(self, global_dir: Path) -> set[str]:
        """Names in ``global-workflows.yaml`` that are NOT TTL-stale (fail-soft → set())."""
        fresh: set[str] = set()
        for rec in _load_index(Path(global_dir)):
            name = rec.get("name")
            if not name:
                continue
            if is_stale(rec.get("last_used"), today=self.today):
                continue  # TTL-stale globals are not surfaced (NF-035)
            fresh.add(name)
        return fresh
