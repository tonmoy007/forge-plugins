# T-009: stop-reflect.py — The Heart of Forge

> ⚠️ This is the most complex hook. Read everything below before starting.
> Don't shortcut. Get this right.

## Context

The Stop hook is what makes Forge *Forge*. It's the difference between "a plugin with
some commands" and "a self-improving orchestration system." Get this wrong and
nothing else matters.

Read in this order:
- `CLAUDE.md` — your operating principles
- `build/02-architecture/architecture.md` §3.2 (Stop hook flow) and §5.5 (Stop hook spec)
- `build/02-architecture/adr/004-stop-hook-sequential.md` — **mandatory** before starting
- `build/03-spec/technical-spec.md` §2.5 (the algorithm)
- `references/claude-code-hooks.md` — Stop event details, exit code 2 semantics
- `tasks/lessons.md` — anything from prior hook work

Tasks already done (you depend on their outputs):
- T-003 produced `_state_lib.py` — import from it; don't shell out
- T-005, T-006 produced `gate-criteria.md` and `check-gate.py` — invoke check-gate
- T-019 produced `extract-lessons.py` — invoke it for lesson extraction
- T-027 (later) produces `mine-skills.py` — for now, stub the skill mining call

## What Makes This Hook Special

It runs four things sequentially:
1. **Reflection** (always) — call reflector agent, append to state.md
2. **Lesson extraction** (when corrections flagged) — call extract-lessons.py
3. **Gate check** (always) — call check-gate.py, possibly exit 2 to block
4. **Skill mining** (async, fire-and-forget) — spawn mine-skills.py

Read ADR-004 for *why* sequential, *why* skill mining is async, and *why* gate check
exits 2 only on explicit "done" signals.

## Task

Implement `hooks/stop-reflect.py` per the spec.

**Files to create**:

1. **`hooks/stop-reflect.py`** — the hook itself
   - stdlib only (no pyyaml — but you can call scripts that use it)
   - Imports `_state_lib` for state.md operations
   - Calls `scripts/check-gate.py` and `scripts/extract-lessons.py` as subprocesses
     (they can have deps; the hook stays light)
   - Spawns `scripts/mine-skills.py` as detached subprocess
   - Logs all errors to `.forge/errors.log` (never crashes loudly)
   - Detects `stop_hook_active` and exits early to prevent loops

2. **`hooks/_invoke_agent.py`** — helper module for spawning Claude subagents
   - `invoke_agent(name, context_dict) -> str` — returns agent output
   - Uses Claude Code's subagent API (whatever that exact interface is — research first)
   - Has a graceful fallback if subagent invocation fails (return empty string, log)

3. **`tests/unit/test_stop_reflect.py`** — comprehensive tests:
   - Stop with no Forge project → silent exit 0
   - Stop in Forge project, gate passes, no done signal → reflects + warns about partial
   - Stop in Forge project, gate fails, done signal → exit 2 with unmet criteria listed
   - Stop with correction flags → lesson extraction is called
   - Stop with `stop_hook_active=true` → immediate exit (loop prevention)
   - Stop with one step crashing → other steps still run
   - Skill mining is spawned but doesn't block the hook return

4. **`tests/integration/test_stop_pipeline.py`** — end-to-end test:
   - Set up a fixture project at Stage 6
   - Inject a transcript with corrections
   - Run the hook
   - Assert: reflection appears in state.md, lesson appears in lessons.md, gate result printed

## Algorithm (Detailed)

```python
#!/usr/bin/env python3
"""Stop hook: reflect, extract lessons, check gate, mine skills."""

import json
import sys
import subprocess
import logging
from pathlib import Path
from typing import Optional

# Add scripts/ to path so we can import _state_lib
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from _state_lib import read_state, append_to_section, advance_stage

logger = logging.getLogger(__name__)


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        log_error("invalid_stdin", "")
        sys.exit(0)  # don't crash session

    # Loop prevention
    if data.get("stop_hook_active"):
        sys.exit(0)

    cwd = Path(data.get("cwd", "."))
    if not (cwd / "pipeline" / "state.md").exists():
        sys.exit(0)  # not a Forge project

    state = read_state(cwd)
    transcript_path = data.get("transcript_path")
    user_done = detect_done_signal(transcript_path)

    # Step 1: Reflect
    try:
        reflection = run_reflector(cwd, state, transcript_path, depth="light")
        append_to_section(cwd, "Last Reflection", reflection)
    except Exception as e:
        log_error("reflection_failed", e)

    # Step 2: Extract lessons (if corrections flagged)
    correction_flags_path = cwd / ".forge" / "correction-flags.jsonl"
    if correction_flags_path.exists() and correction_flags_path.stat().st_size > 0:
        try:
            extract_lessons_proc = subprocess.run(
                ["python", str(cwd.parent / "scripts" / "extract-lessons.py"),
                 "--transcript", transcript_path,
                 "--since-flag", str(correction_flags_path)],
                capture_output=True, text=True, timeout=10
            )
            if extract_lessons_proc.returncode == 0 and extract_lessons_proc.stdout:
                count = sum(1 for line in extract_lessons_proc.stdout.splitlines()
                           if line.startswith("- id:"))
                if count > 0:
                    print(f"📚 Captured {count} lesson(s) from corrections.")
                    # Reset flags after successful extraction
                    correction_flags_path.write_text("")
        except subprocess.TimeoutExpired:
            log_error("extract_lessons_timeout", "")
        except Exception as e:
            log_error("extract_lessons_failed", e)

    # Step 3: Gate check
    try:
        gate_proc = subprocess.run(
            ["python", str(Path(__file__).parent.parent / "scripts" / "check-gate.py"),
             "--stage", str(state["current_stage"])],
            capture_output=True, text=True, timeout=5
        )
        gate_result = json.loads(gate_proc.stdout) if gate_proc.stdout else {}

        unmet_blockers = [
            c for c in gate_result.get("details", [])
            if not c["passed"] and c["severity"] == "blocker"
        ]

        if user_done:
            if not unmet_blockers:
                advance_stage(cwd)
                print(f"✅ Stage {state['current_stage']} gate passed. Advanced.")
            else:
                print(f"🚫 Cannot advance from Stage {state['current_stage']}.")
                print("Unmet blockers:")
                for c in unmet_blockers:
                    print(f"  - {c['id']}: {c['description']}")
                sys.exit(2)  # block stop
        else:
            passed = gate_result.get("passed", 0)
            total = gate_result.get("total", 0)
            if total > 0:
                print(f"⚠️ Stage {state['current_stage']}: {passed}/{total} gate criteria met.")

    except subprocess.TimeoutExpired:
        log_error("gate_check_timeout", "")
    except Exception as e:
        log_error("gate_check_failed", e)

    # Step 4: Skill mining (async, fire-and-forget)
    try:
        subprocess.Popen(
            ["python", str(Path(__file__).parent.parent / "scripts" / "mine-skills.py"),
             "--session", data.get("session_id", "")],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
    except Exception as e:
        log_error("skill_mining_spawn_failed", e)
        # Don't propagate — this is best-effort

    sys.exit(0)


def detect_done_signal(transcript_path: Optional[str]) -> bool:
    """Detect if user explicitly said this stage is done."""
    if not transcript_path or not Path(transcript_path).exists():
        return False
    # Read last 10 user messages, look for done signals
    # Patterns: "done", "ship it", "advance", "next stage", "looks good let's move on"
    # Be conservative — false positive blocks user; false negative is fine
    ...


def run_reflector(cwd: Path, state: dict, transcript_path: str, depth: str) -> str:
    """Spawn reflector agent, return its output."""
    # Use the subagent invocation mechanism (see _invoke_agent.py)
    ...


def log_error(kind: str, error: object) -> None:
    """Log to .forge/errors.log without breaking the session."""
    ...


if __name__ == "__main__":
    main()
```

## Definition of Done

- [ ] `hooks/stop-reflect.py` runs successfully on test fixture (no crashes, exit 0)
- [ ] Stop in non-Forge project → silent exit (no output, no errors)
- [ ] Stop with corrections flagged → lesson extraction runs and updates lessons.md
- [ ] Stop with gate fail + done signal → exit code 2 with unmet criteria printed
- [ ] Stop with `stop_hook_active=true` → immediate exit (verified by stderr inspection)
- [ ] Skill mining subprocess is spawned (verified by checking process list briefly)
- [ ] Hook completes within 10s on a typical project
- [ ] All errors logged to `.forge/errors.log`, never crash loudly
- [ ] Unit tests cover all branches; > 90% line coverage
- [ ] Integration test passes against fixture project

## Verification

```bash
# 1. Stop with no Forge project — silent
mkdir -p /tmp/no-forge && cd /tmp/no-forge
echo '{"session_id":"test","hook_event_name":"Stop","cwd":"/tmp/no-forge","transcript_path":""}' \
  | python $OLDPWD/hooks/stop-reflect.py
# Expect: exit 0, empty stdout
echo "Exit: $?"

# 2. Stop in Forge project — full pipeline
cd /tmp && rm -rf forge-test && mkdir forge-test && cd forge-test
bash $OLDPWD/scripts/init-pipeline.sh
echo '{"session_id":"test","hook_event_name":"Stop","cwd":"/tmp/forge-test","transcript_path":""}' \
  | python $OLDPWD/hooks/stop-reflect.py
# Expect: exit 0, "Stage 0: ..." style output
cat pipeline/state.md | grep "Last Reflection" -A 3

# 3. Loop prevention
echo '{"session_id":"test","hook_event_name":"Stop","cwd":"/tmp/forge-test","stop_hook_active":true}' \
  | python $OLDPWD/hooks/stop-reflect.py
# Expect: exit 0, no output

# 4. Tests
cd $OLDPWD
pytest tests/unit/test_stop_reflect.py tests/integration/test_stop_pipeline.py -v --cov

# 5. Latency check
cd /tmp/forge-test
time (echo '{...}' | python $OLDPWD/hooks/stop-reflect.py)
# Expect: real time < 10s
```

## Commit

```
feat(T-009): stop-reflect.py — the orchestrating Stop hook

Implements the four-step Stop pipeline:
1. Reflection (always)
2. Lesson extraction (when corrections flagged)
3. Gate check (always; exit 2 on unmet blockers if user signaled done)
4. Skill mining (async, fire-and-forget)

- hooks/stop-reflect.py — main hook
- hooks/_invoke_agent.py — subagent invocation helper
- tests/unit/test_stop_reflect.py — branch coverage
- tests/integration/test_stop_pipeline.py — end-to-end

Per ADR-004: sequential pipeline, async skill mining only.

Ref: T-009
REQ: REQ-034, REQ-050, REQ-051, REQ-052
```

## Update Trail

1. progress.md → T-009 done, current → T-010
2. todo.md → archive T-009, activate T-010
3. lessons.md → things you learned about Claude Code subagent invocation
4. decisions.md → any concrete choices about reflector agent prompt structure, lesson extraction
   thresholds, etc.

## Notes

- This hook will reveal weaknesses in T-019 (extract-lessons.py) and T-006 (check-gate.py)
  if their interfaces don't match what this hook needs. If you find a mismatch, **stop and
  fix the upstream task** rather than working around it. Workarounds compound.

- The subagent invocation API is the part with the most unknowns. Spend research time on
  it before writing code. If it's too complex for v0.1, consider a fallback: have the
  reflector agent be invoked via prompt-hook type instead of command-hook. Document the
  decision in decisions.md.

- Don't try to perfect the reflector's output format here. The reflector agent itself is
  T-016. This task just needs to *call* it; the agent's persona handles output quality.

- The "done signal" detection (`detect_done_signal`) is heuristic. Start conservative
  (only obvious phrases like "ship it", "advance to next stage", "we're done with stage N").
  False positives block the user; false negatives just mean they need to be more explicit.
