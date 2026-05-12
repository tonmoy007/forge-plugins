# Test Results — Todo API

## Unit Tests

```
pytest tests/unit/ -v --tb=short
================================ 47 passed in 3.21s ================================
```

All 47 unit tests pass. Coverage: 87% on `src/`.

## Integration Tests

```
pytest tests/integration/ -v --tb=short
================================ 18 passed in 24.7s ================================
```

18 integration tests pass (Postgres via testcontainers). Slowest: token refresh cycle (1.2s — DB round trips).

## Load Test Results

### Read latency (`tests/load/read_latency.js`)

```
scenarios: 100 VUs, 60s
  http_req_duration p(50)=48.2ms p(95)=98.1ms p(99)=142.3ms
  http_reqs: 18,432 (307/s)
  http_req_failed: 0.00%
```

### Write latency (`tests/load/write_latency.js`)

```
scenarios: 50 VUs, 60s
  http_req_duration p(50)=61.4ms p(95)=134.8ms p(99)=287.1ms
  http_reqs: 6,218 (103/s)
  http_req_failed: 0.00%
```

Both within NFR-001 targets. No errors under load.
