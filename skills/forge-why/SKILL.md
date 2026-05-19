---
name: forge-why
description: Explain a Forge gate criterion, lesson tag, pipeline stage, or current
  blocker(s). Use this skill whenever a user types `/forge:why`, asks "why is
  G1-001 failing?", "what does this gate mean?", "what's blocking me?", "what is
  Stage 3?", or "show me lessons tagged X". Make sure to use this skill BEFORE
  suggesting `/forge:force-advance` — `/forge:why` often shows the user a fix
  they can apply in seconds, avoiding an unnecessary override and lesson. Also use
  proactively when a gate fails: a user asking "what does check-gate.py mean by
  G3-002?" deserves an explanation, not just the raw JSON.
allowed-tools: [Bash]
---

# Forge Why

Pure read-only deterministic lookup. Translates a Forge identifier into a
human-readable explanation. Four input modes:

| Target form | Example | Resolves to |
| --- | --- | --- |
| Gate criterion ID | `G1-001`, `G7-API-002`, `G12-LIB-001` | Description + check type + severity + fix hint |
| Stage number (terse or prefixed) | `3` or `stage-3` | Stage name, purpose, artifacts, gate counts |
| Lesson tag | `force-advance`, `slow-consumer` | Up to 5 most-recent lessons with that tag |
| (empty) | `/forge:why` | Current stage's active blockers + fix hints |

## When to Use

- User types `/forge:why <something>` or just `/forge:why`
- A gate just failed and the user asks "why?" or "what does that mean?"
- User asks "what is Stage N?" or "what does this stage do?"
- User asks about lessons: "show me force-advance lessons", "any slow-consumer warnings?"
- BEFORE suggesting `/forge:force-advance` — always explain the blocker first

## When NOT to Use

- The user is asking a question Forge cannot answer (general programming questions,
  questions about their domain) — `/forge:why` only resolves Forge IDs and concepts
- The user has already heard the explanation — don't repeat it on follow-up

## Steps

1. Identify the target the user is asking about:
   - Starts with `G` followed by digit → gate criterion ID
   - Matches `<digit>` or `stage-<digit>` (1-12) → stage number
   - Empty or "current blockers" → bare invocation
   - Anything else → lesson tag
2. Run:
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/scripts/why.py "<target>" --cwd "<project>"
   ```
   For bare invocation, omit the target:
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/scripts/why.py --cwd "<project>"
   ```
3. Present the output to the user **verbatim**. The fix hints inside are
   literal — do not paraphrase them.
4. If the result includes a fix hint that points to a specific file/command, do
   NOT execute it automatically. Wait for the user to ask. The `why` command
   informs; it doesn't act.
5. If the result is `not found` (exit 1), suggest alternatives:
   - For an unknown gate ID: "That ID doesn't exist. Did you mean one of these?"
     followed by running `/forge:status` to list active gates
   - For an unknown lesson tag: "No lessons match that tag. Run `/forge:retro`
     to see what's been recorded so far"
   - For an out-of-range stage: "Stages are 1-12; you may have meant a different number"

## Verification

After running, all of these should be true:
- The user has the answer to what they asked about
- For gate explanations, the user knows the criterion's severity (blocker vs warning)
- For current-blocker explanations, the user knows each blocker's fix hint
- The user can decide their next move: fix the blocker, ask another `/forge:why`,
  run `/forge:status`, or (if they've considered it) force-advance

## Examples

**User**: "Why is G3-002 failing?"

**Claude**: [runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/why.py G3-002 --cwd "$(pwd)"`]

```
Gate criterion: G3-002
  Stage:       3
  Severity:    blocker
  Check type:  file_exists
  Description: At least one ADR present
  Check args:  {"path": "pipeline/03-architecture/adr"}

  Fix hint:
    Add at least one ADR. Either run `/forge:adr` or create
    pipeline/03-architecture/adr/0001-<short-title>.md.
```

"This is a blocker — Stage 3 won't advance until you have at least one
Architecture Decision Record. Want me to walk you through creating one, or do
you have one to point to?"

---

**User**: "What's blocking me right now?"

**Claude**: [runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/why.py --cwd "$(pwd)"`]

```
Stage 3: 2 blocker(s):

  ✗ G3-001 — Architecture doc exists
      detail: pipeline/03-architecture/architecture.md: file does not exist
      fix:    Create pipeline/03-architecture/architecture.md describing system
              structure, components, and key data flows.

  ✗ G3-002 — At least one ADR present
      detail: pipeline/03-architecture/adr: directory contains no .md files
      fix:    Add at least one ADR. Either run `/forge:adr` or create
              pipeline/03-architecture/adr/0001-<short-title>.md.

To override: /forge:force-advance --reason '<why>'  (records a lesson)
```

"Two blockers. The architecture doc is the bigger one — let me know if you want
to start drafting it together, or if you'd rather sketch the ADR first."

---

**User**: "What is stage 7?"

**Claude**: [runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/why.py 7 --cwd "$(pwd)"`]

```
Stage 7 — evaluation
  Purpose: Test against NFRs; verify acceptance criteria; profile-specific checks.
  Gate criteria: 4 blocker(s), 2 warning(s)
  Artifacts:
    - pipeline/07-evaluation/eval-report.md
  Criterion IDs: G7-001, G7-002, G7-API-001, G7-API-002, G7-API-003, G7-FS-001
```

"Stage 7 is where you validate that what you built in Stage 6 actually meets the
requirements from Stage 1. For your `api` project, it adds API-specific checks
like contract tests and load tests on top of the base gates."

---

**User**: "Have I force-advanced before?"

**Claude**: [runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/why.py force-advance --cwd "$(pwd)"`]

```
Lesson tag: force-advance
  Total matches: 2 (showing 2 most recent)

  [1] 2026-05-14 — Stage 3
      trigger: Stage 3 advanced with unresolved blockers
      rule:    Deferring ADRs to next sprint; team consensus from standup
      blockers: G3-002, G3-005

  [2] 2026-05-10 — Stage 1
      trigger: Stage 1 advanced with unresolved blockers
      rule:    Customer demo Monday; will fill in REQ-IDs after
      blockers: G1-002
```

"Twice so far in this project. The Stage 3 override is from yesterday — those
ADR gates (G3-002, G3-005) are still failed if you want to come back to them."