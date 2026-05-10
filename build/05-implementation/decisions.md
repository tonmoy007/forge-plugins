# Implementation Decisions Log

> Append-only log of decisions made during implementation.
> Every non-trivial choice gets an entry. Future sessions read this to understand why
> things are the way they are.

## Format

```markdown
## YYYY-MM-DD T-XXX — <decision title>

**Context**: <what we were doing, what choice came up>

**Decision**: <what we chose>

**Why**: <reasoning>

**Alternatives considered**: <what we didn't pick and why>

**Consequences**: <what this means for future work>
```

---

## Decisions

## 2026-05-10 T-003 — Normalize PyYAML datetime objects on state load

**Context**: `python-frontmatter` uses PyYAML under the hood. PyYAML automatically parses
bare ISO-8601 timestamps (e.g. `last_updated: 2026-05-07T12:00:00Z`) as Python `datetime`
objects. This caused `validate_frontmatter` (which requires `str` for `last_updated`) to
reject the round-trip `read_state → write_state` with "got datetime".

**Decision**: Added `_normalize_metadata(metadata)` in `_state_lib.py` that converts any
`datetime.datetime` or `datetime.date` values to ISO strings immediately after loading.
Applied in `read_state` and `write_state`.

**Why**: Callers always see `last_updated` as a string, matching the schema contract and
making the round-trip safe. The alternative (widening `REQUIRED_FIELDS["last_updated"]` to
accept both `str` and `datetime`) would leak the PyYAML implementation detail into the API.

**Alternatives considered**: Widening the type union — rejected because it would require
callers to handle two types. Using PyYAML's `safe_load` with a string-only loader — rejected
because `python-frontmatter` doesn't expose that easily.

**Consequences**: All consumers of `read_state` always receive strings. If a field is ever
intentionally typed as `datetime` in the schema, `_normalize_metadata` would need updating.
