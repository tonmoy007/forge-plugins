#!/usr/bin/env python3
"""Shared ID-scanning primitives for validate-traceability.py and trace-matrix.py.

Everything in here is pure/read-only (never raises, never writes) so it can be
imported freely by a gap-analysis CLI and a matrix-generator CLI without either
duplicating the other's regex/heuristic definitions (both existed as literal
copy-paste before this extraction — see validate-traceability.py's original
inline definitions).

ID conventions: references/gate-criteria.md is canonical for REQ-\\d{3} /
NFR-\\d{3}; FEAT/UF/T/ADR have no fixed digit width documented anywhere, so
only case/separator are checked for those.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage_table as stage_table  # noqa: E402

_KNOWN_PREFIXES = ("REQ", "NFR", "FEAT", "UF", "T", "ADR")
_CANONICAL_WIDTH = {"REQ": 3, "NFR": 3}

_ID_TOKEN = re.compile(r"\b([A-Za-z]{1,6})([-_])(\d+[A-Za-z0-9]*)\b")
_HEADING_DEF = re.compile(r"^#{1,6}\s+.*?\b([A-Z]{1,6}-\d+[A-Za-z0-9]*)\b", re.MULTILINE)
_ANY_ID = re.compile(r"\b([A-Z]{1,6}-\d+[A-Za-z0-9]*)\b")

# Only REQ/NFR/FEAT/UF have a single canonical "home" doc where they're defined —
# T-ids are legitimately re-headed in progress.md/eval-report.md by design, so
# they're excluded from the misplaced check.
_MISPLACED_HOME = {
    "REQ": "pipeline/01-srs/srs.md",
    "NFR": "pipeline/01-srs/srs.md",
    "FEAT": "pipeline/02-product-ux/prd.md",
    "UF": "pipeline/02-product-ux/prd.md",
}

# prefix -> (home doc, [downstream docs where a definition must be referenced,
# in pipeline order]). The orphan check only runs once at least one downstream
# doc exists — too early in the pipeline to call anything "orphaned" otherwise.
_ORPHAN_CHECK = {
    "REQ": ("pipeline/01-srs/srs.md",
            ["pipeline/05-plan/task-dag.md", "pipeline/06-implementation/progress.md",
             "pipeline/07-evaluation/eval-report.md"]),
    "NFR": ("pipeline/01-srs/srs.md",
            ["pipeline/05-plan/task-dag.md", "pipeline/07-evaluation/eval-report.md"]),
    "FEAT": ("pipeline/02-product-ux/prd.md",
             ["pipeline/01-srs/srs.md", "pipeline/03-architecture/architecture.md"]),
    "UF": ("pipeline/02-product-ux/prd.md",
           ["pipeline/01-srs/srs.md", "pipeline/03-architecture/architecture.md"]),
}


@dataclass
class Issue:
    category: str
    token: str
    file: str
    detail: str


# ---------------------------------------------------------------------------
# Scans
# ---------------------------------------------------------------------------


# Generated reports live under pipeline/ (traceability-matrix.md alongside it,
# validate-traceability.py's optional --out) but must never be scanned as input —
# a gap table quoting a malformed id (e.g. "req-001") would otherwise be picked
# up as a fresh instance of that id on the next run, a self-referential feedback
# loop where the tool's own prior report pollutes its next scan.
_GENERATED_REPORT_NAMES = {"traceability-matrix.md", "validation-report.md"}


def pipeline_md_files(project_root: Path) -> list[Path]:
    pipeline = project_root / "pipeline"
    if not pipeline.exists():
        return []
    return sorted(
        p for p in pipeline.rglob("*.md") if p.name not in _GENERATED_REPORT_NAMES
    )


def scan_malformed(project_root: Path) -> list[Issue]:
    """Wrong case, wrong separator, or wrong digit-padding on a known ID prefix."""
    issues: list[Issue] = []
    for md in pipeline_md_files(project_root):
        text = md.read_text(encoding="utf-8", errors="replace")
        rel = str(md.relative_to(project_root))
        for m in _ID_TOKEN.finditer(text):
            prefix_raw, sep, digits_raw = m.groups()
            prefix_upper = prefix_raw.upper()
            if prefix_upper not in _KNOWN_PREFIXES:
                continue
            problems: list[str] = []
            if prefix_raw != prefix_upper:
                problems.append(f"prefix should be uppercase '{prefix_upper}'")
            if sep != "-":
                problems.append("separator should be '-'")
            digit_match = re.match(r"\d+", digits_raw)
            width = _CANONICAL_WIDTH.get(prefix_upper)
            if width and digit_match and len(digit_match.group(0)) != width:
                problems.append(f"expected {width}-digit id (e.g. {prefix_upper}-{'0' * width})")
            if problems:
                issues.append(Issue("malformed", m.group(0), rel, "; ".join(problems)))
    return issues


def find_definitions(project_root: Path) -> dict[str, list[str]]:
    """Heading-style occurrences per id — a `### REQ-001 ...` line is a definition;
    an inline mention in prose or a table is not."""
    defs: dict[str, list[str]] = {}
    for md in pipeline_md_files(project_root):
        text = md.read_text(encoding="utf-8", errors="replace")
        rel = str(md.relative_to(project_root))
        for m in _HEADING_DEF.finditer(text):
            token = m.group(1)
            prefix = token.split("-", 1)[0]
            if prefix not in _KNOWN_PREFIXES:
                continue
            defs.setdefault(token, []).append(rel)
    return defs


def scan_misplaced(defs: dict[str, list[str]]) -> list[Issue]:
    issues: list[Issue] = []
    for token, files in defs.items():
        prefix = token.split("-", 1)[0]
        home = _MISPLACED_HOME.get(prefix)
        if not home:
            continue
        for f in sorted(set(files)):
            if f != home:
                issues.append(Issue("misplaced", token, f, f"home doc is {home}"))
    return issues


def scan_duplicates(project_root: Path) -> list[Issue]:
    """The same id heading-defined more than once in the SAME file — a copy/paste
    bug. Cross-file recurrence (task-dag.md and progress.md both heading T-001) is
    expected traceability, not a duplicate, so this only looks within one file."""
    issues: list[Issue] = []
    for md in pipeline_md_files(project_root):
        text = md.read_text(encoding="utf-8", errors="replace")
        rel = str(md.relative_to(project_root))
        seen: dict[str, int] = {}
        for m in _HEADING_DEF.finditer(text):
            token = m.group(1)
            prefix = token.split("-", 1)[0]
            if prefix not in _KNOWN_PREFIXES:
                continue
            seen[token] = seen.get(token, 0) + 1
        for token, count in seen.items():
            if count > 1:
                issues.append(Issue("duplicate", token, rel, f"defined {count} times in the same file"))
    return issues


def scan_unimplemented(project_root: Path) -> list[Issue]:
    """A REQ/NFR/FEAT/UF defined in its home doc but never mentioned again in any
    of the docs that are supposed to carry it forward."""
    issues: list[Issue] = []
    for prefix, (home_rel, downstream_rels) in _ORPHAN_CHECK.items():
        home = project_root / home_rel
        if not home.exists():
            continue
        existing_downstream = [project_root / d for d in downstream_rels if (project_root / d).exists()]
        if not existing_downstream:
            continue
        home_text = home.read_text(encoding="utf-8", errors="replace")
        defined_ids = sorted({
            m.group(1) for m in _ANY_ID.finditer(home_text)
            if m.group(1).startswith(prefix + "-")
        })
        downstream_text = "\n".join(
            d.read_text(encoding="utf-8", errors="replace") for d in existing_downstream
        )
        for tid in defined_ids:
            if tid not in downstream_text:
                issues.append(Issue(
                    "unimplemented", tid, home_rel,
                    f"never referenced in {', '.join(downstream_rels)}",
                ))
    return issues


def scan_all(project_root: Path) -> list[Issue]:
    """Run every check and return the combined issue list."""
    issues: list[Issue] = []
    issues += scan_malformed(project_root)
    defs = find_definitions(project_root)
    issues += scan_misplaced(defs)
    issues += scan_duplicates(project_root)
    issues += scan_unimplemented(project_root)
    return issues


# ---------------------------------------------------------------------------
# Matrix cells (id x stage-dir -> 'define' | 'reference')
# ---------------------------------------------------------------------------


def find_matrix_cells(project_root: Path) -> dict[str, dict[str, str]]:
    """id -> {stage_dir: 'define'|'reference'} across every pipeline doc.

    A stage_dir is 'define' if any file under pipeline/<stage_dir>/ heading-
    defines the id (define always wins over a mere reference in that same
    directory); otherwise it's 'reference' if the id appears there at all.
    """
    cells: dict[str, dict[str, str]] = {}
    for md in pipeline_md_files(project_root):
        text = md.read_text(encoding="utf-8", errors="replace")
        rel = str(md.relative_to(project_root))
        parts = Path(rel).parts
        if len(parts) < 2:
            continue
        stage_dir = parts[1]
        for m in _ANY_ID.finditer(text):
            token = m.group(1)
            prefix = token.split("-", 1)[0]
            if prefix not in _KNOWN_PREFIXES:
                continue
            cells.setdefault(token, {}).setdefault(stage_dir, "reference")

    for token, files in find_definitions(project_root).items():
        for f in files:
            parts = Path(f).parts
            if len(parts) >= 2:
                cells.setdefault(token, {})[parts[1]] = "define"
    return cells


# ---------------------------------------------------------------------------
# Responsible-agent attribution (references/stage-order.md via _stage_table)
# ---------------------------------------------------------------------------


def stage_for_path(rel_path: str, plugin_root: Optional[Path] = None) -> Optional[dict]:
    """Given a pipeline-relative path like 'pipeline/01-srs/srs.md', return that
    stage's entry from stage-order.md (stage/dir/agent/...), or None if the path
    doesn't map to a known stage directory."""
    parts = Path(rel_path).parts
    if len(parts) < 2 or parts[0] != "pipeline":
        return None
    stage_dir = parts[1]
    for s in stage_table.stages(plugin_root):
        if s["dir"] == stage_dir:
            return s
    return None


def attribute(
    issue: Issue, project_root: Path, plugin_root: Optional[Path] = None
) -> tuple[Optional[int], Optional[str]]:
    """Return (stage, agent) responsible for resolving this issue.

    - malformed / misplaced / duplicate: the stage that owns the doc the
      problem was actually found in — whoever wrote that file should fix it.
    - unimplemented: the EARLIEST existing downstream doc's stage — the
      requirements analyst who defined the id isn't who forgot to carry it
      forward; the first downstream stage that had the chance to reference it
      and didn't is the accountable one.
    """
    if issue.category == "unimplemented":
        prefix = issue.token.split("-", 1)[0]
        entry = _ORPHAN_CHECK.get(prefix)
        if entry:
            _, downstream_rels = entry
            for rel in downstream_rels:
                if (project_root / rel).exists():
                    stage_entry = stage_for_path(rel, plugin_root)
                    if stage_entry:
                        return stage_entry["stage"], stage_entry["agent"]

    stage_entry = stage_for_path(issue.file, plugin_root)
    if stage_entry:
        return stage_entry["stage"], stage_entry["agent"]
    return None, None
