# Large Document Split Convention (REQ-LARGEDOC-001)

> When a stage document (SRS, architecture, spec, …) grows past a comfortable
> reading size, split it into a directory with a manifest instead of one giant
> file. Downstream stages locate sections via the manifest, never by guessing
> filenames. Backward-compatible: the single-file layout keeps working.

## The two layouts

**Single-file (default, legacy-compatible):**

```
pipeline/04-spec/technical-spec.md
```

**Multi-file (for large documents):**

```
pipeline/04-spec/technical-spec/
├── index.md            ← manifest: lists the parts, in order
├── 01-overview.md
├── 02-interfaces.md
└── 03-data-contracts.md
```

The directory is named exactly like the single-file document **without** the
`.md` extension (`technical-spec.md` → `technical-spec/`).

## The manifest (`index.md`)

`index.md` lists the parts in reading order. Any markdown that references the
part filenames works; an ordered list is the conventional form:

```markdown
# Technical Spec — manifest

1. [Overview](01-overview.md)
2. [Interfaces](02-interfaces.md)
3. [Data contracts](03-data-contracts.md)
```

Rules:
- Parts are read in the order they appear in `index.md`.
- `index.md` itself is not a content part (it's the table of contents).
- A part not listed in the manifest is ignored (sort-order fallback only applies
  when the manifest lists nothing usable).

## Reading either layout

Use `scripts/read-doc.py` — it resolves whichever layout is present and prints
the concatenated content (manifest order for multi-file):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/read-doc.py pipeline/04-spec/technical-spec
```

The `.md` suffix is optional; the resolver tries `<base>.md` first, then
`<base>/index.md`. Consumers (e.g. `/forge:spec`, downstream stages) should read
documents through this resolver rather than opening a hard-coded `.md` path, so a
document can be split later without breaking readers.

## Validation

`tests/unit/test_large_doc.py` asserts both layouts resolve, manifest order is
honored, and a missing document reports not-found.
