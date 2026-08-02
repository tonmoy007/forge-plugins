# Skill Format Reference

> Reference for writing SKILL.md files in `skills/`.

## File Structure

A skill is a folder containing a SKILL.md and optional helpers:

```
skills/<skill-name>/
├── SKILL.md         # required
├── scripts/         # optional helper scripts the skill calls
└── references/      # optional docs the skill loads on-demand
```

The folder name becomes the slash command. E.g., `skills/forge-init/` → `/forge:init`
(the `forge:` namespace comes from the plugin name automatically).

## SKILL.md Format

```markdown
---
name: forge-init
description: Initialize Forge pipeline in a project. Use whenever a user mentions
  setting up Forge, initializing a new project, or wants the SDLC pipeline scaffolded.
  Make sure to use this skill the first time a user works in a project that doesn't
  yet have a pipeline/ directory.
allowed-tools: [Read, Write, Bash, Glob]
disable-model-invocation: false
---

# Forge Init

Brief description of what this skill does.

## When to Use

Explicit trigger conditions. Be specific:
- User says "/forge:init" or "initialize forge"
- User describes starting a new project they want orchestrated
- Working directory has no `pipeline/` folder but user wants to use Forge

## Steps

1. Check that `pipeline/` doesn't already exist (if it does, prompt the user)
2. Run `bash ${CLAUDE_PLUGIN_ROOT}/scripts/init-pipeline.sh`
3. Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/detect-project-type.py`
4. Update `pipeline/state.md` with detected project type
5. Print welcome message with next-step suggestion

## Verification

After running, these should be true:
- `pipeline/state.md` exists with valid frontmatter
- `pipeline/{01-srs..12-release}/` directories exist
- `tasks/{todo,lessons}.md` exist
- `.forge/` directory exists with empty patterns.jsonl

## Examples

**User**: "Set up Forge for this project"

**Claude**: [reads SKILL.md, runs the steps]
"Initialized Forge pipeline. Detected project type: ml-pipeline (confidence 0.85, indicators: torch in requirements.txt).

Created:
- pipeline/ with 12 stage directories
- tasks/todo.md and tasks/lessons.md
- .forge/ for memory

Next step: run `/forge:srs` to define requirements, or `/forge:resume` if you've worked on this before."
```

## Frontmatter Fields

| Field | Required | Purpose |
|-------|----------|---------|
| `name` | yes | Internal identifier (matches folder name) |
| `description` | yes | When Claude should auto-invoke. Be **specific and pushy**. |
| `allowed-tools` | no | Restrict which tools the skill can use |
| `disable-model-invocation` | no | If `true`, only invocable via slash command, not auto |
| `model` | no | Override the model (e.g., to use a cheaper model) |

## Description Best Practices

The `description` is the **primary triggering mechanism**. Claude reads only the description
(not the body) to decide whether to invoke.

**Bad**: "Initialize a Forge project"

**Good**: "Initialize the Forge SDLC pipeline. Use whenever a user mentions setting up
Forge, starting a new orchestrated project, scaffolding pipeline directories, or anything
involving 'init' / 'initialize' / 'set up' in the context of starting work in a fresh
project. Make sure to use this skill before any other forge command if no pipeline/ exists."

The "pushy" phrasing combats Claude's tendency to undertrigger skills.

## Tool Restrictions

If a skill should only do certain things, restrict via `allowed-tools`:

```yaml
allowed-tools: [Read, Write, Bash, Glob]   # no Edit, no WebSearch
```

Available tools: `Read`, `Write`, `Edit`, `MultiEdit`, `Bash`, `Grep`, `Glob`, `WebSearch`,
`WebFetch`, `Task` (subagent), and any MCP tools available in the session.

## Argument Substitution

In SKILL.md body:
- `$ARGUMENTS` — full user input after the slash command
- `$0`, `$1`, `$2`, ... — positional args
- `${CLAUDE_SKILL_DIR}` — path to this skill's directory
- `${CLAUDE_PLUGIN_ROOT}` — path to the plugin root

## Testing a Skill

```bash
# Validate the SKILL.md format
python scripts/validate-skill.py skills/forge-init/SKILL.md

# Try it in a Claude Code session
claude --plugin-dir $(pwd)
# Then in the session: /forge:init
```

## Naming Conventions

For Forge:
- Stage commands: `forge-<stage-short>` (e.g., `forge-srs`, `forge-build`)
- Action commands: `forge-<action>` (e.g., `forge-init`, `forge-status`, `forge-resume`)
- Always lowercase, hyphen-separated
