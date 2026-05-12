# Incident Log — Todo API

## INC-001 — 2026-05-12 (resolved)

**Severity**: P2  
**Duration**: 8 minutes  
**Summary**: Elevated 500 errors on POST /todos after deploy v1.0.0.

**Root cause**: asyncpg pool size default (10) too small under initial traffic spike.  
**Resolution**: Increased `DB_POOL_SIZE` env var to 20; restarted container.  
**Follow-up**: Add pool utilization alert at 80% (done — see observability.md alerts).
