# Stage 4 Contract Artifact Rules

## Module Specifications

Each `MOD` SHALL state: owning `SRV`/component, responsibility, boundary,
provided and consumed interfaces, dependencies, data ownership/use, invariants,
operations, failure behavior, concurrency/transaction expectations, security,
observability, performance contracts, and upstream lineage. A module is not a
folder, class, or source-file design.

## Interface Specifications

Each `INT`/`CONTRACT` SHALL identify public or internal visibility, owner and
consumer, transport/binding where architecture selected one, operation/event
name, request/response or publish/consume semantics, DTO references,
preconditions, postconditions, idempotency, ordering, retry/timeout behavior,
authentication/authorization, errors, version, compatibility, and lineage.

## DTO and Event Rules

Each `DTO` SHALL define field name, semantic meaning, type, requiredness,
nullability, cardinality, allowed values/range/format, default semantics,
classification, validation references, serialization format, version behavior,
and owning interface. Events additionally define producer, consumers, trigger,
delivery guarantees, ordering key, deduplication/idempotency, retention, and
schema evolution rule. Do not create DTOs unrelated to an interface.

## Configuration Rules

Each `CFG` SHALL define owning module, key, purpose, data type, source,
environment scope, requiredness, default, valid range/format, secrecy class,
reload behavior, validation, operational owner, and failure behavior. Never put
real credentials, secrets, or implementation-specific deployment values in a
specification.

## Validation and Error Catalog Rules

Each `VAL` SHALL state trigger, target field/object, rule, evaluation order,
failure `ERR`, message-safe detail, and linked REQ/business rule. Each `ERR`
SHALL define stable code, category, HTTP/protocol mapping when applicable,
meaning, trigger, recoverability, retryability, safe client message, internal
diagnostic data, security exposure rule, and owning contract. Errors are not
validation rules and must not leak secrets or internal topology.

## State Machine and Sequence Rules

Each `FSM` SHALL list entity/aggregate, states, initial/terminal states,
transitions, triggers, guards, actions, invalid transitions, persistence,
concurrency, errors, and lineage. Each `SEQ` SHALL describe a bounded scenario
using numbered participants and messages, including preconditions, alternate,
failure, timeout/retry, compensation, postconditions, interfaces/DTOs/errors,
and observability signals. It specifies behavior, not code flow.
