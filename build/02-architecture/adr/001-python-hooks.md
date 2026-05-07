# ADR-001: Hooks are Python (not Bash)

**Status**: Accepted
**Date**: 2026-05-05

## Context

Claude Code hooks support `command` (any shell command) and `prompt` (LLM call) types.
For command hooks, we can use Bash, Python, Node, Go, anything on PATH.

Forge hooks need to:
- Parse JSON from stdin
- Read/write Markdown and YAML files
- Filter and aggregate lists
- Sometimes spawn HTTP calls (deferred — not in v0.1)
- Run fast (< 200ms total budget)

## Decision

All hooks are written in **Python 3.11+**, using **stdlib only**.

## Rationale

**Why not Bash?**
- JSON parsing in Bash requires `jq` or hand-parsing — fragile.
- YAML parsing is essentially impossible without external tools.
- Hook logic gets complex (the Stop hook is a 4-step pipeline) — Bash becomes unreadable.
- Error handling in Bash is notoriously hard.

**Why not Node?**
- Cold-start time for `node` invocation can exceed 100ms; combined across 7 hooks per session, that's significant.
- Most users have Python available; Node is optional.

**Why not a compiled binary (Go, Rust)?**
- Distribution complexity: we'd need to build per-platform binaries.
- Plugin marketplace doesn't yet support multi-arch binaries cleanly.
- Plain text scripts are auditable by users (security/trust).

**Why stdlib only?**
- Hooks run on every event. Adding `pyyaml`/`pydantic` to every hook startup adds ~30-100ms per invocation.
- Heavy lifting (YAML parsing, statistical analysis) happens in `scripts/` which can have deps.
- Hooks invoke scripts when needed (e.g., `stop-reflect.py` calls `scripts/check-gate.py` which uses pyyaml).

## Consequences

**Positive**:
- Fast cold-start (~30-50ms for `python -c "pass"`).
- Cross-platform without builds.
- Auditable, editable by users.
- Easy to test (`pytest hooks/`).

**Negative**:
- Requires Python 3.11+ on user's PATH (we accept this).
- JSON parsing only via `json` module (no schema validation in hooks themselves).
- Can't use `pyyaml` directly in hooks; must round-trip through scripts.

## Alternatives Considered

1. **Bash + jq**: Rejected for readability and complex Stop hook logic.
2. **Python with pyyaml in hooks**: Rejected for latency budget.
3. **Single Python "dispatcher"** that handles all hook events: deferred — could optimize later if startup cost is the bottleneck.
4. **HTTP hooks** (one server, multiple endpoints): rejected for v0.1 — adds operational complexity (run a server) and conflicts with offline-first NFR-004.

## Migration Path

If we need to switch to a dispatcher pattern (single long-running Python process):
- Add `hooks/dispatcher.py` that hosts all event handlers
- Update `plugin.json` to point all events to the dispatcher with `--event=<name>`
- Existing per-event scripts become importable modules
- No user-visible change; pure refactor
