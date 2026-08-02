#!/usr/bin/env node
/**
 * Forge — SDLC Orchestrator for OpenCode
 *
 * Ported from Forge (Claude Code plugin) to OpenCode plugin API.
 * Routes lifecycle events to Python hook scripts via subprocess.
 *
 * Event mapping:
 *   session.created       → session-start.py
 *   message.send.before   → prompt-submit.py
 *   tool.execute.before   → pre-tool-write.py
 *   tool.execute.after    → post-tool-use.py
 *   session.idle          → stop-reflect.py
 *   session.compacted     → pre-compact.py
 *   session.deleted       → session-end.py
 */

import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { spawn } from "child_process";
import { existsSync } from "fs";

const __dirname = dirname(fileURLToPath(import.meta.url));

/**
 * Run a Python hook script with JSON payload on stdin.
 * Returns { stdout, stderr, exitCode }.
 */
async function runHook(scriptPath, payload, timeoutMs = 30_000) {
  return new Promise((resolve, reject) => {
    const proc = spawn("python3", [scriptPath], {
      stdio: ["pipe", "pipe", "pipe"],
      env: {
        ...process.env,
        FORGE_ROOT: __dirname,
        FORGE_OPENCODE_PLUGIN_ROOT: __dirname,
        FORGE_PROJECT_ROOT: payload.cwd || process.cwd(),
        CLAUDE_PLUGIN_ROOT: __dirname,
        CLAUDE_PROJECT_DIR: payload.cwd || process.cwd(),
      },
    });

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (chunk) => (stdout += chunk.toString()));
    proc.stderr.on("data", (chunk) => (stderr += chunk.toString()));

    const timer = setTimeout(() => {
      proc.kill("SIGTERM");
      reject(new Error(`Hook ${scriptPath} timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    proc.on("close", (code) => {
      clearTimeout(timer);
      resolve({ stdout, stderr, exitCode: code ?? 1 });
    });

    proc.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });

    proc.stdin.write(JSON.stringify(payload));
    proc.stdin.end();
  });
}

/**
 * Resolve a hook script path relative to the plugin's scripts/ dir.
 */
function hookScript(name) {
  // Try hooks/ first (Python hook scripts), then scripts/ (helpers)
  const hooksPath = resolve(__dirname, "hooks", name);
  if (existsSync(hooksPath)) return hooksPath;

  const scriptsPath = resolve(__dirname, "scripts", name);
  if (existsSync(scriptsPath)) return scriptsPath;

  return hooksPath; // will fail gracefully in runHook
}

// ──────────────────────────────────────────────────────────────
// OpenCode Plugin Entry Point
// ──────────────────────────────────────────────────────────────

export default async function forgePlugin(context) {
  const { project, $ } = context;
  const projectRoot = project?.root || process.cwd();

  /**
   * Build a payload matching what Forge's Python hooks expect on stdin.
   */
  function buildPayload(eventType, eventData = {}) {
    return {
      cwd: projectRoot,
      session_id: eventData.sessionId || "opencode",
      hook_event_name: eventType,
      ...eventData,
    };
  }

  return {
    event: async ({ event }) => {
      const { type, data } = event;

      try {
        switch (type) {
          // ── Session Start ──────────────────────────────
          case "session.created": {
            const payload = buildPayload("SessionStart", {
              trigger: data?.trigger || "startup",
              sessionId: data?.sessionId,
            });
            const result = await runHook(
              hookScript("session-start.py"),
              payload,
            );
            // Inject context from hook output
            if (result.stdout.trim()) {
              const msg = result.stdout.trim();
              console.log(msg.startsWith("[Forge]") ? msg : `[Forge] ${msg}`);
            }
            break;
          }

          // ── User Prompt Submit ─────────────────────────
          case "message.send.before": {
            const payload = buildPayload("UserPromptSubmit", {
              prompt: data?.message || data?.content || "",
              sessionId: data?.sessionId,
            });
            const result = await runHook(
              hookScript("prompt-submit.py"),
              payload,
            );
            if (result.stdout.trim()) {
              try {
                const parsed = JSON.parse(result.stdout);
                if (parsed.additionalContext) {
                  const ctx = parsed.additionalContext;
                  console.log(ctx.startsWith("[Forge]") ? ctx : `[Forge] ${ctx}`);
                }
              } catch {
                const msg = result.stdout.trim();
                console.log(msg.startsWith("[Forge]") ? msg : `[Forge] ${msg}`);
              }
            }
            break;
          }

          // ── Pre Tool Use (Design System Enforcement) ───
          case "tool.execute.before": {
            const toolName = data?.tool || "";
            // Only intercept Write/Edit/MultiEdit file operations
            const isFileOp = ["Write", "Edit", "MultiEdit", "write", "edit"].includes(
              toolName,
            );
            if (!isFileOp) break;

            const payload = buildPayload("PreToolUse", {
              tool_name: toolName,
              tool_input: data?.args || data,
              sessionId: data?.sessionId,
            });
            const result = await runHook(
              hookScript("pre-tool-write.py"),
              payload,
            );
            // Check for blocking decision
            if (result.exitCode === 2) {
              return { override: true, decision: "deny", reason: result.stdout || "Forge rule violation" };
            }
            break;
          }

          // ── Post Tool Use (Logging) ────────────────────
          case "tool.execute.after": {
            const payload = buildPayload("PostToolUse", {
              tool_name: data?.tool || "",
              tool_response: data?.result || null,
              tool_input: data?.args || null,
              sessionId: data?.sessionId,
            });
            await runHook(hookScript("post-tool-use.py"), payload);
            break;
          }

          // ── Session Idle (Reflection + Lessons) ────────
          case "session.idle": {
            const payload = buildPayload("Stop", {
              stop_hook_active: false,
              sessionId: data?.sessionId,
            });
            const result = await runHook(hookScript("stop-reflect.py"), payload);
            if (result.exitCode === 2) {
              // Stop hook wants to keep going
              console.log(`[Forge] Reflection suggests more work needed.`);
            }
            break;
          }

          // ── Session Compacted (Checkpoint) ─────────────
          case "session.compacted": {
            const payload = buildPayload("PreCompact", {
              sessionId: data?.sessionId,
            });
            await runHook(hookScript("pre-compact.py"), payload);
            break;
          }

          // ── Session Deleted (Cleanup) ──────────────────
          case "session.deleted": {
            const payload = buildPayload("SessionEnd", {
              usage: data?.usage || {},
              sessionId: data?.sessionId,
            });
            await runHook(hookScript("session-end.py"), payload);
            break;
          }
        }
      } catch (err) {
        // Forge hooks never crash the session — best-effort only
        console.error(`[Forge] Hook error (${type}): ${err.message}`);
      }
    },
  };
}
