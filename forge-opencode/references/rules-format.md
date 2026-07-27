# Rules Format — user-authored project rules (v0.3.0; enforcing rules added v0.3.3)

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
enforce: false          # optional; scope: glob only — true BLOCKS a matching write
severity: error         # optional; surfaced in the block message (default error)
---
The rule text the agent should follow. Keep it short and high-signal — rule
injection shares the session-start ≤2000-token budget with lessons.
```

## Scopes

| scope | activates | injected by |
| --- | --- | --- |
| `always` | every session | `session-start.py` |
| `stage` | only when `current_stage ∈ stages` | `session-start.py` |
| `glob` | only on a `Write`/`Edit` to a file matching `globs` | `pre-tool-write.py` (advisory, or **blocking** with `enforce: true`) |
| `manual` | never automatically; reference it by name | — |

## Enforcing rules (v0.3.3, REQ-AUTO-006)

A `glob` rule with `enforce: true` is a **governance guardrail**: a `Write`/`Edit` to a
matching path is **blocked** (`pre-tool-write` exits 2) and the rule text is surfaced as
the denial reason. This is the safety counterpart to autopilot's `--unattended` mode —
use it to fence off paths an autonomous run must not touch:

```markdown
---
description: Lockfiles and secrets are off-limits to autonomous runs
scope: glob
globs: ["**/*.lock", "**/*.env", "**/secrets/**"]
enforce: true
severity: error
---
Do not modify dependency lockfiles or secret material. Surface the need to a human instead.
```

- `enforce` only takes effect on `scope: glob` (there is nothing to match a file against
  otherwise); `validate` warns if you set it elsewhere.
- Blocking is by **path match** — the guardrail protects whole paths, it does not inspect
  content. Pair it with a gate or a human checkpoint for semantic checks.
- Omit `enforce` (or set it `false`) to keep the v0.3.0 **advisory** behavior.

## Matching & ordering

- **Globs** use stdlib `fnmatch` with sensible `**` handling: `**/*.tsx` matches both
  `app/Button.tsx` (nested) and `Button.tsx` (root); a slashless pattern (`*.py`) matches
  by basename. Paths are normalized to `/`.
- **Ordering** is `priority` descending, then file name. Lower-numbered file prefixes
  (`00-`, `10-`) are a convenient secondary sort.

## Guarantees (the non-negotiables)

- **Advisory by default.** `glob` rules surface as `additionalContext` on a write and
  never block it (exit 0), exactly like the design-system check — **unless** they opt in
  with `enforce: true`, the one sanctioned blocking path (see "Enforcing rules").
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
  *advisory* steering by default. Use a gate to enforce stage exit, a rule to nudge — or
  an `enforce: true` glob rule to hard-block writes to specific paths.
- **Profiles** (`references/project-type-profiles.md`) are Forge-authored per-type
  overrides; rules are the user's per-project layer on top.
