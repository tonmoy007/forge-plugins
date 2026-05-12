# Risk Register — Todo API

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|------------|--------|------------|
| R-001 | asyncpg connection pool exhaustion under load | M | H | Pool size tuned to DB max_connections; connection timeout set; health check monitors pool |
| R-002 | JWT secret leaks → all tokens compromised | L | H | Secret stored in env var only; never logged; rotate immediately if leaked |
| R-003 | Postgres schema migration fails on deploy | M | H | Migrations run in transaction; rollback on failure; migration state checked before app starts |
| R-004 | Rate limiter in-memory state lost on restart | M | L | In-memory is acceptable for v1; Redis upgrade path documented for multi-instance |
| R-005 | k6 load test environment doesn't reflect prod | M | M | Run against staging DB with prod-equivalent data volume |
| R-006 | testcontainers slow in CI (Docker pull) | M | L | Pre-pull Postgres image in CI cache; timeout set to 120s |
