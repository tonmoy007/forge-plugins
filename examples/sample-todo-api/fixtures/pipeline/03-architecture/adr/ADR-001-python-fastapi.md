# ADR-001 — Use Python + FastAPI

**Status**: Accepted  
**Date**: 2026-05-12

## Context

Need to choose an implementation language and HTTP framework. Options evaluated:
Go + Chi, Python + FastAPI, Node.js + Fastify.

## Decision

Use Python 3.12 with FastAPI.

## Rationale

- FastAPI generates OpenAPI specs automatically from type annotations (eliminates manual spec drift)
- Pydantic v2 gives fast, type-safe request/response validation
- asyncpg is well-maintained and performant for async Postgres access
- Team has existing Python expertise; Go would require ramp-up
- Fastify is fast but TypeScript ecosystem adds tooling overhead for a solo API

## Consequences

- Startup time ~300ms (acceptable; this is not a Lambda cold-start scenario)
- Memory usage ~80MB idle (acceptable)
- Python GIL is not a bottleneck for I/O-bound workload
- Must use `uvicorn` + `gunicorn` in production for multi-worker concurrency
