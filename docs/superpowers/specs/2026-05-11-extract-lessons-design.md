# Design: extract-lessons.py (T-019)

**Date**: 2026-05-11  
**Task**: T-019  
**REQ-IDs**: REQ-052

---

## Purpose

Parse `.forge/correction-flags.jsonl` (written by `hooks/prompt-submit.py` on every user
correction) and emit structured lesson entries appended to `tasks/lessons.md`.

Offline mode (rule-based) is the primary and always-available path. An optional `--llm`
flag routes through `_invoke_agent.py` (lesson-extractor persona) when available.

---

## CLI Interface

```
python3 scripts/extract-lessons.py \
  --input .forge/correction-flags.jsonl \
  --output tasks/lessons.md \
  [--dry-run]           # print without writing
  [--since YYYY-MM-DD]  # skip flags older than this date
  [--llm]               # use _invoke_agent.py (stub today, real when wired)
```

Exits 0 in all normal cases. Exits non-zero only on unrecoverable I/O errors.

---

## Data Structures

**Input** (one JSON object per line in correction-flags.jsonl):
```json
{"ts": "2026-05-11T09:00:00Z", "session": "abc123", "prompt": "don't use subprocess here, use importlib.util instead"}
```

**Internal types**:
```python
@dataclass
class CorrectionFlag:
    ts: str       # ISO-8601 timestamp
    session: str
    prompt: str   # raw correction text, ≤200 chars

@dataclass
class Lesson:
    date: str     # YYYY-MM-DD
    title: str    # ≤60 chars, imperative
    trigger: str  # "When ..."
    rule: str     # the actionable rule
    why: str      # failure mode prevented
    tags: list[str]
```

**Output** (appended to tasks/lessons.md after `## Lessons` header):
```markdown
### YYYY-MM-DD — <title>
- **Trigger**: <trigger>
- **Rule**: <rule>
- **Why**: <why>
- **Tags**: [<tag1>, <tag2>]
```

---

## Data Flow

```
.forge/correction-flags.jsonl
    ↓ parse_flags(path, since=None) → list[CorrectionFlag]
    ↓ deduplicate against existing ### headings in tasks/lessons.md
    ↓ extract_lesson(flag, use_llm=False) → Lesson | None
    ↓ format_lesson(lesson) → markdown str
    ↓ append_lessons(output_path, lessons)   ← atomic write
```

---

## Rule-Based Extraction

Patterns applied in order to the `prompt` string:

| Pattern | Maps to |
|---------|---------|
| `"don't X"` / `"never X"` / `"stop X"` | Rule: "Don't X" |
| `"always X"` / `"use X"` / `"prefer X"` | Rule: "Always X" |
| `"X instead of Y"` / `"use X not Y"` | Rule: "Use X, not Y" |
| Clause containing `"because"` / `"otherwise"` | → Why field |
| Filenames (`.py`, `.md`, `.json`, `.sh`) in prompt | → Tags |
| Keywords: `test`, `hook`, `script`, `yaml`, `git`, `python` | → Tags |

**Title**: First imperative clause, stripped and truncated to 60 chars.

**Trigger**: Words before the correction keyword, prefixed with "When "; falls back to
`"When this pattern occurs"`.

**Why**: Extracted from consequence phrases; falls back to `"Prevents repeating this mistake"`.

Returns `None` if no correction pattern is detected — that flag is silently skipped.

---

## LLM Path

When `--llm` is passed:
1. Call `_invoke_agent.py` with persona `lesson-extractor` and the raw prompt as input.
2. Parse the agent response as a `Lesson` dict.
3. On empty response or any error → fall back to rule-based silently.

Today `_invoke_agent.py` is a stub (returns empty). The interface is wired; behaviour
improves automatically when the stub is replaced in a future task.

---

## Deduplication

Before emitting lessons:
1. Load all existing `### ` headings from `tasks/lessons.md` (the part after `— `).
2. For each candidate lesson title, compute `difflib.SequenceMatcher` ratio against every
   existing title (both lowercased, stripped).
3. Skip the candidate if any ratio ≥ 0.8.

---

## Error Handling

| Situation | Behaviour |
|-----------|-----------|
| `--input` file missing | Exit 0 silently (no flags yet is normal) |
| Malformed JSONL line | `logging.warning`, skip line, continue |
| `--output` file missing | Create fresh with standard header |
| Write failure | Propagate exception (non-zero exit) |

---

## Testing Plan

~25 tests in `tests/unit/test_extract_lessons.py`:

- `parse_flags`: valid JSONL, malformed line skipped, `--since` filter
- `extract_lesson`: "don't X", "always X", "use X instead of Y", Why extraction,
  unrecognisable prompt → `None`
- `deduplicate`: exact title skipped, similar title (ratio ≥ 0.8) skipped, new title passes
- `format_lesson`: output matches `tasks/lessons.md` markdown format exactly
- `append_lessons`: dry-run no write, real write appends after `## Lessons`
- End-to-end: sample correction-flags.jsonl fixture → valid lesson in output file

---

## Done-When Criterion

Run against a fixture file containing:
```json
{"ts": "2026-05-11T09:00:00Z", "session": "test", "prompt": "don't use subprocess here, use importlib.util instead because Python can't import hyphenated filenames"}
```

Expected output appended to `tasks/lessons.md`:
```markdown
### 2026-05-11 — Don't use subprocess; use importlib.util instead
- **Trigger**: When this pattern occurs
- **Rule**: Don't use subprocess; use importlib.util instead
- **Why**: Python can't import hyphenated filenames
- **Tags**: [python]
```
