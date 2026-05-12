# Test Strategy — Todo API

## Pyramid

- **Unit tests** (~70%): service logic, model validators, JWT helpers, rate limiter
- **Integration tests** (~25%): route tests against a real Postgres instance (testcontainers-python)
- **Load tests** (~5%): k6 scripts verifying NFR-001 latency targets

## Unit Tests

Location: `tests/unit/`  
Runner: pytest + pytest-asyncio  
Coverage target: ≥80% on `src/` (NFR-011)

Key test files:
- `test_auth_service.py` — register, login, refresh, duplicate email, invalid credentials
- `test_todo_service.py` — CRUD, ownership enforcement, filter combinations, pagination
- `test_rate_limiter.py` — window expiry, limit enforcement, reset after window
- `test_jwt.py` — encode, decode, expiry, tampered signature

## Integration Tests

Location: `tests/integration/`  
Fixture: `conftest.py` spins up Postgres via testcontainers, runs migrations, tears down after session.

Key test files:
- `test_auth_routes.py` — full register→login→refresh cycle, 429 on rate limit
- `test_todo_routes.py` — CRUD via HTTP, 404 on wrong owner, filter query params

## Load Tests

Location: `tests/load/`  
Tool: k6  
Scripts: `read_latency.js` (GET /todos, 100 VUs, 60s), `write_latency.js` (POST /todos, 50 VUs, 60s)  
Pass criteria: p99 < 200 ms read, p99 < 500 ms write (REQ-NF-001)

## CI Pipeline

1. `pytest tests/unit/ --cov=src --cov-fail-under=80`
2. `pytest tests/integration/` (requires Docker for testcontainers)
3. `k6 run tests/load/read_latency.js` (staging environment only)
