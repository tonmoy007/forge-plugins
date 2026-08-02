# Pattern Bus Schema (`.forge/patterns.jsonl`)

> Versioned schema for the pattern bus that feeds the skill-miner
> (REQ-PATTERN-001 / T-120). One JSON object per line. `post-tool-use.py` is the
> producer; `scripts/mine-skills.py` is the consumer.
>
> **Deprecated (v0.3.5, REQ-SM-010):** this n-gram pattern bus is the legacy v1
> path. The active skill-miner is now the semantic pipeline in
> `scripts/skill_miner_v2.py` (it consumes `.forge/session-log.jsonl`, not this
> bus). See `references/skill-mining.md`. This schema is retained for back-compat.

## Common envelope

Every record carries:

| Field            | Type    | Notes |
| ---------------- | ------- | ----- |
| `schema_version` | int     | Current schema version (**1**). Consumers ignore lines whose version they don't understand. |
| `ts`             | string  | ISO-8601 UTC timestamp (`YYYY-MM-DDTHH:MM:SSZ`). |
| `kind`           | string  | Record type — see below. |
| `session`        | string  | Session id (join key). No prompt content, no PII. |

## Record kinds

### `tool_seq_3` — repeated tool sequence (skill-mining signal)

A sliding window of the last 3 tool calls. The skill-miner aggregates these by
`signature`; a signature seen **≥ 3 times** (across ≥ 2 distinct sessions, span
≥ 60s — see `mine-skills.py` `_is_substantive`) triggers a SKILL.md draft proposal.

| Field       | Type        | Notes |
| ----------- | ----------- | ----- |
| `tools`     | string[3]   | Tool names in order (e.g. `["Read","Edit","Bash"]`). |
| `signature` | string      | `sha1("\|".join(tools))[:12]` — stable across calls. |

Example:

```json
{"schema_version":1,"ts":"2026-06-09T10:00:00Z","kind":"tool_seq_3","tools":["Read","Edit","Bash"],"signature":"a1b2c3d4e5f6","session":"s-1"}
```

## Versioning

- Bump `schema_version` on any breaking field change.
- Adding a new optional field or a new `kind` is backward-compatible (no bump).
- Consumers parse defensively: skip unparseable lines and unknown `kind`s rather
  than failing the whole read.

## Invariants (enforced by `tests/unit/test_pattern_bus.py`)

- Every line in `patterns.jsonl` parses as JSON and validates against this schema.
- A real session that uses ≥ 3 tools produces a non-empty `patterns.jsonl`.
- A signature repeated ≥ 3 times (substantive) fires a skill-miner proposal.
