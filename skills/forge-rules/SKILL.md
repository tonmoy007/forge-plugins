---
name: forge-rules
description: Set up and manage user-authored Forge rules — project constraints that steer
  Forge's agents (like Cursor .cursor/rules). Use whenever the user runs /forge:rules,
  says "set up rules", "add a project rule", "create a coding rule", "make Forge always
  do X", "enforce a convention", or wants to list/validate existing rules. Rules live in
  .forge/rules/*.md with a scope (always/stage/glob/manual) and are injected at session
  start and on matching file writes. If no rules dir exists, the feature is a clean no-op.
allowed-tools: [Read, Bash]
---

# forge-rules — author & manage project rules

User rules are Markdown files under `.forge/rules/*.md` with YAML frontmatter
(`description`, `scope`, `stages?`, `globs?`, `priority?`) + a body (the rule text). They
steer Forge's agents without changing code: Forge injects them into context at the right
moments. They are **advisory** — they never block a write (REQ-RULES-010).

## Scope model (mirrors Cursor project rules)

- `always` — injected every session (within the ≤2000-token context budget).
- `stage` — injected only when the pipeline is on a listed `stages:` number.
- `glob` — surfaced when writing a file matching `globs:` (advisory feedback).
- `manual` — never auto-injected; referenced explicitly by name.

## When to Use

- User runs `/forge:rules [init|list|add|validate]`.
- User wants Forge to "always"/"never" do something, or to enforce a convention
  scoped to a stage or a set of files.

## Subcommands

Scaffold the rules directory (idempotent — never clobbers existing files):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rules.py init --cwd .
```

Add a new rule (refuses to overwrite an existing file):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rules.py add <name> --scope <always|stage|glob|manual> --description "..." --cwd .
```

List the active rules / validate them:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rules.py list --cwd .
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rules.py validate --cwd .
```

## How to run

1. If the user is setting up rules for the first time, run `init`, then open the created
   `.forge/rules/00-style.md` and tailor it (or `add` a new rule).
2. For `add`, pick the scope from the user's intent: a blanket convention → `always`;
   tied to a phase (e.g. only during build/eval) → `stage` with `stages:`; tied to file
   types (e.g. UI files) → `glob` with `globs:`.
3. After writing/editing rule files, run `validate` and relay any `WARN` lines.
4. Tell the user where rules take effect: `always`/`stage` rules appear in the next
   session-start context block; `glob` rules surface as advisory feedback when a matching
   file is written. See `references/rules-format.md` for the full schema.

## Notes

- Rules are advisory and never block writes — they nudge, they don't gate.
- No `.forge/rules/` directory ⇒ the whole feature is a silent no-op (existing Forge
  behavior is unchanged).
- Rule injection shares the session-start token budget with lessons; keep rule bodies
  short and high-signal.
