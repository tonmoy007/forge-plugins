# ADR-009: Skill Recall Is a Symlink, Not a Copy

**Status**: Accepted
**Date**: 2026-06-22

## Context

The unified graduation layer ([ADR-008](008-graduation-layer.md)) promotes a project's
deliberately-mined, human-**approved** skills to a durable global store and recalls them
into other projects. Promotion copies the approved skill directory once into
`~/.forge/skills/<slug>/` and indexes it in `~/.forge/global-skills.yaml`.

**Recall** is the other half: at session-start, a graduated skill must become visible to
Claude Code in the current project. Claude Code discovers skills by directory — an approved
skill is installed at the discovered plugin `skills/<slug>/` path (`skill-approval.py
approve`). So recall has to make `~/.forge/skills/<slug>/` appear under that plugin
`skills/` path. The question: **copy** the directory in, or **symlink** it?

This is the highest-risk part of the layer (R-2): a project or plugin may already have its
own skill at the same slug, and recall must never clobber or shadow that real, possibly
locally-edited skill.

## Decision

**Recall symlinks `~/.forge/skills/<slug>` into the discovered plugin `skills/` path; it
never copies when it can symlink, never overwrites a real entry, and a project/plugin skill
of the same slug always wins.**

- **Single source of truth.** The graduated skill lives once under
  `~/.forge/skills/<slug>/`. Recall creates a directory **symlink**
  (`os.symlink(src, dest, target_is_directory=True)`) from the plugin `skills/<slug>` path
  to it. There is one copy to edit; an edit to the graduated skill propagates to every
  project that recalled it, and recall is cheap and reversible (remove the link).

- **Project/plugin-wins, never clobber.** Recall symlinks a global skill **only** when no
  same-slug entry already exists at the plugin path: if `dest.is_symlink() or dest.exists()`
  it is **skipped**. A real project/plugin skill (or an already-present recall symlink) is
  left exactly as-is. Recall never deletes or overwrites a file, and never follows a link
  into deleting a project/plugin skill.

- **Idempotent.** A second recall with the link already present is a no-op (`dest` exists →
  skipped), so repeated session-starts add and remove no symlink (AC-GR-007).

- **TTL-filtered.** Global skills whose `last_used` is older than the shared 30-day
  `is_stale` TTL are not surfaced at recall (REQ-NF-035).

- **Copy fallback on platforms that cannot symlink.** If `os.symlink` raises (`OSError` /
  `NotImplementedError` / `ValueError` — e.g. Windows without privilege), recall **degrades
  to a guarded `shutil.copytree`** into the same destination; if even that fails it logs and
  moves on. Recall **never raises** (REQ-NF-034).

## Rationale

1. **One source of truth beats N drifting copies.** A symlink means a graduated skill is
   edited and reasoned about in exactly one place; copies would diverge per project and the
   global store would stop being authoritative.
2. **Cheap and reversible.** Recall is a single `os.symlink`; "un-recalling" is removing a
   link. No bytes are duplicated per project.
3. **No-clobber is the safety property.** Skipping when any same-slug entry exists is what
   makes project/plugin-wins true and guarantees recall can never damage a user's own skill
   (R-2; AC-GR-002 asserts no clobber).
4. **Fail-soft keeps a symlink-hostile platform working.** The copy fallback means a
   platform that cannot symlink still recalls the skill (degraded to a copy) instead of
   erroring — consistent with the never-raises discipline.

## Alternatives considered

- **Copy the directory in (no symlink).** Rejected as the primary path: duplicates bytes per
  project and lets recalled copies drift from the global source of truth. Kept only as the
  fail-soft fallback where symlinking is unavailable.
- **Overwrite / merge a same-slug project skill.** Rejected outright: it would silently
  replace a user's own, possibly locally-edited skill. Project/plugin always wins.
- **Recall via a search-path overlay (as workflows do) instead of materializing.** Rejected
  for skills: Claude Code discovers skills by directory under the plugin `skills/` path, so a
  loader-style search-path overlay (the workflow approach) does not apply — the skill must
  physically appear at that path, hence symlink-or-copy.

## Consequences

- Recall lives in `_graduation_skills.SkillTier.recall`; the symlink/copy/no-clobber/TTL
  logic is there, exercised by `tests/unit/test_graduation_skills.py`.
- Removing a graduated skill from `~/.forge/skills/` breaks any recall symlinks pointing at
  it (dangling links); the layer treats `~/.forge` as durable user-owned state and does not
  garbage-collect project symlinks.
- Workflows recall differently — by **search path**, not symlink — because the workflow loader
  resolves by enumerating directories; see [ADR-008](008-graduation-layer.md) and
  [`references/graduation-layer.md`](../../../references/graduation-layer.md).
