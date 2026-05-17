#!/usr/bin/env python3
"""Context pruner: return a prioritized artifact list within a token budget.

Usage:
    context-pruner.py --stage N --cwd PATH [--budget N]

Output (JSON to stdout):
    {
      "stage": N, "budget": N, "total_tokens": N,
      "artifacts": [
        {"path": "pipeline/state.md", "priority": 1, "tokens": 200, "content": "..."},
        ...
      ]
    }

Artifacts are sorted by priority (1 = highest), read, optionally section-extracted
and max-token-capped, then greedily selected until the budget is exhausted.

REQ-023: each stage reads only its relevant artifacts (no full pipeline dump).
NFR-003: total output stays under 2000 tokens; default budget is 1800.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_CHARS_PER_TOKEN = 4  # consistent with session-start.py
_DEFAULT_BUDGET = 1800  # leave 200 tokens for session-start's own framing
_PARTIAL_INCLUDE_MIN = 50  # only partially include an artifact if ≥ 50 tokens remain


# ---------------------------------------------------------------------------
# Per-stage artifact priority map
# Keys: stage number (int)
# Each entry: {path (relative to cwd), priority, max_tokens?, section?}
#
# Stage 6 (Build) deliberately excludes srs.md and architecture.md — the task-dag
# and spec sections are sufficient for implementation; the full upstream docs add
# noise and eat the budget.
# ---------------------------------------------------------------------------
_STAGE_ARTIFACTS: dict[int, list[dict]] = {
    0: [
        {"path": "pipeline/state.md", "priority": 1, "max_tokens": 300},
    ],
    1: [  # SRS
        {"path": "pipeline/state.md", "priority": 1, "max_tokens": 300},
        {"path": "tasks/lessons.md", "priority": 2, "max_tokens": 400},
        {"path": "references/gate-criteria.md", "priority": 3, "max_tokens": 300,
         "section": "Stage 1"},
    ],
    2: [  # Product/UX
        {"path": "pipeline/state.md", "priority": 1, "max_tokens": 300},
        {"path": "pipeline/01-srs/srs.md", "priority": 2, "max_tokens": 600},
        {"path": "tasks/lessons.md", "priority": 3, "max_tokens": 300},
        {"path": "references/gate-criteria.md", "priority": 4, "max_tokens": 200,
         "section": "Stage 2"},
    ],
    3: [  # Architecture
        {"path": "pipeline/state.md", "priority": 1, "max_tokens": 300},
        {"path": "pipeline/01-srs/srs.md", "priority": 2, "max_tokens": 700},
        {"path": "tasks/lessons.md", "priority": 3, "max_tokens": 300},
        {"path": "references/gate-criteria.md", "priority": 4, "max_tokens": 200,
         "section": "Stage 3"},
    ],
    4: [  # Spec
        {"path": "pipeline/state.md", "priority": 1, "max_tokens": 300},
        {"path": "pipeline/01-srs/srs.md", "priority": 2, "max_tokens": 500},
        {"path": "pipeline/03-architecture/architecture.md", "priority": 3,
         "max_tokens": 500},
        {"path": "tasks/lessons.md", "priority": 4, "max_tokens": 300},
    ],
    5: [  # Plan
        {"path": "pipeline/state.md", "priority": 1, "max_tokens": 300},
        {"path": "pipeline/04-spec/spec.md", "priority": 2, "max_tokens": 600},
        {"path": "pipeline/03-architecture/architecture.md", "priority": 3,
         "max_tokens": 400},
        {"path": "pipeline/01-srs/srs.md", "priority": 4, "max_tokens": 400},
        {"path": "tasks/lessons.md", "priority": 5, "max_tokens": 300},
    ],
    6: [  # Build — task-dag + spec + design system; srs.md and architecture.md excluded
        {"path": "pipeline/state.md", "priority": 1, "max_tokens": 300},
        {"path": "pipeline/05-plan/task-dag.md", "priority": 2, "max_tokens": 700},
        {"path": "pipeline/04-spec/spec.md", "priority": 3, "max_tokens": 500},
        {"path": "pipeline/02-product-ux/design-system.md", "priority": 4,
         "max_tokens": 300},
        {"path": "tasks/lessons.md", "priority": 5, "max_tokens": 300},
    ],
    7: [  # Eval
        {"path": "pipeline/state.md", "priority": 1, "max_tokens": 300},
        {"path": "pipeline/05-plan/task-dag.md", "priority": 2, "max_tokens": 500},
        {"path": "pipeline/04-spec/spec.md", "priority": 3, "max_tokens": 500},
        {"path": "tasks/lessons.md", "priority": 4, "max_tokens": 300},
    ],
    8: [  # Deploy
        {"path": "pipeline/state.md", "priority": 1, "max_tokens": 300},
        {"path": "pipeline/05-plan/task-dag.md", "priority": 2, "max_tokens": 400},
        {"path": "pipeline/08-deploy/deploy-plan.md", "priority": 3, "max_tokens": 500},
        {"path": "tasks/lessons.md", "priority": 4, "max_tokens": 300},
    ],
    9: [  # Monitor
        {"path": "pipeline/state.md", "priority": 1, "max_tokens": 300},
        {"path": "pipeline/08-deploy/deploy-plan.md", "priority": 2, "max_tokens": 400},
        {"path": "pipeline/09-monitor/monitoring.md", "priority": 3, "max_tokens": 500},
        {"path": "tasks/lessons.md", "priority": 4, "max_tokens": 300},
    ],
    10: [  # Feedback
        {"path": "pipeline/state.md", "priority": 1, "max_tokens": 300},
        {"path": "pipeline/07-evaluation/eval-report.md", "priority": 2,
         "max_tokens": 500},
        {"path": "pipeline/10-feedback/feedback.md", "priority": 3, "max_tokens": 500},
        {"path": "tasks/lessons.md", "priority": 4, "max_tokens": 300},
    ],
    11: [  # Resolve
        {"path": "pipeline/state.md", "priority": 1, "max_tokens": 300},
        {"path": "pipeline/10-feedback/feedback.md", "priority": 2, "max_tokens": 500},
        {"path": "pipeline/11-resolve/backlog.md", "priority": 3, "max_tokens": 500},
        {"path": "tasks/lessons.md", "priority": 4, "max_tokens": 300},
    ],
    12: [  # Release
        {"path": "pipeline/state.md", "priority": 1, "max_tokens": 300},
        {"path": "pipeline/12-release/release-notes.md", "priority": 2,
         "max_tokens": 600},
        {"path": "pipeline/12-release/checklist.md", "priority": 3, "max_tokens": 400},
        {"path": "tasks/lessons.md", "priority": 4, "max_tokens": 300},
    ],
}


def token_estimate(text: str) -> int:
    """Approximate token count using chars-per-token heuristic."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


def extract_section(text: str, section_name: str) -> str | None:
    """Extract markdown content under the first heading matching section_name.

    Matches any heading level (# / ## / ###) whose stripped text contains
    section_name (case-insensitive). Returns None if no match.
    """
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    in_section = False

    for line in lines:
        stripped = line.lstrip("#").strip() if line.startswith("#") else None
        if stripped is not None:
            if section_name.lower() in stripped.lower():
                in_section = True
                result.append(line)
                continue
            if in_section:
                break  # next heading at same or higher level ends the section
        if in_section:
            result.append(line)

    return "".join(result) if result else None


def read_artifact(cwd: Path, spec: dict) -> dict | None:
    """Read one artifact from disk, applying section extraction and token cap.

    Returns None if the file does not exist or cannot be read.
    """
    path = cwd / spec["path"]
    if not path.exists():
        return None
    try:
        content = path.read_text(errors="replace")
    except OSError:
        return None

    # Extract a specific section if requested
    section = spec.get("section")
    if section:
        extracted = extract_section(content, section)
        if extracted:
            content = extracted

    # Apply per-artifact token cap
    max_tokens = spec.get("max_tokens")
    if max_tokens and token_estimate(content) > max_tokens:
        max_chars = max_tokens * _CHARS_PER_TOKEN
        content = content[:max_chars] + "\n... [truncated]"

    return {
        "path": spec["path"],
        "priority": spec["priority"],
        "tokens": token_estimate(content),
        "content": content,
    }


def select_artifacts(
    cwd: Path, stage: int, budget: int
) -> tuple[list[dict], int]:
    """Greedily select artifacts by priority until the budget is exhausted.

    Returns (selected_artifacts, tokens_used).
    """
    specs = sorted(
        _STAGE_ARTIFACTS.get(stage, []), key=lambda s: s["priority"]
    )
    selected: list[dict] = []
    remaining = budget

    for spec in specs:
        if remaining <= 0:
            break

        artifact = read_artifact(cwd, spec)
        if artifact is None:
            continue

        if artifact["tokens"] <= remaining:
            selected.append(artifact)
            remaining -= artifact["tokens"]
        elif remaining >= _PARTIAL_INCLUDE_MIN:
            # Partial include: trim to fit remaining budget
            max_chars = remaining * _CHARS_PER_TOKEN
            content = artifact["content"][:max_chars] + "\n... [truncated]"
            artifact["content"] = content
            artifact["tokens"] = token_estimate(content)
            selected.append(artifact)
            remaining = 0

    return selected, budget - remaining


def prune(stage: int, cwd: Path, budget: int = _DEFAULT_BUDGET) -> dict:
    """Return the pruned artifact set for the given stage as a dict."""
    selected, used = select_artifacts(cwd, stage, budget)
    return {
        "stage": stage,
        "budget": budget,
        "total_tokens": used,
        "artifacts": selected,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Return prioritized artifact list within a token budget."
    )
    parser.add_argument("--stage", type=int, required=True, help="Pipeline stage (0-12)")
    parser.add_argument("--cwd", type=str, default=".", help="Project root directory")
    parser.add_argument(
        "--budget", type=int, default=_DEFAULT_BUDGET,
        help=f"Token budget (default: {_DEFAULT_BUDGET})"
    )
    args = parser.parse_args(argv)

    if args.stage < 0 or args.stage > 12:
        print(
            json.dumps({"error": f"stage must be 0-12, got {args.stage}"}),
            file=sys.stderr,
        )
        sys.exit(1)

    cwd = Path(args.cwd).resolve()
    result = prune(args.stage, cwd, args.budget)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
