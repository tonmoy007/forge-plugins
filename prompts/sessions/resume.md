# Resume Session

> Paste this when continuing mid-task or after a context-window reset.

---

Resume work on Forge.

1. Read `CLAUDE.md`
2. Read `build/05-implementation/progress.md` — find any task marked 🟡 (in progress)
3. Read `tasks/todo.md` — see what was active
4. Run `git status` to check for uncommitted changes
5. Read the most recent entries in `build/05-implementation/decisions.md`

Respond with:

```
## Resume Status

- Active task: T-XXX (status: 🟡)
- Uncommitted changes: <yes/no — if yes, list files>
- Last decision logged: <date> — <title>

## Where I Left Off

<summary of what was happening before>

## Next Step

<concrete next action — one step, not the whole plan>
```

Then proceed with that next step. If there are uncommitted changes, decide whether to:
- Commit what's there as a checkpoint
- Continue and commit when the logical unit is complete

Either way, **state the choice and why before acting**.
