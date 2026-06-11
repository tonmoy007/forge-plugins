# DEVELOPMENT.md — Building Forge with Claude Code

> Workflows for human developers driving Claude through this build.
> If you're Claude, read `CLAUDE.md` instead.

---

## Setup

```bash
git clone <repo-url> forge
cd forge

# Python deps for hooks/scripts
pip install -r requirements.txt

# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Verify the plugin can be loaded by Claude Code
# (this validates plugin.json schema; doesn't actually install)
python scripts/validate-plugin.py
```

---

## Daily Development Workflow

### Option 1: Direct prompts to Claude

Open Claude Code in the repo, paste one of these prompts:

**Continue from last session:**
```
Read CLAUDE.md, then build/05-implementation/progress.md.
Continue from where the last session left off.
```

**Start a specific task:**
```
Read CLAUDE.md, then read prompts/development/T-007-session-start-hook.md.
Execute that task.
```

**Plan-first for ambiguous work:**
```
Read CLAUDE.md and build/04-plan/task-dag.md.
For task T-014 (write all 12 stage agent personas), produce a detailed plan
covering: agent structure, persona components, how to write good ones.
Wait for my approval before writing any agents.
```

### Option 2: Use the prompt library

Every task in the DAG has a corresponding file in `prompts/development/`. Pick the next
unblocked task from `build/04-plan/task-dag.md`, find its prompt, paste it.

### Option 3: Free-form

Just tell Claude what you want. It will read CLAUDE.md and orient itself.

---

## Branch Strategy

```
main         ← releasable plugin (tagged versions only)
  ↑
develop      ← integration branch — work here by default
  ↑
t-NNN-name   ← per-task branches for risky changes
```

For most tasks, work directly on `develop` and commit. For tasks marked **[L]** (large)
or anything touching multiple components, branch off `develop`.

---

## Testing the Plugin

Three layers:

### Unit tests
```bash
pytest tests/unit/
```
Tests individual scripts and hooks in isolation. Each Python file in `hooks/` and `scripts/`
has a corresponding `test_*.py`.

### Integration tests
```bash
pytest tests/integration/
```
Tests hook + skill flows. Uses fixture pipelines in `tests/fixtures/`.

### End-to-end test
```bash
bash tests/integration/full-pipeline.sh
```
Spins up `examples/sample-todo-api`, installs the plugin locally, and runs all 12 stages
via headless Claude Code (`claude -p`). This is the acceptance test for any release.

### Manual install for dev testing

```bash
# Install the plugin from local checkout (Claude Code v2.1+)
claude plugin install --plugin-dir $(pwd)

# Reload after changes (no restart needed)
# In Claude Code: /reload-plugins
```

---

## How Claude Develops Each Task

The intended flow for each task:

1. **Claude reads** the task from `build/04-plan/task-dag.md`
2. **Claude reads** the matching prompt from `prompts/development/T-XXX-*.md` (if it exists)
3. **Claude reads** the relevant spec from `build/03-spec/technical-spec.md`
4. **Claude proposes a plan** (for non-trivial tasks)
5. **You approve** the plan (or correct it)
6. **Claude implements** — writing files in the appropriate top-level dirs
7. **Claude tests** — runs the test it wrote, verifies output
8. **Claude commits** — with `feat(T-XXX): description` referencing task ID
9. **Claude updates** `build/05-implementation/progress.md`
10. **Claude states** what was done and what to verify

If any step is skipped, push back. The discipline is what makes this work.

---

## Code Review

When Claude finishes a task, before merging to `main`:

```bash
# See what changed
git diff develop main

# Run full test suite
pytest tests/ && bash tests/integration/full-pipeline.sh

# Check the plugin still loads
python scripts/validate-plugin.py

# Manually test the affected slash commands
claude  # then try /forge:* commands
```

If anything's off, file the issue in `tasks/lessons.md` so future Claude sessions don't repeat it.

---

## Adding a New Stage Agent

If you decide Forge needs a 13th stage (or want to redesign one):

1. Update `build/01-srs/srs.md` — add the requirement
2. Update `build/02-architecture/architecture.md` — add the agent to the registry
3. Update `build/03-spec/technical-spec.md` — specify the agent's contract
4. Update `build/04-plan/task-dag.md` — add tasks for the new agent
5. Create `prompts/agents/<agent-name>.md` — prompt for developing the agent
6. Then start the actual work

Don't shortcut by jumping straight to `agents/<new-agent>.md` — the trace upstream
is what makes the system maintainable.

---

## Working Without Claude Code

You can develop hooks and scripts without running Claude Code at all:

```bash
# Test a hook directly with synthetic stdin
echo '{"session_id": "test", "stage": 6}' | python hooks/session-start.py

# Run a script
python scripts/check-gate.py --stage 5

# Validate a SKILL.md
python scripts/validate-skill.py skills/forge-init/SKILL.md
```

This is faster than going through a full Claude Code session for tight iteration loops.

---

## Common Pitfalls

- **Don't** commit anything to `.claude-plugin/plugin.json` without running
  `python scripts/validate-plugin.py` first. A malformed plugin.json breaks Claude Code's
  plugin loader silently.
- **Don't** import non-stdlib packages in hooks. Hooks run on every event; latency matters.
  Use scripts (which can have deps) for heavy lifting.
- **Don't** use `print()` in hooks — it gets injected into Claude's context. Use `logging`.
  Reserve stdout for explicit context injection.
- **Don't** skip the `tasks/lessons.md` update when something goes wrong. Future Claude
  needs to know.

---

## Releasing

When `main` has a green test run + manual smoke test passes:

```bash
# Bump manifests + CHANGELOG, then tag (use scripts/bump-version.py X.Y.Z first)
VERSION=vX.Y.Z
git tag $VERSION
git push origin $VERSION

# Update plugin.json version field to match
# Update CHANGELOG.md

# Publish (when we have a marketplace)
# claude plugin publish .
```
