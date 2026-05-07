# Claude Code Hooks Reference

> Quick reference for Claude when implementing hooks.
> Source: Claude Code docs, current as of 2026-Q1.

## Hook Events

| Event | Cadence | Can Block? | Use Case |
|-------|---------|------------|----------|
| `SessionStart` | Once per session | No | Inject context |
| `UserPromptSubmit` | Per turn | Yes (modify prompt) | Add context, validate prompts |
| `PreToolUse` | Per tool call | **Yes** (exit 2) | Block dangerous ops, modify input |
| `PostToolUse` | Per tool call | No (can prompt Claude) | Logging, validation, formatting |
| `PostToolUseFailure` | Per failed tool | No | Error handling |
| `SubagentStart` | Per subagent | No | Setup |
| `SubagentStop` | Per subagent | **Yes** (exit 2 forces continue) | Validation |
| `Notification` | Async | No | UI notifications |
| `Stop` | Per turn | **Yes** (exit 2) | Quality gates |
| `StopFailure` | On error | No | Recovery |
| `PreCompact` | Pre context compact | No | Backup |
| `SessionEnd` | Once per session | No | Cleanup |

## Hook Handler Types

1. **Command** — runs a shell command, JSON on stdin, JSON/text on stdout
2. **Prompt** — invokes Claude with a prompt template
3. **Agent** — invokes a subagent with full tool access
4. **HTTP** — POSTs to an HTTP endpoint
5. **MCP Tool** — invokes an MCP server tool

Forge uses **command hooks** exclusively (Python scripts).

## Hook Input/Output

### Input (stdin)

JSON with at minimum:
```json
{
  "session_id": "string",
  "hook_event_name": "Stop",
  "transcript_path": "/path/to/transcript",
  "cwd": "/path/to/working/dir"
}
```

Plus event-specific fields:

- **PreToolUse / PostToolUse**: `tool_name`, `tool_input`, `tool_response` (post only)
- **UserPromptSubmit**: `prompt` (string)
- **SessionStart**: `trigger` (startup|resume|clear|compact)
- **Stop**: `stop_hook_active` (bool — true if this hook is calling itself, prevent loops)

### Output (stdout)

**Plain text** — gets injected into Claude's context.

**JSON** — structured response:

```json
{
  "hookSpecificOutput": {
    "additionalContext": "string",
    "permissionDecision": "allow|deny|ask",
    "updatedInput": { ... }
  },
  "decision": "block",
  "reason": "explanation shown to user/Claude"
}
```

### Exit Codes

- `0` — success, continue normally
- `2` — **blocking signal** (effect varies by event):
  - PreToolUse: deny the tool call
  - Stop: prevent stopping (force Claude to continue)
  - SubagentStop: prevent stopping
- Other non-zero — log warning, continue

## Hook Configuration in plugin.json

```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "regex|empty for all",
        "hooks": [
          {
            "type": "command",
            "command": "python ${CLAUDE_PLUGIN_DIR}/hooks/script.py",
            "timeout": 5,
            "async": false
          }
        ]
      }
    ]
  }
}
```

**Matcher rules**:
- Empty `""` matches everything
- Pipe-separated: `Write|Edit|MultiEdit`
- **No spaces around `|`**
- Case-sensitive
- Specific events have specific matchers (PreToolUse: tool name; SessionStart: trigger type)

**Variables available in commands**:
- `${CLAUDE_PLUGIN_DIR}` — absolute path to plugin root
- `${CLAUDE_TOOL_INPUT_FILE_PATH}` — for tool hooks, the file being acted on
- `${CLAUDE_PROJECT_DIR}` — user's working directory

## Common Patterns

### Block dangerous bash commands

```python
import json, sys, re
data = json.load(sys.stdin)
cmd = data.get("tool_input", {}).get("command", "")
if re.search(r'rm\s+-rf\s+/', cmd):
    print("Blocked: dangerous rm")
    sys.exit(2)
sys.exit(0)
```

### Inject context on session start

```python
import json, sys
data = json.load(sys.stdin)
print(f"[Forge] You're in {data['cwd']}")
sys.exit(0)
```

### Add additionalContext from PreToolUse

```python
import json, sys
data = json.load(sys.stdin)
output = {
    "hookSpecificOutput": {
        "additionalContext": "Reminder: this file uses design tokens"
    }
}
print(json.dumps(output))
sys.exit(0)
```

## Gotchas

1. **Do not use `print()` for debugging in hooks**. It gets injected into Claude's context.
   Use `logging` to a file, or `sys.stderr`.

2. **Hooks must be fast**. Cumulative latency across all hooks per event matters.
   Stay under 200ms total per event.

3. **Hooks run in user shell context** with full filesystem access. Be careful what you write.

4. **Async hooks** run in background but can't return a decision. Use for logging only.

5. **`stop_hook_active`** — if your Stop hook calls Claude (which can stop again), check this
   flag to prevent infinite loops:
   ```python
   if data.get("stop_hook_active"):
       sys.exit(0)
   ```

6. **Hook order** — multiple hooks for the same event run in parallel by default.
   Forge runs them sequentially via a single dispatcher script when order matters.

7. **Errors propagate** — a hook crashing with non-2 exit code doesn't break the session,
   but stderr output appears in transcript. Keep error handling tight.

## Testing Hooks Locally

```bash
# Test with synthetic input
echo '{"session_id": "test", "hook_event_name": "Stop", "cwd": "'$(pwd)'", "transcript_path": ""}' \
  | python hooks/stop-reflect.py
echo "Exit: $?"

# Test with real-looking transcript
echo '{...}' | python hooks/stop-reflect.py 2>stderr.log
cat stderr.log
```

## Reload After Changes

In Claude Code: `/reload-plugins` — picks up changes to hooks, skills, agents without restart.
