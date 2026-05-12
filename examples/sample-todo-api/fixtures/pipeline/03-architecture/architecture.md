# Architecture — Todo API

**Relates to**: FEAT-001, FEAT-002, FEAT-003, FEAT-004

---

## System Overview

Three-tier architecture: HTTP API layer → application/domain layer → Postgres.
Deployed as a single Docker container with Postgres as a sidecar in development,
and as a separate managed database service in production.

---

## Components

### AuthService (FEAT-001, FEAT-004)
Handles registration, login, token issuance, token refresh, and rate limiting.
Issues HS256 JWTs (access 15 min, refresh 7 days). Rotates refresh tokens on use.
Rate limiter implemented as an in-process sliding-window counter backed by a Redis
or in-memory store (configurable via env var).

### TodoService (FEAT-002, FEAT-003)
CRUD operations on todo items. All reads/writes scoped to `user_id` from the JWT.
Supports cursor-based pagination (default page 50, max 200).
Filtering: `status` enum check + `due_date` range via SQL WHERE clause.

### HTTP Router
`POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`
`GET /todos`, `POST /todos`, `GET /todos/:id`, `PATCH /todos/:id`, `DELETE /todos/:id`

### Database (Postgres)
Schema: `users`, `todos`, `refresh_tokens`. See `data-model.md`.
Migrations managed with a lightweight migration runner (no ORM required).

---

## Cross-Cutting Concerns

- **Structured logging**: every request emits JSON log with `request_id`, `user_id`,
  `method`, `path`, `status`, `duration_ms` (REQ-NF-003)
- **Error handling**: all errors mapped to RFC 7807 Problem Details JSON
- **Config**: 12-factor — all config via environment variables

---

## Technology Decisions

See `adr/` directory for individual Architecture Decision Records.

- Language: Python 3.12 + FastAPI (chosen: typed, async, OpenAPI auto-generation)
- Database driver: asyncpg (async Postgres, no ORM overhead)
- Auth library: PyJWT
- Container: python:3.12-slim base image
