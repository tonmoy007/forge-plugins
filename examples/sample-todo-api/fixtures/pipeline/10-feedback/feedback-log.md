# Feedback Log — Todo API

## FB-001 — 2026-05-12

**Source**: Beta user (direct message)  
**Feedback**: "The cursor pagination is confusing — I can't tell how many pages there are."  
**Triage**: P2 — UX friction, no data loss. Add `total_count` field to Page response in v1.1.

## FB-002 — 2026-05-12

**Source**: API consumer (GitHub issue)  
**Feedback**: "Rate limit 429 response doesn't include a `Retry-After` header."  
**Triage**: P1 — RFC compliance gap. Fix in next patch release.

## FB-003 — 2026-05-12

**Source**: Internal testing  
**Feedback**: "Docker image is 480 MB — larger than expected."  
**Triage**: P3 — operational cost. Investigate multi-stage build to reduce to <100 MB in v1.1.
