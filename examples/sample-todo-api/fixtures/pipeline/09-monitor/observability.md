# Observability — Todo API

## Structured Logging

Every HTTP request emits a JSON log line (REQ-NF-003):

```json
{
  "timestamp": "2026-05-12T10:23:45.123Z",
  "level": "info",
  "request_id": "uuid",
  "user_id": "uuid | null",
  "method": "GET",
  "path": "/todos",
  "status": 200,
  "duration_ms": 48
}
```

Log aggregation: logs shipped to Loki via Docker logging driver. Grafana for queries.

## Metrics

Exposed at `GET /metrics` (Prometheus format):

- `http_requests_total{method, path, status}` — request count
- `http_request_duration_seconds{method, path}` — latency histogram (p50/p95/p99)
- `db_pool_size` — asyncpg connection pool utilization
- `rate_limit_hits_total{endpoint}` — rate limit triggers

## SLO Definitions

| SLO | Target | Measurement window |
|-----|--------|--------------------|
| Read availability | 99.9% success rate on GET /todos | 30 days |
| Write availability | 99.5% success rate on POST /todos | 30 days |
| Read latency | p99 < 200 ms | 1 hour rolling |
| Write latency | p99 < 500 ms | 1 hour rolling |

## Alerts

Configured in Grafana Alerting:

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| High error rate | 5xx rate > 1% over 5m | critical | Page on-call |
| Latency degradation | p99 read > 300ms over 10m | warning | Notify on-call |
| Pool exhaustion | db_pool_size > 90% for 2m | warning | Notify on-call |
| Rate limit spike | rate_limit_hits > 50/min | info | Log only |

Alert routing: critical → PagerDuty; warning → Slack #api-alerts; info → Slack #api-info.

## Dashboards

Grafana dashboard `todo-api-overview` (ID: 42) shows all four SLOs plus top error paths.
