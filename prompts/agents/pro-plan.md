You are working inside the Forge SDLC plugin/Orchestrator repository.

## Objective

Upgrade Stage 5 (Implementation Planning) to match the architecture, rigor, determinism, traceability, and enterprise quality of the redesigned Stages 1–4.

DO NOT modify existing files. Create NEW files with the prefix:
- `agents/planner-pro.md`
- `skills/forge-plan-pro/SKILL.md`

The existing files must remain untouched.

---

## BACKGROUND

Forge is a deterministic multi-stage SDLC orchestration framework/plugin for coding agents/harness platforms, currently supporting Claude Code and OpenCode.

**Core principles:**
- Each stage owns its artifacts
- Each stage extends the previous stage
- No stage may redefine artifacts created earlier
- Traceability is append-only
- Determinism is the priority of the pipeline

**Pipeline:**
```
Stage 1: Requirements Engineering ↓
Stage 2: Product Design ↓
Stage 3: System Architecture ↓
Stage 4: Technical Specification ↓
Stage 5: Implementation Planning ↓
Stage 6: Implementation ↓
Stage 7: Testing ↓
Stage 8: Deployment ↓
Stage 9+: Operations
```

---

## MISSION OF STAGE 5

Stage 5 transforms the approved Technical Specification into an executable implementation plan. This stage is the bridge between specification and coding.

**It answers:**
- WHAT should be built first
- WHO owns it
- IN WHAT ORDER
- WHAT DEPENDS ON WHAT
- WHAT CAN BE BUILT IN PARALLEL
- HOW THE WORK SHOULD BE VERIFIED

**Stage 5 SHALL NOT:** write production code, redesign the architecture, or modify requirements.

---

## CURRENT STAGE OWNERSHIP

**Stage 1 owns:** Business Goals, Requirements, Business Rules, Constraints, Assumptions, Dependencies, Risks, Success Criteria

**Stage 2 owns:** Epics, Capabilities, Features, User Stories, User Flows, Navigation, Screens, Components, UX Acceptance Criteria

**Stage 3 owns:** Architecture, Services, Containers, Deployment, Data Model, API Inventory, ADRs, Architecture Decisions

**Stage 4 owns:** Technical Specification, Modules, Interfaces, DTOs, Contracts, Configuration, Validation Rules, Error Catalog, State Machines, Performance Contracts, Security Contracts

**Stage 5 SHALL NOT recreate any of the above. It extends them.**

---

## STAGE 5 SHOULD OWN

- Implementation Plan, Implementation Phases, Milestones, Work Packages, Development Tasks
- Task Breakdown, Task Dependencies, Task Priority, Execution Order, Parallelization Plan
- Developer Assignment Guidance, Implementation Waves, Repository Structure Mapping
- Branch Strategy, Commit Strategy, Definition of Ready, Definition of Done
- Implementation Checklists, Code Generation Order, Implementation Risks
- Technical Debt Register, Implementation Assumptions, Implementation Constraints
- Verification Gates, Build Order, Integration Order, Migration Plan, Rollback Plan
- Task Traceability, Delivery Plan

---

## TRACEABILITY

Stage 5 extends Stage 4. The complete lineage becomes:

```
BG → REQ → EP → CAP → FEAT → US → UF → SCR → CMP → API → SRV → DB → ADR → SPEC → MOD → INT → DTO → CFG → ERR → PLAN → PHASE → WP → TASK → CHECKLIST → CODE
```

Stage 5 SHALL NOT invent parent artifacts. Every planning artifact must reference upstream IDs.

---

## IDENTIFIERS

Create deterministic identifiers:

- PLAN-001, PHASE-001, WP-001, TASK-001, CHK-001, MILE-001
- RISK-PLAN-001, TD-001, CODE-READY-001, DONE-001

Never reuse identifiers from previous stages.

---

## PRIMARY GOAL

Produce a deterministic implementation roadmap that allows multiple developers or AI coding agents to execute work independently with minimal ambiguity.

The output should support: Human teams, AI coding agents, Parallel development, Incremental delivery, Enterprise governance.

---

## OUTPUT CONTRACT

Generate an enterprise-grade agent. Expected length 500–700+ lines. The agent should contain sections including:

Role, Primary Goal, Stage Ownership, Responsibilities, Context Scope, Artifact Ownership, Implementation Planning Principles, Planning Philosophy, Execution Principles, Task Decomposition Rules, Dependency Analysis, Parallelization Rules, Milestone Planning, Risk Planning, Technical Debt Planning, Definition of Ready, Definition of Done, Task Identifier Rules, Deliverables, Output Contract, Traceability Rules, Repository Planning, Branching Strategy, Commit Strategy, Implementation Order, Integration Order, Migration Planning, Rollback Planning, Verification Gates, Quality Gates, Workflow, Validation Rules, Revision Behaviour, Failure Behaviour, Completion Report, Behavioral Rules, Web Research Policy, Completion Message.

---

## DELIVERABLES

Generate planning artifacts in `pipeline/05-implementation-plan/`:

- implementation-plan.md, implementation-phases.md, work-packages.md, task-breakdown.md
- dependency-graph.md, parallelization-plan.md, repository-plan.md, branch-strategy.md
- milestones.md, definition-of-ready.md, definition-of-done.md
- implementation-risk-register.md, technical-debt-register.md, traceability.md

The exact artifact set should be configurable through project profiles.

---

## TASK DECOMPOSITION

Every task must have: deterministic ID, reference upstream artifacts, be independently executable and verifiable, contain effort estimate, dependencies, outputs, completion criteria, acceptance checks, implementation notes, ownership guidance.

Never create vague tasks.

**Example:**
```
TASK-042
Implements: MOD-008, INT-003, REQ-F-014
Estimated effort: 8 hours
Depends on: TASK-011, TASK-018
Produces: Authentication Service
Verification: Unit tests pass, Static analysis passes, Integration contract satisfied
```

---

## PARALLELIZATION

Identify: Independent work streams, Merge points, Shared modules, Blocking tasks, Critical path, Concurrency opportunities.

Provide explicit execution ordering.

---

## DEFINITION OF READY

Every task shall define: Inputs available, Dependencies complete, Specifications approved, Architecture approved, No blockers.

---

## DEFINITION OF DONE

Every task shall define: Implementation complete, Tests written, Lint passes, Contracts satisfied, Documentation updated, Ready for review.

---

## QUALITY GATES

Validate:
- Every module has implementation tasks
- Every interface has implementation tasks
- Every task references specifications
- Every work package references modules
- Every milestone references work packages
- No orphan tasks, No duplicate IDs, No cyclic dependencies
- Execution order is deterministic

---

## SKILL REQUIREMENTS

Generate `skills/forge-plan-pro/SKILL.md`. The skill shall be orchestration only. It SHALL NOT duplicate planning logic.

**It SHALL:**
- Run `state-manager.py preflight --stage 5`
- Load `load-profile.py`
- Read `agents/planner-pro.md`
- Execute the persona
- Verify generated artifacts, traceability, planning completeness, stage ownership
- Advance: `state-manager.py advance --to 5`
- Present `next-hint`

The orchestration architecture must match the redesigned Stage 1–4 skills.

---

## LARGE DOCUMENT SUPPORT

Support `read-doc.py`. Support split documents. Never hardcode implementation-plan.md. Always use the document resolver.

---

## PROFILE SUPPORT

Honor project profile overrides. Support: replace_with, additional_artifacts, additional_steps, additional_concerns, skip_steps.

Examples: Microservices, Monolith, Library, CLI, Mobile, ML, Embedded, Infrastructure, API, Event-driven.

---

## VALIDATION

Include deterministic validation:
- Every task references specifications
- Every task belongs to a work package
- Every work package belongs to a phase
- Every phase belongs to the implementation plan
- Every milestone has measurable exit criteria
- No orphan planning artifacts
- No implementation code
- No duplicated work
- No circular task dependencies
- No missing upstream references

---

## IMPORTANT

Do NOT overwrite existing files. Create ONLY:
- `agents/planner-pro.md`
- `skills/forge-plan-pro/SKILL.md`

Maintain formatting consistency with the redesigned enterprise agents. The resulting agent should be comparable in quality, depth, determinism, and traceability to the redesigned Stage 2(product-designer), Stage 3(system-architect), and Stage 4(spec-writer) agents.

The planning artifacts produced by Stage 5 must be directly consumable by Stage 6 (Implementation) without requiring additional planning.
