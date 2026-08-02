You are working inside the Forge SDLC Orchestrator repository.

## Objective

Redesign the Sprint subsystem into an enterprise-grade Sprint Planning & Execution module that aligns with the redesigned Stage 5 (Implementation Planning).

DO NOT modify existing sprint functionality. Create NEW files with the prefix:
- `agents/sprint-planner-pro.md`
- `skills/forge-sprint-pro/SKILL.md`

The existing forge-sprint implementation must remain untouched for backward compatibility.

---

## BACKGROUND

Forge is a deterministic SDLC orchestration framework. Stage ownership is strict. Each stage owns specific artifacts. Traceability is append-only. No stage may redefine artifacts created by previous stages.

**Sprint Planning is NOT a pipeline stage.** It is an OPTIONAL orchestration layer that operates on top of Stage 5. Projects that never use sprints should behave exactly as they do today.

---

## PIPELINE

```
Stage 1: Requirements Engineering ↓
Stage 2: Product Design ↓
Stage 3: System Architecture ↓
Stage 4: Technical Specification ↓
Stage 5: Implementation Planning ↓
Sprint Planning (OPTIONAL) ↓
Stage 6: Implementation ↓
Stage 7: Testing ↓
Stage 8: Deployment
```

---

## MISSION

The Sprint Planner transforms the implementation plan into executable sprint backlogs.

**It determines:** What work should be executed together, which tasks are ready/blocked, which work can execute in parallel, sprint goals, sprint scope, capacity, dependencies, risks, carry-over, acceptance gates.

**The Sprint Planner NEVER changes:** Requirements, Architecture, Technical Specification, Implementation Plan, Task IDs, Pipeline State.

The Sprint Planner is a VIEW over the Implementation Plan. The Implementation Plan remains the single source of truth.

---

## INPUT ARTIFACTS

**Read ONLY:** `pipeline/state.md`, `pipeline/05-implementation-plan/` (implementation-plan.md, implementation-phases.md, work-packages.md, task-breakdown.md, dependency-graph.md, traceability.md), `progress.md` (Stage 6 if present).

Do NOT modify these artifacts.

---

## SPRINT OWNERSHIP

**Sprint Planning owns:** Sprint Goals, Sprint Scope, Sprint Backlog, Capacity Planning, Task Allocation, Dependency Validation, Sprint Risks, Sprint Burndown Metadata, Sprint Review, Sprint Retrospective, Sprint Metrics, Sprint Traceability, Sprint Lessons Learned, Carry-over Tracking, Developer Allocation, AI Agent Allocation.

**DO NOT OWN:** Requirements, Features, Architecture, Specifications, Implementation Tasks, Task IDs, Progress Tracking, Source Code, Testing, Deployment.

---

## TRACEABILITY

Sprint artifacts extend Stage 5. The complete chain becomes:

```
BG → REQ → EP → CAP → FEAT → US → UF → SCR → CMP → API → SRV → ADR → SPEC → MOD → TASK → SPR
```

Sprint SHALL NEVER invent parent artifacts. Every sprint artifact references upstream IDs.

**Example:** `SPR-002 → TASK-041 → WP-005 → MOD-007 → SPEC-003 → REQ-F-018`

---

## IDENTIFIERS

Generate deterministic IDs: SPR-001, SPRGOAL-001, SPRRISK-001, SPRREV-001, SPRRETRO-001, SPRMETRIC-001, SPRCAP-001, SPRTRACE-001.

Never modify existing TASK IDs.

---

## SPRINT DELIVERABLES

Generate in `pipeline/05-implementation-plan/sprints/`:

- `sprint-001.md`, `sprint-001-capacity.md`, `sprint-001-dependencies.md`
- `sprint-001-risk-register.md`, `sprint-001-traceability.md`
- `sprint-001-review.md`, `sprint-001-retrospective.md`, `sprint-001-metrics.md`

Subsequent sprints follow the same pattern.

---

## SPRINT DOCUMENT CONTENT

Each sprint shall include: Sprint ID, Sprint Goal, Business Value, Milestones Covered, Work Packages, Tasks, Dependencies, Blocked Tasks, Parallel Work Streams, Developer Allocation, AI Agent Allocation, Risk Register, Capacity Summary, Definition of Ready, Definition of Done, Acceptance Gates, Expected Deliverables, Demo Scope, Exit Criteria, Carry-over Policy.

---

## CAPACITY PLANNING

Support: Velocity, Developer Capacity, AI Capacity, Estimated Hours, Story Points (optional), Risk Buffer, Slack, Critical Tasks, Stretch Tasks.

The planner should recommend balanced sprint sizes.

---

## DEPENDENCY VALIDATION

Before planning a sprint verify: All predecessor tasks complete, Specifications exist, Architecture exists, No unresolved blockers, No circular dependencies, No orphan tasks, Tasks are implementation-ready.

---

## PARALLEL EXECUTION

Identify: Independent work streams, Critical path, Merge points, Blocking tasks, Concurrent opportunities.

---

## AI AGENT ALLOCATION

Support assigning implementation work to AI agents. Allocation should be configurable.

**Example:** `TASK-021 → Claude | TASK-022 → Codex | TASK-023 → GPT | TASK-024 → Human Developer`

---

## SPRINT REVIEW

Generate: Completed Tasks, Incomplete Tasks, Carry-over, Velocity, Blocked Work, Defects, Technical Debt, Lessons Learned, Architecture Deviations, Specification Deviations, Scope Changes, Recommended Improvements.

---

## RETROSPECTIVE

Generate: What Went Well, What Went Poorly, Process Improvements, Technical Improvements, Architecture Observations, Planning Improvements, AI Effectiveness, Recommended Actions.

---

## VALIDATION

**Fail sprint generation when:**
- No implementation plan exists
- Dependency graph invalid
- Circular dependencies exist
- Capacity exceeded
- Duplicate task assignments
- Tasks assigned twice
- Sprint has no measurable goal
- Sprint lacks acceptance criteria
- Sprint contains orphan tasks

---

## AGENT REQUIREMENTS

Create an enterprise-grade `agents/pro-sprint-planner.md`. Expected length: 400–600+ lines.

Include sections: Role, Primary Goal, Responsibilities, Stage Ownership, Context Scope, Sprint Planning Principles, Capacity Planning, Dependency Analysis, Risk Analysis, Parallel Execution, AI Allocation, Sprint Goal Rules, Sprint Deliverables, Traceability Rules, Validation, Workflow, Revision Behaviour, Quality Gates, Completion Report, Failure Behaviour, Web Research Policy, Behavioral Rules, Completion Message.

---

## SKILL REQUIREMENTS

Create `skills/forge-sprint-pro/SKILL.md`. The skill SHALL ONLY orchestrate. It SHALL NOT contain sprint planning logic.

**Responsibilities:** Run preflight, Load project profile, Load Sprint Planner persona, Execute the persona, Invoke deterministic sprint scripts, Verify generated artifacts, Verify traceability, Verify sprint readiness, Report results, Never mutate pipeline state, Never modify implementation tasks.

---

## SCRIPT INTEGRATION

Integrate with `scripts/sprint.py`. Support: plan, review, list, future subcommands.

Do NOT replace deterministic script behavior. The LLM augments reporting and validation only.

---

## PROFILE SUPPORT

Honor project profile overrides. Support: replace_with, additional_artifacts, additional_steps, additional_concerns, skip_steps.

Examples: Microservices, Monolith, Library, CLI, Mobile, ML, Embedded, Infrastructure.

---

## QUALITY GATES

Validate:
- Every sprint has a goal, measurable deliverables, dependency validation, risk analysis, capacity analysis, traceability
- Every sprint has Definition of Ready, Definition of Done, acceptance gates, review criteria, retrospective criteria
- Every task references upstream artifacts

---

## IMPORTANT

Do NOT overwrite existing files. Create ONLY:
- `agents/sprint-planner-pro.md`
- `skills/forge-sprint-pro/SKILL.md`

Maintain formatting consistency with the redesigned enterprise agents and skills from Stages 1–5.

The resulting Sprint Planning subsystem should be suitable for enterprise software teams and AI-assisted development, while remaining fully optional and backward compatible with existing Forge projects.
