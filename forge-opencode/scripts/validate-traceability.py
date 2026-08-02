#!/usr/bin/env python3
"""Pipeline gap analysis and traceability confirmation.

Runs four checks over pipeline/**/*.md that the existing gate scripts don't cover
(see _trace_scan.py): malformed IDs, misplaced ID definitions, duplicate ID
definitions, and unimplemented/orphaned requirements — then rolls up the existing
traceability/gate scripts (traceability-check.py --full-chain,
check_dag_completeness.py, check_dag_completion.py, check_srs_acceptance.py,
spec-coverage.py, check_nfr_coverage.py, check_progress_sync.py, check_todos.py)
into one combined gap-analysis report, so traceability is confirmed end-to-end in
a single pass.

Runs with --cwd = project root. Exit 0 if the report has zero issues; 1 otherwise.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _trace_scan import (  # noqa: E402
    Issue,
    scan_all,
    scan_malformed,
    find_definitions,
    scan_misplaced,
    scan_duplicates,
    scan_unimplemented,
)


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str = ""


# ---------------------------------------------------------------------------
# Rollup of existing gate/traceability scripts
# ---------------------------------------------------------------------------

_GATE_SCRIPTS: list[tuple[str, list[str]]] = [
    ("traceability chain (traceability-check.py --full-chain)",
     ["traceability-check.py", "--full-chain"]),
    ("task DAG completeness (check_dag_completeness.py)", ["check_dag_completeness.py"]),
    ("task DAG completion (check_dag_completion.py)", ["check_dag_completion.py"]),
    ("SRS acceptance criteria (check_srs_acceptance.py)",
     ["check_srs_acceptance.py", "pipeline/01-srs/srs.md"]),
    ("spec coverage (spec-coverage.py)", ["spec-coverage.py"]),
    ("NFR coverage (check_nfr_coverage.py)", ["check_nfr_coverage.py"]),
    ("progress sync (check_progress_sync.py)", ["check_progress_sync.py"]),
    ("TODO ticketing (check_todos.py)", ["check_todos.py"]),
]


def run_gate_scripts(project_root: Path, plugin_dir: Path) -> list[GateResult]:
    results: list[GateResult] = []
    for name, argv in _GATE_SCRIPTS:
        script = plugin_dir / "scripts" / argv[0]
        if not script.exists():
            results.append(GateResult(name, True, "script not found — skipped"))
            continue
        try:
            proc = subprocess.run(
                [sys.executable, str(script), *argv[1:]],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            results.append(GateResult(name, False, "timed out"))
            continue
        detail = (proc.stderr or proc.stdout).strip()
        results.append(GateResult(name, proc.returncode == 0, detail))
    return results


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def build_report(project_root: Path, plugin_dir: Path) -> tuple[list[Issue], list[GateResult]]:
    issues = scan_all(project_root)
    gates = run_gate_scripts(project_root, plugin_dir)
    return issues, gates


_CAT_TITLES = {
    "malformed": "Malformed IDs",
    "misplaced": "Misplaced ID Definitions",
    "duplicate": "Duplicate ID Definitions",
    "unimplemented": "Unimplemented / Orphaned Requirements",
}


def format_report(issues: list[Issue], gates: list[GateResult]) -> str:
    lines: list[str] = ["# Forge Validation Report", "", "## Traceability & Gate Rollup", ""]
    for g in gates:
        mark = "✅" if g.passed else "❌"
        suffix = f" — {g.detail}" if g.detail and not g.passed else ""
        lines.append(f"- {mark} {g.name}{suffix}")
    lines.append("")

    by_cat: dict[str, list[scan.Issue]] = {}
    for i in issues:
        by_cat.setdefault(i.category, []).append(i)

    for cat, title in _CAT_TITLES.items():
        cat_issues = by_cat.get(cat, [])
        lines.append(f"## {title} ({len(cat_issues)})")
        lines.append("")
        if not cat_issues:
            lines.append("None found.")
        else:
            for i in cat_issues:
                lines.append(f"- `{i.token}` in `{i.file}` — {i.detail}")
        lines.append("")

    total_gate_fail = sum(1 for g in gates if not g.passed)
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Gate/traceability checks failing: {total_gate_fail}/{len(gates)}")
    for cat, title in _CAT_TITLES.items():
        lines.append(f"- {title}: {len(by_cat.get(cat, []))}")
    lines.append("")
    clean = total_gate_fail == 0 and not issues
    lines.append("**Status: CLEAN**" if clean else "**Status: ISSUES FOUND**")

    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="validate-traceability.py")
    parser.add_argument("--cwd", type=Path, default=Path("."))
    parser.add_argument("--plugin-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="write report here instead of stdout")
    args = parser.parse_args(argv)

    project_root = args.cwd.resolve()
    plugin_dir = (args.plugin_dir or Path(__file__).parent.parent).resolve()

    issues, gates = build_report(project_root, plugin_dir)
    report = format_report(issues, gates)

    if args.out:
        args.out.write_text(report + "\n", encoding="utf-8")
    else:
        print(report)

    clean = all(g.passed for g in gates) and not issues
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
