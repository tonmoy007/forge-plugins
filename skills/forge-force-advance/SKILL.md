---
name: forge-force-advance
description: Override a blocking gate and advance the pipeline stage, recording a
  lesson with the user's stated reason. Use this skill ONLY when a user explicitly
  asks to "force advance", "skip the gate", "override the blocker", "advance anyway",
  or otherwise expresses intent to proceed despite failing gate criteria. Make sure
  to require an explicit `--reason` justification from the user (≥ 10 characters)
  before invoking the script — the lesson recorded becomes part of the retrospective
  and protects future-them from forgetting why this happened. Do NOT use this skill
  proactively or as a workaround for fixable gate failures; if the user hasn't asked
  to override, ask whether they want to fix the blocker first.
allowed-tools: [Bash]
---

# Forge Force Advance

Bypasses the gate-blocker check, advances `pipeline/state.md` by one stage, and
records a permanent lesson with the user's reason. The overridden gate criteria
themselves remain failed — they'll show up again in subsequent gate checks unless
actually resolved.

This is a **conscious admission** that work was incomplete at advance time. The
lesson is the only protection against that fact being forgotten.

## When to Use

- User says `/forge:force-advance`
- User says "force advance", "skip the gate", "advance anyway", "override the blocker"
- User has acknowledged they cannot or will not resolve a blocker right now
  (e.g., needs ops help, blocked on a third party, deliberately deferring scope)
- User has already heard `/forge:why` output and decided to proceed anyway

## When NOT to Use

- The user is asking *how* to fix a blocker — explain or run `/forge:why` instead
- The blocker is trivially fixable (missing file, missing section heading) — fix it
- The user hasn't asked to override — never proactively suggest force-advance as a
  workaround; gates exist for a reason

## Steps

1. If the user hasn't provided a reason yet, ask:
   "Force-advance records a permanent lesson. What's the reason you're advancing
   despite the active blockers? (≥ 10 characters; this will be reviewed in retro.)"
2. Wait for the user's reason. Confirm it's at least 10 non-whitespace characters.
3. (Optional but recommended) Run `/forge:why` first to surface the actual blockers
   so the lesson context is fresh.
4. Run the force-advance command:
   ```bash
   python ${CLAUDE_PLUGIN_DIR}/scripts/force-advance.py \
       --reason "<the user's exact reason>" \
       --cwd "<project>"
   ```
   Use `--to N` if the user explicitly asked to jump to a specific stage rather
   than advance by one.
5. Present the script output to the user. Highlight:
   - The stage transition (Stage N → Stage N+1)
   - The list of blockers that were overridden
   - The fact that the lesson is now recorded and will appear in `/forge:retro`

## Verification

After running, all of these should be true:
- `pipeline/state.md` shows `current_stage` incremented
- `pipeline/state.md` has a new row in `## Stage History` marked `FORCE`
- `.forge/lessons.yaml` has a new entry tagged `force-advance`
- `tasks/lessons.md` has a human-readable summary under `## Lessons`
- The user understands the overridden blockers will reappear in the next gate check
  for the new stage's own criteria, but the old stage's blockers persist as failed
  unresolved work

## Examples

**User**: "Just force advance. I'll fix the missing ADRs later."

**Claude**: "Before I do, what's the reason? It'll be recorded as a lesson and
reviewed at the end of the cycle (≥ 10 characters)."

**User**: "Deferring ADRs to next sprint; team consensus from today's standup."

**Claude**: [runs `python ${CLAUDE_PLUGIN_DIR}/scripts/force-advance.py
--reason "Deferring ADRs to next sprint; team consensus from today's standup."
--cwd "$(pwd)"`]

"Done:
```
Stage 3 → 4 (force-advanced)
  Blockers overridden: G3-002, G3-005
  Reason: 'Deferring ADRs to next sprint; team consensus from today's standup.'
  Lesson recorded with tag: force-advance
  Will surface in /forge:retro at end of cycle.
```

Note that G3-002 and G3-005 remain failed in `/forge:status` — when you address
them next sprint, they'll automatically clear."

---

**User**: "/forge:force-advance --reason 'urgent'"

**Claude**: "That reason is only 6 characters — force-advance requires at least
10 non-whitespace characters so the retro context is meaningful. Can you flesh
it out? For example: 'urgent demo for customer Monday; will fix gate next cycle'."

---

**User**: "Why won't G1-001 pass? Just skip it for now."

**Claude**: "Let me first check what G1-001 actually requires — running
`/forge:why G1-001`." [runs why.py G1-001]

"It needs at least one functional requirement with a REQ-NNN ID in
`pipeline/01-srs/srs.md`. That's usually a 30-second fix. Would you like me to
help add a REQ entry, or do you still want to force-advance?"

[Wait for the user to choose. Do not assume force-advance is the right answer
just because the user mentioned skipping.]