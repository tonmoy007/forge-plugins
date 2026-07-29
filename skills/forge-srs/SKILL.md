---
name: forge-srs
description: Run Stage 1 of the Forge pipeline — requirements analysis. Use when the
  user says /forge:srs, wants to write requirements, define what to build, produce an
  SRS, or start a new project with Forge. Invokes the requirements-analyst persona.
allowed-tools: [Read, Write, WebSearch, WebFetch, Grep]
---

# /forge:srs — Requirements Analysis

## Purpose

This skill orchestrates Stage 1 of the Forge pipeline.

Its responsibilities are limited to:

- Validating pipeline state
- Loading stage configuration
- Loading the Requirements Analyst persona
- Executing the persona workflow
- Verifying required artifacts
- Advancing pipeline state
- Presenting the next-stage guidance

All requirements elicitation, clarification, analysis, prioritization, validation,
and SRS generation are owned exclusively by the Requirements Analyst persona.

---

## When to Use

Invoke this skill when:

- The user enters `/forge:srs`
- The user wants to define software requirements
- The user wants to write or refine an SRS
- The user wants to describe what should be built
- The user is starting a new Forge project
- The project is currently in Stage 0 or Stage 1

---

## Pre-flight Check

### 1. Verify Forge Project

Read:

`pipeline/state.md`

If the file does not exist, inform the user that the current directory is not a
Forge project and stop.

---

### 2. Validate Current Stage

Read the current stage from:

`pipeline/state.md`

If `current_stage > 1`:

- Inform the user that Stage 1 has already been completed.
- Ask whether they want to:
  - revise the existing SRS,
  - regenerate the SRS from scratch, or
  - leave it unchanged.
- Never overwrite `pipeline/01-srs/srs.md` without explicit confirmation.

If `current_stage == 1`:

Continue in refinement mode.

If `current_stage == 0`:

Continue normally.

---

### 3. Load Stage Profile

Execute:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 1
```

Load any stage-specific profile overrides including:

- domain-specific emphasis
- additional artifacts
- validation criteria
- skipped sections
- additional requirement categories
- project-type concerns

These overrides supplement the Requirements Analyst workflow and must never
replace it.

---

## Execute Stage

### 1. Load Persona

Read:

`agents/requirements-analyst.md`

Adopt the Requirements Analyst persona completely.

---

### 2. Execute Persona Workflow

Execute the workflow exactly as defined in the Requirements Analyst persona.

The persona is solely responsible for:

- requirements elicitation
- clarification
- assumptions
- analysis
- categorization
- prioritization
- stakeholder mapping
- requirement validation
- acceptance criteria
- traceability
- SRS generation
- web research (when appropriate)

The persona conducts a single bounded round of clarification questions
(REQ-INTERACTIVE-CLARIFY-001) before writing `pipeline/01-srs/srs.md` — one
batch, not a drip. Unanswered questions become documented assumptions in
the SRS.

Apply any project profile overrides loaded during pre-flight.

If an existing SRS already exists, refine it incrementally unless the user has
explicitly requested regeneration.

---

## Verification

Before advancing the pipeline, verify that the persona produced a valid Stage 1
deliverable.

Required artifact:

- `pipeline/01-srs/srs.md`

The document must satisfy the Output Contract defined in
`agents/requirements-analyst.md`.

At minimum verify that it contains:

- Project overview
- Functional requirements
- Non-functional requirements
- Sequential REQ IDs
- Acceptance criteria
- Constraints and assumptions
- Open questions

If the persona generated:

`pipeline/01-srs/stakeholder-map.md`

verify that it was written successfully.

If any required artifact is missing or incomplete:

- Do NOT advance the pipeline.
- Inform the user which verification failed.
- Request any missing information if necessary.

---

## Advance Pipeline State

Only after successful verification execute:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 1
```

---

## Final Validation

Confirm:

- `pipeline/01-srs/srs.md` exists
- `pipeline/state.md` shows:

```yaml
current_stage: 1
```

---

## Completion Message

Provide a concise completion summary including:

- Number of functional requirements
- Number of non-functional requirements
- Number of unresolved questions
- Number of documented assumptions
- Any optional artifacts generated

Do not summarize the entire SRS unless requested.

---

## Next Step

Derive the next-stage guidance from the canonical pipeline state.

Never hardcode stage hints.

Execute:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 1
```

Present the command output to the user verbatim.

---

## Orchestration Rules

This skill SHALL:

- orchestrate Stage 1 only
- never redefine the Requirements Analyst workflow
- never duplicate business logic from the persona
- never bypass persona validation
- never advance the stage if verification fails
- never overwrite an existing SRS without user confirmation
- always honor stage profile overrides
- always use the Requirements Analyst as the single source of truth for Stage 1 behavior

The Requirements Analyst persona remains the authoritative definition of how
requirements analysis and SRS generation are performed.
