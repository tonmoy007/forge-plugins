#!/usr/bin/env python3
"""Loader for the canonical pipeline stage table (references/stage-order.md).

Single source of truth for stage order, canonical directory names, prerequisites,
and next-step hints. Stage skills, next-step hints (REQ-NEXTHINT-001), pre-flight
entry checks (REQ-GATE-ENTRY-001), the path-collision fix (REQ-PATHS-001), and
stage-bound enforcement (REQ-PIPEBOUNDS-001) all read from here instead of
hardcoding stage facts.

stdlib + PyYAML only (PyYAML is already a documented runtime dep; see _state_lib).
The stage-order.md file ships with the plugin, so it is located relative to this
script, not the user's project cwd.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

STAGE_TABLE_RELPATH = "references/stage-order.md"

# Match the established YAML-in-markdown convention used by gate-criteria.md
# (parsed identically in scripts/why.py and scripts/check-gate.py).
_YAML_BLOCK = re.compile(r"```yaml\n(.*?)```", re.DOTALL)


def _default_plugin_root() -> Path:
    """Plugin root = parent of the scripts/ directory this file lives in."""
    return Path(__file__).resolve().parent.parent


def _table_path(plugin_root: Optional[Path] = None) -> Path:
    return (plugin_root or _default_plugin_root()) / STAGE_TABLE_RELPATH


@lru_cache(maxsize=4)
def _load_raw(table_path_str: str) -> dict[str, Any]:
    """Parse the first ```yaml block of stage-order.md into a dict (cached)."""
    text = Path(table_path_str).read_text()
    match = _YAML_BLOCK.search(text)
    if not match:
        raise ValueError(f"no ```yaml block found in {table_path_str}")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict) or "stages" not in data:
        raise ValueError(f"{table_path_str} is missing a top-level 'stages' list")
    return data


def load_table(plugin_root: Optional[Path] = None) -> dict[str, Any]:
    """Return the parsed stage table: {'bounds':..., 'stages': [...], 'cycles':...}."""
    return _load_raw(str(_table_path(plugin_root)))


def stages(plugin_root: Optional[Path] = None) -> list[dict[str, Any]]:
    """Return the stage entries ordered by stage number."""
    return sorted(load_table(plugin_root)["stages"], key=lambda s: s["stage"])


def stage(n: int, plugin_root: Optional[Path] = None) -> Optional[dict[str, Any]]:
    """Return the entry for stage `n`, or None if `n` is not a defined stage."""
    return next((s for s in load_table(plugin_root)["stages"] if s["stage"] == n), None)


def _field(n: int, key: str, plugin_root: Optional[Path] = None) -> Any:
    entry = stage(n, plugin_root)
    return entry.get(key) if entry else None


def canonical_dir(n: int, plugin_root: Optional[Path] = None) -> Optional[str]:
    """Canonical `pipeline/` subdirectory for stage `n` (e.g. '04-spec')."""
    return _field(n, "dir", plugin_root)


def primary_artifact(n: int, plugin_root: Optional[Path] = None) -> Optional[str]:
    """The canonical handoff file stage `n` produces for the next stage."""
    return _field(n, "primary_artifact", plugin_root)


def prerequisite(n: int, plugin_root: Optional[Path] = None) -> Optional[str]:
    """File that must exist before stage `n` may run (None for stage 1)."""
    return _field(n, "prerequisite", plugin_root)


def prerequisite_skill(n: int, plugin_root: Optional[Path] = None) -> Optional[str]:
    """The /forge:* skill that produces stage `n`'s prerequisite (None for stage 1)."""
    return _field(n, "prerequisite_skill", plugin_root)


def next_stage(n: int, plugin_root: Optional[Path] = None) -> Optional[int]:
    """The stage number after `n` (None after the final stage)."""
    return _field(n, "next_stage", plugin_root)


def next_skill(n: int, plugin_root: Optional[Path] = None) -> Optional[str]:
    """The /forge:* skill to run after stage `n`."""
    return _field(n, "next_skill", plugin_root)


def next_hint(n: int, plugin_root: Optional[Path] = None) -> Optional[str]:
    """The exact user-facing next-step hint string for after stage `n`."""
    return _field(n, "next_hint", plugin_root)


def bounds(plugin_root: Optional[Path] = None) -> dict[str, Any]:
    """The {'min_stage', 'max_stage', 'on_overflow'} bounds block."""
    return load_table(plugin_root).get("bounds", {})


def min_stage(plugin_root: Optional[Path] = None) -> int:
    return bounds(plugin_root).get("min_stage", 0)


def max_stage(plugin_root: Optional[Path] = None) -> int:
    return bounds(plugin_root).get("max_stage", 12)


def cycles(plugin_root: Optional[Path] = None) -> dict[str, Any]:
    """Cycle-type definitions: {'full': {'entry':1,'exit':12}, ...}."""
    return load_table(plugin_root).get("cycles", {})


def validate(plugin_root: Optional[Path] = None) -> list[str]:
    """Return a list of consistency errors in the table (empty = valid).

    Checks: stages 1..max contiguous and unique, no duplicate directory names,
    next_stage chain consistent, and prerequisite(N) == primary_artifact(N-1).
    """
    errors: list[str] = []
    table = load_table(plugin_root)
    entries = sorted(table["stages"], key=lambda s: s["stage"])
    nums = [s["stage"] for s in entries]
    top = max_stage(plugin_root)

    expected = list(range(1, top + 1))
    if nums != expected:
        errors.append(f"stage numbers {nums} are not contiguous 1..{top}")

    dirs = [s["dir"] for s in entries]
    dupes = sorted({d for d in dirs if dirs.count(d) > 1})
    if dupes:
        errors.append(f"duplicate directory names: {dupes}")

    by_num = {s["stage"]: s for s in entries}
    for s in entries:
        n = s["stage"]
        expected_next = n + 1 if n < top else None
        if s.get("next_stage") != expected_next:
            errors.append(
                f"stage {n}: next_stage is {s.get('next_stage')!r}, expected {expected_next!r}"
            )
        prev = by_num.get(n - 1)
        if prev is None:
            if s.get("prerequisite") is not None:
                errors.append(f"stage {n}: prerequisite should be null (no prior stage)")
        elif s.get("prerequisite") != prev.get("primary_artifact"):
            errors.append(
                f"stage {n}: prerequisite {s.get('prerequisite')!r} != "
                f"stage {n-1} primary_artifact {prev.get('primary_artifact')!r}"
            )
    return errors
