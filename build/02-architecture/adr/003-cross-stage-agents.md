# ADR-003: Cross-Stage Agents Are Hook-Triggered, Not User-Invoked

**Status**: Accepted
**Date**: 2026-05-05

## Context

Forge has 16 agents total: 12 stage-specific (one per pipeline stage) and 4 cross-stage
(reflector, lesson-extractor, skill-miner, gate-checker).

The 12 stage agents are obvious — they correspond 1:1 with `/forge:srs` through `/forge:release`
slash commands.

The 4 cross-stage agents need a different invocation model. Three options:

1. Each gets its own slash command (`/forge:reflect`, `/forge:extract-lessons`, etc.)
2. They run inline as part of stage agents (i.e., the builder also reflects)
3. They're triggered by hooks (Stop hook spawns reflector, etc.)

## Decision

**Cross-stage agents are spawned by hooks, not exposed as user-facing slash commands.**

Specifically:
- **Reflector** — spawned by `Stop` hook after every Stop event
- **Lesson Extractor** — spawned by `Stop` hook when corrections are flagged
- **Skill Miner** — spawned by `Stop` hook (async) when pattern frequency thresholds hit
- **Gate Checker** — spawned by `Stop` hook before advancing stages

## Rationale

**Why not slash commands?**
- These agents should run on schedule (every Stop event), not on user demand
- Asking the user to run `/forge:reflect` after every task is friction we don't want
- Users would forget; the discipline must be automatic
- Slash commands clutter the namespace (already 16 commands; adding 4 more dilutes value)

**Why not inline in stage agents?**
- Mixing concerns: the builder agent shouldn't also do meta-reflection on its own work
- Self-reflection in the same context is biased (the agent has already convinced itself)
- Tool restrictions matter: the reflector should be read-only; the builder needs full access
- A separate context window improves objectivity

**Why hooks?**
- Hooks fire deterministically on lifecycle events — perfect for "after every X, do Y"
- Hooks have access to session metadata (transcript path, session ID, cwd)
- Hooks can pipe data into agent invocations (e.g., transcript path → reflector input)
- Hooks can chain agents (gate check → reflect → extract lessons → mine skills)

## Consequences

**Positive**:
- Cross-stage behavior is automatic, not opt-in
- User namespace stays clean
- Each agent has its own context (no bleeding)
- Reflection is consistent across sessions

**Negative**:
- Stop hook latency budget includes 4 agent spawns (mitigated: skill-miner is async)
- Debugging: harder to manually invoke for testing (mitigated: scripts/test-agent.py wrapper)
- Discoverability: users don't see these agents in `/forge:*` listing (mitigated: docs)

## Alternatives Considered

1. **Slash commands for all 16**: rejected for the reasons above.

2. **Inline in stage agents**: rejected — mixing concerns, biased self-reflection.

3. **A dispatcher agent** that routes to sub-agents: considered but adds latency and indirection.
   The hook-direct model is simpler.

4. **Background worker process**: considered for skill-miner; rejected for v0.1 (adds operational
   complexity). May revisit if mining becomes expensive.

## Implementation Notes

The Stop hook is the orchestrator for cross-stage agents:

```python
# hooks/stop-reflect.py (simplified)

def main():
    data = json.load(sys.stdin)
    if data.get("stop_hook_active"):
        return  # avoid loops

    # Step 1: reflection (always)
    invoke_agent("reflector", data)

    # Step 2: lesson extraction (if corrections flagged)
    if has_correction_flags(data):
        invoke_agent("lesson-extractor", data)

    # Step 3: gate check (always)
    gate_result = run_script("check-gate.py", data)

    # Step 4: skill mining (async)
    spawn_async("python", "scripts/mine-skills.py", "--session", data["session_id"])
```

`invoke_agent()` calls Claude Code's subagent API with the agent's persona file.
This keeps each agent in its own context window.

## Migration Path

If we ever need a user-facing way to invoke these agents (e.g., for debugging):

1. Add `/forge:reflect`, `/forge:extract-lessons`, etc. as slash commands
2. The skill loads the same agent persona
3. The agent doesn't know whether it was hook-triggered or user-invoked

This is a non-breaking addition; the hook-triggered path stays the primary one.
