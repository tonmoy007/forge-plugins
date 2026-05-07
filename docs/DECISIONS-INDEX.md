# Decisions Index

> Index of all architectural and implementation decisions.
> ADRs (architecture-level) live in `build/02-architecture/adr/`.
> Implementation-level decisions live in `build/05-implementation/decisions.md`.

## Architecture Decision Records

| ID | Title | Status | Date |
|----|-------|--------|------|
| [001](../build/02-architecture/adr/001-python-hooks.md) | Python (not Bash) for hooks | Accepted | 2026-05-05 |
| [002](../build/02-architecture/adr/002-dual-lesson-format.md) | Lessons in both Markdown and YAML | Accepted | 2026-05-05 |
| [003](../build/02-architecture/adr/003-cross-stage-agents.md) | Cross-stage agents are hook-triggered | Accepted | 2026-05-05 |
| [004](../build/02-architecture/adr/004-stop-hook-sequential.md) | Stop hook runs sequential pipeline | Accepted | 2026-05-05 |

## Implementation Decisions

See `build/05-implementation/decisions.md` for chronological log.

These are recorded by Claude during implementation. Examples of what goes there:
- Choice of `python-frontmatter` vs alternatives for state.md parsing
- Specific regex patterns for design system token detection
- Frequency thresholds for skill mining (3 vs 5)
- Reflection length budgets (50 words light, 250 medium, 500 deep)

## Adding a New ADR

When you make a non-trivial architecture decision:

1. Copy `build/02-architecture/adr/_template.md` (create if missing)
2. Number sequentially (ADR-005, etc.)
3. Fill in: Status, Date, Context, Decision, Rationale, Consequences, Alternatives
4. Add an entry to this index
5. Reference the ADR from related code/docs

## Adding an Implementation Decision

For smaller decisions made during a task:

1. Append to `build/05-implementation/decisions.md`
2. Use the standard format (date, T-ID, title, context, decision, why, alternatives, consequences)
3. No need to create a separate file — the chronological log is fine
4. If a decision turns out to be major (other code depends on it), promote to an ADR
