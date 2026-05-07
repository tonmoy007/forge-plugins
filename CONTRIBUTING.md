# Contributing to Forge

> A full contributing guide will be written as part of T-031 (after the plugin works).
> For now, here's the short version.

## Development Workflow

See `DEVELOPMENT.md` for the full workflow. The short version:

1. Pick the next 🔲 task from `build/05-implementation/progress.md`
2. Read its prompt at `prompts/development/T-XXX-*.md` (write one if missing)
3. Run the prompt through Claude Code
4. Verify, commit with task ID, update progress

## Adding a New Stage Agent

1. Update `build/01-srs/srs.md` — add the requirement
2. Update `build/02-architecture/architecture.md` — add to agent registry
3. Update `build/03-spec/technical-spec.md` — specify contract
4. Update `build/04-plan/task-dag.md` — add tasks
5. Create `prompts/agents/<agent-name>.md` — development prompt
6. Then start the actual work (writing the persona, the skill, etc.)

## Code Style

- Python: type hints on public functions, dataclasses for structured data
- Markdown: 100-char soft line limit, code blocks tagged with language
- Commits: `<type>(T-XXX): <subject>` referencing task ID

## Testing

- Unit tests for every script and hook
- Integration tests for hook/skill flows
- E2E test for the full pipeline (`tests/integration/full-pipeline.sh`)

## Pull Requests

- One PR per task (or per logical milestone)
- PR description references T-IDs and REQ-IDs
- All tests must pass
- Update CHANGELOG if user-visible
