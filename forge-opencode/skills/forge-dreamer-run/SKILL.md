---
name: dreamer-run
description: Run the Forge Dreamer — a nightly lesson consolidation daemon
  (/forge:dreamer-run) that applies confidence decay to dormant lessons, detects
  duplicate and contradicting lesson pairs (flag only — never auto-merges or
  auto-resolves), and writes a daily digest to pipeline/log/daily-<date>.md.
  When background agents are available, an optional cheap-model, session-reused
  consolidation summary is appended to the digest. Safe to run multiple times the
  same day — digest is idempotent (overwritten with identical content).
allowed-tools: [Bash]
---

# Forge Dreamer Run — lesson consolidation

Runs the Dreamer daemon (REQ-F-015..021). Idempotent: running `/forge:dreamer-run`
twice the same day produces the same digest. The Dreamer reuses a single `claude -p`
session (resumed each run) pinned to a cheap model for the optional consolidation
step, and writes the daily digest to `pipeline/log/`.

## When to Use

- User types `/forge:dreamer-run` or asks to consolidate lessons, run lesson decay,
  check for duplicate or contradicting lessons, or produce a daily digest.
- As a nightly/scheduled step after a batch of new lessons have been synced.

## When NOT to Use

- The user wants to view the latest digest directly — read `pipeline/log/daily-<date>.md`.
- The user wants to edit or delete lessons — Dreamer flags only, never mutates decisions.

## Steps

1. Run the Dreamer consolidation pass:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dreamer.py --run --cwd "$(pwd)"
   ```
2. Present the results to the user:
   - **Decayed**: N lessons moved to dormant (confidence below threshold).
   - **Duplicate pairs**: N pairs flagged (Jaccard ≥ 0.8 on trigger+rule word-sets).
   - **Contradiction pairs**: N pairs flagged (similar trigger, opposing rule polarity).
   - **Digest**: path to `pipeline/log/daily-<date>.md`.
   - **Consolidation**: whether a background summary was generated.
3. Remind the user:
   - Duplicate and contradiction pairs are **flags only** — the Dreamer never merges
     or resolves them automatically. Review the digest and decide manually.
   - The digest is at `pipeline/log/daily-<date>.md` and can be read any time.

## Verification

- `pipeline/log/daily-<date>.md` exists and contains today's date after a successful run.
- Re-running `/forge:dreamer-run` the same day produces the same digest content
  (no duplication, no appending).
