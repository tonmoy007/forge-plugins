---
name: forge-set-profile
description: Switch the project-type profile for a Forge-managed project. Use whenever
  the user runs /forge:set-profile, wants to change or correct the detected project type
  (e.g. "set the profile to monorepo", "this is actually a mobile app, fix the type",
  "change project_type to data-contract"), or when auto-detection picked the wrong
  profile. Pass the target type as the argument; pass --dry-run to preview without writing.
allowed-tools: [Read, Bash]
---

# forge-set-profile

Override the auto-detected project type. The profile drives stage emphasis, design-system
mode, and the additional gate criteria applied across the pipeline, so correcting it
changes how later stages behave.

## When to Use

- User runs `/forge:set-profile <type>`
- Auto-detection (`detect-project-type.py`) chose the wrong profile
- The project changed shape (e.g. a CLI grew into a fullstack app)
- User says "set/change the profile", "this is actually a <type>", "fix the project type"

## Valid profiles

`api`, `fullstack`, `ml-pipeline`, `cli`, `library`, `monorepo`, `mobile`,
`data-contract`, `script`, `unknown` — defined in
`references/project-type-profiles.md`. An unknown name is rejected with the valid list.

## How to run

Preview first if the user is unsure:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/set-profile.py <type> --cwd . --dry-run
```

Apply the change:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/set-profile.py <type> --cwd .
```

The script validates `<type>`, then updates `project_type` in `pipeline/state.md`
atomically (validated frontmatter, body preserved). It reports the old → new value, or
"no change" if already set. Relay that result to the user, and note that the new profile
takes effect on the next stage that reads it.
