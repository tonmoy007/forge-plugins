# ADR-012: Docker Workflow Enforcement — Cross-Cutting Handling + an Opt-In Profile, Advisory and Never-Blocking, with a Declarative Tool Registry

**Status**: Accepted
**Date**: 2026-06-24

## Context

Forge can manage a containerized project, but until now had no awareness of Docker as a
workflow: no check that a project's `Dockerfile`/compose is hygienic (pinned base image,
healthcheck, non-root user, `.dockerignore`), and no verification that the CLIs a workflow
needs — `docker`, `docker compose`, `gh` for git/GitHub flows — are actually installed. A user
could hit a wall at the deploy or release stage because a required tool was missing, with no
early signal and no guided install. There was also no first-class way to tell Forge "this is a
Docker project."

Two constraints bound the design, both confirmed against the code before implementation:

1. **Docker is orthogonal to the profile cascade.** `scripts/detect-project-type.py:detect()`
   returns exactly one mutually-exclusive `type`, so a containerized FastAPI app classifies as
   `api`. A literal "9th docker profile" in the auto-detect cascade would only ever fire for
   pure-infra repos — the common "app that ships a container" case would get **no** Docker
   treatment. Docker handling must therefore be **cross-cutting**, not gated on a profile.
2. **Hooks run non-interactively.** A hook can detect a missing tool and surface a message, but
   it cannot pop an installer. Running an install (`brew`/`apt`/`winget`) must happen in a
   **skill turn** where the user can confirm. So detection and offering-to-install are separate
   surfaces.

## Decision

**Ship a fail-soft, never-block Docker-and-tooling layer**: a declarative, extensible tool
registry with detection cached like the existing capability probe; an advisory Docker hygiene
check wired cross-cutting into deploy; and an opt-in `docker` profile that never auto-overrides
a real app type.

Four load-bearing decisions:

- **Cross-cutting, not a mutually-exclusive profile.** Because `detect()` returns one type and
  Docker is orthogonal, Docker hygiene + tool checks attach to **any** project — via the
  self-no-op'ing `scripts/check_docker_readiness.py` run unconditionally at deploy
  (`skills/forge-deploy/SKILL.md`), and the tool registry's `docker_artifacts_present`
  condition — rather than only to a `docker`-typed project. The `docker` profile
  (`references/project-type-profiles.md`) is an **opt-in overlay** (stage emphasis + the
  advisory hygiene criterion) and a **suggestion-only** hint from `detect-project-type.py`
  (`suggested_profile: "docker"`, only when the type is otherwise `unknown` and Docker
  dominates) — it never auto-overrides a real app type.
- **Advisory, never block.** The hygiene check is **agent-surfaced** (the deploy skill relays
  its `WARN:` lines, and the profile's `additional_criteria` entry documents the concern for
  the stage agent), **not** a mechanical `gate-criteria.md` entry — so it can never fail a gate.
  `check_docker_readiness.py` exits 0 even when it finds problems.
- **Detect in a hook; install in a skill.** `hooks/session-start.py` and `scripts/doctor.py`
  only ever detect and report a missing tool. `skills/forge-preflight/SKILL.md` is the **sole**
  surface that runs an installer, and only after the user explicitly confirms which tool to
  install. Auto-install was considered and rejected.
- **Declarative + extensible registry.** Tools live as data in
  `references/tool-registry.md` — adding a new required CLI is a registry entry, not new code.
  The detection/cache/TTL machinery reuses the capability-probe pattern
  (`hooks/_background_agent.py`: `shutil.which` + `.forge/*.json` + 24h TTL + detached refresh,
  T-138) rather than inventing a second one.

## Rationale

1. **The common case gets coverage without misclassification.** Cross-cutting hygiene means a
   Dockerized FastAPI app is checked for Docker hygiene *and* still gets the `api` profile's
   spec/eval treatment — neither is sacrificed for the other.
2. **Nothing in this layer can regress an existing project.** Every script here is fail-soft and
   exits 0; a project with no Docker artifacts and all tools present is byte-identical in
   behavior to the pre-v0.7.0 baseline (no advisory output, no new blocking path).
3. **Consent before any install.** The non-interactive/interactive split (detect in a hook,
   install only in a confirmed skill turn) is the only way to offer installs without ever running
   a command the user hasn't seen and approved.
4. **One detection pattern, not two.** Reusing the capability-probe's cache/TTL/detached-refresh
   shape for tool status keeps the hot-path cost (a session-start hook read) identical in kind to
   an already-shipped, already-measured pattern.

## Alternatives considered

- **A literal 9th cascade profile (`docker` as a mutually-exclusive `type`).** Rejected: would
  only fire for pure-infrastructure repos with no other signal; the common "app that ships a
  container" case (a Dockerized API, a Dockerized fullstack app) would get no Docker treatment
  at all, since `detect()`'s cascade already classifies those as `api`/`fullstack`.
  A hybrid two-path design was also considered and rejected as YAGNI for the rare pure-infra
  repo — the cross-cutting-plus-opt-in-overlay shape already covers it.
- **Auto-installing missing tools without confirmation.** Rejected during brainstorming — running
  an installer non-interactively on a user's machine without consent is unacceptable regardless
  of how the tool was detected as missing.
- **A mechanical, blocking Docker gate in base `gate-criteria.md`.** Rejected: this release's
  Docker hygiene is explicitly advisory; a hard-coded blocking entry there would fail every
  containerized project on day one for issues the user may not be ready to fix yet, contradicting
  the never-block decision the rest of this layer is built around.
- **Generating Dockerfiles/compose/CI as the mandatory deploy output.** Not chosen — the deploy
  agent may still author them, but Forge does not enforce a generated containerized deploy path
  as part of this layer.

## Consequences

- New: `references/tool-registry.md` (declarative registry), `scripts/tool_preflight.py`
  (detection + `.forge/tool-status.json` cache), `scripts/check_docker_readiness.py` (advisory
  hygiene), `skills/forge-preflight/SKILL.md` (the sole install surface).
- Changed: `scripts/doctor.py` gains `check_required_tools`; `hooks/session-start.py` gains a
  budget-aware tool advisory (dropped first under token pressure, ahead of lessons/rules — a
  stricter budget posture than the existing capability/health/traceability notes, which are not
  currently budget-counted); `skills/forge-deploy/SKILL.md` runs the hygiene check
  unconditionally; `scripts/detect-project-type.py` emits `has_docker`/`docker_indicators` and
  a `docker` suggestion hint; `references/project-type-profiles.md` gains `## Profile: docker`.
- Out of scope (recorded, not silently dropped): running agents **inside** Docker containers
  (sandboxed execution — a separate, larger track, closest to the existing `worktree_isolation`
  toggle); auto-installing tools without confirmation; a mechanical/blocking Docker gate; the
  engine trio (`build/01-srs/srs-v0.6.0.md` §6) and the standing non-goals
  (`build/01-srs/srs-v0.4.1.md` §5.4) — unchanged.
- See `references/docker-and-tooling.md` for the user-facing reference on the registry format,
  the required-tool resolution rules, and the advisory hygiene checks.
