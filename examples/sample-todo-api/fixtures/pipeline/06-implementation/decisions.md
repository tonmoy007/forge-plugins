# Implementation Decisions — Todo API

## Cursor pagination over offset

Offset pagination with large offsets causes full-table scans. Cursor pagination (keyed on
`(created_at, id)`) is O(log n) regardless of page depth. Trade-off: clients cannot jump
to arbitrary pages, but for a todo list this is never needed.

## bcrypt for password hashing

bcrypt has a built-in work factor and is resistant to GPU attacks. argon2id would be
marginally stronger but bcrypt is well-supported by Python's `passlib` and simpler to
configure. Revisit for v2 if compliance requires argon2id.

## In-memory rate limiter for v1

A Redis-backed rate limiter is correct for multi-instance deployments. For v1 (single
instance), in-memory is simpler and sufficient. The rate limiter interface is abstracted
behind a `RateLimiter` protocol so the Redis implementation can be swapped without
touching route code.

## No ORM

SQLAlchemy adds abstraction cost that isn't justified for a small, well-defined schema.
Raw asyncpg queries are explicit, fast, and easier to optimize. Query logic lives in
repository classes, not scattered across models.
