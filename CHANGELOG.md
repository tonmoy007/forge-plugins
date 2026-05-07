# Changelog

All notable changes to Forge are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Status
Pre-alpha — repository scaffolded, build artifacts complete, implementation pending.

### Added (Repository Scaffolding)
- `CLAUDE.md` — Claude's operating manual for working in this repo
- `README.md`, `DEVELOPMENT.md`, `ROADMAP.md`, `CONTRIBUTING.md`
- `build/01-srs/srs.md` — full SRS with REQ-001 through REQ-092
- `build/02-architecture/architecture.md` — component map, hook registry, memory tiers
- `build/02-architecture/adr/` — ADRs 001–004 (Python hooks, dual lessons, cross-stage agents, sequential Stop)
- `build/03-spec/technical-spec.md` — implementation-ready specs for all hooks and scripts
- `build/04-plan/task-dag.md` — 33 tasks across 7 milestones with dependencies
- `build/05-implementation/{progress,decisions}.md` — tracking templates
- `references/` — claude-code-hooks, skill-format, agent-format, gate-criteria, project-type-profiles, pipeline-stages
- `prompts/development/` — detailed prompts for T-001, T-002, T-003 + template + index
- `prompts/agents/` — persona prompts for requirements-analyst, builder, reflector
- `prompts/sessions/` — bootstrap and resume prompts
- `examples/sample-todo-api/` — e2e test fixture
- `.github/workflows/tests.yml` — CI scaffolding
- `requirements.txt`, `.gitignore`, `LICENSE`

### Pending Implementation
- All tasks in `build/04-plan/task-dag.md` from T-001 through T-033
- Plugin code itself (hooks, skills, agents, scripts)
- See `build/05-implementation/progress.md` for live status

---

## [0.1.0] — Future (M7 complete)

First user-installable release. To be filled in when T-033 lands.
