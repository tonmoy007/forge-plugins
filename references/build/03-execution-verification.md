# Stage 6 Pro — Execution and Verification

## Per-Task Loop

Every task follows the same deterministic sequence
(`BUILDER_PRO-PLAN.md`'s "Every Task" pipeline, scoped to what this phase actually
implements):

```text
load context   (script — references/build/02-context-resolution.md)
  → generate    (Builder Pro — code + tests, against the context bundle)
  → gate        (script — the four checks below, per-check report)
  → escalate or commit
      pass  → commit + progress write + traceability update + build-log append
      fail  → DEFECT-### opened (or attempt count incremented), no commit
```

If verification fails: **no commit.** Builder Pro never trusts itself — the gate is
mandatory, not advisory, on every single task with no exceptions.

## The Four-Check Gate

Carried forward from the deleted Revision-1 `quality-gate-runner.md` enumeration.
`scripts/build_executor.py` detects what the project already uses (`package.json`
scripts, `pytest`/`pyproject.toml`, the project's own lint/format config, `tsconfig.json`,
etc.) — it never invents a build system — then runs:

1. **Compile** — if the language has a compile/build step (TypeScript, Go, Rust,
   etc.); skipped with a stated reason for languages that don't compile (plain
   Python, JS without a bundler).
2. **Lint** — the project's configured linter/formatter (eslint, ruff, gofmt, etc.).
3. **Test** — the project's test suite; at minimum the tests touching the task's
   changed/new files, the full suite when it is fast enough to run.
4. **Static analysis** — the project's configured type-checker (mypy, `tsc
   --noEmit`, etc.) if configured.

Plus any Stage 6 `additional_criteria` from
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 6` — reported
as additional checks, never folded into one of the four core checks.

## Per-Check Report Shape

Never a single aggregate boolean. One line per check, minimum four plus one per
`additional_criteria` item:

```text
compile: pass | fail (<why>) | skipped (<reason>)
lint: pass | fail (<why>) | skipped (<reason>)
test: pass | fail (<why>) | skipped (<reason>)
static analysis: pass | fail (<why>) | skipped (<reason>)
<additional_criteria id>: pass | fail (<why>)
```

A caller must be able to see exactly which check failed, not just "gate failed."
`scripts/build_executor.py` commits only when every reported check is `pass` or a
justified `skipped` — any `fail` blocks the commit unconditionally.

## `DEFECT-###` — Escalation Identifier

First use of this identifier type in the repo; its lifecycle is fully specified
here, not just named.

- **Opened when**: the gate fails on the same task two consecutive attempts (the
  first failure is a normal retry signal — generate again against the same
  context bundle; the second consecutive failure on the same task escalates).
- **Fields**: `id` (`DEFECT-###`, zero-padded, sequential, allocated from the
  highest existing suffix in `build-log.jsonl`), `task_id`, `failing_check(s)`,
  `evidence` (the failing check's captured stderr/stdout tail), `attempts`,
  `status` (`open` | `resolved`), `opened_at`.
- **Recorded**: one `build-log.jsonl` line per attempt (see
  `references/build/05-workflow-governance.md` for the entry shape) plus a
  `DEFECT-###` line appended under the task's entry in
  `pipeline/06-implementation/progress.md`, so a human resuming the batch sees it
  without parsing the log.
- **Resolved when**: a subsequent attempt on the same task passes every gate check
  — the script marks the `DEFECT-###` `resolved` in the same progress.md line it
  updates to mark the task done. A `DEFECT-###` is never silently cleared; the
  resolving commit sha is the evidence.
- **Lifecycle owner**: the script opens and resolves `DEFECT-###` records
  mechanically (attempt-count and gate-outcome are deterministic signals);
  Builder Pro does not decide when one opens.

## Escalation Behavior

On a `DEFECT-###` open, the script stops attempting the task automatically (no
silent infinite retry loop) and reports the defect to the invoking skill, which
surfaces it to the user per `references/build/05-workflow-governance.md`'s failure
handling. Never proceed to the next task in a batch run while a `DEFECT-###` is open
on the current one unless the user explicitly directs a skip.
