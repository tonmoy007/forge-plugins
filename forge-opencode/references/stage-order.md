# Stage Order Reference — Single Source of Truth

> **Canonical** definition of pipeline stage order, directory names, prerequisites,
> and next-step hints. Parsed by `scripts/_stage_table.py`.
>
> This file is the single source of truth that resolves the directory-name drift
> reported in EF-005 (e.g. `04-spec` vs `04-technical-spec`, `02-product` vs
> `02-product-ux`). Stage skills, `forge:init` scaffolding, `state-manager`
> next-step hints (REQ-NEXTHINT-001), pre-flight entry checks (REQ-GATE-ENTRY-001),
> and stage-bound enforcement (REQ-PIPEBOUNDS-001) all derive from this table —
> no component may hardcode a stage directory, prerequisite, or next-step string.
>
> Companion docs: `pipeline-stages.md` (prose purpose/activities per stage) and
> `gate-criteria.md` (exit gates per stage). The `dir` values here are authoritative
> for those files too.
>
> Format: a single YAML block. Each stage entry has:
> - `stage`: integer 1–12
> - `dir`: canonical directory under `pipeline/` (no other name is valid)
> - `name` / `label`: short / human stage name
> - `skill`: the `/forge:*` command that drives the stage
> - `agent`: the persona file in `agents/`
> - `primary_artifact`: the canonical handoff file this stage produces that the
>   next stage consumes — used as the prerequisite marker by the next stage
> - `prerequisite` / `prerequisite_skill`: the file (and the skill that produces
>   it) that must exist before this stage may run. `null` for stage 1.
>   Invariant: `prerequisite(N) == primary_artifact(N-1)` for the full cycle.
> - `next_stage` / `next_skill` / `next_hint`: where to go after this stage and
>   the exact user-facing hint string.
>
> `bounds` defines the valid `current_stage` range and the post-stage-12 behavior.
> `cycles` defines the entry/exit stage for each cycle type from `pipeline-stages.md`.

---

```yaml
bounds:
  min_stage: 0          # 0 = pipeline initialized, no stage started yet
  max_stage: 12
  on_overflow: cycle-wrap   # advancing past max_stage wraps to (cycle + 1, stage 0)

stages:
  - stage: 1
    dir: "01-srs"
    name: "srs"
    label: "Requirements / SRS"
    skill: "/forge:srs"
    agent: "requirements-analyst"
    primary_artifact: "pipeline/01-srs/srs.md"
    prerequisite: null
    prerequisite_skill: null
    next_stage: 2
    next_skill: "/forge:product"
    next_hint: "Next: run /forge:product to turn requirements into product/UX — PRD, user flows, and the design system."

  - stage: 2
    dir: "02-product-ux"
    name: "product / UX"
    label: "Product + UX + Design System"
    skill: "/forge:product"
    agent: "product-designer"
    primary_artifact: "pipeline/02-product-ux/prd.md"
    prerequisite: "pipeline/01-srs/srs.md"
    prerequisite_skill: "/forge:srs"
    next_stage: 3
    next_skill: "/forge:arch"
    next_hint: "Next: run /forge:arch to design the system architecture — components, data model, ADRs."

  - stage: 3
    dir: "03-architecture"
    name: "architecture"
    label: "Architecture"
    skill: "/forge:arch"
    agent: "system-architect"
    primary_artifact: "pipeline/03-architecture/architecture.md"
    prerequisite: "pipeline/02-product-ux/prd.md"
    prerequisite_skill: "/forge:product"
    next_stage: 4
    next_skill: "/forge:spec"
    next_hint: "Next: run /forge:spec to write the implementation-ready technical spec."

  - stage: 4
    dir: "04-spec"
    name: "spec"
    label: "Technical Spec"
    skill: "/forge:spec"
    agent: "spec-writer"
    primary_artifact: "pipeline/04-spec/technical-spec.md"
    prerequisite: "pipeline/03-architecture/architecture.md"
    prerequisite_skill: "/forge:arch"
    next_stage: 5
    next_skill: "/forge:plan"
    next_hint: "Next: run /forge:plan to decompose the spec into a task DAG with dependencies."

  - stage: 5
    dir: "05-plan"
    name: "plan"
    label: "Plan / Task DAG"
    skill: "/forge:plan"
    agent: "planner"
    primary_artifact: "pipeline/05-plan/task-dag.md"
    prerequisite: "pipeline/04-spec/technical-spec.md"
    prerequisite_skill: "/forge:spec"
    next_stage: 6
    next_skill: "/forge:build"
    next_hint: "Next: run /forge:build to implement tasks from the plan (one task, or --milestone N for a batch)."

  - stage: 6
    dir: "06-implementation"
    name: "build / implementation"
    label: "Implementation (Build)"
    skill: "/forge:build"
    agent: "builder"
    primary_artifact: "pipeline/06-implementation/progress.md"
    prerequisite: "pipeline/05-plan/task-dag.md"
    prerequisite_skill: "/forge:plan"
    next_stage: 7
    next_skill: "/forge:eval"
    next_hint: "Next: run /forge:eval to evaluate the build against requirements and NFRs."

  - stage: 7
    dir: "07-evaluation"
    name: "evaluation"
    label: "Evaluation"
    skill: "/forge:eval"
    agent: "evaluator"
    primary_artifact: "pipeline/07-evaluation/eval-report.md"
    prerequisite: "pipeline/06-implementation/progress.md"
    prerequisite_skill: "/forge:build"
    next_stage: 8
    next_skill: "/forge:deploy"
    next_hint: "Next: run /forge:deploy to plan and execute the deployment."

  - stage: 8
    dir: "08-deploy"
    name: "deploy"
    label: "Deploy"
    skill: "/forge:deploy"
    agent: "devops"
    primary_artifact: "pipeline/08-deploy/deploy-plan.md"
    prerequisite: "pipeline/07-evaluation/eval-report.md"
    prerequisite_skill: "/forge:eval"
    next_stage: 9
    next_skill: "/forge:monitor"
    next_hint: "Next: run /forge:monitor to configure observability — metrics, alerts, dashboards, SLOs."

  - stage: 9
    dir: "09-monitor"
    name: "monitor"
    label: "Monitor"
    skill: "/forge:monitor"
    agent: "observer"
    primary_artifact: "pipeline/09-monitor/observability.md"
    prerequisite: "pipeline/08-deploy/deploy-plan.md"
    prerequisite_skill: "/forge:deploy"
    next_stage: 10
    next_skill: "/forge:feedback"
    next_hint: "Next: run /forge:feedback to collect and triage user feedback and monitoring signal."

  - stage: 10
    dir: "10-feedback"
    name: "feedback"
    label: "Feedback"
    skill: "/forge:feedback"
    agent: "triage"
    primary_artifact: "pipeline/10-feedback/triage.md"
    prerequisite: "pipeline/09-monitor/observability.md"
    prerequisite_skill: "/forge:monitor"
    next_stage: 11
    next_skill: "/forge:resolve"
    next_hint: "Next: run /forge:resolve to fix prioritized issues from triage, each with a regression test."

  - stage: 11
    dir: "11-resolve"
    name: "resolve"
    label: "Resolve"
    skill: "/forge:resolve"
    agent: "resolver"
    primary_artifact: "pipeline/11-resolve/hotfixes.md"
    prerequisite: "pipeline/10-feedback/triage.md"
    prerequisite_skill: "/forge:feedback"
    next_stage: 12
    next_skill: "/forge:release"
    next_hint: "Next: run /forge:release to tag the version, write release notes, and close the cycle."

  - stage: 12
    dir: "12-release"
    name: "release"
    label: "Release"
    skill: "/forge:release"
    agent: "release-manager"
    primary_artifact: "pipeline/12-release/release-notes.md"
    prerequisite: "pipeline/11-resolve/hotfixes.md"
    prerequisite_skill: "/forge:resolve"
    next_stage: null
    next_skill: "/forge:retro"
    next_hint: "Cycle complete. Run /forge:retro for the retrospective; the next advance wraps to (cycle + 1, stage 0)."

# Cycle types from pipeline-stages.md. entry/exit are inclusive stage numbers.
# Pre-flight prerequisite enforcement (REQ-GATE-ENTRY-001) applies only to the
# stages a given cycle actually traverses; the sequential prerequisite above is
# the full-cycle default.
cycles:
  full:      { entry: 1, exit: 12 }
  iteration: { entry: 5, exit: 12 }
  hotfix:    { entry: 6, exit: 9 }
  tech-debt: { entry: 3, exit: 8 }
```
