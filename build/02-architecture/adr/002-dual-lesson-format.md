# ADR-002: Lessons Stored as Both Markdown and YAML

**Status**: Accepted
**Date**: 2026-05-05

## Context

Forge captures lessons across sessions and projects. Lessons must be:
1. **Human-readable** — users want to skim them, edit them, share them
2. **Machine-readable** — hooks need to filter by stage tags, project type, etc., quickly

A single format can't optimize both. Markdown is great for humans, terrible for filtering.
YAML is the inverse.

## Decision

Lessons are stored in **both** formats:

- **`tasks/lessons.md`** — canonical, human-edited, markdown
- **`.forge/lessons.yaml`** — derived, machine-read, regenerated on session start

The markdown is the source of truth. The YAML is a generated mirror.

## Rationale

**Why markdown is the source of truth**:
- Users edit it (add lessons, fix wording, delete bad lessons)
- It's the artifact that goes in PRs and code review
- It's what shows in IDE preview
- It's what users skim during retrospectives

**Why we need YAML at all**:
- Hooks (especially session-start.py) need to filter lessons by current stage tags + project type
- Filtering markdown requires parsing markdown headers + tag lines — fragile
- YAML parsing in Python is straight-line, fast, schema-checked

**Why regeneration on session start**:
- Markdown is always authoritative
- Regenerating ensures YAML never drifts
- ~50ms cost is acceptable; happens once per session, not per hook

## Consequences

**Positive**:
- Users have one place to edit (the markdown)
- Hooks have fast access (the YAML)
- No conflict resolution between formats
- Easy to validate sync (hash check)

**Negative**:
- Two files to track in git (markdown is committed; yaml is gitignored)
- Generation logic must be robust (a markdown parsing bug corrupts YAML)
- Brief window during regeneration where YAML might be stale (mitigated: atomic write)

## Alternatives Considered

1. **Markdown only**: rejected — hook latency from markdown parsing on every event is too high.

2. **YAML only**: rejected — users hate editing YAML for prose. Lessons have multi-sentence
   "why" sections that are awkward in YAML strings.

3. **JSON only**: same as YAML problem, plus no comments.

4. **SQLite**: rejected — adds a runtime dependency, not version-controllable in a
   diff-friendly way, overkill for the volume of data.

5. **Frontmatter-only markdown** (single file, parsed both ways): rejected — frontmatter is
   per-file, not per-lesson. Each lesson would need its own file → 100s of tiny files.

## Migration Path

If we need to change formats later (e.g., add per-lesson SQLite cache for full-text search):

1. Markdown stays the source of truth (don't break user workflow)
2. Add a new generated artifact alongside YAML
3. Hooks switch over once the new format is proven
4. Old YAML stays for backward compat one minor version, then removed

## Sync Mechanics

`scripts/sync-lessons.py` runs on `SessionStart`:

```python
def sync_lessons():
    md_path = Path("tasks/lessons.md")
    yaml_path = Path(".forge/lessons.yaml")

    md_hash = hash_file(md_path)
    yaml_meta = read_yaml_meta(yaml_path)

    if yaml_meta.get("source_hash") != md_hash:
        regenerate_yaml(md_path, yaml_path, source_hash=md_hash)
```

Atomic write: write to `.lessons.yaml.tmp`, fsync, rename.

## Schema

YAML schema is versioned (`schema_version: 1`). Migration scripts in `scripts/migrate/`
handle bumps. See `build/03-spec/technical-spec.md` §6 for the schema.
