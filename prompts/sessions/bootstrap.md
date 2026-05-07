# Session Bootstrap

> Paste this into a fresh Claude Code session to get oriented. Use when starting work.

---

You are working on **Forge**, a Claude Code plugin that orchestrates a 12-stage SDLC pipeline.

This is your first time in this session. Before doing anything else:

1. Read `CLAUDE.md` (top-level) — your operating manual
2. Read `build/05-implementation/progress.md` — current state of the build
3. Read `build/04-plan/task-dag.md` — full task list with dependencies
4. Read `tasks/lessons.md` — what we've learned so far
5. Run `git log --oneline -10` to see recent history

After reading those, respond with exactly this format:

```
## Orientation Complete

- Current milestone: M<N> — <name>
- Next task: T-XXX — <title>
- Last commit: <commit subject>
- Active lessons: <count> total, <count> relevant to next task

## Proposed Next Step

I'll start T-XXX by:
1. Reading prompts/development/T-XXX-*.md
2. Reading build/03-spec/technical-spec.md §<relevant section>
3. <next concrete step>

Ready to proceed?
```

Then **wait** for my approval before making any changes. Don't write code until I say go.

If anything in the orientation is unclear or contradictory, flag it before proposing the next step.
