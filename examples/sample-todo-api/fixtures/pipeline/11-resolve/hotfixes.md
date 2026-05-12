# Hotfixes — Todo API

## HF-001 — v1.0.1 — Retry-After header on 429 (2026-05-12)

**Issue**: FB-002 — RFC 7231 requires `Retry-After` header on 429 responses.  
**Fix**: `src/middleware/rate_limit.py` — added `Retry-After: <seconds>` to response headers when limit exceeded.  
**Regression test**: `tests/unit/test_rate_limiter.py::test_retry_after_header_present`  
**Released**: v1.0.1 — deployed same day.
