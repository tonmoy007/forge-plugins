# Task DAG — Todo API

**Implements**: REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, NFR-001, NFR-002, NFR-003

---

## Tasks

### T-001 — Database schema and migrations (REQ-001, REQ-002, REQ-003)
Done when: `001_initial_schema.sql` creates all three tables; migration runner applies it idempotently.

### T-002 — AuthService: register and login (REQ-001, REQ-002)
Done when: unit tests pass for register (happy + duplicate email) and login (happy + bad credentials).

### T-003 — JWT token issuance and validation (REQ-002)
Done when: access tokens expire at TTL; tampered tokens fail validation; refresh tokens rotate on use.

### T-004 — Rate limiter middleware (REQ-005)
Done when: >10 auth requests/min/IP returns 429; counter resets after window.

### T-005 — TodoService: CRUD (REQ-003)
Done when: create/read/update/delete with ownership enforcement; wrong-owner returns NotFoundError.

### T-006 — TodoService: filtering and pagination (REQ-004)
Done when: status filter, date range filter, cursor pagination all pass integration tests.

### T-007 — Structured logging middleware (NFR-003)
Done when: every response produces a JSON log line with `request_id`, `user_id`, `method`, `path`, `status`, `duration_ms`.

### T-008 — Docker packaging (NFR-002)
Done when: `docker compose up` starts API + Postgres; health check passes; migrations run on start.

### T-009 — Load tests (NFR-001)
Done when: k6 read script p99 < 200 ms and write script p99 < 500 ms at target concurrency.

### T-010 — CI pipeline
Done when: GitHub Actions workflow runs lint + unit + integration tests on PR; fails fast on first error.

---

## Dependencies

```
T-001 → T-002 → T-003 → T-004
             ↓
        T-005 → T-006
             ↓
        T-007 → T-008 → T-009
                         ↓
                       T-010
```
