# Stage 4 Cross-Cutting Contract Rules

## Integration Contracts

For each approved internal or external integration, define ownership, purpose,
boundary, protocol, authentication, authorization, request/response or event
mapping, data classification, mapping/transformation rules, rate/size limits,
timeouts, retry/backoff, idempotency, ordering, circuit/failure behavior,
observability, support ownership, versioning, and exit/fallback behavior.

## Data and File Format Contracts

For each data/file contract, define owner, schema, field semantics, encoding,
format, validation, lifecycle/retention references, privacy classification,
integrity rules, import/export behavior, schema evolution, and lineage. Respect
the Stage 3 data model; do not redesign it.

## Performance Contracts

Each `PERF` contract SHALL identify scope, operation, workload basis, metric,
target/threshold, percentile where relevant, measurement method, dependency
assumptions, degradation behavior, and REQ/NFR lineage.

## Security Contracts

Each `SEC` contract SHALL identify asset/data classification, trust boundary,
control, authentication, authorization, input/output protection, encryption or
secret handling requirement, audit event, threat/failure behavior, compliance
reference, and verification condition. It implements no security mechanism.

## Compatibility and Versioning Rules

Each `COMP` contract SHALL define affected public contract, supported versions,
compatibility direction, breaking-change criteria, deprecation notice/window,
migration behavior, negotiation/default behavior, and rollback rule.

Versioning rules SHALL apply consistently to public APIs, events, DTOs, file
formats, configurations, errors, and behavior. A breaking change requires an
explicit compatibility rule and, when it alters a technical decision, a `TDR`.

## Operational Contracts

Operational contracts SHALL define health/readiness semantics, logs/metrics/
traces/audit signals, correlation identifiers, alert/SLO references, runbook
trigger, capacity/degradation behavior, backup/recovery interfaces where
architected, and operational ownership.
