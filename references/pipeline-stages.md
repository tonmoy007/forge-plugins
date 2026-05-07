# Pipeline Stages Reference

> Definitions of all 12 SDLC stages. Each stage skill loads this on invocation
> to know what it's doing.

---

## Stage 1: SRS (Software Requirements Specification)

**Purpose**: Convert vague user input into a complete, testable requirements document.

**Agent**: `requirements-analyst`

**Inputs**:
- User's project description (free-form)
- Any existing context they mention

**Outputs**:
- `pipeline/01-srs/srs.md` — full SRS with REQ-IDs, acceptance criteria
- `pipeline/01-srs/stakeholder-map.md` (if applicable)

**Activities**:
1. Listen to user's description
2. Ask clarifying questions (max 3 rounds)
3. Categorize: functional / non-functional / constraint / assumption
4. Assign REQ-IDs sequentially
5. Write testable acceptance criteria
6. Surface unstated requirements (auth, logging, errors, scale, etc.)
7. List open questions explicitly

**Gate criteria**: See `gate-criteria.md` Stage 1

**Typical duration**: 1–3 sessions for new projects.

---

## Stage 2: Product + UX + Design System

**Purpose**: Turn requirements into product decisions, user flows, and the design system
that will govern Stage 6 implementation.

**Agent**: `product-designer`

**Inputs**:
- `pipeline/01-srs/srs.md`

**Outputs**:
- `pipeline/02-product-ux/prd.md` — product requirements with FEAT-IDs
- `pipeline/02-product-ux/user-flows.md` — primary user journeys
- `pipeline/02-product-ux/design-system.md` — tokens, components, patterns
- `pipeline/02-product-ux/wireframes/` — low-fidelity wireframes (for fullstack profile)

**Activities**:
1. Map REQ-IDs to FEAT-IDs (features)
2. Prioritize features (must-have, should-have, could-have)
3. Design user flows (happy path + error paths)
4. Design system: tokens (color, type, space, motion), component specs, patterns
5. Accessibility checklist (WCAG AA minimum)
6. Responsive breakpoints (if applicable)

**Profile-specific behaviors**:
- API: skips wireframes, focuses on error formats
- ML: replaced with data-pipeline-design
- CLI: replaced with cli-ux-design (commands, help, errors)
- Library: replaced with public-api design

**Gate criteria**: See `gate-criteria.md` Stage 2

---

## Stage 3: Architecture

**Purpose**: Design the system. Bridge product requirements to implementation structure.

**Agent**: `system-architect`

**Inputs**:
- `pipeline/01-srs/srs.md`
- `pipeline/02-product-ux/*`

**Outputs**:
- `pipeline/03-architecture/architecture.md` — component map, boundaries, interactions
- `pipeline/03-architecture/c4-diagrams.md` — context, container, component diagrams
- `pipeline/03-architecture/data-model.md` — schemas, ER diagrams
- `pipeline/03-architecture/api-contracts.md` — interface specs
- `pipeline/03-architecture/adr/` — architecture decision records

**Activities**:
1. Map FEATs to components
2. Define component boundaries and responsibilities
3. Design data model
4. Specify API contracts (internal and external)
5. Document trade-offs as ADRs
6. Identify failure modes
7. Security considerations
8. Versioning strategy

**Gate criteria**: See `gate-criteria.md` Stage 3

---

## Stage 4: Technical Spec

**Purpose**: Bridge architecture to code. Zero ambiguity for the builder.

**Agent**: `spec-writer`

**Inputs**:
- All `pipeline/01-srs/*`
- All `pipeline/02-product-ux/*`
- All `pipeline/03-architecture/*`

**Outputs**:
- `pipeline/04-spec/technical-spec.md` — implementation-ready specs
- `pipeline/04-spec/interface-spec.md` — function signatures, types, schemas
- `pipeline/04-spec/test-strategy.md` — what to test, at what layer

**Activities**:
1. For each component: write detailed implementation spec
2. Define function signatures, type contracts
3. Specify error handling
4. Document edge cases
5. Test strategy: unit / integration / e2e split

**Gate criteria**: See `gate-criteria.md` Stage 4

---

## Stage 5: Plan / Task DAG

**Purpose**: Decompose into smallest independently-verifiable tasks with dependencies.

**Agent**: `planner`

**Inputs**:
- `pipeline/04-spec/*`

**Outputs**:
- `pipeline/05-plan/task-dag.md` — task list with dependencies, sizes, REQ-IDs
- `pipeline/05-plan/milestones.md` — task groupings into deliverables
- `pipeline/05-plan/risk-register.md` — risks with impact, likelihood, mitigation

**Activities**:
1. Decompose spec into tasks (T-001, T-002, ...)
2. Estimate sizes (S/M/L)
3. Identify dependencies → DAG
4. Group into milestones
5. Identify critical path
6. Risk register

**Gate criteria**: See `gate-criteria.md` Stage 5

---

## Stage 6: Implementation (Build)

**Purpose**: Execute the DAG. Build correctly, test thoroughly, commit cleanly.

**Agent**: `builder`

**Inputs**:
- `pipeline/05-plan/task-dag.md`
- `pipeline/04-spec/*`
- `pipeline/02-product-ux/design-system.md` (for UI work)

**Outputs**:
- Source code in repo
- Tests passing
- `pipeline/06-implementation/progress.md` — task-level status tracking
- `pipeline/06-implementation/decisions.md` — implementation choices made

**Activities** (per task):
1. Read task definition + spec
2. Read existing code (always read before edit)
3. Plan changes
4. Implement
5. Write/update tests
6. Run tests
7. Commit with task ID reference
8. Update progress.md

**Active hooks**:
- `pre-tool-write.py` — design system enforcement
- `post-tool-use.py` — progress tracking, pattern logging

**Gate criteria**: See `gate-criteria.md` Stage 6

---

## Stage 7: Evaluation

**Purpose**: Find every way this could break. Multi-criteria evaluation.

**Agent**: `evaluator`

**Inputs**:
- All pipeline artifacts
- Source code

**Outputs**:
- `pipeline/07-evaluation/eval-report.md` — multi-criteria matrix
- `pipeline/07-evaluation/test-results.md` — test execution results
- `pipeline/07-evaluation/security-review.md` — security findings (if applicable)

**Eval matrix dimensions**:
- Functional: does it do what SRS says?
- Performance: meets NFR targets?
- Security: known vuln classes covered?
- Usability: WCAG AA, error UX, recovery paths?
- Reliability: graceful failures, retries, timeouts?
- Observability: logs, metrics, traces present?
- Design system: tokens used, no raw values?
- Documentation: code commented, public API documented?

**Gate criteria**: See `gate-criteria.md` Stage 7

---

## Stage 8: Deploy

**Purpose**: Ship safely. Rollback at every step possible.

**Agent**: `devops`

**Inputs**:
- `pipeline/07-evaluation/*`

**Outputs**:
- `pipeline/08-deploy/deploy-plan.md` — strategy, rollback, blast radius
- `pipeline/08-deploy/deploy-log.md` — what happened, when

**Activities**:
1. Pre-deploy: backup, verify rollback path
2. Deploy: canary → progressive rollout
3. Smoke tests
4. Monitor key metrics for X minutes
5. Decide: roll forward or rollback

**Gate criteria**: See `gate-criteria.md` Stage 8

---

## Stage 9: Monitor

**Purpose**: Detect problems before users do.

**Agent**: `observer`

**Inputs**:
- `pipeline/08-deploy/*`

**Outputs**:
- `pipeline/09-monitor/observability.md` — metrics, alerts, dashboards, SLOs
- `pipeline/09-monitor/incident-log.md` — incidents observed (ongoing)

**Activities**:
1. Define SLOs from NFRs
2. Configure alerts (4xx rate, latency p99, error rate)
3. Build dashboards
4. On-call setup
5. Track incidents

**Gate criteria**: See `gate-criteria.md` Stage 9

---

## Stage 10: Feedback

**Purpose**: Prioritize by impact, not volume. Synthesize signal from noise.

**Agent**: `triage`

**Inputs**:
- User reports, support tickets, monitoring data
- `pipeline/09-monitor/incident-log.md`

**Outputs**:
- `pipeline/10-feedback/feedback-log.md` — all incoming feedback
- `pipeline/10-feedback/triage.md` — categorized, prioritized

**Activities**:
1. Collect feedback
2. Deduplicate
3. Categorize: bug / feature request / UX / docs
4. Prioritize: P0 (data loss/security) / P1 (significant impact) / P2 (annoyance) / P3 (nice-to-have)
5. Assign owner

**Gate criteria**: See `gate-criteria.md` Stage 10

---

## Stage 11: Resolve

**Purpose**: Fix fast, fix right. Every fix gets a regression test.

**Agent**: `resolver`

**Inputs**:
- `pipeline/10-feedback/triage.md`
- Source code

**Outputs**:
- `pipeline/11-resolve/hotfixes.md` — fixes applied, with test refs
- `pipeline/11-resolve/backlog-updates.md` — items deferred to future cycles

**Activities**:
1. Pull P0/P1 from triage
2. Reproduce → write failing test → fix → verify test passes
3. Document hotfix
4. Defer P2/P3 to backlog

**Gate criteria**: See `gate-criteria.md` Stage 11

---

## Stage 12: Release

**Purpose**: Ship the version. Capture what we learned.

**Agent**: `release-manager`

**Inputs**:
- All pipeline artifacts from this cycle

**Outputs**:
- `pipeline/12-release/release-notes.md` — user-facing changelog
- `pipeline/12-release/release-checklist.md` — pre-release checks
- `pipeline/12-release/retrospective.md` — what went well/poorly, lessons

**Activities**:
1. Compile release notes
2. Run release checklist
3. Tag version, publish artifacts
4. Update CHANGELOG
5. Retrospective: what to keep, what to change next cycle

**Gate criteria**: See `gate-criteria.md` Stage 12

---

## Cycle Types

The pipeline supports four cycle types:

### Full cycle (new feature)
Stage 1 → 12. Used for major features starting from idea.

### Iteration cycle
Stage 5 → 12. Used when SRS/architecture stable, just adding to backlog.

### Hotfix cycle
Stage 6 → 9. Used for urgent production fixes. Bypasses planning.

### Tech debt cycle
Stage 3 → 8. Used for refactoring without user-facing changes. Skips Stage 10–12.

The `cycle` field in `pipeline/state.md` tracks which type is active.

---

## Stage Transitions

Transitions are gated by `gate-criteria.md`. Forced transitions (override gate failures)
are logged with justification in `pipeline/state.md` history table.

The Stop hook checks gates on every Stop event. If user explicitly says "advance to
next stage" but gate fails, exit code 2 blocks the transition.
