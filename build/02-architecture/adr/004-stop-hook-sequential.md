# ADR-004: Stop Hook Runs Sequential Pipeline (Not Parallel)

**Status**: Accepted
**Date**: 2026-05-05

## Context

The Stop hook runs four steps:

1. Reflection (compare output to gate criteria, log findings)
2. Lesson extraction (parse corrections from transcript)
3. Gate check (verify exit criteria, advance/block stage)
4. Skill mining (look for repeated patterns)

Each step takes time. We need to decide: run them sequentially or in parallel?

Total time budgets:
- Reflection: ~3s (calls reflector agent)
- Lesson extraction: ~2s (calls lesson-extractor when triggered)
- Gate check: ~500ms (script, no LLM)
- Skill mining: ~5s+ (calls skill-miner when threshold hit)

If sequential: ~10s worst case.
If parallel: ~5s worst case (limited by slowest).

The Stop hook timeout in plugin.json is 15s.

## Decision

**Run the four steps sequentially. Skill mining is the only async/non-blocking step.**

Specifically:
- Steps 1–3 run sequentially in the same Python process
- Step 4 (skill mining) is spawned as a detached subprocess that doesn't block

## Rationale

**Why sequential for steps 1–3?**

1. **Data dependencies**: Lesson extraction reads correction flags that the reflector might
   produce. Gate check uses the reflection's gap analysis. The chain is:
   - Reflector identifies gaps → flags potential lessons → lesson-extractor formalizes them
   - Gate check uses both the reflector's assessment and any new lessons

2. **State consistency**: All three modify `pipeline/state.md`. Parallel writes would race.
   Sequential = no locking needed.

3. **User experience**: Output appears in order. Reflection first, then lessons, then
   gate result. A user reading the output sees a coherent story.

4. **Latency budget acceptable**: 5–10s on Stop is fine. Stop happens at logical
   pause points (end of agent turn), not during active typing. Users tolerate it.

5. **Simpler error handling**: If step 1 fails, do we still run steps 2–3? Sequential
   makes this explicit (catch and continue, or abort). Parallel adds combinatorial
   error states.

**Why async for step 4 (skill mining)?**

1. **No data dependency on the rest**: skill mining reads `.forge/patterns.jsonl`,
   doesn't depend on reflection output

2. **Variable latency**: skill mining can take 5–60s if it actually generates a SKILL.md
   (calls the skill-miner agent). Blocking the Stop hook on this is unacceptable.

3. **Output isn't time-sensitive**: a proposed skill can show up in the next turn or
   the next session — there's no race with anything else

4. **Skipping it is fine**: if the user closes the session before mining completes,
   nothing is lost (patterns persist in `.forge/patterns.jsonl`, mining picks up next time)

## Consequences

**Positive**:
- Predictable order of execution
- No race conditions on state.md writes
- Coherent output for the user
- Async skill mining doesn't bloat Stop latency

**Negative**:
- Worst-case Stop latency is ~10s (vs ~5s parallel)
- If reflector fails, lesson extraction doesn't run (mitigated: each step has try/except)

## Alternatives Considered

1. **Fully parallel**: rejected — race conditions, output ordering, error handling complexity.

2. **All async (fire and forget)**: rejected — gate check needs to be synchronous to
   block the Stop event when criteria fail (exit code 2). Async hooks can't return
   blocking signals.

3. **Streaming pipeline**: e.g., reflector starts, lesson-extractor starts as soon as
   reflector produces output. Considered but adds plumbing complexity for marginal
   latency gains. Defer to v0.2 if needed.

4. **Run reflection only (skip everything else)**: simpler, but misses the whole point —
   gate enforcement and lesson capture are critical features.

## Implementation Notes

```python
# hooks/stop-reflect.py

def main():
    data = json.load(sys.stdin)
    if data.get("stop_hook_active"):
        return

    cwd = data["cwd"]
    if not is_forge_project(cwd):
        return

    # Step 1: Reflect (sequential, blocking)
    try:
        reflection = run_reflector(data)
        append_to_state(reflection)
    except Exception as e:
        log_error("reflection_failed", e)
        # continue to next steps — partial value is better than none

    # Step 2: Extract lessons (sequential, blocking)
    if has_correction_flags(cwd):
        try:
            lessons = run_lesson_extractor(data)
            append_to_lessons(lessons)
        except Exception as e:
            log_error("lesson_extraction_failed", e)

    # Step 3: Gate check (sequential, blocking — can exit 2)
    try:
        gate_result = run_check_gate(cwd)
        if user_signaled_done(data) and gate_result.failed:
            print(f"🚫 Stage {gate_result.stage}: {gate_result.unmet_summary}")
            sys.exit(2)
        elif gate_result.passed and user_signaled_done(data):
            advance_stage(cwd)
            print(f"✅ Stage {gate_result.stage} advanced.")
        else:
            print(f"⚠️ Stage {gate_result.stage}: {gate_result.summary}")
    except Exception as e:
        log_error("gate_check_failed", e)

    # Step 4: Skill mining (async, fire-and-forget)
    subprocess.Popen(
        ["python", "scripts/mine-skills.py", "--session", data["session_id"]],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )

    sys.exit(0)
```

## Migration Path

If we discover Stop latency is hurting UX:

1. Profile to find the slowest step
2. Consider moving lesson extraction to async (it doesn't block gate check directly,
   even though gate criteria might reference lessons)
3. Consider streaming output (print as each step completes, rather than at the end)

These are incremental improvements; they don't require breaking the sequential model.
