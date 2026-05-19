---
name: forge-init
description: Initialize the Forge SDLC pipeline in a project. Use whenever a user
  mentions setting up Forge, starting a new orchestrated project, scaffolding
  pipeline directories, or anything involving 'init', 'initialize', 'set up Forge',
  or 'start using Forge' in the context of starting work on a project. Also use
  when the user passes `--dry-run` to preview what would be created without
  writing any files. Make sure to use this skill before any other `/forge:*`
  command if `pipeline/` doesn't exist yet.
allowed-tools: [Read, Write, Bash, Glob]
---

# forge-init

## When to Use

Use this skill whenever the user wants to:

- Start using Forge in a project
- Initialize the Forge pipeline in a new or existing project
- Says "init", "initialize", "set up Forge", or "start using Forge"
- Describes starting a new project they want orchestrated
- Passes `--dry-run` to preview what would be created without writing files

## Steps

1. Parse `$ARGUMENTS` for `--dry-run`. If present, set `DRY_RUN=true`. If the user passed `--type <profile>`, capture that as `OVERRIDE_TYPE`.
2. **If `DRY_RUN`**:
   - Run `bash ${CLAUDE_PLUGIN_DIR}/scripts/init-pipeline.sh --dry-run`
   - Present the plan verbatim. The final line reads "Re-run without --dry-run to apply."
   - **Stop here. Do not proceed to step 3 or any subsequent step.** Wait for the user to explicitly confirm they want to apply the plan before doing the real init.
3. Run the real init in manifest mode to capture what was created:
   - `bash ${CLAUDE_PLUGIN_DIR}/scripts/init-pipeline.sh --manifest-only`
   - The manifest is JSON: `{dry_run: false, root: "<abs path>", created: [...], skipped: [...]}`
   - Parse the JSON. The `created` array length tells you how many files were written; the `skipped` array shows pre-existing files that were left alone.
4. Detect the project type (skip if `OVERRIDE_TYPE` was set):
   - Run `python3 ${CLAUDE_PLUGIN_DIR}/scripts/detect-project-type.py --cwd .`
   - The output is JSON with a `project_type` (or `assigned_profile`) field, plus a `confidence` score and `indicators` list.
   - **If the response contains `suggested_profile` instead of `assigned_profile`** (this happens for the `script` profile, which is opt-in only), prompt the user: *"This looks like a small script (under 500 LOC, no package manifest). Forge has a streamlined `script` profile (4 active stages instead of 12). Use it, or the full pipeline?"* — and use the user's choice.
   - **If confidence < 0.7**, ask the user: *"I detected `[type]` (confidence [N]%) based on `[indicators]`. Does that sound right, or would you like to pick a different profile?"*
   - Available types: `ml-pipeline`, `fullstack`, `api`, `cli`, `library`, `script`, `unknown`.
5. Write the detected (or user-confirmed) type into `pipeline/state.md`:
   - `python3 ${CLAUDE_PLUGIN_DIR}/scripts/state-manager.py set --field project_type --value <type> --cwd .`
   - This is the only place project_type gets set on init; do not hand-edit the YAML frontmatter.
   - The assigned profile influences which lessons get surfaced at session start and which gate criteria apply.
6. Check `.gitignore` for `.forge/`:
   - Read `.gitignore` if it exists.
   - If `.forge/` (or `.forge`) is NOT already on a non-commented line, ask the user: *"`.forge/` holds runtime state — lessons, session logs, hook errors. It's typically noise to commit. Add `.forge/` to .gitignore? (y/N)"*
   - On yes (or "yes", "sure", "go ahead", etc.): append `.forge/` to `.gitignore`. If `.gitignore` doesn't exist, create it with just that line.
   - On no (or silence after a reasonable prompt): do nothing. Do not ask again in subsequent sessions.
7. Print a welcome message that includes:
   - How many files were created (from the manifest's `created.length`)
   - The assigned project type
   - Whether `.forge/` was added to `.gitignore`
   - The next suggested command (`/forge:srs` for a fresh project, `/forge:resume` if the user mentioned an existing pipeline)

## Verification

After running (in non-dry-run mode), confirm:

- `pipeline/state.md` exists with valid YAML frontmatter (`schema_version: 1`, `current_stage: 0`, `project_type: <not "unknown" if detected>`)
- `pipeline/01-srs/` through `pipeline/12-release/` all exist
- `tasks/todo.md` and `tasks/lessons.md` exist
- `.forge/lessons.yaml` and `.forge/patterns.jsonl` exist
- `.forge/sessions/` exists (with `.gitkeep`)
- If the user accepted the gitignore prompt, `.gitignore` contains `.forge/` on its own line
- The user knows the next command to run

In dry-run mode, confirm:

- No files exist that didn't exist before invocation
- The user has seen the full plan and the "Re-run without --dry-run to apply." line

## Examples

**User**: "Initialize Forge here"

**Claude**: [runs `bash ${CLAUDE_PLUGIN_DIR}/scripts/init-pipeline.sh --manifest-only` and parses the JSON; 18 files created]

[runs `python3 ${CLAUDE_PLUGIN_DIR}/scripts/detect-project-type.py --cwd .` and gets `{"project_type": "api", "confidence": 0.85, "indicators": ["fastapi in requirements.txt", "routes/ directory"]}`]

[runs `python3 ${CLAUDE_PLUGIN_DIR}/scripts/state-manager.py set --field project_type --value api --cwd .`]

[reads `.gitignore` and finds no `.forge/` entry]

"Initialized Forge pipeline. Detected project type: **api** (confidence 85% — based on fastapi in requirements.txt, `routes/` directory).

Created 18 files:
- `pipeline/` with 12 stage directories
- `pipeline/state.md` (initial state)
- `tasks/todo.md` and `tasks/lessons.md`
- `.forge/` for runtime memory

`.forge/` isn't in your `.gitignore` yet — it holds runtime state (lessons, sessions, hook errors) that's usually noise to commit. Want me to add it? (y/N)"

**User**: "yes"

**Claude**: [appends `.forge/` to `.gitignore`]

"Added `.forge/` to `.gitignore`. Next step: run `/forge:srs` to define requirements, or `/forge:resume` if you've worked on this before."

---

**User**: "/forge:init --dry-run"

**Claude**: [runs `bash ${CLAUDE_PLUGIN_DIR}/scripts/init-pipeline.sh --dry-run`]

```
would create: pipeline/01-srs/.gitkeep
would create: pipeline/02-product-ux/wireframes/.gitkeep
would create: pipeline/03-architecture/adr/.gitkeep
... (15 more lines)
─────────────────────────────────────────────────────────────
Forge pipeline plan:
  18 file(s) would be created
  target: /home/user/my-project

Re-run without --dry-run to apply.
```

"That's the plan — 18 files in `pipeline/`, `tasks/`, and `.forge/`. Nothing was created. Run `/forge:init` (without `--dry-run`) when you're ready, or tell me what you'd like to tweak first."

[STOP. Do not call init-pipeline.sh again without explicit user confirmation.]

---

**User**: "Set up Forge for this 200-line shell script project"

**Claude**: [runs `bash ${CLAUDE_PLUGIN_DIR}/scripts/init-pipeline.sh --manifest-only`; 18 files created]

[runs `python3 ${CLAUDE_PLUGIN_DIR}/scripts/detect-project-type.py --cwd .` and the response includes `"suggested_profile": "script"` because the repo is small and has no package manifest]

"This looks like a small script (under 500 LOC, no package manifest). Forge has a streamlined `script` profile that compresses the pipeline from 12 stages to 4 active ones (SRS-lite → Build → Eval → optional Release). Want to use it, or stick with the full pipeline?"

**User**: "use the script profile"

**Claude**: [runs `python3 ${CLAUDE_PLUGIN_DIR}/scripts/state-manager.py set --field project_type --value script --cwd .`]

[gitignore check, etc.]

"Done. Using the **script** profile — Stages 2, 5, 8, 9, 10, 11 are skipped; Stages 3, 4, 12 are optional. Next step: `/forge:srs` for a one-page requirements doc."

---

**User**: "init Forge but skip the gitignore stuff, I manage that elsewhere"

**Claude**: [runs init-pipeline.sh, detect-project-type.py, state-manager.py as normal]

[honors the user's request — skips step 6 entirely]

"Initialized Forge. 18 files created. Detected project type: **library**. Next step: `/forge:srs`."