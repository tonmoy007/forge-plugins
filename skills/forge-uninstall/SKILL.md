---
name: forge-uninstall
description: Remove Forge filesystem state from the current project, and optionally
  global state, with a mandatory preview step before any deletion. Use this skill
  whenever a user types `/forge:uninstall`, says "remove Forge", "I want to uninstall
  this plugin", "clean up Forge files", "delete pipeline/", expresses frustration
  suggesting they may give up on Forge, or asks to start over from scratch. Make
  sure to ALWAYS run with `--dry-run` first and present the plan to the user;
  NEVER proceed to actual removal without an explicit user confirmation in the
  same turn. This skill does NOT unregister the plugin from Claude Code itself —
  always remind the user to run `/plugin uninstall forge@forge-plugins` as a
  separate step after filesystem removal.
allowed-tools: [Bash]
---

# Forge Uninstall

Removes Forge filesystem state — `pipeline/` artifacts, `.forge/` runtime state, and
optionally `~/.forge/` global lessons — from the user's project. Does **not** remove the
Claude Code plugin registration; that's a separate `/plugin uninstall` action.

## When to Use

- User types `/forge:uninstall` or `/forge:remove`
- User says "uninstall Forge", "remove Forge from this project", "I want to start over"
- User says "clean up Forge files", "remove .forge/", "delete pipeline/"
- User is frustrated and considering abandoning Forge — offer this as a clean exit
- User wants to migrate a project away from Forge while keeping the SDLC documents
- User asks "how do I undo `/forge:init`?"

## Steps

1. **Always preview first.** Run a dry-run BEFORE any destructive action:
   ```bash
   python ${CLAUDE_PLUGIN_DIR}/scripts/uninstall.py --dry-run --cwd "<project>"
   ```
2. Present the full plan output **verbatim** to the user. Do not paraphrase what will
   be removed; the user needs to see the exact paths, file counts, and sizes
3. Ask for an explicit confirmation: "Should I proceed with removal? Reply 'yes' to
   confirm, or tell me to keep artifacts / include global state if those apply."
4. Only after the user replies with an unambiguous yes (or equivalent — "do it",
   "go ahead", "remove it"), run the actual removal:
   ```bash
   python ${CLAUDE_PLUGIN_DIR}/scripts/uninstall.py --cwd "<project>" --yes
   ```
5. If the user said "keep my SRS / specs / pipeline files", add `--keep-artifacts`.
   This preserves `pipeline/` and only removes `.forge/`
6. If the user wants to also wipe `~/.forge/` (lessons across ALL their Forge projects),
   add `--include-global`. **Confirm this separately** — it affects projects other than
   the current one
7. After the script completes, ALWAYS remind the user of the two follow-up steps:
   - `/plugin uninstall forge@forge-plugins` — unregister the plugin from Claude Code
   - To reinstall later: `/plugin marketplace add tonmoy007/forge-plugins && /plugin install forge@forge-plugins`

## Verification

After running, all of these should be true:
- A dry-run plan was shown to the user before any destructive action
- The user explicitly confirmed the removal in plain language
- `<project>/.forge/` no longer exists
- `<project>/pipeline/` either no longer exists, or was preserved (if `--keep-artifacts`)
- The user has been told that the plugin itself remains registered in Claude Code until
  they run `/plugin uninstall forge@forge-plugins`
- The user has the reinstall command in case they want to come back later

## Examples

**User**: "I want to uninstall Forge from this project"

**Claude**: [runs `python ${CLAUDE_PLUGIN_DIR}/scripts/uninstall.py --dry-run --cwd "$(pwd)"`]

"Here's what would be removed:

```
Forge uninstall — plan
======================

Will remove:
  • /home/user/proj/.forge
      Forge runtime state (sessions, lessons.yaml, hook errors)
      14 files, 132.5 KB
  • /home/user/proj/pipeline
      Pipeline artifacts (srs.md, prd.md, arch.md, etc.)
      37 files, 1.2 MB
```

Proceed with removal? Reply 'yes' to confirm. If you'd like to keep your SRS / specs /
architecture documents (and only remove the runtime), say 'keep artifacts'."

**User**: "yes, but keep my SRS"

**Claude**: [runs `python ${CLAUDE_PLUGIN_DIR}/scripts/uninstall.py --cwd "$(pwd)" --yes --keep-artifacts`]

[Presents the output verbatim, including the next-steps reminder]

"Done. Two more things:
1. To fully remove the plugin from Claude Code: `/plugin uninstall forge@forge-plugins`
2. If you change your mind later: `/plugin marketplace add tonmoy007/forge-plugins`
   then `/plugin install forge@forge-plugins`"

---

**User**: "I'm done with Forge across all my projects"

**Claude**: "Before I do this, I want to be explicit — you've asked for two things:
1. Remove Forge state from this project (`.forge/` and `pipeline/`)
2. Remove cross-project lessons in `~/.forge/` (affects ALL your Forge projects, not
   just this one)

Both are destructive. Let me preview both:" [runs `--dry-run --include-global`]
"...
Proceed with all of this? I'd also recommend backing up `~/.forge/global-lessons.yaml`
first if there's anything in there you want to keep."