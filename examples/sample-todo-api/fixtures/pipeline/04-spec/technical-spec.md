# Technical Spec — Todo API

**Implements**: REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, NFR-001, NFR-002, NFR-003

---

## Stack

- Runtime: Python 3.12
- Framework: FastAPI 0.111
- Database driver: asyncpg 0.29
- Validation: Pydantic v2
- Auth: PyJWT 2.8
- Server: uvicorn 0.29 (dev), gunicorn 22 + uvicorn workers (prod)
- Container: python:3.12-slim

## Module Layout

```
src/
  main.py          — FastAPI app factory, middleware wiring
  routers/
    auth.py        — /auth/* routes (REQ-001, REQ-002, REQ-005)
    todos.py       — /todos/* routes (REQ-003, REQ-004)
  services/
    auth.py        — AuthService: register, login, refresh_token
    todos.py       — TodoService: CRUD + filtering
  models/
    user.py        — User Pydantic model + DB row mapper
    todo.py        — Todo Pydantic model + DB row mapper
  db/
    pool.py        — asyncpg connection pool setup
    migrations.py  — migration runner (reads sql/migrations/*.sql)
  middleware/
    request_id.py  — attaches UUID to every request
    logging.py     — structured JSON log emission (NFR-003)
    rate_limit.py  — sliding window per-IP limiter (REQ-005)
    auth.py        — JWT Bearer validation
sql/
  migrations/
    001_initial_schema.sql
tests/
  unit/            — service + model tests
  integration/     — route tests against real Postgres (testcontainers)
```

## Configuration (env vars)

| Variable            | Default        | Required |
|---------------------|----------------|----------|
| DATABASE_URL        | —              | yes      |
| JWT_SECRET          | —              | yes      |
| JWT_ALGORITHM       | HS256          | no       |
| ACCESS_TOKEN_TTL    | 900            | no       |
| REFRESH_TOKEN_TTL   | 604800         | no       |
| RATE_LIMIT_RPM      | 10             | no       |
| LOG_LEVEL           | info           | no       |

## Performance Budget (NFR-001)

Read endpoints (GET /todos, GET /todos/:id): target p99 < 200 ms at 100 concurrent users.  
Write endpoints: target p99 < 500 ms.  
Load tested with k6; results in `pipeline/07-evaluation/test-results.md`.
