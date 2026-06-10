---
name: forge-review
description: Run a multi-dimensional parallel code review over the current change.
  Use when the user runs /forge:review, asks to review the diff / a file / the branch,
  wants a thorough review across correctness, security, performance, and conventions,
  or says "review my changes", "check this code", "find issues in the diff". Fans the
  review dimensions out in parallel and synthesizes one deduplicated, severity-sorted
  report.
allowed-tools: [Read, Bash]
---

# forge-review

Independent reviewers, one per dimension (correctness, security, performance,
conventions), run in bounded parallel over the same change and their findings are
merged into a single deduplicated, severity-sorted report. This is the first consumer
of the orchestration primitive (`scripts/_orchestrate.py`).

## When to Use

- User runs `/forge:review`
- User asks to review the current diff, a file, or the branch
- User wants a broad review ("find anything wrong", "is this safe/fast/clean?")

## Pre-flight

Background capability is **not** required — review is synchronous orchestration, not a
daemon. But it does spend (one bounded agent per dimension), so it is cost-gated through
`_cost_cap`. If `.forge/capabilities.json` reports background unavailable, the dimensions
still run synchronously via `claude -p`; if the cost cap is hit, dimensions are skipped
and noted (no silent truncation).

## How to run

Pick the target — the staged diff is the common case:

```bash
git diff --staged > /tmp/forge-review-target.diff
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review_synthesize.py \
  --target /tmp/forge-review-target.diff --cwd .
```

Or review a specific file, or pipe a diff on stdin (`--target -`):

```bash
git diff main... | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review_synthesize.py --target - --cwd .
```

The script fans the four dimensions out in parallel (deterministic, index-ordered),
validates each reviewer's structured findings, drops any malformed dimension without
sinking the review, and prints a Markdown report grouped by severity. Relay the report
to the user; if dimensions were dropped (noted on stderr), say so rather than implying
full coverage.
