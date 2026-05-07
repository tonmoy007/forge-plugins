# prompts/

> Prompts you can paste to Claude Code to direct development work.
> Each prompt is self-contained — it tells Claude what to read, what to do, and what
> "done" looks like.

## Categories

- **`development/`** — One prompt per task in the DAG (`T-001-scaffold.md` through `T-033-publish.md`).
  Use these to work through the build sequentially.

- **`agents/`** — Per-agent persona development prompts. When you're working on
  designing or refining a specific stage agent, use these.

- **`sessions/`** — Session bootstrap prompts. Drop one of these in to a fresh
  Claude Code session to orient it quickly.

## How to Use

1. **For the next task in the DAG**: open `build/05-implementation/progress.md`,
   find the first 🔲 task, open `prompts/development/T-XXX-*.md`, paste it.

2. **For a fresh session that needs orientation**: paste `sessions/bootstrap.md`.

3. **For continuing mid-task**: paste `sessions/resume.md`.

4. **For agent-specific work**: paste the relevant `agents/*.md`.

## Prompt Conventions

Every prompt follows:

```markdown
# T-XXX: Title

## Context
<what you should already know from CLAUDE.md and prior tasks>

## Task
<what to do, with explicit steps>

## Definition of Done
<how to know when to stop>

## Verification
<how to prove it works>

## Commit
<expected commit message format>
```

## Adding a New Prompt

When adding a prompt:
1. Match the format above
2. Reference REQ-IDs and prior tasks explicitly
3. Include verification commands
4. Test it: paste into a fresh Claude session and confirm Claude does the right thing
