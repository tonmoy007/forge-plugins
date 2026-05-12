# Triage — Todo API

## Priority Definitions

- **P0**: System down or data loss — fix immediately
- **P1**: Significant functionality broken — fix in next patch
- **P2**: Degraded UX — fix in next minor release
- **P3**: Low-impact improvement — schedule for backlog

## Triaged Items

| ID | Priority | Title | Target |
|----|----------|-------|--------|
| FB-002 | P1 | Missing Retry-After header on 429 | v1.0.1 patch |
| FB-001 | P2 | No total_count in pagination response | v1.1.0 |
| FB-003 | P3 | Docker image size 480 MB | v1.1.0 |
| INC-001 | P2 | Pool exhaustion alert threshold | Done ✅ |

## Decision Log

- FB-002 (P1): Added `Retry-After` header to rate limiter middleware — ships in v1.0.1.
- FB-001 (P2): `total_count` requires a COUNT(*) query on every list call — acceptable cost; schedule for v1.1.
- FB-003 (P3): Multi-stage build investigation deferred to v1.1 planning.
