# Project Type Profiles

> Adaptive workflow profiles. Each profile adjusts which stages emphasize what, what
> additional gate criteria apply, and how agents tune their prompts.
>
> Used by: `forge-init` to assign profile, every stage skill to load overrides.

---

## How Profiles Work

When `/forge:init` runs, it detects the project type and stores it in `pipeline/state.md`:

```yaml
project_type: ml-pipeline
```

Then each stage skill, before invoking its agent, reads this profile from
`references/project-type-profiles.md` and applies the overrides.

Overrides are layered on top of base stage definitions — they don't replace them.

---

## Detection Heuristics

```yaml
detection:
  api:
    indicators:
      - file_exists: ["openapi.yaml", "openapi.json", "swagger.yaml"]
      - dir_exists: ["api/", "routes/"]
      - file_contains: { path: "package.json", pattern: "express|fastify|hono|koa" }
      - file_contains: { path: "requirements.txt", pattern: "fastapi|flask|django" }
      - file_contains: { path: "go.mod", pattern: "gin-gonic|echo|fiber" }
    confidence_threshold: 0.6

  fullstack:
    indicators:
      - file_exists: ["next.config.js", "next.config.ts", "remix.config.js", "nuxt.config.ts"]
      - dir_exists: ["pages/", "app/", "src/pages/", "src/app/"]
      - file_contains: { path: "package.json", pattern: "next|remix|nuxt|svelte-kit" }
    confidence_threshold: 0.7

  ml-pipeline:
    indicators:
      - file_contains: { path: "requirements.txt", pattern: "torch|tensorflow|transformers|jax|sklearn" }
      - file_contains: { path: "pyproject.toml", pattern: "torch|tensorflow|transformers" }
      - file_exists: ["train.py", "model.py", "dataset.py"]
      - dir_exists: ["models/", "checkpoints/", "data/"]
    confidence_threshold: 0.5

  cli:
    indicators:
      - file_contains: { path: "Cargo.toml", pattern: "clap|structopt" }
      - file_contains: { path: "go.mod", pattern: "cobra|urfave/cli" }
      - file_contains: { path: "pyproject.toml", pattern: "click|typer|argparse" }
      - file_exists: ["bin/", "cmd/"]
    confidence_threshold: 0.6

  library:
    indicators:
      - file_exists: ["setup.py", "setup.cfg"]
      - file_contains: { path: "package.json", pattern: "\"main\":|\"exports\":" }
      - file_contains: { path: "pyproject.toml", pattern: "\\[project\\]" }
      - no_app_entry_point: true
    confidence_threshold: 0.5
```

---

## Profile: api

```yaml
name: api
description: REST/GraphQL/gRPC API service. No UI.

stage_emphasis:
  high: [architecture, spec, evaluation, monitor]
  low: [product-ux]

stage_overrides:
  stage_2:
    skip_wireframes: true
    design_system_mode: api-minimal  # only error formats, status codes, response shapes
    skip_steps: ["visual_design", "wireframes", "component_specs"]
    additional_steps:
      - "Define error response schema (RFC 7807 Problem Details)"
      - "Define standard status codes by operation type"
      - "Define rate limit response format"

  stage_3:
    additional_artifacts:
      - "pipeline/03-architecture/openapi-spec.yaml"
    additional_concerns:
      - "Idempotency key strategy"
      - "Versioning strategy (URL vs header vs accept)"
      - "Pagination strategy"

  stage_7:
    additional_criteria:
      - id: G7-API-001
        description: All endpoints have contract tests
        check: script_returns_zero
        args: { script: "scripts/api-contract-test.py" }
        severity: blocker
      - id: G7-API-002
        description: Load test passes (p99 < documented target)
        check: script_returns_zero
        args: { script: "scripts/load-test.py" }
        severity: blocker
      - id: G7-API-003
        description: Auth bypass review complete
        severity: blocker

  stage_9:
    additional_criteria:
      - id: G9-API-001
        description: 4xx/5xx rate alerts configured
        severity: blocker
      - id: G9-API-002
        description: Latency p99 alert configured
        severity: blocker
```

---

## Profile: fullstack

```yaml
name: fullstack
description: Full-stack web app with UI and backend.

stage_emphasis:
  high: [product-ux, architecture, implementation]

stage_overrides:
  stage_2:
    design_system_mode: full
    additional_steps:
      - "Define responsive breakpoints"
      - "Define dark mode tokens"
      - "Define motion/animation tokens"

  stage_3:
    additional_concerns:
      - "Rendering strategy (SSR / SSG / ISR / CSR per route)"
      - "Frontend/backend boundary (BFF vs direct DB access)"
      - "Session/auth flow (cookie scope, CSRF, token storage)"
      - "Data fetching pattern (RSC, loaders, client queries)"
    additional_artifacts:
      - "pipeline/03-architecture/route-manifest.md"

  stage_6:
    additional_criteria:
      - id: G6-FS-001
        description: No raw CSS values in UI files (design tokens enforced)
        check: script_returns_zero
        args: { script: "scripts/token-audit.py" }
        severity: blocker
      - id: G6-FS-002
        description: Client bundle size under route budget
        check: script_returns_zero
        args: { script: "scripts/bundle-size-check.py" }
        severity: warning
      - id: G6-FS-003
        description: Server/client component boundary respected (no client-only APIs in RSC)
        severity: warning

  stage_7:
    additional_criteria:
      - id: G7-FS-001
        description: Lighthouse score > 90 (perf, a11y, best practices, SEO)
        check: script_returns_zero
        args: { script: "scripts/lighthouse-check.py", argv: ["--min", "90"] }
        severity: warning
      - id: G7-FS-002
        description: WCAG AA compliance check passes
        severity: blocker
      - id: G7-FS-003
        description: Responsive at 320px, 768px, 1024px, 1440px breakpoints
        severity: blocker
```

---

## Profile: ml-pipeline

```yaml
name: ml-pipeline
description: Machine learning training/inference pipeline.

stage_emphasis:
  high: [architecture, spec, evaluation, monitor]
  low: [product-ux]

stage_overrides:
  stage_2:
    replace_with: data-pipeline-design
    artifacts:
      - "pipeline/02-product-ux/data-flow.md"
      - "pipeline/02-product-ux/data-schema.md"
      - "pipeline/02-product-ux/feature-spec.md"
    skip_steps: ["wireframes", "ux_design", "visual_design"]

  stage_3:
    additional_concerns:
      - "Training vs inference path separation"
      - "Checkpoint format and versioning"
      - "GPU memory budget per component"
      - "Data versioning (DVC, MLflow, etc.)"

  stage_4:
    additional_artifacts:
      - "pipeline/04-spec/model-spec.md"  # architecture, hyperparameters
      - "pipeline/04-spec/data-spec.md"   # schemas, validation rules

  stage_7:
    additional_criteria:
      - id: G7-ML-001
        description: Model accuracy on holdout set above threshold
        check: script_returns_zero
        args: { script: "scripts/check-model-accuracy.py" }
        severity: blocker
      - id: G7-ML-002
        description: Inference latency p99 within budget
        severity: blocker
      - id: G7-ML-003
        description: GPU memory peak under budget
        severity: blocker
      - id: G7-ML-004
        description: Reproducibility test passes (same seed → same output)
        severity: warning
      - id: G7-ML-005
        description: Drift detection strategy documented (training/serving skew, input drift, performance drift)
        severity: blocker

  stage_9:
    additional_criteria:
      - id: G9-ML-001
        description: Model drift detection configured
        severity: blocker
      - id: G9-ML-002
        description: Data quality monitoring (input distribution shifts)
        severity: blocker
      - id: G9-ML-003
        description: Inference latency tracking
        severity: warning
```

---

## Profile: cli

```yaml
name: cli
description: Command-line tool.

stage_emphasis:
  high: [spec, implementation, evaluation]
  low: [product-ux, deploy]

stage_overrides:
  stage_2:
    replace_with: cli-ux-design
    artifacts:
      - "pipeline/02-product-ux/command-tree.md"  # `tool sub command --flag` structure
      - "pipeline/02-product-ux/help-text.md"
      - "pipeline/02-product-ux/error-messages.md"
    skip_steps: ["wireframes", "visual_design", "component_specs"]
    additional_steps:
      - "Define exit codes for every error path"
      - "Design help text for each command"
      - "Plan progress indicators for long operations"

  stage_7:
    additional_criteria:
      - id: G7-CLI-001
        description: --help text exists for every command
        severity: blocker
      - id: G7-CLI-002
        description: Exit codes documented and consistent
        severity: blocker
      - id: G7-CLI-003
        description: Tab completion script provided (bash/zsh)
        severity: warning
      - id: G7-CLI-004
        description: Works with stdin/stdout pipes (non-TTY mode)
        severity: warning

  stage_8:
    skip: true  # CLI doesn't deploy in the traditional sense
    replace_with: package-publish
    artifacts:
      - "pipeline/08-deploy/package-spec.md"  # how it gets distributed (homebrew, cargo, npm, pip)
```

---

## Profile: library

```yaml
name: library
description: Reusable code library/package.

stage_emphasis:
  high: [spec, implementation, evaluation, release]
  low: [product-ux, deploy, monitor]

stage_overrides:
  stage_2:
    replace_with: api-design
    artifacts:
      - "pipeline/02-product-ux/public-api.md"  # what's exposed
      - "pipeline/02-product-ux/usage-examples.md"
    skip_steps: ["wireframes", "visual_design"]

  stage_4:
    additional_concerns:
      - "Public vs internal API boundary"
      - "Backward compatibility commitment level (semver, etc.)"
      - "Bundle size budget"

  stage_7:
    additional_criteria:
      - id: G7-LIB-001
        description: Public API surface minimized (no leaked internals)
        severity: blocker
      - id: G7-LIB-002
        description: Backward compatibility test against previous version
        severity: blocker
      - id: G7-LIB-003
        description: Documentation coverage 100% on public API
        severity: blocker
      - id: G7-LIB-004
        description: Bundle size under budget (if applicable)
        severity: warning

  stage_8:
    skip: true
    replace_with: package-publish

  stage_9:
    skip: true  # libraries don't have runtime monitoring

  stage_12:
    additional_criteria:
      - id: G12-LIB-001
        description: CHANGELOG follows Keep a Changelog format
        severity: blocker
      - id: G12-LIB-002
        description: Semver enforced (breaking changes → major bump)
        severity: blocker
      - id: G12-LIB-003
        description: Migration guide for breaking changes
        severity: blocker
```

---

## Profile: unknown

```yaml
name: unknown
description: Could not auto-detect. User selects manually.

behavior:
  - On forge-init, prompt the user with profile choices
  - Default to "fullstack" if user can't decide (most common)
  - Document the choice in pipeline/state.md
```

---

## Custom Profiles

Users can define custom profiles in `~/.forge/profiles/<name>.md`. Forge looks for those
first; if not found, falls back to this file.

The schema is the same. Custom profiles get loaded into the merged profile registry on
session start.
