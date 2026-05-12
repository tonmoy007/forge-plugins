# Release Checklist — Todo API v1.0.1

## Pre-release

- [x] All Stage 11 hotfixes have regression tests
- [x] `pytest tests/ -x` passes (65 tests, 0 failures)
- [x] Docker image builds: `docker build -t todo-api:v1.0.1 .`
- [x] Image pushed to registry: `ghcr.io/org/todo-api:v1.0.1`
- [x] Changelog updated in `CHANGELOG.md`
- [x] Version bumped in `pyproject.toml` → 1.0.1

## Deploy

- [x] Staging deploy successful — health check passed
- [x] Smoke test on staging: register + login + create + list + 429 check
- [x] Production deploy: `docker compose -f docker-compose.prod.yml up -d`
- [x] Production health check: `GET /health` → 200
- [x] Production smoke test passed

## Post-release

- [x] Git tag created: `git tag v1.0.1`
- [x] GitHub release published with release notes
- [x] Deferred items (FB-001, FB-003) added to v1.1 milestone
- [x] On-call briefed on v1.0.1 changes
