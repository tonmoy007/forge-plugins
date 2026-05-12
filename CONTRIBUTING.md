# Contributing to Forge

Forge is a Claude Code plugin that orchestrates a 12-stage SDLC pipeline with
specialized agents, persistent memory, auto-reflection, and adaptive workflows.

This guide covers setup, development conventions, and three extension paths:
adding an agent, a stage, or a project-type profile. For step-by-step
walkthroughs with complete examples, see `docs/agent-authoring.md`.

---

## Setup

```bash
git clone <repo-url>
cd forge-plugin
pip install -r requirements.txt   # pyyaml, click, rich (hooks are stdlib-only)
python3 scripts/validate-plugin.py  # must exit 0
python3 -m pytest tests/ --tb=short -q  # all tests must pass
```

---

## Repository Map

```
forge-plugin/
├── agents/        ← agent persona files (.md) — one per role
├── hooks/         ← Python scripts called by Claude Code on lifecycle events
├── scripts/       ← helper CLIs (state-manager, check-gate, mine-skills, …)
├── skills/        ← /forge:* slash commands — one subdirectory per skill
├── references/    ← reference docs loaded on demand (gate-criteria, profiles)
├── tests/
│   ├── unit/      ← per-script tests, fast
│   └── integration/ ← end-to-end pipeline tests
└── build/         ← design artefacts (SRS, architecture, task DAG) — read-only
```

The installed plugin wiring lives in `.claude-plugin/plugin.json`. It globs
`skills/*` automatically, so new skills appear without manual registration.
New hooks must be added to the `hooks` array in `plugin.json`.

---

## Development Workflow

1. Work from `develop`, not `main`.
2. Pick the next task from `build/04-plan/task-dag.md`.
3. Read (don't guess) every file before editing it.
4. Add or update tests for every code change.
5. Run `python3 scripts/validate-plugin.py` and the full test suite before
   committing.
6. Update `build/05-implementation/progress.md` when the task is done.
7. One commit per task; format below.

---

## Three Ways to Extend Forge

### 1. Add an agent persona

Create `agents/<role>.md` with the standard frontmatter block and five sections
(Role, Goal, Context Scope, Output Contract, Workflow). Wire it into the
stage skill that should invoke it by adding a `Read agents/<role>.md` step.

See **"Adding an Agent Persona"** in `docs/agent-authoring.md`.

### 2. Add a stage (or freestanding skill)

Create `skills/forge-<name>/SKILL.md` with YAML frontmatter, then add the
stage's gate criteria to `references/gate-criteria.md`. If the skill maps to
a numbered pipeline stage (1–12), update the valid-stage list in
`scripts/state-manager.py` and wire profile overrides in
`references/project-type-profiles.md`.

See **"Adding a Stage"** in `docs/agent-authoring.md`.

### 3. Add a project-type profile override

Edit the relevant `## Profile: <type>` block in
`references/project-type-profiles.md`, adding a `stage_N:` key. Verify
with:

```bash
python3 scripts/load-profile.py --cwd . --stage <N>
```

See **"Adding a Project-Type Profile"** in `docs/agent-authoring.md`.

---

## Testing Conventions

- Unit tests: `tests/unit/test_<script_name>.py`.
- Scripts with hyphenated filenames (e.g., `mine-skills.py`) must be loaded
  via `importlib.util`. **Register the module in `sys.modules` before calling
  `exec_module`** — required for `@dataclass` introspection in Python 3.12+.
  See `tests/unit/test_mine_skills.py` for the canonical pattern.
- Structural tests for `.md` files assert frontmatter keys and required section
  headers. See `tests/unit/test_forge_retro.py` for the pattern.
- Do not mock the filesystem in tests; use `pytest`'s `tmp_path` fixture.
- Each new hook or script must reach the done-when criterion in its test.

---

## Code Style

- **Python**: type hints on all functions, `dataclasses` for structured data,
  `logging.getLogger(__name__)` (never bare `print()` in hooks). Stdlib only
  in hooks; scripts may use `pyyaml`, `click`, `rich`.
- **Markdown**: 100-char soft line limit; code blocks tagged with language.
- **Hooks**: shebang `#!/usr/bin/env python3`, executable bit (`chmod +x`),
  read JSON from stdin, write to stdout, exit 0 unless blocking (exit 2 to
  block PreToolUse/Stop events — comment why).

---

## Commit Format

```
<type>(<scope>): <subject>

<body — why this change>

Ref: T-XXX
```

- **Types**: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
- **Scope**: task ID or component name (`hooks`, `skills`, `agents`, `scripts`)
- **Subject**: imperative mood, lowercase, ≤72 chars, no trailing period

---

## Pull Requests

- One PR per task or logical milestone.
- PR description references T-IDs and REQ-IDs.
- All tests must pass; `validate-plugin.py` must exit 0.
- Update `CHANGELOG.md` for any user-visible change.
- Target `develop`; `develop → main` merges require a passing e2e test.
