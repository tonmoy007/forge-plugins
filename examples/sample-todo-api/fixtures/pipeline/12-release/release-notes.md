# Release Notes — Todo API v1.0.1

**Release date**: 2026-05-12  
**Type**: Patch

## Changes

### Fixed
- `Retry-After` header now included in 429 rate-limit responses (FB-002, RFC 7231 compliance)

---

# Release Notes — Todo API v1.0.0

**Release date**: 2026-05-12  
**Type**: Initial release

## Features

- **User accounts** — register and log in with email/password; JWT access + refresh tokens
- **Todo management** — create, read, update, delete todos scoped to authenticated user
- **Filtering** — filter by status (open/done) and due date range; cursor-based pagination
- **Rate limiting** — auth endpoints limited to 10 req/min/IP to prevent brute force
- **Structured logging** — all requests emit JSON logs with request_id and duration
- **Docker deployment** — `docker compose up` starts full stack; migrations run on boot

## Known Limitations

- Rate limiter is in-memory (single-instance only; Redis upgrade in v1.1)
- Pagination does not expose total count (planned for v1.1)
- Docker image is 480 MB (multi-stage build planned for v1.1)
