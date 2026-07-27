# Gate Criteria Reference

> Machine-readable exit criteria for each pipeline stage.
> Parsed by `scripts/check-gate.py` to verify whether a stage can advance.
>
> Format: YAML block per stage. Each criterion has:
> - `id`: unique within the stage (e.g., G6-001)
> - `description`: human-readable
> - `check`: how to verify (file_exists | file_contains | script_returns_zero | all_tests_pass)
> - `args`: parameters for the check
> - `severity`: blocker | warning (only blockers prevent advancement)

---

## Stage 1: SRS

```yaml
stage: 1
name: srs
criteria:
  - id: G1-001
    description: SRS file exists
    check: file_exists
    args: { path: "pipeline/01-srs/srs.md" }
    severity: blocker

  - id: G1-002
    description: SRS contains at least one functional requirement (REQ-NNN)
    check: file_contains
    args:
      path: "pipeline/01-srs/srs.md"
      pattern: "REQ-\\d{3}"
      min_matches: 1
    severity: blocker

  - id: G1-003
    description: Each requirement has acceptance criteria
    check: script_returns_zero
    args:
      script: "scripts/check_srs_acceptance.py"
      argv: ["pipeline/01-srs/srs.md"]
    severity: blocker

  - id: G1-004
    description: Non-functional requirements present (NFR-NNN)
    check: file_contains
    args:
      path: "pipeline/01-srs/srs.md"
      pattern: "NFR-\\d{3}"
      min_matches: 1
    severity: warning

  - id: G1-005
    description: Open questions section explicit (or empty if all resolved)
    check: file_contains
    args:
      path: "pipeline/01-srs/srs.md"
      pattern: "(?i)open questions"
      min_matches: 1
    severity: warning

  - id: G1-006
    description: Glossary section exists
    check: file_contains
    args:
      path: "pipeline/01-srs/srs.md"
      pattern: "(?i)glossary"
      min_matches: 1
    severity: warning
```

---

## Stage 2: Product + UX + Design System

```yaml
stage: 2
name: product
criteria:
  - id: G2-001
    description: PRD exists
    check: file_exists
    args: { path: "pipeline/02-product-ux/prd.md" }
    severity: blocker

  - id: G2-002
    description: User flows documented
    check: file_exists
    args: { path: "pipeline/02-product-ux/user-flows.md" }
    severity: blocker

  - id: G2-003
    description: Design system created
    check: file_exists
    args: { path: "pipeline/02-product-ux/design-system.md" }
    severity: blocker

  - id: G2-004
    description: Design tokens defined (colors, typography, spacing)
    check: file_contains
    args:
      path: "pipeline/02-product-ux/design-system.md"
      pattern: "(?i)(--color-|--font-|--space-)"
      min_matches: 3
    severity: blocker

  - id: G2-005
    description: Component specs present
    check: file_contains
    args:
      path: "pipeline/02-product-ux/design-system.md"
      pattern: "(?i)## component"
      min_matches: 1
    severity: warning

  - id: G2-006
    description: Accessibility checklist included
    check: file_contains
    args:
      path: "pipeline/02-product-ux/design-system.md"
      pattern: "(?i)(accessibility|wcag|a11y)"
      min_matches: 1
    severity: warning

  - id: G2-007
    description: Each FEAT traces back to a REQ
    check: script_returns_zero
    args:
      script: "scripts/traceability-check.py"
      argv: ["--from", "pipeline/02-product-ux/prd.md", "--to", "pipeline/01-srs/srs.md", "--prefix", "FEAT"]
    severity: blocker
```

---

## Stage 3: Architecture

```yaml
stage: 3
name: architecture
criteria:
  - id: G3-001
    description: Architecture document exists
    check: file_exists
    args: { path: "pipeline/03-architecture/architecture.md" }
    severity: blocker

  - id: G3-002
    description: C4 diagrams documented (text or mermaid)
    check: file_exists
    args: { path: "pipeline/03-architecture/c4-diagrams.md" }
    severity: warning

  - id: G3-003
    description: Data model defined
    check: file_exists
    args: { path: "pipeline/03-architecture/data-model.md" }
    severity: blocker

  - id: G3-004
    description: API contracts specified
    check: file_exists
    args: { path: "pipeline/03-architecture/api-contracts.md" }
    severity: warning

  - id: G3-005
    description: At least one ADR documented
    check: script_returns_zero
    args:
      script: "scripts/check_dir_nonempty.py"
      argv: ["pipeline/03-architecture/adr/"]
    severity: blocker

  - id: G3-006
    description: Components map to FEATs
    check: script_returns_zero
    args:
      script: "scripts/traceability-check.py"
      argv: ["--from", "pipeline/03-architecture/architecture.md", "--to", "pipeline/02-product-ux/prd.md"]
    severity: blocker
```

---

## Stage 4: Technical Spec

```yaml
stage: 4
name: spec
criteria:
  - id: G4-001
    description: Technical spec exists
    check: file_exists
    args: { path: "pipeline/04-spec/technical-spec.md" }
    severity: blocker

  - id: G4-002
    description: Interface spec defined (function signatures, types)
    check: file_exists
    args: { path: "pipeline/04-spec/interface-spec.md" }
    severity: blocker

  - id: G4-003
    description: Test strategy documented
    check: file_exists
    args: { path: "pipeline/04-spec/test-strategy.md" }
    severity: blocker

  - id: G4-004
    description: Spec covers all components from architecture
    check: script_returns_zero
    args:
      script: "scripts/spec-coverage.py"
      argv: []
    severity: warning
```

---

## Stage 5: Plan / Task DAG

```yaml
stage: 5
name: plan
criteria:
  - id: G5-001
    description: Task DAG exists
    check: file_exists
    args: { path: "pipeline/05-plan/task-dag.md" }
    severity: blocker

  - id: G5-002
    description: Tasks have IDs (T-NNN)
    check: file_contains
    args:
      path: "pipeline/05-plan/task-dag.md"
      pattern: "T-\\d{3}"
      min_matches: 3
    severity: blocker

  - id: G5-003
    description: Risk register exists
    check: file_exists
    args: { path: "pipeline/05-plan/risk-register.md" }
    severity: warning

  - id: G5-004
    description: Milestones identified
    check: file_exists
    args: { path: "pipeline/05-plan/milestones.md" }
    severity: warning

  - id: G5-005
    description: All tasks have done criteria
    check: script_returns_zero
    args:
      script: "scripts/check_dag_completeness.py"
      argv: []
    severity: blocker

  - id: G5-006
    description: Each task references a REQ
    check: script_returns_zero
    args:
      script: "scripts/traceability-check.py"
      argv: ["--from", "pipeline/05-plan/task-dag.md", "--to", "pipeline/01-srs/srs.md"]
    severity: blocker
```

---

## Stage 6: Implementation

```yaml
stage: 6
name: build
criteria:
  - id: G6-001
    description: All DAG tasks marked done
    check: script_returns_zero
    args:
      script: "scripts/check_dag_completion.py"
      argv: []
    severity: blocker

  - id: G6-002
    description: All tests pass
    check: all_tests_pass
    args: { test_command: "pytest tests/ -x" }
    severity: blocker

  - id: G6-003
    description: No raw CSS values in UI files (design tokens used)
    check: script_returns_zero
    args:
      script: "scripts/token-audit.py"
      argv: []
    severity: warning

  - id: G6-004
    description: Test coverage above threshold
    check: script_returns_zero
    args:
      script: "scripts/check_coverage.py"
      argv: ["--min", "80"]
    severity: warning

  - id: G6-005
    description: No TODO/FIXME comments without ticket reference
    check: script_returns_zero
    args:
      script: "scripts/check_todos.py"
      argv: []
    severity: warning

  - id: G6-006
    description: Progress.md reflects completed tasks
    check: script_returns_zero
    args:
      script: "scripts/check_progress_sync.py"
      argv: []
    severity: blocker
```

---

## Stage 7: Evaluation

```yaml
stage: 7
name: eval
criteria:
  - id: G7-001
    description: Eval report exists
    check: file_exists
    args: { path: "pipeline/07-evaluation/eval-report.md" }
    severity: blocker

  - id: G7-002
    description: Test results documented
    check: file_exists
    args: { path: "pipeline/07-evaluation/test-results.md" }
    severity: blocker

  - id: G7-003
    description: All NFR targets evaluated
    check: script_returns_zero
    args:
      script: "scripts/check_nfr_coverage.py"
      argv: []
    severity: blocker

  - id: G7-004
    description: Security review complete
    check: file_contains
    args:
      path: "pipeline/07-evaluation/eval-report.md"
      pattern: "(?i)security"
      min_matches: 1
    severity: warning

  - id: G7-005
    description: No P0/P1 bugs unresolved
    check: script_returns_zero
    args:
      script: "scripts/check_open_bugs.py"
      argv: ["--severity", "P0,P1"]
    severity: blocker
```

---

## Stage 8: Deploy

```yaml
stage: 8
name: deploy
criteria:
  - id: G8-001
    description: Deploy plan documented
    check: file_exists
    args: { path: "pipeline/08-deploy/deploy-plan.md" }
    severity: blocker

  - id: G8-002
    description: Rollback procedure defined
    check: file_contains
    args:
      path: "pipeline/08-deploy/deploy-plan.md"
      pattern: "(?i)rollback"
      min_matches: 1
    severity: blocker

  - id: G8-003
    description: Deployment log exists (post-deploy)
    check: file_exists
    args: { path: "pipeline/08-deploy/deploy-log.md" }
    severity: warning

  - id: G8-004
    description: Health checks pass
    check: script_returns_zero
    args:
      script: "scripts/check_health.py"
      argv: []
    severity: blocker
```

---

## Stage 9: Monitor

```yaml
stage: 9
name: monitor
criteria:
  - id: G9-001
    description: Observability setup documented
    check: file_exists
    args: { path: "pipeline/09-monitor/observability.md" }
    severity: blocker

  - id: G9-002
    description: Alerts configured
    check: file_contains
    args:
      path: "pipeline/09-monitor/observability.md"
      pattern: "(?i)alert"
      min_matches: 1
    severity: blocker

  - id: G9-003
    description: SLOs defined
    check: file_contains
    args:
      path: "pipeline/09-monitor/observability.md"
      pattern: "(?i)slo"
      min_matches: 1
    severity: warning

  - id: G9-004
    description: Incident log started
    check: file_exists
    args: { path: "pipeline/09-monitor/incident-log.md" }
    severity: warning
```

---

## Stage 10: Feedback

```yaml
stage: 10
name: feedback
criteria:
  - id: G10-001
    description: Feedback log exists
    check: file_exists
    args: { path: "pipeline/10-feedback/feedback-log.md" }
    severity: blocker

  - id: G10-002
    description: Triage document exists
    check: file_exists
    args: { path: "pipeline/10-feedback/triage.md" }
    severity: blocker

  - id: G10-003
    description: Feedback items prioritized (P0/P1/P2/P3)
    check: file_contains
    args:
      path: "pipeline/10-feedback/triage.md"
      pattern: "P[0-3]"
      min_matches: 1
    severity: warning
```

---

## Stage 11: Resolve

```yaml
stage: 11
name: resolve
criteria:
  - id: G11-001
    description: Hotfixes documented
    check: file_exists
    args: { path: "pipeline/11-resolve/hotfixes.md" }
    severity: blocker

  - id: G11-002
    description: Backlog updated with deferred items
    check: file_exists
    args: { path: "pipeline/11-resolve/backlog-updates.md" }
    severity: blocker

  - id: G11-003
    description: Each hotfix has a regression test
    check: script_returns_zero
    args:
      script: "scripts/check_hotfix_tests.py"
      argv: []
    severity: blocker
```

---

## Stage 12: Release

```yaml
stage: 12
name: release
criteria:
  - id: G12-001
    description: Release notes drafted
    check: file_exists
    args: { path: "pipeline/12-release/release-notes.md" }
    severity: blocker

  - id: G12-002
    description: Release checklist complete
    check: file_exists
    args: { path: "pipeline/12-release/release-checklist.md" }
    severity: blocker

  - id: G12-003
    description: Retrospective written
    check: file_exists
    args: { path: "pipeline/12-release/retrospective.md" }
    severity: blocker

  - id: G12-004
    description: Version tagged in git
    check: script_returns_zero
    args:
      script: "scripts/check_git_tag.py"
      argv: []
    severity: warning

  - id: G12-005
    description: CHANGELOG updated
    check: file_exists
    args: { path: "CHANGELOG.md" }
    severity: warning

  - id: G12-006
    description: Full traceability chain intact (REQ → FEAT → Component → Task → Test)
    check: script_returns_zero
    args:
      script: "scripts/traceability-check.py"
      argv: ["--full-chain"]
    severity: blocker
```

---

## Check Types Reference

### `file_exists`
```yaml
check: file_exists
args:
  path: "relative/path/to/file"
```
Passes if file exists and is non-empty.

### `file_contains`
```yaml
check: file_contains
args:
  path: "relative/path"
  pattern: "regex pattern"
  min_matches: 1   # optional, default 1
```
Passes if regex matches at least `min_matches` times.

### `script_returns_zero`
```yaml
check: script_returns_zero
args:
  script: "scripts/some_check.py"
  argv: ["arg1", "arg2"]
```
Passes if script exits 0. Script's stderr is captured for failure message.

### `all_tests_pass`
```yaml
check: all_tests_pass
args:
  test_command: "pytest tests/ -x"
```
Runs the command, passes if exit 0.

---

## Severity Levels

- **`blocker`**: Stage cannot advance until this passes.
- **`warning`**: Logged in reflection but doesn't block. The user can override blockers
  by setting `gate_enforcement: warn` in `~/.forge/config.yaml`, but warnings stay visible.
