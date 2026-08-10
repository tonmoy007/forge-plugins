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
  
  script:
    # Conservative — `script` is opt-in for projects too small to justify
    # the full pipeline. Auto-detected only when the repo is unambiguously tiny.
    indicators:
      - total_loc_under: 500            # all source files combined
      - no_file_exists: ["package.json", "setup.py", "pyproject.toml",
                         "Cargo.toml", "go.mod", "Gemfile", "composer.json"]
      - file_count_under: 20            # excluding hidden / .git / node_modules
      - language_subset: ["python", "shell", "javascript"]
    confidence_threshold: 0.75          # high bar — defaults to `unknown` if unsure
    suggest_only: true                  # on match, prompt the user rather than auto-assign

  monorepo:
    # Checked FIRST — a monorepo wraps single-package signals (a Next.js app,
    # an API, a library) inside workspaces, so it must win before those match.
    indicators:
      - file_exists: ["pnpm-workspace.yaml", "lerna.json", "turbo.json", "nx.json"]
      - file_contains: { path: "package.json", pattern: "\"workspaces\"" }
      - file_contains: { path: "Cargo.toml", pattern: "\\[workspace\\]" }
      - dir_exists_all: ["packages/", "apps/"]
    confidence_threshold: 0.85

  mobile:
    # Checked after monorepo but before fullstack/api: a React Native repo has a
    # package.json and would otherwise be mistaken for fullstack.
    indicators:
      - file_exists: ["pubspec.yaml"]                      # Flutter
      - file_exists: ["Podfile"]                           # iOS
      - file_glob: ["*.xcodeproj", "*.xcworkspace"]        # iOS
      - dir_with_file: { dir: "android/", file: "build.gradle" }  # Android
      - file_contains: { path: "package.json", pattern: "react-native" }
    confidence_threshold: 0.85

  data-contract:
    # After ml/fullstack but before api/library: a schema-first repo (.proto,
    # schemas/, buf.yaml) with no server framework classifies here, not api.
    indicators:
      - file_glob: ["*.proto", "*.avsc", "*.graphql", "*.graphqls"]
      - file_exists: ["buf.yaml", "dbt_project.yml"]
      - dir_exists: ["schemas/", "contracts/"]
      - no_app_framework: true   # a server dep makes it `api`, not data-contract
    confidence_threshold: 0.8```

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

## Profile: monorepo

```yaml
name: monorepo
description: Multi-package workspace (pnpm/yarn/npm workspaces, Turborepo, Nx,
  Lerna, or a Cargo workspace) holding several apps and shared packages in one
  repo. Emphasis shifts to cross-package architecture and build orchestration.

stage_emphasis:
  high: [architecture, plan]

stage_overrides:
  stage_3:
    additional_concerns:
      - "Package boundaries and ownership (who owns what; public vs internal packages)"
      - "Shared-dependency strategy (single-version policy vs per-package versions)"
      - "Build orchestration (Turborepo / Nx task graph, caching, affected-only builds)"
      - "Versioning model (fixed/locked vs independent per-package versioning)"
      - "Circular-dependency prevention between internal packages"
    additional_artifacts:
      - "pipeline/03-architecture/package-graph.md"  # internal dependency graph

  stage_5:
    additional_steps:
      - "Group tasks per package; order them by the internal dependency graph"
      - "Call out shared-package changes that fan out to multiple consumers"
    additional_concerns:
      - "Cross-package change coordination (one PR vs staged per-package rollout)"

  stage_7:
    additional_criteria:
      - id: G7-MONO-001
        description: Internal package dependency graph is acyclic
        check: script_returns_zero
        args: { script: "scripts/check_monorepo_graph.py" }
        severity: blocker
```

---

## Profile: mobile

```yaml
name: mobile
description: Native or cross-platform mobile app (Flutter, React Native, native
  iOS, or native Android). UI-heavy, so product-ux carries weight, and shipping
  means clearing an app-store review — captured by a store-readiness release gate.

stage_emphasis:
  high: [product-ux, implementation, evaluation]

stage_overrides:
  stage_2:
    design_system_mode: full
    additional_steps:
      - "Size touch targets for thumbs (min 44x44pt iOS / 48x48dp Android)"
      - "Design offline, empty, loading, and error states for every screen"
      - "Follow platform conventions (iOS Human Interface Guidelines / Material Design)"
    additional_concerns:
      - "Per-platform navigation patterns (tab bar vs bottom nav, back behavior)"
      - "Safe-area / notch / gesture-bar handling"

  stage_3:
    additional_concerns:
      - "Offline sync and local persistence strategy (conflict resolution)"
      - "Push notification delivery and permission flow"
      - "Deep link / universal link routing"
      - "State restoration after process death / backgrounding"

  stage_12:
    additional_criteria:
      - id: G12-MOBILE-001
        description: App store metadata present (bundle id / version / signing config)
        check: script_returns_zero
        args: { script: "scripts/check_store_readiness.py" }
        severity: blocker
```

---

## Profile: data-contract

```yaml
name: data-contract
description: Schema-first project whose deliverable is data contracts (Protobuf,
  Avro, JSON Schema, GraphQL SDL, or dbt models), not a UI or a running service.
  Emphasis shifts to precise schema definition and backward-compatibility.

stage_emphasis:
  high: [spec, architecture, evaluation]
  low: [product-ux]

stage_overrides:
  stage_2:
    skip_wireframes: true
    skip_steps: ["visual_design", "wireframes", "component_specs"]

  stage_4:
    additional_steps:
      - "Define every schema with explicit field/type semantics and required-ness"
      - "Document the compatibility mode (backward / forward / full) per schema"
      - "Define a versioning + deprecation policy (reserve field numbers, never reuse)"
    additional_concerns:
      - "Wire/serialization compatibility across producers and consumers"
      - "Migration path for breaking changes (dual-publish, version negotiation)"

  stage_7:
    additional_artifacts:
      - "pipeline/07-evaluation/compatibility-matrix.md"  # producer/consumer x version
    additional_criteria:
      - id: G7-DC-001
        description: Schema hygiene + compatibility policy — no duplicate protobuf
          field numbers; buf breaking-change policy present. Hygiene + policy,
          NOT a semantic cross-version diff (which needs the prior schema version).
        check: script_returns_zero
        args: { script: "scripts/check_schema_compat.py" }
        severity: blocker
```

---

## Profile: script

```yaml
name: script
description: Small, single-purpose script or utility. Compressed 4-stage pipeline
  designed for projects under ~500 LOC where the full 12-stage flow would be
  overkill. Honest about when Forge is overkill: this profile exists so users
  don't bounce off Forge on their first try with a tiny project.

stage_emphasis:
  high: [srs, implementation, evaluation]
  low: []  # nothing is "low" — most stages are skipped entirely

# Stages 2, 3, 5, 8, 9, 10, 11, 12 are effectively no-ops for `script` projects.
# Their gate criteria are softened to warnings and their artifacts are optional.

stage_overrides:
  stage_2:
    skip: true
    rationale: |
      A 200-line script doesn't have a UX in the design-system sense. If the
      script has any user-facing surface (e.g., help text), capture it in the
      SRS instead.

  stage_3:
    optional: true
    rationale: |
      Architecture for a single-file script is the file itself. If the script
      grows beyond one module, prompt the user to revisit the profile.
    soft_criteria:  # downgraded from blocker to warning
      - id: G3-001
      - id: G3-002

  stage_4:
    optional: true
    rationale: |
      Technical spec is fused into the SRS for `script` profile. Skip unless
      the user explicitly invokes /forge:spec.

  stage_5:
    skip: true
    rationale: |
      Task DAG for a script is just "write it, test it, ship it" — not worth
      modeling.

  stage_6:
    additional_artifacts: []  # no progress tracker overhead
    additional_criteria:
      - id: G6-SCRIPT-001
        description: Script is executable (has shebang and chmod +x) OR is invokable via `python <script>`
        check: script_returns_zero
        args: { script: "scripts/check-script-runnable.py" }
        severity: blocker
      - id: G6-SCRIPT-002
        description: Help text or `--help` flag exists if the script takes args
        severity: warning

  stage_7:
    soft_criteria:  # downgrade these to warnings — full eval suite is overkill
      - id: G7-001
      - id: G7-002
      - id: G7-003
    additional_criteria:
      - id: G7-SCRIPT-001
        description: At least one test exists (pytest test, bash assertion, or executable example)
        check: script_returns_zero
        args: { script: "scripts/check-script-has-tests.py" }
        severity: blocker
      - id: G7-SCRIPT-002
        description: Script runs end-to-end without error on a sample input
        severity: warning

  stage_8:
    skip: true
    replace_with: distribute
    artifacts:
      - "pipeline/08-deploy/distribute.md"  # one paragraph: "copy to ~/bin/" or "pipx install ."

  stage_9:
    skip: true
    rationale: Scripts don't have runtime monitoring needs.

  stage_10:
    skip: true
    rationale: Feedback for a personal script is just "did it work last time?"

  stage_11:
    skip: true
    rationale: Resolution is "edit the script and re-run."

  stage_12:
    optional: true
    rationale: |
      Tag a version only if you intend to share or version this script. Most
      scripts don't need a release stage.
```

---

## Profile: docker

```yaml
name: docker
description: Opt-in overlay for any containerized project. Docker handling is
  cross-cutting — check_docker_readiness.py runs unconditionally at deploy for
  every project regardless of profile — so this profile is never required to
  get that coverage. Select it explicitly (/forge:set-profile docker) or
  accept the suggestion when Docker artifacts dominate an otherwise-unknown
  project. Never auto-assigned over a real app type (a Dockerized FastAPI
  service stays `api`).

stage_emphasis:
  high: [architecture, deploy]
  low: []

stage_overrides:
  stage_3:
    additional_concerns:
      - "Multi-stage build strategy"
      - "Base image and version pinning strategy"
      - "Build secrets and volume handling"
      - "Layer caching strategy"

  stage_8:
    additional_steps:
      - "Build the image(s)"
      - "Scan the image(s) for known vulnerabilities"
      - "Push to the target registry"
    additional_criteria:
      - id: G8-DOCKER-001
        description: Docker hygiene check passes (pinned base image, HEALTHCHECK, non-root USER, .dockerignore present)
        check: script_returns_zero
        args: { script: "scripts/check_docker_readiness.py" }
        severity: warning

  stage_9:
    additional_concerns:
      - "Container restart / OOM-kill monitoring"
      - "Resource limit (CPU/memory) alerting"
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
