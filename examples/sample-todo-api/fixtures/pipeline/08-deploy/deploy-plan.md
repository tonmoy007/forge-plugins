# Deploy Plan — Todo API

## Target Environment

- Platform: Docker on a single VPS (Hetzner CX21, 2 vCPU, 4 GB RAM)
- Postgres: managed Postgres 16 (Supabase free tier for v1)
- Container registry: GitHub Container Registry (ghcr.io)

## Pre-deploy Checklist

- [ ] All Stage 7 gate criteria passed
- [ ] Docker image built and pushed: `ghcr.io/org/todo-api:v1.0.0`
- [ ] Environment variables set in production `.env` (DATABASE_URL, JWT_SECRET)
- [ ] Postgres migrations reviewed (no destructive changes)
- [ ] Staging smoke test passed

## Deploy Steps

1. SSH to VPS
2. `docker pull ghcr.io/org/todo-api:v1.0.0`
3. `docker compose -f docker-compose.prod.yml up -d`
4. Confirm health check: `curl http://localhost:8000/health` → 200
5. Run smoke tests: register + login + create todo + list

## Rollback Procedure

If the deploy fails or health check does not pass within 2 minutes:

1. `docker compose -f docker-compose.prod.yml down`
2. `docker compose -f docker-compose.prod.yml up -d` (previous image tag still pulled)
3. Confirm previous version health check passes
4. File incident in `pipeline/08-deploy/deploy-log.md`
5. Investigate failure before retrying deploy

Rollback is fast because the previous image is cached locally.

## DNS / Traffic

No load balancer for v1. Single container exposed on port 443 via Caddy reverse proxy.
Caddy handles TLS termination (Let's Encrypt auto-renew).
