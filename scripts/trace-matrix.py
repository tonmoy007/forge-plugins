#!/usr/bin/env python3
"""Generate a full traceability matrix (id x stage) and gap notices.

Builds on _trace_scan.py's shared scanning primitives:
  - a markdown matrix: every known id (REQ/NFR/FEAT/UF/T/ADR) as a row, every
    stage directory that has at least one cell as a column, marked "define" (id
    is heading-defined there) or "reference" (id merely appears there);
  - the same four gap categories validate-traceability.py reports (malformed,
    misplaced, duplicate, unimplemented), each attributed to the responsible
    stage/agent via _trace_scan.attribute();
  - .forge/traceability-gaps.jsonl — a fresh snapshot of open gaps (overwritten
    each run, not appended) that hooks/session-start.py reads to surface an
    advisory note to the responsible agent the next time their stage is active.

Runs with --cwd = project root. Exit 0 if no gaps were found; 1 otherwise —
same convention as validate-traceability.py, though this is primarily a report
generator, not a gate.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage_table as stage_table  # noqa: E402
from _trace_scan import Issue, attribute, find_matrix_cells, scan_all  # noqa: E402


def _stage_label(stage_dir: str, plugin_root: Path) -> str:
    for s in stage_table.stages(plugin_root):
        if s["dir"] == stage_dir:
            return f"S{s['stage']}"
    return stage_dir


def build_matrix_table(cells: dict[str, dict[str, str]], plugin_root: Path) -> str:
    """Markdown table: rows = ids, columns = every stage dir with any cell data."""
    if not cells:
        return "_No ids found in `pipeline/` yet._"

    def _stage_num(stage_dir: str) -> int:
        return next(
            (s["stage"] for s in stage_table.stages(plugin_root) if s["dir"] == stage_dir), 99
        )

    all_dirs = sorted({d for row in cells.values() for d in row}, key=_stage_num)
    header = "| ID | " + " | ".join(_stage_label(d, plugin_root) for d in all_dirs) + " |"
    sep = "|---|" + "---|" * len(all_dirs)
    rows = [header, sep]
    for token in sorted(cells):
        marks = []
        for d in all_dirs:
            cell = cells[token].get(d)
            marks.append("◆" if cell == "define" else ("●" if cell == "reference" else ""))
        rows.append(f"| `{token}` | " + " | ".join(marks) + " |")
    return "\n".join(rows) + "\n\n◆ = defined here · ● = referenced here"


def build_gap_rows(issues: list[Issue], project_root: Path, plugin_root: Path) -> list[dict]:
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for i in issues:
        stage, agent = attribute(i, project_root, plugin_root)
        rows.append({
            "id": i.token,
            "category": i.category,
            "file": i.file,
            "detail": i.detail,
            "stage": stage,
            "agent": agent,
            "generated_at": now,
        })
    return rows


def format_report(matrix_table: str, gap_rows: list[dict]) -> str:
    lines = ["# Traceability Matrix", "", matrix_table, "", "## Gaps & Responsible Agents", ""]
    if not gap_rows:
        lines.append("None found.")
    else:
        lines.append("| ID | Category | File | Stage | Agent | Detail |")
        lines.append("|---|---|---|---|---|---|")
        for g in gap_rows:
            stage = g["stage"] if g["stage"] is not None else "?"
            agent = g["agent"] or "unassigned"
            lines.append(
                f"| `{g['id']}` | {g['category']} | `{g['file']}` | {stage} | {agent} | {g['detail']} |"
            )
    lines.append("")
    lines.append(f"Total gaps: {len(gap_rows)}")
    return "\n".join(lines)


def write_gaps_jsonl(path: Path, gap_rows: list[dict]) -> None:
    """Overwrite with a fresh snapshot — this is point-in-time state, not a log."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(g) for g in gap_rows)
    path.write_text(content + ("\n" if gap_rows else ""), encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="trace-matrix.py")
    parser.add_argument("--cwd", type=Path, default=Path("."))
    parser.add_argument("--plugin-dir", type=Path, default=None)
    parser.add_argument(
        "--out", type=Path, default=None,
        help="default: <cwd>/pipeline/traceability-matrix.md",
    )
    parser.add_argument(
        "--gaps-out", type=Path, default=None,
        help="default: <cwd>/.forge/traceability-gaps.jsonl",
    )
    parser.add_argument("--no-write", action="store_true", help="print only, write nothing")
    args = parser.parse_args(argv)

    project_root = args.cwd.resolve()
    plugin_dir = (args.plugin_dir or Path(__file__).parent.parent).resolve()

    cells = find_matrix_cells(project_root)
    issues = scan_all(project_root)
    gap_rows = build_gap_rows(issues, project_root, plugin_dir)
    matrix_table = build_matrix_table(cells, plugin_dir)
    report = format_report(matrix_table, gap_rows)

    print(report)

    if not args.no_write:
        out = args.out or (project_root / "pipeline" / "traceability-matrix.md")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report + "\n", encoding="utf-8")

        gaps_out = args.gaps_out or (project_root / ".forge" / "traceability-gaps.jsonl")
        write_gaps_jsonl(gaps_out, gap_rows)

    return 0 if not gap_rows else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
