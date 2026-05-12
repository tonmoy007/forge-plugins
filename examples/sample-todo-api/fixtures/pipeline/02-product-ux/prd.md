# Product Requirements Document — Todo API

**Relates to**: REQ-001, REQ-002, REQ-003, REQ-004, REQ-005

---

## Product Vision

A reliable, secure REST API that lets developers build todo applications without
worrying about auth, persistence, or rate limiting.

---

## Features

### FEAT-001 — Account Management
Derived from REQ-001.  
Users can register and log in. Duplicate email registration is rejected clearly.

### FEAT-002 — Authenticated Todo Management
Derived from REQ-003.  
Full CRUD on todo items scoped to the authenticated user. Ownership enforced at
the data layer — no item from another user is ever returned.

### FEAT-003 — Advanced Filtering
Derived from REQ-004.  
Client can combine `status` and `due_date` filters. Paginated results (cursor-based,
page size 50 default, 200 max).

### FEAT-004 — Security Controls
Derived from REQ-002 and REQ-005.  
JWT access/refresh token pair, token rotation on refresh, rate limiting on auth
endpoints (10 req/min/IP), structured audit log.

---

## Out of Scope (v1)

- Tags/labels on todo items (REQ-004 extension, deferred)
- Soft-delete / archive
- Multi-user shared todo lists
- OAuth2 / social login
