---
name: forge-init
description: Use whenever a user wants to start using Forge in a project, or mentions 'init', 'initialize', 'set up Forge', or describes starting a new project they want orchestrated.
allowed-tools: [Read, Write, Bash, Glob]
---

# forge-init

## When to Use

Use this skill whenever the user wants to:
- Start using Forge in a project
- Initialize the Forge pipeline in a new or existing project
- Says "init", "initialize", "set up Forge", or "start using Forge"
- Describes starting a new project they want orchestrated

## Steps

1. Run `bash ${CLAUDE_PLUGIN_DIR}/scripts/init-pipeline.sh` to create the pipeline directory structure
2. Run `python3 ${CLAUDE_PLUGIN_DIR}/scripts/detect-project-type.py` to identify the project type
3. Update `pipeline/state.md` — replace `project_type: unknown` with the detected type
4. Print a welcome message listing what was created
5. Suggest the next command: `/forge:srs` to begin Stage 1 (Requirements), or `/forge:resume` if this project already has a pipeline in progress

## Verification

After running, confirm:
- `pipeline/state.md` exists with valid YAML frontmatter (`schema_version: 1`, `current_stage: 0`)
- `pipeline/01-srs/` through `pipeline/12-release/` all exist
- `tasks/todo.md` and `tasks/lessons.md` exist
- `.forge/lessons.yaml` and `.forge/patterns.jsonl` exist
