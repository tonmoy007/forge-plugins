# Technical Specification — Forge Plugin

> Implementation-ready specs. Detailed enough that any of the 33 tasks in the DAG
> can be executed without guessing.

---

## 1. plugin.json Schema

```json
{
  "$schema": "https://claude.ai/schemas/plugin.v1.json",
  "name": "sdlc-orchestrator",
  "displayName": "Forge",
  "version": "0.1.0",
  "description": "Full lifecycle SDLC orchestrator with specialized agents, memory, and auto-reflection",
  "author": {
    "name": "Saddam",
    "url": "https://github.com/<user>/forge"
  },
  "license": "MIT",
  "claude_code_version": ">=2.1.0",
  "engines": {
    "python": ">=3.11"
  },

  "skills": ["skills/*"],
  "agents": ["agents/*"],

  "hooks": {
    "SessionStart": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python ${CLAUDE_PLUGIN_ROOT}/hooks/session-start.py",
        "timeout": 5
      }]
    }],
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python ${CLAUDE_PLUGIN_ROOT}/hooks/prompt-submit.py",
        "timeout": 3
      }]
    }],
    "PreToolUse": [{
      "matcher": "Write|Edit|MultiEdit",
      "hooks": [{
        "type": "command",
        "command": "python ${CLAUDE_PLUGIN_ROOT}/hooks/pre-tool-write.py",
        "timeout": 3
      }]
    }],
    "PostToolUse": [{
      "matcher": "Write|Edit|MultiEdit|Bash",
      "hooks": [{
        "type": "command",
        "command": "python ${CLAUDE_PLUGIN_ROOT}/hooks/post-tool-use.py",
        "timeout": 5,
        "async": true
      }]
    }],
    "Stop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python ${CLAUDE_PLUGIN_ROOT}/hooks/stop-reflect.py",
        "timeout": 15
      }]
    }],
    "SubagentStop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python ${CLAUDE_PLUGIN_ROOT}/hooks/subagent-stop.py",
        "timeout": 5
      }]
    }],
    "SessionEnd": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python ${CLAUDE_PLUGIN_ROOT}/hooks/session-end.py",
        "timeout": 10,
        "async": true
      }]
    }]
  }
}
```

---

## 2. Hook Specifications

### 2.1 session-start.py

**Inputs** (stdin JSON):
```json
{
  "session_id": "string",
  "hook_event_name": "SessionStart",
  "trigger": "startup|resume|clear|compact",
  "transcript_path": "string|null",
  "cwd": "string"
}
```

**Outputs** (stdout):
- Plain text block (≤ 2000 tokens) injected as additionalContext
- Format:
  ```
  [Forge] Pipeline: Stage {N} — {name} | Task: {task_id} | Milestone: {m}/{total}
  [Forge] Project type: {type}
  [Forge] Active lessons ({count}): {abbreviated_list}
  [Forge] Next gate criteria: {one_line_summary}
  ```

**Exit codes**:
- 0: success (with or without context block)
- non-2: log warning, no blocking

**Algorithm**:
```
1. Parse stdin JSON.
2. cwd = JSON["cwd"]
3. If not exists(cwd + "/pipeline/state.md"):
     # Not a Forge project — exit silently with no output.
     exit 0
4. state = parse_state_md(cwd + "/pipeline/state.md")
5. lessons = filter_lessons(
       cwd + "/.forge/lessons.yaml",
       stage = state.current_stage,
       project_type = state.project_type
   )[:5]  # top 5 most relevant
6. global_lessons = filter_lessons(
       "~/.forge/global-lessons.yaml",
       stage = state.current_stage,
       project_type = state.project_type
   )[:3]
7. design_summary = ""
   if state.current_stage >= 6 and exists(cwd + "/pipeline/02-product-ux/design-system.md"):
       design_summary = extract_design_summary(...)  # token + component count
8. context = compose_context_block(state, lessons + global_lessons, design_summary)
9. assert token_count(context) < 2000
10. print(context)
11. exit 0
```

**Token budget**: ≤ 2000 tokens for all output.

**Test cases** (`tests/unit/test_session_start.py`):
- No pipeline/ dir → silent exit
- Fresh state (Stage 0) → "Pipeline not initialized" message
- Stage 6 with 3 lessons → full context block
- Stage 6 with 50 lessons → only top 5 included
- Corrupted state.md → fallback to safe default

### 2.2 prompt-submit.py

**Inputs**:
```json
{
  "session_id": "string",
  "hook_event_name": "UserPromptSubmit",
  "prompt": "string",
  "cwd": "string"
}
```

**Outputs**:
- JSON with `additionalContext` if stage transition detected
- Plain text otherwise (or empty)

**Algorithm**:
```
1. Parse stdin JSON.
2. prompt = JSON["prompt"]
3. detected_stage = detect_stage_intent(prompt)
   # Match against keywords: "/forge:build", "implementation", "deploy", etc.
4. correction_signals = detect_corrections(prompt)
   # Patterns: "no", "wrong", "instead", "actually", "I told you"
5. If correction_signals:
     append_to(".forge/correction-flags.jsonl", {
         "session": ..., "ts": ..., "prompt": prompt[:200]
     })
6. If detected_stage and detected_stage != current_stage:
     If gate_passed(current_stage):
         advance_state(detected_stage)
     return additionalContext: "Transitioning to Stage {N}..."
7. exit 0
```

### 2.3 pre-tool-write.py (Design System Enforcement)

**Inputs**:
```json
{
  "session_id": "string",
  "hook_event_name": "PreToolUse",
  "tool_name": "Write|Edit|MultiEdit",
  "tool_input": {
    "file_path": "string",
    "content": "string"  // Write
    // OR
    "old_string": "string", "new_string": "string"  // Edit
  },
  "cwd": "string"
}
```

**Outputs**:
- JSON `{"hookSpecificOutput": {"additionalContext": "..."}}` if violations found
- Empty otherwise

**Algorithm**:
```
1. Parse stdin JSON.
2. file_path = tool_input["file_path"]
3. If not is_ui_file(file_path):  # extension check
     exit 0  # silent
4. If state.current_stage < 6:
     exit 0  # design enforcement only after Build
5. If not exists(cwd + "/pipeline/02-product-ux/design-system.md"):
     exit 0  # no design system to enforce
6. content = tool_input.get("content") or tool_input.get("new_string", "")
7. violations = scan_for_violations(content)
   # Patterns:
   # - /#[0-9a-fA-F]{3,8}\b/ not preceded by var(--color
   # - /\b\d+px\b/ not from spacing scale [4,8,12,16,...]
   # - /font-family:\s*[^v]/ (not var(--font...))
   # - /z-index:\s*\d/ (not var(--z...))
   # - /!important/
8. If violations:
     msg = format_violations(violations)
     print(json.dumps({"hookSpecificOutput": {"additionalContext": msg}}))
9. exit 0
```

**UI file extensions**: `.tsx`, `.jsx`, `.ts`, `.js`, `.vue`, `.svelte`, `.css`, `.scss`, `.html`

### 2.4 post-tool-use.py

**Inputs**:
```json
{
  "session_id": "string",
  "hook_event_name": "PostToolUse",
  "tool_name": "string",
  "tool_input": {...},
  "tool_response": {...},
  "cwd": "string"
}
```

**Outputs**: Empty (logs only, async).

**Algorithm**:
```
1. Parse stdin JSON.
2. log_entry = {
     "ts": now_iso(),
     "session": session_id,
     "tool": tool_name,
     "file": tool_input.get("file_path", ""),
     "success": tool_response.get("success", true)
   }
3. append_to(".forge/session-log.jsonl", log_entry)
4. If state.current_stage == 6 and tool == "Write":
     update_progress_md(file_path, completed=detect_task_completion())
5. # Pattern tracking
   recent_tools = read_last_n(".forge/session-log.jsonl", 5)
   if is_pattern(recent_tools):
       append_to(".forge/patterns.jsonl", {
           "ts": now_iso(),
           "kind": "tool_seq",
           "tools": [t["tool"] for t in recent_tools]
       })
6. exit 0
```

### 2.5 stop-reflect.py

**Inputs**:
```json
{
  "session_id": "string",
  "hook_event_name": "Stop",
  "transcript_path": "string",
  "cwd": "string",
  "stop_hook_active": false  // true if this hook called itself
}
```

**Outputs**: JSON or text depending on action.

**Algorithm**:
```
1. Parse stdin JSON.
2. If stop_hook_active:  # avoid infinite loops
     exit 0

3. # Step 1: Reflection (lightweight)
   transcript_summary = summarize_transcript(transcript_path, last_n_turns=10)
   reflection = compose_reflection(state, transcript_summary)
   append_to_state_md("## Last Reflection", reflection)

4. # Step 2: Lesson extraction
   correction_flags = read(".forge/correction-flags.jsonl", since_last_stop=true)
   if correction_flags:
       lessons = extract_lessons(transcript_path, correction_flags)
       for lesson in lessons:
           append_to("tasks/lessons.md", format_lesson(lesson))
           append_to(".forge/lessons.yaml", lesson)
       # Notify user
       print(f"📚 Captured {len(lessons)} lesson(s) from corrections.")

5. # Step 3: Gate check
   gate_result = check_gate(state.current_stage)
   if gate_result.all_passed:
       if user_signaled_done:
           advance_state(state.current_stage + 1)
           print(f"✅ Stage {state.current_stage} gate passed. Advanced.")
   else:
       if user_signaled_done:
           print(f"🚫 Cannot advance. Unmet: {gate_result.unmet}")
           exit 2  # block stop
       else:
           print(f"⚠️ Stage {state.current_stage}: {gate_result.passed}/{gate_result.total} gate criteria met.")

6. # Step 4: Skill mining (async via subprocess)
   subprocess_no_wait(["python", "scripts/mine-skills.py", "--session", session_id])

7. exit 0
```

### 2.6 subagent-stop.py

Captures subagent output, updates state.md with what was accomplished.
Simple: parse output, append to "## Subagent Activity" section.

### 2.7 session-end.py

```
1. Final state persist (state.md is always current, just touch it)
2. Write .forge/sessions/{timestamp}.md with:
   - Duration
   - Tasks worked on (from progress.md diff)
   - Lessons added (from lessons.md diff)
   - Files modified (from session-log.jsonl)
3. exit 0
```

---

## 3. Script Specifications

### 3.1 state-manager.py

CLI:
```bash
python scripts/state-manager.py read              # → JSON of current state
python scripts/state-manager.py advance           # → advance to next stage
python scripts/state-manager.py set-task T-007    # → update current_task
python scripts/state-manager.py reflect "text"    # → append to reflection
```

**Implementation**:
- Parse YAML frontmatter from `pipeline/state.md`
- Use `python-frontmatter` lib (declared in requirements.txt)
- Atomic writes via tempfile + rename

### 3.2 check-gate.py

CLI:
```bash
python scripts/check-gate.py --stage 6
# → JSON: {"stage": 6, "criteria": [...], "passed": 5, "failed": 2, "details": [...]}
```

**Algorithm**:
```
1. Load references/gate-criteria.md (YAML sections per stage).
2. For stage N, iterate criteria.
3. Each criterion has a "check" type:
     - file_exists: check artifact path
     - file_contains: regex match on file
     - script_returns_zero: run a verification script
     - all_tests_pass: invoke pytest with markers
4. Aggregate results, return JSON.
```

### 3.3 extract-lessons.py

CLI:
```bash
python scripts/extract-lessons.py \
    --transcript /path/to/transcript \
    --since-flag /path/to/correction-flags.jsonl
# → YAML list of new lessons
```

**Algorithm**: Parse transcript, look for correction patterns, infer rule from context.
Returns `[{trigger, rule, why, tags}]`.

This is the trickiest script — likely calls Claude itself for inference. Spec:
- Use Anthropic SDK if available
- Prompt: "Given this correction context, extract a Trigger/Rule/Why lesson"
- If no API key, fall back to rule-based extraction (worse quality but works offline)

### 3.4 mine-skills.py

CLI:
```bash
python scripts/mine-skills.py --session <id>
# → 0 if no proposals, 1+ if proposals (with paths in stdout)
```

**Algorithm**:
```
1. Aggregate .forge/patterns.jsonl by signature
2. Filter: frequency ≥ 3, not in blacklist
3. For each candidate: invoke skill-miner agent (or rule-based generator)
4. Write proposals to .forge/proposed-skills/<name>/SKILL.md
5. Print proposal paths
```

### 3.5 token-audit.py, traceability-check.py, context-pruner.py, validate-plugin.py, validate-skill.py

Detailed in respective task prompts (see `prompts/development/`).

---

## 4. Skill File Contracts

Every SKILL.md in `skills/` follows:

```markdown
---
name: forge-<stage|action>
description: <when to use, pushy phrasing for triggering>
allowed-tools: [...]  # optional, restricts what the skill can call
disable-model-invocation: false  # default — allow auto-invoke
---

# <Skill Name>

## When to Use
<explicit trigger conditions>

## Steps
1. <step 1>
2. <step 2>
...

## Verification
<how to know it worked>
```

---

## 5. Agent File Contracts

Every agent in `agents/` follows:

```markdown
---
name: <agent-name>
description: <purpose>
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, WebSearch]  # subset
model: <optional override>
---

# <Agent Name>

## Role
<persona description>

## Goal
<what they aim to achieve>

## Context Scope
<which files/artifacts they read; explicit list>

## Output Contract
<what they must produce — exact filenames>

## Workflow
<numbered steps>

## Examples
<good/bad output samples>
```

---

## 6. State File Schemas

### 6.1 pipeline/state.md (with YAML frontmatter)

See `architecture.md` §4.2.

### 6.2 .forge/lessons.yaml

```yaml
schema_version: 1
lessons:
  - id: L-NNN
    stage: [int]            # which stages this applies to
    project_types: [string] # which profiles this applies to (or [] for all)
    trigger: string         # when this lesson kicks in
    rule: string            # what to do
    why: string             # why this matters
    frequency: int          # times applied
    last_used: iso_date
    tags: [string]
```

### 6.3 .forge/patterns.jsonl

Append-only JSONL. Each line:
```json
{
  "ts": "iso8601",
  "session": "string",
  "kind": "tool_seq | instruction | fix_pattern",
  "signature": "hash of normalized pattern",
  "details": { ... }
}
```

---

## 7. Test Strategy

### 7.1 Unit Tests (`tests/unit/`)

- One file per hook, one file per script
- Synthetic stdin/stdout
- No real filesystem dependencies (use `tmp_path` fixture)
- Coverage target: > 80%

### 7.2 Integration Tests (`tests/integration/`)

- Hook + script chains: e.g., write a violation → pre-tool-write detects it
- State transitions: advance through stages, verify state.md
- Lesson lifecycle: create → inject → use → promote

### 7.3 End-to-End Test

`tests/integration/full-pipeline.sh`:
1. Initialize fresh project in `examples/sample-todo-api/`
2. Install plugin via `--plugin-dir`
3. Run headless Claude (`claude -p`) through stages 1–12 with scripted prompts
4. Assert all artifacts exist
5. Assert traceability chain holds (REQ → FEAT → Task → Test)

---

## 8. Performance Budgets

| Component | Target | Measurement |
|-----------|--------|-------------|
| session-start.py | < 100ms | `time` in test |
| prompt-submit.py | < 50ms | `time` in test |
| pre-tool-write.py | < 50ms | `time` in test |
| post-tool-use.py | < 100ms (async, doesn't block) | `time` in test |
| stop-reflect.py | < 5s | `time` in test |
| Total per-event hook overhead | < 200ms | aggregated |

---

## 9. Migration Strategy

For schema_version bumps in state.md or lessons.yaml:

1. SessionStart detects version mismatch
2. Looks for `scripts/migrate/v<old>-to-v<new>.py`
3. If found, runs migration with backup of original
4. If not found, prints warning, continues with best-effort parse
