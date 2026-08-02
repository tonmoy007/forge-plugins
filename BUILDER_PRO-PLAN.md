# BUILDER PRO-PLAN
I think **the Builder is the heart of the system**, not just "Stage 6". It's the execution engine that converts all previous artifacts into production code.

My biggest recommendation is to **stop thinking of it as a coding agent** and instead think of it as an **Execution Orchestrator**.

---

# My Proposed Stage 6

```
Requirements
        │
Product Design
        │
Architecture
        │
Technical Spec
        │
Implementation Plan
        │
Sprint (optional)
        │
──────────────────────────────
        │
   BUILDER
        │
──────────────────────────────
        │
Code
Tests
Docs
Commits
Progress
Verification
```

The Builder should consume **everything**.

---

# Builder Mission

Instead of

> "Generate code"

The mission should be

> Execute the implementation plan deterministically while maintaining traceability, quality, and recoverability.

That single sentence changes everything.

---

# Builder Owns

I would make Builder own only execution artifacts.

```
pipeline/06-implementation/

progress.md

build-log.md

generated-files.md

verification.md

test-results.md

implementation-decisions.md

coverage.md

quality-report.md

dependency-report.md

execution-trace.md

rollback.md

```

Notice:

It owns

execution

not

requirements.

---

# Builder Reads

Builder reads

```
Stage 1

SRS

↓

Stage 2

PRD

↓

Stage 3

Architecture

↓

Stage 4

Technical Spec

↓

Stage 5

Implementation Plan

↓

Sprint
(optional)
```

Builder should never ask

> "What should I build?"

Everything is already specified.

---

# Builder Doesn't Think

This is a huge difference.

Stages 1–5 are reasoning stages.

Stage 6 should mostly execute.

Meaning

```
TASK-041

↓

Read

↓

Find Spec

↓

Find Module

↓

Find Interfaces

↓

Generate

↓

Verify

↓

Commit

↓

Update Progress
```

not

```
Invent architecture

Invent APIs

Invent behavior
```

---

# Internal Architecture

I'd split Builder internally into specialized execution agents.

```
Execution Orchestrator

├── Context Loader

├── Task Resolver

├── Code Generator

├── Refactoring Agent

├── Test Generator

├── Documentation Generator

├── Linter

├── Static Analyzer

├── Build Runner

├── Verification Agent

├── Commit Generator

├── Progress Updater

└── Recovery Agent
```

One giant coding prompt won't scale.

---

# Context Resolution

Builder should never load the whole project.

Instead

```
TASK-014

↓

Find module

↓

Find interfaces

↓

Find DTO

↓

Find requirements

↓

Load ONLY relevant docs

↓

Generate
```

Token usage becomes tiny.

---

# Every Task

Every task should follow

```
Load Context

↓

Verify Inputs

↓

Generate Code

↓

Compile

↓

Run Tests

↓

Lint

↓

Static Analysis

↓

Verify Spec

↓

Update Progress

↓

Commit
```

This is deterministic.

---

# Traceability

This is where Forge can become unique.

Every generated file should know why it exists.

```
auth_controller.ts

↓

TASK-044

↓

MOD-007

↓

SPEC-003

↓

ADR-002

↓

REQ-F-019
```

Imagine

```
forge explain auth_controller.ts
```

returns

```
Generated from

TASK-044

↓

MOD-007

↓

SPEC-003

↓

REQ-F-019
```

That's incredible for maintenance.

---

# Builder Modes

I wouldn't have one mode.

I'd have

```
build task

build module

build work-package

build milestone

build sprint

build project
```

All use the same engine.

Only the scope changes.

---

# Verification

Builder should never trust itself.

Every build

```
Generate

↓

Compile

↓

Test

↓

Compare to Spec

↓

Architecture Validation

↓

Requirement Validation

↓

Coverage

↓

Quality Gates
```

If verification fails

No commit.

---

# Incremental

Never regenerate.

Instead

```
Current code

+

Task

↓

Patch

↓

Verify

↓

Commit
```

This is how humans work.

---

# Recovery

Builder should be resumable.

```
TASK-041

completed

TASK-042

failed

TASK-043

not started
```

Restart

```
Continue from TASK-042
```

No recomputation.

---

# AI Agnostic

Builder shouldn't know Claude or GPT.

Instead

```
Execution Kernel

↓

Claude Adapter

GPT Adapter

Codex Adapter

Gemini Adapter

OpenHands Adapter

Local Model Adapter
```

Exactly like your kernel abstraction.

---

# Quality Gates

I would enforce

```
Compile

Tests

Lint

Formatting

Static Analysis

Architecture Validation

Specification Validation

Requirement Validation

Coverage

Security Scan
```

No gate

No completion.

---

# Progress

Instead of

```
Done
```

I'd keep

```
TASK-041

Started

Completed

Files

Commit

Tests

Coverage

Duration

Verification

Rollback

Dependencies
```

Almost like a CI pipeline.

---

# Enterprise Artifacts

Builder could produce

```
generated-files.md

execution-trace.md

verification.md

coverage.md

dependency-report.md

quality-report.md

security-report.md

implementation-decisions.md

```

These become invaluable for audits and debugging.

---

# My Overall Vision

If I were designing Forge from scratch, I'd model Stage 6 as an **Execution Engine**, not a code generator. Stages 1–5 progressively eliminate ambiguity until Stage 6 has a single responsibility: execute a deterministic implementation plan while preserving traceability and enforcing quality gates.

The resulting architecture would look like this:

```text
Requirements
      │
      ▼
Product Design
      │
      ▼
Architecture
      │
      ▼
Technical Specification
      │
      ▼
Implementation Planning
      │
      ▼
Sprint Planning (optional)
      │
      ▼
═══════════════════════════════
      Forge Builder
═══════════════════════════════
      │
Context Resolution
      │
Task Execution
      │
Code Generation
      │
Verification
      │
Commit
      │
Progress Tracking
      │
Traceability Update
═══════════════════════════════
      ▼
Production-Ready Code
```

This design also positions Forge well for future capabilities like distributed AI agents, resumable builds, human-in-the-loop approvals, and continuous implementation, because the Builder is orchestrating execution rather than simply emitting code. In my view, that's the architectural leap that distinguishes an SDLC operating system from a sophisticated code-generation tool.

Phase 1 — Normalize stages 1–3 to thin-router

Refactor to proven pattern: agent ~130 lines + references/<domain>/01–05.md, skill lists mandatory reference loads.

- references/srs/01–05.md ← from 616-line agent
- references/product/01–05.md ← from 347-line agent
- references/architect/ — renumber existing 4 files to 01–05, move the 554-line skill's inline logic in

Use the fingerprint-diff verification from the sprint refactor (paragraph-block extraction + 80-char key lookup). Caught a dropped sentence last time. It works — reuse it.

Phase 2 — Builder Pro

Per your own workflow rule: SRS + task-DAG docs before code.

Shape it same as stages 4/5:

agents/builder-pro.md              ~130 lines, thin router
references/build/
  01-foundation.md                 ownership, scope, IDs, output contract
  02-context-resolution.md         task → module → interfaces → minimal load
  03-execution-verification.md     per-task loop, gates, escalation, DEFECT-###
  04-traceability-validation.md    file → TASK → SPEC → REQ, extends existing chain
  05-workflow-governance.md        modes, resume, profiles, parallel, failure, report
skills/forge-build-pro/SKILL.md    orchestration only, zero domain logic
scripts/build_executor.py          deterministic engine — reuses parallel_build.py

Split of labor:
- Script owns: context resolve, gate execution, commit, progress write, build-log.jsonl, resume, worktree/parallel
- Agent owns: generate code, generate tests, verify against spec — t
- Artifacts: progress.md + build-log.jsonl + traceability extension. Reports on demand.

---
Sanity check: I verified every claim above against the files — frontmatter read directly on all 12 pro files, agent refs by grep, registration gap by grep across scripts/ hooks/ tests/ .claude-plugin/, manifest confirmed directory-scan via JSON parse. No code changed; read-only session.                                    
result: Verdict delivered — Pro stages 1–3 are unreachable dead code (6 name: collisions with Classic + 3 skills loading non-Pro agents), stages 4/5/sprint are correct; BUILDER_PRO-PLAN's execution-orchestrator vision is sound but must cut the provider-adapter layer, 13 sub-agents → 3, and 11 artifacts → 2; recommended sequence is Phase 0 fix-and-register-Pro (+ duplicate-name test), Ph the thin-router pattern, then Phase 2 Builder Pro.
