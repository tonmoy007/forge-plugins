---
name: forge-product
description: >
  Run Stage 2 of the Forge pipeline — Product Design & UX. Transforms the
  approved Stage 1 SRS into complete, traceable product design artifacts
  including the PRD, user stories, personas, information architecture,
  navigation model, user flows, screen specifications, wireframes,
  component inventory, design system, UX decisions, and traceability matrix.
  Invokes the Product Designer persona.

allowed-tools:
  - Read
  - Write
  - WebSearch
  - WebFetch
---

# /forge:product

**Aliases:** `/forge:ux`, `/forge:product`

---

## Purpose

Stage 2 transforms an approved SRS into deterministic Product Design artifacts. Defines **what users experience**, not **how the software is built**. Output becomes canonical input for Stage 3 (Architecture).

---

## When To Use

- User invokes `/forge:product` or `/forge:ux`
- User requests: PRD, User Flows, User Stories, Personas, Wireframes, Design System, Information Architecture, Navigation Model, UX Specs, Product Design, Screen Specifications

---

## Stage Ownership

- **Stage:** 02 — Product Design & UX
- **Input:** Stage 1 SRS (`pipeline/01-srs/srs.md`)
- **Output:** Complete Product Design Specification (`pipeline/02-product-ux/`)

---

## Pre-flight Check

### 1. Entry Gate (REQ-GATE-ENTRY-001)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py preflight --stage 2
```

If non-zero: STOP. Display message verbatim. User must complete Stage 1 or use `/forge:force-advance`.

### 2. Project Verification

Read `pipeline/state.md`. Verify Forge project initialized, current stage valid, project profile exists. If invalid: STOP.

### 3. SRS Verification

Verify `pipeline/01-srs/srs.md` exists. If missing: return "Stage 1 (SRS) must be completed before Product Design. Run `/forge:srs`." Do not continue.

### 4. Stage Progress Check

If `current_stage > 2`, inform user Stage 2 appears completed. Ask whether to Review, Revise, or Regenerate. Do not overwrite without confirmation.

### 5. Load Project Profile

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 2
```

Profile overrides may include: `replace_with`, `skip_steps`, `additional_steps`, `additional_artifacts`, `artifact_templates`, `validation_rules`, `quality_gates`. Follow the loaded profile exactly. Never ignore overrides.

---

## Load Product Designer

Read `agents/product-designer.md`. Adopt the Product Designer persona completely.

---

## Read Context

- Read `pipeline/state.md`
- Read `pipeline/01-srs/srs.md`
- Read existing `pipeline/02-product-ux/` files (for iteration/refinement only)

Never use architecture, implementation, API, or source code as design inputs.

---

## Execution Workflow

### Step 1 — Build Requirement Inventory
Identify: Functional, Non-functional, Business Rules, Constraints, UX Requirements, External Dependencies. Verify every requirement has a stable REQ-ID.

### Step 2 — Generate Personas (PER-001...)

### Step 3 — Group Requirements
Produce Epics(EP-001...), Capabilities(CAP-001...), Features(FE-001...). Every feature must reference originating REQ IDs.

### Step 4 — Generate User Stories(US-001...)
Each story includes: Story ID, Requirement References, Acceptance Criteria(AC-001...), Priority

### Step 5 — Create Information Architecture
Generate `information-architecture.md`

### Step 6 — Create Navigation Model
Generate `navigation.md`

### Step 7 — Generate User Flows(UF-001...)
Each flow includes: Flow ID, Actors, Preconditions, Main Flow, Alternate Flow, Exceptions, Postconditions, Screen References(SCR-001...)

### Step 8 — Generate Screen Specifications(SCR-001...)
Every screen defines: Purpose, Layout, Navigation, States, Permissions, Responsive Behaviour, Accessibility, Business Rules

### Step 9 — Generate Wireframes
Text only. No images.

### Step 10 — Generate Component Inventory(CMP-001...)
Each component includes: Component ID, Variants, States, Accessibility, Parent Screens

### Step 11 — Generate Design System
Include: Color Tokens, Typography, Spacing, Radius, Elevation, Motion, Component Standards

### Step 12 — Generate UX Decision Log(DDR-001...)
Generate `ux-decisions.md`

### Step 13 — Generate UX Risk Register(UXR-001...)
Generate `ux-risk-register.md`

### Step 14 — Generate Traceability Matrix
Create `traceability.md`. Map: `REQ → EP → CAP → FEAT → US → UF → SCR → CMP → AC`. No orphaned artifacts.

### Step 15 — Run Validation
Validate:
- Every requirement maps to a feature.
- Every feature maps to user stories.
- Every story maps to user flows.
- Every flow maps to screens.
- Every screen maps to components.
- Every component belongs to a screen.
- Every screen documents Accessibility, Responsive Behaviour, States.
- No duplicate IDs, invented functionality, or orphaned artifacts.

If validation fails: Repair automatically. Only stop if repair is impossible.

### Step 16 — Write Artifacts
Generate under `pipeline/02-product-ux/`:
```
prd.md
personas.md
information-architecture.md
navigation.md
user-stories.md
user-flows.md
wireframes.md
screen-specifications.md
components.md
design-system.md
ux-decisions.md
traceability.md
ux-risk-register.md
```
Do not omit required artifacts.

---

## Completion

### Advance Stage
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 2
```
If unsuccessful: STOP. Display the error.

### Verify Artifacts

All 13 files under `pipeline/02-product-ux/` exist. `pipeline/state.md` contains `current_stage: 2`. Confirm validation status: PASS or FAIL.

### Success Summary

Report: Requirements Processed, Personas Generated, Epics, Capabilities, Features, User Stories, User Flows, Screens, Components, Design Decisions, UX Risks, Validation Result

---

## Next Stage

Derive hint from canonical stage table (REQ-NEXTHINT-001). Run:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py next-hint --stage 2
```
Present output verbatim.

---

## Behavioral Rules

**Always:** Preserve complete traceability, produce deterministic identifiers, never invent functionality, keep design implementation-independent, prioritize clarity over creativity, prefer explicit documentation over assumptions, fail validation rather than producing ambiguous artifacts

**Never:** Design APIs, design databases, write implementation code, define infrastructure, skip accessibility, skip responsive behavior, skip validation, break traceability

---

## Success Criteria

Stage 2 complete only when:
- Every approved requirement is represented in downstream UX artifacts.
- All generated artifacts pass validation.
- All documents are written successfully.
- Stage state is advanced to 2.
- Next stage hint has been displayed.

The Product Design specification MUST be complete enough that a software architect can begin Stage 3 without additional stakeholder clarification.
