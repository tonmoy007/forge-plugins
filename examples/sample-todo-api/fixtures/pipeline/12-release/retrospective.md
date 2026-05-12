# Retrospective — Cycle 1

**Project**: api (Todo API)  
**Cycle**: 1 (started 2026-05-06, completed 2026-05-12)  
**Stages completed**: 12/12  
**Tasks completed**: 10  
**Sessions**: 4

## What Went Well

- T-001 (schema + migrations) completed in a single session with no rework — clear spec paid off
- Load tests (T-009) passed on first run: p99 read 142 ms vs 200 ms target, well within budget
- Docker packaging (T-008) was straightforward because env-var config was planned from Stage 3
- Security review in Stage 7 found no open issues — OWASP checklist approach was effective
- Hotfix HF-001 shipped same day as FB-002 report; Retry-After regression test added immediately

## What Didn't Go Well

- INC-001: asyncpg pool exhaustion on deploy — pool size should have been in load test config from Stage 7
- FB-002: missing Retry-After header was a spec gap — RFC 7231 compliance not checked in Stage 4
- Docker image 480 MB larger than expected — multi-stage build should have been specced in Stage 3

## Lessons Captured

| Date | Title | Tags |
|------|-------|------|
| 2026-05-12 | Always include RFC compliance checklist in interface-spec | spec, api |
| 2026-05-12 | Specify DB pool size in load test config, not just app config | deploy, performance |
| 2026-05-12 | Multi-stage Docker build should be default, not optional | deploy, docker |

## Skill Proposals

No skill proposals pending. Patterns may not have reached the frequency threshold yet.

## Action Items

- [ ] Add RFC 7231 compliance checklist to Stage 4 (Spec) template — before next cycle start
- [ ] Include pool exhaustion scenario in Stage 7 (Eval) load test suite — before next cycle start
- [ ] Default to multi-stage Docker builds in Stage 3 (Architecture) decisions — next cycle
- [ ] Run `forge:retro` immediately after Stage 12 gate passes, not after hotfixes — process improvement
