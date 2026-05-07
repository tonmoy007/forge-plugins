# T-XXX: <Title>

> **Template** — use this format for every development prompt.
> Copy this file to `prompts/development/T-XXX-<short-name>.md` and fill in.

## Context

<What you should know before starting. Reference specific sections of:>
- `CLAUDE.md` — relevant principles
- `build/01-srs/srs.md` — REQ-IDs satisfied by this task
- `build/02-architecture/architecture.md` — component context
- `build/03-spec/technical-spec.md` — exact specifications
- `tasks/lessons.md` — any prior lessons that apply
- Prior task outputs (e.g., "T-003 produced `_state_lib.py` which you'll import")

<What this task does NOT include — so Claude doesn't scope-creep.>

## Task

<Concrete steps. Each step should be verifiable.>

**Files to create**:
1. `path/to/file.py` — what it does
2. `path/to/test.py` — what it tests

**Files to modify**:
- `path/to/existing.py` — what changes

## Definition of Done

- [ ] Specific testable criteria
- [ ] One per line
- [ ] Each must be verifiable from the verification commands

## Verification

```bash
# Concrete commands that prove the task is done.
# These get pasted into the terminal — they should work as-is.
```

## Commit

```
<type>(T-XXX): <subject>

<body explaining why>

Ref: T-XXX
REQ: <REQ-IDs>
```

## Update Trail

After committing:
1. `build/05-implementation/progress.md` → mark task done, set new current task
2. `tasks/todo.md` → archive this task, activate next
3. `tasks/lessons.md` → add any lessons learned
4. `build/05-implementation/decisions.md` → add any ADR-worthy decisions

## Notes

<Gotchas, alternative approaches considered, links to relevant docs>
