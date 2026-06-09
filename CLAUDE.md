# CLAUDE.md — Working in the Forge Development Repo

> Claude reads this automatically. It tells you (Claude) where the project is, how to work
> in this repo, and what to do next. Treat it as your operating manual.

---

## What You Are Building

You are building **Forge**, a Claude Code plugin that orchestrates a 12-stage SDLC pipeline
with specialized agents, persistent memory, auto-reflection, and adaptive workflows.

**This is meta-work**: you are using Claude Code to build a plugin that extends Claude Code.
Read `build/01-srs/srs.md` for the full requirements, `build/02-architecture/architecture.md`
for the design, and `build/04-plan/task-dag.md` for the implementation order.

---

## First Thing You Do Every Session

**Always run this sequence at session start, before doing anything else:**

```
1. Read CLAUDE.md (this file)             — orientation
2. Read build/05-implementation/progress.md — current state
3. Read build/04-plan/task-dag.md          — what's next
4. Read tasks/lessons.md                   — what we've learned
5. Glance at recent commits (git log -5)   — what just happened
```

Then state in chat: *"I've read the orientation. Current state: [stage], next task: [T-XXX].
Ready to proceed?"* — and wait for the user's confirmation before making any changes.

If you skip this step, you will inevitably duplicate work, miss decisions made in prior
sessions, or repeat mistakes already captured in lessons.md. **Don't skip it.**

---

## Core Working Principles

These override anything else when there's a conflict:

1. **Plan before building.** Any task with 3+ steps starts with a plan stated in chat,
   even if the user is asking for something specific. Plans get approved, then executed.

2. **Read before editing.** Before any `str_replace` or `Edit`, view the current file.
   File state changes between sessions; assumptions go stale.

3. **One task at a time.** Work the DAG in order. Don't get clever and do "while I'm here"
   side quests — they break traceability and confuse future sessions.

4. **Commit per task.** Each completed task gets one logical commit referencing its T-ID
   (`feat(T-007): build session-start.py hook`). No mega-commits, no fix-stuff commits.

5. **Update progress.md as you go**, not at the end. If the session ends mid-task,
   the next session needs to know exactly where you stopped.

6. **Capture lessons immediately.** When the user corrects you, add the lesson to
   `tasks/lessons.md` *before* fixing the actual code. The lesson is more valuable
   than the fix because it prevents future mistakes.

7. **No fabrication.** Never invent file paths, API signatures, or test results.
   If unknown, run the tool and check. Saying "this should work" without verifying
   is a worse outcome than saying "I don't know — let me check."

---

## Repository Layout

```
forge/
├── .claude-plugin/    ← THE PLUGIN OUTPUT (where users install from)
├── skills/            ← /forge:* slash commands (each is a folder with SKILL.md)
├── agents/            ← agent persona files (.md per agent)
├── hooks/             ← Python hook scripts (executable, called by Claude Code)
├── scripts/           ← helper scripts (state-manager.py, check-gate.py, etc.)
├── references/        ← reference docs loaded on-demand by skills
├── assets/            ← static assets (banners, templates)
│
├── build/             ← THE BUILD PIPELINE for the plugin itself
│   ├── 01-srs/        ← what the plugin must do
│   ├── 02-architecture/  ← how it fits together (+ ADRs)
│   ├── 03-spec/       ← implementation-ready specifications
│   ├── 04-plan/       ← task DAG (what you're working through)
│   ├── 05-implementation/  ← progress tracker, decisions log
│   └── 06-evaluation/ ← eval reports, test results
│
├── prompts/           ← prompts users can paste to direct Claude
│   ├── development/   ← one per task in the DAG
│   ├── agents/        ← per-agent persona development
│   └── sessions/      ← session bootstrap prompts
│
├── tests/             ← test the plugin
│   ├── unit/          ← per-script unit tests
│   ├── integration/   ← hook + skill flow tests
│   └── fixtures/      ← test pipeline projects
│
├── examples/          ← sample projects to test plugin against
│   └── sample-todo-api/  ← the canonical test target
│
├── docs/              ← user-facing docs (built when ready for release)
│
├── tasks/
│   ├── todo.md        ← active task tracker
│   └── lessons.md     ← lessons learned across sessions
│
├── README.md
├── CLAUDE.md          ← this file
├── DEVELOPMENT.md     ← workflows for human developers
└── ROADMAP.md         ← milestone overview
```

**You read from `build/` to know what to build.**
**You write to top-level dirs (`hooks/`, `skills/`, `agents/`, `scripts/`) to actually build it.**
**You update `build/05-implementation/progress.md` to track what you've done.**

---

## Conventions

### Python (hooks, scripts)

- Python 3.11+
- No external dependencies in hooks if possible (stdlib only — they run on every event)
- Scripts can use `pyyaml`, `click`, `rich` — declare in `requirements.txt`
- Every hook script: shebang `#!/usr/bin/env python3`, executable bit set
- Every hook reads JSON from stdin, writes JSON or text to stdout, exits 0 by default
- Exit code 2 *only* to block (PreToolUse, Stop) — document why in a comment
- Type hints required on all functions
- Use `dataclasses` for structured data, not raw dicts
- Logging: `logging.getLogger(__name__)`, never `print()` in hooks
  (print in hooks goes to Claude's context — only use it for context injection)

### Markdown (skills, agents, refs)

- SKILL.md files: YAML frontmatter (`name`, `description`) required
- Agent files: same structure as SKILL.md but in `agents/`
- Line length: soft 100, hard 120
- Code blocks have language tags

### Commits

```
<type>(<scope>): <subject>

<body explaining why>

Ref: T-XXX
```

- Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
- Scope: usually the T-ID or component (`hooks`, `skills`, `agents`, `scripts`)
- Subject: imperative, lowercase, no period, ≤72 chars
- Always reference the task ID

### Branches

- `main` — stable, releasable plugin; branch off it and tag releases from it
- `develop` — integration + testing branch; PRs land here first
- Feature branches — created **from `main`**, named for the change
  (`<type>/<short-description>`, e.g. `feat/batch-inference`, `fix/login-loop`)
- Flow: branch from `main` → PR into `develop` → test on `develop` →
  merge `develop → main` → release on version bump (tag `vX.Y.Z`)
- Never commit directly to `main` or `develop`; never push directly to `main`
  without a tested `develop → main` merge

---

## Verification Before Saying "Done"

Before marking any task complete:

1. **The change works.** Run it, see it work. Don't trust "it should work."
2. **Tests added or updated.** Each new hook/script gets a test in `tests/`.
3. **Progress updated.** `build/05-implementation/progress.md` reflects reality.
4. **Lessons captured.** Anything surprising goes in `tasks/lessons.md`.
5. **Committed.** With a message referencing the T-ID.
6. **Stated in chat.** Summarize what changed and what to verify.

If any of those is "I'll do it later," it's not done.

---

## When Things Go Wrong

| Situation | What to Do |
|-----------|-----------|
| You don't know what to do | Read the orientation files (top of this doc), then ask the user a specific question |
| A test fails | Read the actual error. Don't guess. Don't "fix" by modifying the test. |
| The user corrects you | Add a lesson to `tasks/lessons.md` first, then fix the code |
| You realize the plan is wrong | Stop. Tell the user. Propose a revision. Don't push through. |
| Context is filling up | Update `progress.md`, commit, summarize state, suggest a fresh session |
| You're tempted to delete a failing test | Don't. The test is telling you something. Find out what. |
| You've been refactoring for 30+ minutes | Stop and check: are you still on the original task? |

---

## Self-Check Before Each Major Step

Internal questions Claude should ask itself:

- Is this on the current task? (Check `progress.md`.)
- Have I read the file I'm about to edit?
- Will this change need a test? Have I planned the test?
- Does this match the spec at `build/03-spec/`?
- Am I using project conventions (commit format, naming, structure)?
- Will the next Claude session understand what I did and why?

---

## Where to Find Things

| I need to know... | Read this |
|-------------------|-----------|
| What this plugin does | `build/01-srs/srs.md` |
| How it's structured | `build/02-architecture/architecture.md` |
| Detailed component specs | `build/03-spec/technical-spec.md` |
| What to work on next | `build/04-plan/task-dag.md` |
| What's been done so far | `build/05-implementation/progress.md` |
| Decisions and trade-offs | `build/05-implementation/decisions.md` |
| What we've learned | `tasks/lessons.md` |
| How to develop the plugin | `DEVELOPMENT.md` |
| Hook event reference | `references/claude-code-hooks.md` |
| Skill format reference | `references/skill-format.md` |
| A prompt for a specific task | `prompts/development/T-XXX-*.md` |

---

## Session Hygiene

- **Start**: read orientation, state current position
- **Mid-session**: update progress.md after each completed task
- **Long sessions**: if context > 60% full, suggest a checkpoint commit + fresh session
- **End**: ensure progress.md reflects reality, commit anything pending, write a brief
  status to `tasks/todo.md` so next session can resume

---

## What Success Looks Like

When the plugin is done:

- A new user runs `claude plugin install sdlc-orchestrator`
- They run `/forge:init` in a project — pipeline scaffolds, type detected
- They run `/forge:srs` and describe their project — gets SRS with REQ-IDs
- Each `/forge:*` advances through the pipeline with gate enforcement
- Hooks silently track patterns, propose skills after 3+ uses
- Lessons accumulate across sessions and across projects
- The user's mistake rate drops over time as Forge learns

We're not done until that experience works end-to-end. The acceptance test is
`tests/integration/full-pipeline.sh` — it must pass.

---

**Now: read `build/05-implementation/progress.md` to see where we are, then continue.**
