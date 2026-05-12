# Software Requirements Specification — Todo API

**Project**: Todo API  
**Version**: 1.0  
**Date**: 2026-05-12  
**Status**: Approved

---

## Overview

A REST API for managing personal todo items with JWT authentication, Postgres storage,
Docker deployment, and structured JSON logging.

---

## Functional Requirements

### REQ-001 — User Registration
Users can create an account with email and password.  
**Acceptance criteria**: POST /auth/register returns 201 with JWT access and refresh tokens;
duplicate email returns 409.

### REQ-002 — User Authentication
Registered users can obtain JWT access and refresh tokens via POST /auth/login.  
**Acceptance criteria**: Valid credentials return 200 with access_token (15 min TTL) and
refresh_token (7 day TTL); invalid credentials return 401.

### REQ-003 — Todo CRUD
Authenticated users can create, read, update, and delete their own todo items.  
**Acceptance criteria**: CRUD endpoints enforce ownership; other users' todos return 404;
all operations reflected immediately on re-read.

### REQ-004 — Todo Filtering
Users can filter todos by `status` (open|done) and `due_date` (ISO 8601 date range).  
**Acceptance criteria**: GET /todos?status=open returns only open items; combined filters
are AND-ed; empty results return 200 with empty array.

### REQ-005 — Rate Limiting on Auth Endpoints
POST /auth/login and POST /auth/register are rate-limited to prevent brute force.  
**Acceptance criteria**: More than 10 requests per minute from the same IP returns 429;
rate limit resets after 60 seconds.

---

## Non-Functional Requirements

### NFR-001 — Latency
p99 read latency < 200 ms under 100 concurrent users; p99 write latency < 500 ms.

### NFR-002 — Deployability
The API ships as a Docker image; `docker compose up` starts the full stack (API + Postgres).

### NFR-003 — Observability
All log lines are structured JSON with `timestamp`, `level`, `request_id`, and `message` fields.

---

## Constraints

- Storage: Postgres 16+
- Auth: JWT (HS256), refresh token rotation on each use
- Language: no constraint (Python or Go preferred)
- No external secret store required for v1 (env vars suffice)

---

## Open Questions

1. Should soft-delete be supported (archived todos) or hard-delete only? Deferred to v1.1.
2. Should todo items support tags/labels? Out of scope for v1.

---

## Glossary

- **Todo item**: a user-owned record with title, optional description, optional due_date, and status (open|done)
- **JWT**: JSON Web Token used for stateless authentication
- **Refresh token**: long-lived opaque token used to obtain a new access token
- **Rate limiting**: throttling requests per IP to prevent abuse
