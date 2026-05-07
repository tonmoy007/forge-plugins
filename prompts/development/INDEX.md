# Development Prompts Index

> One prompt per task in the DAG.
> Detailed prompts exist for the early critical-path tasks (T-001, T-002, T-003).
> Later tasks have stub prompts to be expanded as we approach them — when context is fresh
> we can write a better prompt than guessing 30 tasks out.

| Task | File | Status |
|------|------|--------|
| T-001 Plugin scaffolding | `T-001-scaffold.md` | ✅ ready |
| T-002 forge-init skill | `T-002-forge-init.md` | ✅ ready |
| T-003 state-manager.py | `T-003-state-manager.md` | ✅ ready |
| T-004 forge-status skill | `T-004-forge-status.md` | 🔲 stub (write before T-003 done) |
| T-005 gate-criteria.md | `T-005-gate-criteria.md` | 🔲 stub |
| T-006 check-gate.py | `T-006-check-gate.md` | 🔲 stub |
| T-007 session-start.py | `T-007-session-start-hook.md` | 🔲 stub |
| T-008 prompt-submit.py | `T-008-prompt-submit-hook.md` | 🔲 stub |
| T-009 stop-reflect.py | `T-009-stop-reflect-hook.md` | 🔲 stub (large — write a careful one) |
| T-010 session-end.py | `T-010-session-end-hook.md` | 🔲 stub |
| T-011 pre-tool-write.py | `T-011-pre-tool-write-hook.md` | 🔲 stub |
| T-012 post-tool-use.py | `T-012-post-tool-use-hook.md` | 🔲 stub |
| T-013 wire hooks | `T-013-wire-hooks.md` | 🔲 stub |
| T-014 stage agent personas | `T-014-stage-agents.md` | 🔲 stub (large — split into 12) |
| T-015 stage skill files | `T-015-stage-skills.md` | 🔲 stub |
| T-016 cross-stage agents | `T-016-cross-stage-agents.md` | 🔲 stub |
| T-017 context-pruner.py | `T-017-context-pruner.md` | 🔲 stub |
| T-018 forge-resume skill | `T-018-forge-resume.md` | 🔲 stub |
| T-019 extract-lessons.py | `T-019-extract-lessons.md` | 🔲 stub |
| T-020 lesson injection | `T-020-lesson-injection.md` | 🔲 stub |
| T-021 lessons.yaml mirror | `T-021-lessons-yaml.md` | 🔲 stub |
| T-022 cross-project memory | `T-022-cross-project-memory.md` | 🔲 stub |
| T-023 project type detection | `T-023-project-type-detection.md` | 🔲 stub |
| T-024 project-type-profiles.md | `T-024-project-profiles.md` | 🔲 stub |
| T-025 wire profiles | `T-025-wire-profiles.md` | 🔲 stub |
| T-026 pattern tracker | `T-026-pattern-tracker.md` | 🔲 stub |
| T-027 mine-skills.py | `T-027-mine-skills.md` | 🔲 stub |
| T-028 skill approval flow | `T-028-skill-approval.md` | 🔲 stub |
| T-029 forge-retro skill | `T-029-forge-retro.md` | 🔲 stub |
| T-030 user-facing README | `T-030-user-readme.md` | 🔲 stub |
| T-031 CONTRIBUTING.md | `T-031-contributing.md` | 🔲 stub |
| T-032 e2e test | `T-032-e2e-test.md` | 🔲 stub |
| T-033 publish | `T-033-publish.md` | 🔲 stub |

## Rule

**Don't write a prompt more than 2 tasks ahead.** Specs change as we build. A prompt
written 20 tasks early is usually wrong by the time we get there.

When you (or Claude) finish a task, the *first action of the next session* is to:
1. Read CLAUDE.md
2. Identify the next task from progress.md
3. If its prompt is a stub: write the full prompt now (with fresh context), commit it,
   then start work
