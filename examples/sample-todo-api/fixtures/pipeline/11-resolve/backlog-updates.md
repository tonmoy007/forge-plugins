# Backlog Updates — Todo API

## Items Deferred to v1.1

| Item | Source | Rationale |
|------|--------|-----------|
| `total_count` in pagination response | FB-001 | Requires COUNT(*) — acceptable cost; not urgent |
| Docker multi-stage build (<100 MB target) | FB-003 | Operational improvement, not user-facing |
| Redis-backed rate limiter for multi-instance | R-004 | Single instance for v1; revisit at scale |
| Soft-delete / archive todos | Open question in SRS | Deferred by decision in Stage 1 |
| Tags/labels on todo items | REQ-F-004 extension | Out of v1 scope explicitly |

## Items Closed / Won't Fix

None.
