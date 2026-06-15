# Rules Format — user-authored project rules (v0.3.0)

> Loaded on demand. Defines the `.forge/rules/*.md` surface that lets a user steer
> Forge's agents with project constraints (à la Cursor `.cursor/rules`). Parsed by
> `scripts/rules.py`; injected by `hooks/session-start.py` (always/stage) and
> `hooks/pre-tool-write.py` (glob). Authored/managed via `/forge:rules`.

## File shape

Each rule is one Markdown file in `.forge/rules/`, with YAML frontmatter + a body:

```markdown
---
description: short summary (shown in `/forge:rules list`)
scope: always | stage | glob | manual
stages: [6, 7]          # required for scope: stage
globs: ["**/*.tsx"]     # required for scope: glob
priority: 10            # optional; higher sorts first (default 0)
---
The rule text the agent should follow. Keep it short and high-signal — rule
injection shares the session-start ≤2000-token budget with lessons.
```

## Scopes

| scope | activates | injected by |
| --- | --- | --- |
| `always` | every session | `session-start.py` |
| `stage` | only when `current_stage ∈ stages` | `session-start.py` |
| `glob` | only on a `Write`/`Edit` to a file matching `globs` | `pre-tool-write.py` (advisory) |
| `manual` | never automatically; reference it by name | — |

## Matching & ordering

- **Globs** use stdlib `fnmatch` with sensible `**` handling: `**/*.tsx` matches both
  `app/Button.tsx` (nested) and `Button.tsx` (root); a slashless pattern (`*.py`) matches
  by basename. Paths are normalized to `/`.
- **Ordering** is `priority` descending, then file name. Lower-numbered file prefixes
  (`00-`, `10-`) are a convenient secondary sort.

## Guarantees (the non-negotiables)

- **Advisory, never blocking.** `glob` rules surface as `additionalContext` on a write;
  they never block it (exit 0), exactly like the design-system check.
- **Fail-soft, never raises.** A malformed file (bad YAML, missing/unknown `scope`, e.g.
  the `README.md`) is skipped; an absent `.forge/rules/` directory makes the whole feature
  a clean no-op.
- **Budget-bounded.** Session-start injects `always` + current-`stage` rules within the
  ≤2000-token context budget (REQ-NF-011); rules are trimmed before lessons.
- **No third-party deps.** Frontmatter is parsed with a stdlib fence splitter + PyYAML
  (read fail-soft). No `frontmatter` package (lesson 2026-05-24).

## CLI (used by `/forge:rules`)

```bash
python3 scripts/rules.py init      --cwd .   # scaffold .forge/rules/ (idempotent)
python3 scripts/rules.py add NAME  --cwd . --scope glob --description "..."
python3 scripts/rules.py list      --cwd .
python3 scripts/rules.py validate  --cwd .   # reports issues; exit 0 unless usage error
```

## Relationship to other Forge mechanisms

- **Lessons** (`tasks/lessons.md`) are *learned* corrections injected the same way; rules
  are *authored* constraints. They coexist in the session-start block.
- **Gates** (`references/gate-criteria.md`) are *blocking* stage-exit checks; rules are
  *advisory* steering. Use a gate to enforce, a rule to nudge.
- **Profiles** (`references/project-type-profiles.md`) are Forge-authored per-type
  overrides; rules are the user's per-project layer on top.
