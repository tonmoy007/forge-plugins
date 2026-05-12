# Deploy Log — Todo API

## Deploy 1 — 2026-05-12

**Version**: v1.0.0  
**Deployer**: CI pipeline (GitHub Actions)  
**Result**: SUCCESS

Steps completed:
1. Image `ghcr.io/org/todo-api:v1.0.0` pulled — OK
2. `docker compose up -d` — OK (container started in 4.2s)
3. Health check `GET /health` → 200 — OK
4. Migrations applied: `001_initial_schema.sql` — OK
5. Smoke test: register + login + create + list — all 200/201

No rollback needed.
