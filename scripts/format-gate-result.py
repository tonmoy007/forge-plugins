#!/usr/bin/env python3
"""Format check-gate.py JSON output into human-readable text with fix hints.

Three input modes:
    1. Pipe:    `python scripts/check-gate.py --stage 3 | python scripts/format-gate-result.py`
    2. File:    `python scripts/format-gate-result.py --input gate-result.json`
    3. Inline:  `python scripts/format-gate-result.py --stage 3`  (runs check-gate.py for you)

Output: a structured report with one block per failing criterion, plus a fix hint
derived from (a) the criterion's gate ID prefix, (b) the check type, or (c) a
sensible fallback. Exits 0 if all criteria passed, 1 if any failed.

Use `--json` to emit the same data structured for tools (just enriches the input
JSON with a `fix_hint` field per criterion).

Ref: T-104
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Fix hints keyed by gate ID prefix. Matched longest-prefix-first.
# Each maps to either a string or a callable that receives the criterion dict
# and returns a string.
_PREFIX_FIX_HINTS: dict[str, str] = {
    # Stage 1 — SRS
    "G1-001": "Edit pipeline/01-srs/srs.md and add at least one functional requirement "
              "with a REQ-NNN identifier.",
    "G1-002": "Add an 'Open Questions' section to pipeline/01-srs/srs.md (use a level-2 "
              "heading: `## Open Questions`).",
    "G1-003": "Add measurable non-functional requirements (NFR-NNN) to "
              "pipeline/01-srs/srs.md — e.g., 'NFR-001: p99 latency < 200ms'.",
    "G1-": "Address the SRS gap in pipeline/01-srs/srs.md per the criterion description.",

    # Stage 2 — Product / UX
    "G2-001": "Add design tokens to pipeline/02-product-ux/design-system.md using CSS "
              "custom properties: `--color-*`, `--font-*`, `--space-*`.",
    "G2-002": "Add WCAG accessibility notes to pipeline/02-product-ux/design-system.md "
              "(at minimum: focus states, contrast ratios, keyboard navigation).",
    "G2-": "Update pipeline/02-product-ux/ per the criterion description.",

    # Stage 3 — Architecture
    "G3-001": "Create pipeline/03-architecture/architecture.md describing system "
              "structure, components, and key data flows.",
    "G3-002": "Add at least one ADR. Either run `/forge:adr` or create "
              "pipeline/03-architecture/adr/0001-<short-title>.md.",
    "G3-": "Update pipeline/03-architecture/ per the criterion description.",

    # Stage 4 — Spec
    "G4-": "Update pipeline/04-spec/ per the criterion description. Each REQ-ID from "
           "the SRS should map to one or more spec sections.",

    # Stage 5 — Plan
    "G5-": "Update pipeline/05-plan/tasks.yaml per the criterion description. Each "
           "T-NNN task should reference at least one REQ-NNN.",

    # Stage 6 — Build
    "G6-001": "All tasks in pipeline/05-plan/tasks.yaml must reach status `done` "
              "before Stage 6 can complete.",
    "G6-": "Continue Stage 6 work: update pipeline/06-implementation/progress.md and "
           "complete remaining tasks per the criterion description.",

    # Stage 7 — Evaluation (and profile-specific extensions)
    "G7-API-001": "Run `pytest tests/integration/api_contract/` (or equivalent) and "
                  "resolve any failures. All endpoints declared in your OpenAPI spec "
                  "must have at least one contract test.",
    "G7-API-002": "Run the load test (typically `scripts/load-test.py` or k6/wrk against "
                  "a staging deploy) and confirm p99 latency is within the documented "
                  "target.",
    "G7-FS-001": "Run Lighthouse against your dev build: `npx lighthouse <url> --view`. "
                 "Address scores below 90 in perf, a11y, best-practices, SEO.",
    "G7-FS-002": "Run `axe`, `pa11y`, or your accessibility tool of choice; fix WCAG AA "
                 "violations before marking Stage 7 complete.",
    "G7-ML-001": "Run model evaluation (`scripts/check-model-accuracy.py` or equivalent) "
                 "on the holdout set. Accuracy must exceed the threshold declared in "
                 "pipeline/04-spec/model-spec.md.",
    "G7-ML-005": "Document drift detection strategy in pipeline/07-evaluation/eval-report.md "
                 "covering training/serving skew, input drift, and performance drift.",
    "G7-CLI-001": "Run `<your-cli> <subcommand> --help` for every command; verify each "
                  "produces non-empty help text.",
    "G7-CLI-002": "Document exit codes in pipeline/02-product-ux/error-messages.md (or "
                  "the equivalent file for your project) — at minimum 0 (success), 1 "
                  "(generic error), 2 (usage error).",
    "G7-LIB-001": "Review your public API surface. Anything not intended for external "
                  "consumption should be underscore-prefixed or behind a `__all__` list.",
    "G7-": "Update pipeline/07-evaluation/eval-report.md per the criterion description.",

    # Stage 8 — Deploy
    "G8-": "Update pipeline/08-deploy/deploy-plan.md per the criterion description.",

    # Stage 9 — Monitor
    "G9-": "Configure monitoring per the criterion description and document in "
           "pipeline/09-monitor/observability-config.md.",

    # Stage 10 — Feedback
    "G10-": "Update pipeline/10-feedback/ per the criterion description.",

    # Stage 11 — Resolve
    "G11-": "Update pipeline/11-resolve/ per the criterion description.",

    # Stage 12 — Release
    "G12-LIB-001": "Reformat CHANGELOG.md per Keep a Changelog "
                   "(https://keepachangelog.com/) — `### Added/Changed/Fixed/Removed`.",
    "G12-LIB-002": "Run `npm version <major|minor|patch>` (or equivalent) such that the "
                   "version bump matches your changes' semver impact.",
    "G12-": "Update pipeline/12-release/ per the criterion description.",

    # Multi-agent (v0.2+)
    "G7-MAS-": "Re-run /forge:eval; the eval-agent will dispatch parallel reviewers and "
               "merge their outputs into eval-report.md.",
    "G-MAS-": "Check .forge/lessons.yaml for `lead-only-violation` entries to identify "
              "which teammate wrote to a canonical artifact.",
}

# Fallback hints by check type when no gate-ID prefix matches.
_CHECK_TYPE_FIX_HINTS: dict[str, str] = {
    "file_exists":
        "Create the missing file at the path shown in the message. The criterion "
        "description tells you what it should contain.",
    "file_contains":
        "Edit the file at the path shown in the message and add content matching the "
        "pattern from the criterion description.",
    "script_returns_zero":
        "Run the check script directly to see its full output: "
        "`python ${{CLAUDE_PLUGIN_DIR}}/{script_path}` — then resolve the issues it surfaces.",
    "all_tests_pass":
        "Run `{test_command}` and resolve each failing test before re-running gate.",
}


def _lookup_fix_hint(criterion: dict) -> str:
    """Return the best available fix hint for a failing criterion."""
    cid = criterion.get("id", "")
    # Try longest-prefix-first by sorting keys by length descending.
    for prefix in sorted(_PREFIX_FIX_HINTS.keys(), key=len, reverse=True):
        if cid.startswith(prefix):
            return _PREFIX_FIX_HINTS[prefix]

    check_type = criterion.get("check", "")
    template = _CHECK_TYPE_FIX_HINTS.get(check_type)
    if template:
        # The script path / test command may be embedded in the message; do our
        # best to surface a useful fix even without that detail.
        return template.format(
            script_path="scripts/<check-script>",
            test_command="pytest",
        )

    return ("Read the criterion description and message above, then make the smallest "
            "change that satisfies it. If the description is ambiguous, run /forge:why "
            "for context.")


def format_text(result: dict) -> str:
    """Render the structured gate result as human-readable text."""
    stage = result.get("stage", "?")
    total = result.get("total", 0)
    passed = result.get("passed", 0)
    failed = result.get("failed", 0)
    details = result.get("details", [])

    header = f"Stage {stage} — gate check: {passed}/{total} passed, {failed} failed"
    bar = "═" * len(header)
    lines = [header, bar, ""]

    blockers = [d for d in details if not d.get("passed") and d.get("severity") == "blocker"]
    warnings = [d for d in details if not d.get("passed") and d.get("severity") != "blocker"]
    passes  = [d for d in details if d.get("passed")]

    if not blockers and not warnings:
        lines.append("✓ All criteria passed. Stage may advance.")
        return "\n".join(lines)

    if blockers:
        lines.append(f"BLOCKERS ({len(blockers)} — must fix before advancing):")
        lines.append("")
        for c in blockers:
            lines.extend(_format_failure(c, icon="✗"))
            lines.append("")

    if warnings:
        lines.append(f"WARNINGS ({len(warnings)} — won't block, but worth addressing):")
        lines.append("")
        for c in warnings:
            lines.extend(_format_failure(c, icon="⚠"))
            lines.append("")

    if passes:
        lines.append(f"PASSED ({len(passes)}): "
                     + ", ".join(c.get("id", "?") for c in passes))
        lines.append("")

    if blockers:
        lines.append("Stage CANNOT advance until all blockers are resolved.")
        lines.append("Override with /forge:force-advance --reason '<why>' "
                     "(records a lesson).")
    else:
        lines.append("Stage may advance. Address warnings when convenient.")

    return "\n".join(lines)


def _format_failure(criterion: dict, *, icon: str) -> list[str]:
    cid = criterion.get("id", "?")
    desc = criterion.get("description", "")
    msg = criterion.get("message", "")
    check_type = criterion.get("check", "")
    severity = criterion.get("severity", "blocker")
    fix = _lookup_fix_hint(criterion)
    return [
        f"  {icon} {cid} ({severity}) — {desc}",
        f"      check: {check_type}",
        f"      detail: {msg}",
        f"      fix:   {fix}",
    ]


def enrich_json(result: dict) -> dict:
    """Return the input with a `fix_hint` field added to each failing criterion."""
    enriched = dict(result)
    enriched["details"] = []
    for c in result.get("details", []):
        c2 = dict(c)
        if not c.get("passed"):
            c2["fix_hint"] = _lookup_fix_hint(c)
        enriched["details"].append(c2)
    return enriched


def _read_input(args: argparse.Namespace) -> dict:
    """Load gate result JSON from stdin, --input file, or by running check-gate.py."""
    if args.input:
        text = Path(args.input).read_text()
    elif args.stage is not None:
        plugin_dir = Path(args.plugin_dir).resolve()
        check_gate = plugin_dir / "scripts" / "check-gate.py"
        proc = subprocess.run(
            [sys.executable, str(check_gate),
             "--stage", str(args.stage),
             "--cwd", str(Path(args.cwd).resolve()),
             "--plugin-dir", str(plugin_dir)],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0 and not proc.stdout.strip().startswith("{"):
            print(proc.stderr or proc.stdout, file=sys.stderr)
            sys.exit(proc.returncode or 1)
        text = proc.stdout
    else:
        if sys.stdin.isatty():
            print("error: no input. Pipe check-gate.py output, use --input, or use --stage.",
                  file=sys.stderr)
            sys.exit(2)
        text = sys.stdin.read()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"error: input is not valid JSON: {e}", file=sys.stderr)
        sys.exit(2)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Format check-gate.py output into human-readable text with fix hints.",
    )
    parser.add_argument("--input", metavar="PATH",
                        help="Read gate result JSON from this file")
    parser.add_argument("--stage", type=int, metavar="N",
                        help="Run check-gate.py for stage N and format its output")
    parser.add_argument("--cwd", default=os.getcwd(), metavar="PATH",
                        help="Project directory (default: cwd; used with --stage)")
    parser.add_argument("--plugin-dir",
                        default=str(Path(__file__).resolve().parent.parent),
                        metavar="PATH",
                        help="Forge plugin root (default: parent of scripts/)")
    parser.add_argument("--json", action="store_true",
                        help="Emit enriched JSON instead of text")
    args = parser.parse_args(argv)

    result = _read_input(args)

    if args.json:
        print(json.dumps(enrich_json(result), indent=2))
    else:
        print(format_text(result))

    return 0 if result.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())