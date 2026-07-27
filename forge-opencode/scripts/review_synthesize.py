#!/usr/bin/env python3
"""/forge:review — parallel reviewers, the first consumer of the orchestration
primitive (T-149, REQ-F-034).

Fans independent review *dimensions* (correctness, security, performance,
conventions) out across `_orchestrate.fan_out`, then synthesizes a single
deduplicated, severity-sorted report. Proves the primitive end-to-end: the
dimensions run in bounded parallel, results are deterministic (index-ordered), and
a malformed dimension is dropped without sinking the whole review.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _orchestrate  # noqa: E402

REVIEW_DIMENSIONS = [
    {"key": "correctness", "focus": "logic errors, bugs, missed edge cases, wrong assumptions"},
    {"key": "security", "focus": "injection, auth gaps, unsafe input, leaked secrets"},
    {"key": "performance", "focus": "hot-path cost, complexity, redundant work, N+1"},
    {"key": "conventions", "focus": "project style, naming, structure, dead code"},
]

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_UNKNOWN_RANK = 5


def _build_prompt(target: str, dimension: dict) -> str:
    return (
        f"You are a Forge code reviewer focused ONLY on **{dimension['key']}** "
        f"({dimension['focus']}). Review the change below. Reply with a single JSON "
        f'object: {{"dimension": "{dimension["key"]}", "findings": [{{"file": str, '
        '"line": int, "severity": "critical|high|medium|low|info", "title": str, '
        '"detail": str}, ...]}. Report only real issues in your dimension; [] if none. '
        f"Be terse.\n\n--- change ---\n{target}"
    )


def _validate_dimension(parsed: dict) -> dict:
    if not isinstance(parsed, dict):
        raise ValueError("dimension result is not an object")
    findings = parsed.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("findings is not a list")
    clean = [f for f in findings if isinstance(f, dict)]
    return {"dimension": parsed.get("dimension"), "findings": clean}


def _finding_key(f: dict) -> tuple:
    return (f.get("file"), f.get("line"), str(f.get("title", "")).strip().lower())


def _rank(f: dict) -> int:
    return _SEVERITY_RANK.get(str(f.get("severity", "")).lower(), _UNKNOWN_RANK)


def _to_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def synthesize(dimension_results: list) -> dict:
    """Flatten → dedup (first wins) → severity-sort → markdown. Pure function."""
    flat: list = []
    seen: set = set()
    for dim in dimension_results:
        for f in dim.get("findings", []) if isinstance(dim, dict) else []:
            if not isinstance(f, dict):
                continue
            key = _finding_key(f)
            if key in seen:
                continue
            seen.add(key)
            flat.append(f)

    flat.sort(key=lambda f: (_rank(f), str(f.get("file", "")), _to_int(f.get("line"))))
    return {"findings": flat, "markdown": _render_markdown(flat)}


def _render_markdown(findings: list) -> str:
    if not findings:
        return "# Forge Review\n\nNo findings.\n"
    lines = [f"# Forge Review — {len(findings)} finding(s)", ""]
    current = None
    for f in findings:
        sev = str(f.get("severity", "other")).upper()
        if sev != current:
            lines.append(f"## {sev}")
            current = sev
        loc = f"{f.get('file', '?')}:{f.get('line', '?')}"
        lines.append(f"- `{loc}` — {f.get('title', '(untitled)')}")
        detail = str(f.get("detail", "")).strip()
        if detail:
            lines.append(f"  {detail}")
    lines.append("")
    return "\n".join(lines)


def run_review(
    target: str,
    *,
    forge_dir: Path,
    dispatch_fn=None,
    max_parallel: int = 4,
    claude_bin: Optional[str] = None,
    cwd: Optional[str] = None,
) -> dict:
    """Fan the review dimensions out and synthesize the report. Never raises."""
    fan = _orchestrate.fan_out(
        REVIEW_DIMENSIONS,
        lambda dim: _build_prompt(target, dim),
        forge_dir=forge_dir,
        feature="review",
        validate=_validate_dimension,
        max_parallel=max_parallel,
        dispatch_fn=dispatch_fn,
        claude_bin=claude_bin,
        cwd=cwd,
    )
    report = synthesize(fan.results)
    report["dropped"] = fan.dropped
    report["cost_usd"] = fan.total_cost_usd
    return report


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="review_synthesize")
    parser.add_argument("--target", default="-", help="path to the change/diff, or - for stdin")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--max-parallel", type=int, default=4)
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.target == "-":
        target = sys.stdin.read()
    else:
        try:
            target = Path(args.target).read_text()
        except OSError as exc:
            print(f"error: cannot read target: {exc}", file=sys.stderr)
            return 1

    report = run_review(target, forge_dir=Path(args.cwd) / ".forge",
                        max_parallel=args.max_parallel, cwd=args.cwd)
    print(report["markdown"])
    if report.get("dropped"):
        print(f"\n_({report['dropped']} review dimension(s) dropped — see logs)_", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
