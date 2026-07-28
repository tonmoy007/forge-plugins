# SRS — Forge v0.7.0 (Docker workflow enforcement + extensible tooling preflight)

> **Status**: **Draft — ready for build** (2026-06-24). A new, **fail-soft / never-block** capability layer,
> orthogonal to the engine trio. Two related pieces: (1) a **cross-cutting Docker handling** path — whenever
> a Forge-managed project ships Docker artifacts, surface **advisory** hygiene findings and ensure the
> required CLIs are present, **regardless of the project's app profile**; and (2) an **extensible,
> declarative tool registry** (`docker`, `docker compose`, `gh`, …) that **detects** missing required tools
> and **offers** to install them (never auto-runs, never blocks). `docker` also becomes an **opt-in profile**
> that never auto-overrides `api`/`fullstack`. Everything is stdlib-only in the hot path, fail-soft, and
> exits 0 — nothing in this release can block pipeline advancement.
>
> **Provenance**: brainstormed 2026-06-24. The user's intent — "strictly enforce docker workflows … git
> workflows … auto ask user to install gh or anything required" — was refined through four decisions:
> a **docker project profile**; the tooling preflight **offers to install, never blocks**; the profile's
> hygiene gate is **advisory**; and the tool registry is **extensible** ("gh or anything required"). Because
> Docker is **orthogonal** to the mutually-exclusive profile cascade (a containerized FastAPI app is still
> `api`), the agreed architecture is **cross-cutting Docker handling + an opt-in `docker` profile** — the
> common "containerized app" case is covered without mis-routing the app type.
>
> **Grounding** (verified 2026-06-24, file:line):
> - **One mutually-exclusive detection cascade.** `scripts/detect-project-type.py:detect()` (`:217`) returns
>   exactly one `type`; `_finalize()` (`:450`) aliases `project_type` and — only when `type == "unknown"`
>   and the repo looks tiny — emits a **non-binding** `suggested_profile: "script"` (`:465-475`,
>   `_detect_script` `:422`). This suggestion-hint pattern is the template for a `docker` suggestion.
> - **Profile gates are advisory, not mechanical.** `scripts/check-gate.py:_load_stage_criteria` (`:37-55`)
>   reads **only** `references/gate-criteria.md`; it does **not** merge a profile's `additional_criteria`.
>   Those are surfaced to the stage agent via `scripts/load-profile.py` (`_extract_profile` `:52-69`) and the
>   stage skills instruct the agent to honor them (`skills/forge-eval|build|release|monitor/SKILL.md` all say
>   "treat each `additional_criteria` …"). So a profile-level advisory check is the **native** never-block
>   pattern. There is also a `soft_criteria` (blocker→warning) convention (the `script` profile).
> - **Gate-script template.** `scripts/check_store_readiness.py` walks the tree skipping ignore dirs
>   (`_walk_files` `:47`), no-ops to **exit 0** when its target platform is absent (`:114-116`), exits 1 with
>   a missing-list otherwise (`:120-123`) — declared in `references/project-type-profiles.md` under the
>   mobile profile's `stage_12.additional_criteria` (`:472-478`, `severity: blocker`).
> - **Capability-probe template.** `hooks/_background_agent.py` detects the `claude` CLI via
>   `shutil.which` (`_resolve_bin` `:64-65`), wraps the result in a `Capability` dataclass (`:46`), and
>   **never raises** (REQ-F-003, `:18-21`); session-start caches it to `.forge/capabilities.json` with a
>   **24h TTL + detached refresh** (T-138). This is the template for a tool-status cache.
> - **Doctor is the report surface.** `scripts/doctor.py` is a registry of `check_*()` functions returning a
>   `CheckResult` dataclass (`:49`); it already probes a CLI (`check_claude_code` `:101-102`, `shutil.which`)
>   and **every failing check carries a specific fix command** (`:4-5`); `run_checks()` (`:512`) aggregates.
> - **Skill shape.** `skills/forge-set-profile/SKILL.md` — `name`/`description`/`allowed-tools` frontmatter,
>   body runs `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/<script>.py … --cwd .` — the template for `/forge:preflight`.

---

## 1. Overview

### 1.1 Problem

Forge can manage a containerized project, but it has no awareness of Docker as a workflow: it never checks
that a project's `Dockerfile`/compose is hygienic (pinned base image, healthcheck, non-root user,
`.dockerignore`), and it never verifies that the CLIs a workflow needs — `docker`, `docker compose`, `gh`
for git/GitHub flows — are actually installed. A user mid-pipeline can hit a wall at the deploy or release
stage because a required tool is missing, with no early signal and no guided install. There is also no
first-class way to tell Forge "this is a Docker project."

Two constraints bound the design, both confirmed against the code:

1. **Docker is orthogonal to the profile cascade.** `detect()` returns exactly one mutually-exclusive type,
   so a containerized FastAPI app classifies as `api`. A literal "9th docker profile" in the auto-detect
   cascade would only ever fire for pure-infra repos — the common "app that ships a container" case would
   get **no** Docker treatment. Docker handling must therefore be **cross-cutting**, not gated on a profile.
2. **Hooks run non-interactively.** A hook can detect a missing tool and surface a message, but it cannot
   pop an installer. Running an install (`brew`/`apt`/`winget`) must happen in a **skill turn** where the
   user can confirm. So detection and offering-to-install are separate surfaces.

### 1.2 Objective

Ship a **fail-soft, never-block** Docker-and-tooling layer:

- A **declarative, extensible tool registry** + a stdlib, never-raising `tool_preflight.py` that detects
  whether each required CLI is present (cached with a TTL, like the capability probe) and resolves the
  per-OS install command — **without running it**.
- **Surfacing** of missing required tools at session-start (one advisory line, budget-aware) and in
  `/forge:doctor` (report + fix command), plus a `/forge:preflight` skill that **offers** to run the install
  command **after the user confirms** — the only piece that can install, and never auto-runs.
- An **advisory Docker hygiene check** (`check_docker_readiness.py`) that no-ops without Docker artifacts and
  **exits 0 even with findings** (warnings only), wired **cross-cutting** into the deploy stage so every
  containerized project gets it regardless of profile.
- An **opt-in `docker` profile** (selectable via `/forge:set-profile`, suggested but **never auto-assigned**)
  carrying deploy/architecture emphasis and the advisory hygiene criterion.

**Zero blocking, zero default disruption**: a project without Docker artifacts and with all tools present
sees no behavior change; nothing exits 2.

### 1.3 Scope

**In scope.**

- **`references/tool-registry.md`** — declarative markdown-with-YAML (same shape as `gate-criteria.md` /
  `project-type-profiles.md`). One entry per tool: `name`, `which` (binary for `shutil.which`), optional
  `version_probe` (argv), `workflows`, `stages`, `required_when` (`always` | `docker_artifacts_present` |
  `release_stage`), and per-OS `install: {darwin, linux, win32}`. Seeded with `docker`, `docker compose`
  (probed via `docker compose version`), and `gh`. A new tool is a **data entry**, not code.
- **`scripts/tool_preflight.py`** — stdlib, never-raising. Pure detection (`shutil.which` + optional
  version probe), result cached to `.forge/tool-status.json` with a **24h TTL + detached refresh**
  (mirroring the capability probe). `required_when` evaluated against project state (Docker artifacts
  present? at release stage?). CLI: `check --cwd .` → JSON `{tool: {present, version, required, reason,
  install_cmd}}`; `install <tool>` → returns the OS-appropriate install command string (**does not run it**).
- **`scripts/doctor.py`** — a new `check_required_tools(forge_root, cwd) -> list[CheckResult]` returning one
  `CheckResult` per **missing required** tool, with the install command as its `fix`; slotted into
  `run_checks()`. `/forge:doctor` stays read-only/diagnostic.
- **`hooks/session-start.py`** — a `_tool_preflight_block` injected after lessons/rules: a one-line advisory
  per missing required tool (e.g. *"⚠ Docker workflow needs `docker` (not found) — run `/forge:preflight`"*),
  read from the cached `.forge/tool-status.json` (**pure stdlib**, no subprocess in the hook), refreshed
  detached. **Budget-aware** — dropped first under token pressure; **never blocks** startup; silent when no
  tool is missing, outside a Forge project, or the cache is unreadable.
- **`skills/forge-preflight/SKILL.md`** (new `/forge:preflight`) — detects missing required tools via
  `tool_preflight.py check`, shows the exact per-OS install command, and runs it via Bash **only after the
  user confirms**. Never auto-runs. The single "offer to install" surface.
- **`scripts/check_docker_readiness.py`** — advisory hygiene check (mirrors `check_store_readiness.py`):
  finds `Dockerfile*` / `docker-compose.yml` / `compose.yaml`; checks base image **pinned** (no
  `:latest` / untagged `FROM`), `HEALTHCHECK` present, non-root `USER`, `.dockerignore` exists, compose
  parses and has `services:`. **No-ops (exit 0) without Docker artifacts** and **exits 0 even with findings**
  (printed as `WARN:` lines) — it can never block.
- **Cross-cutting deploy wiring** — `skills/forge-deploy/SKILL.md` (stage 8) runs `check_docker_readiness.py`
  **unconditionally** (it self-no-ops without a Dockerfile) and relays any `WARN:` findings as advisory,
  never blocking — so every project gets the check, profile or not.
- **`docker` profile** — `## Profile: docker` in `project-type-profiles.md`: `stage_emphasis: high:
  [architecture, deploy]`; stage_3 concerns (multi-stage builds, base-image strategy, secrets/volumes,
  layer caching); stage_8 `additional_criteria` (`G8-DOCKER-001` → `check_docker_readiness.py`,
  `severity: warning`) + steps (build, scan, registry push). Added to the `set-profile.py` valid list and
  the `load-profile` "all N standard profiles" parity test.
- **Detection** — `detect-project-type.py` emits `has_docker: true` + `docker_indicators` when Docker
  artifacts are present, and a `suggested_profile: "docker"` hint **only when** Docker dominates and the
  type is otherwise `unknown` (mirrors the `script` suggestion). **Never auto-assigned** over a real app type.
- **ADR-012** (cross-cutting Docker handling + opt-in profile; advisory hygiene; offer-not-block tooling;
  declarative registry) + reference doc + README + ROADMAP + progress/decisions.

**Out of scope.**

- **Running agents inside Docker containers** (sandboxed execution) — that is a separate, larger track
  (closest to the existing `worktree_isolation` toggle); explicitly not this release.
- **Auto-installing tools without confirmation** (rejected during brainstorming) and **blocking** the
  pipeline on a missing tool or a hygiene finding (the never-block decision).
- **Generating** Dockerfiles / compose / CI as the mandatory deploy output (the "generate deploy artifacts"
  option was not chosen) — the deploy agent may still author them, but Forge does not enforce a generated
  containerized deploy path.
- **A mechanical (blocking) Docker gate** in base `gate-criteria.md` — the hygiene check is agent-surfaced
  and advisory by design.
- The engine trio (per-branch reuse · top-level generation · pipeline-as-WorkflowSpec; `srs-v0.6.0.md` §6)
  and the standing non-goals (`srs-v0.4.1.md` §5.4) — unchanged.

### 1.4 Design principles

- **Cross-cutting, not profile-gated.** Docker hygiene + tool checks fire for **any** project that has
  Docker artifacts or needs a tool, independent of the mutually-exclusive app profile. The `docker` profile
  is an opt-in *overlay* (emphasis + the advisory criterion), never a precondition for Docker treatment, and
  never auto-overrides `api`/`fullstack`.
- **Detect in a hook; install in a skill.** The non-interactive hot path only ever **detects and surfaces**;
  the only code that runs an installer is `/forge:preflight`, **after explicit user confirmation**.
- **Advisory, never block.** No new script exits non-zero as a gate; the hygiene check exits 0 even with
  findings; nothing in this release can stop pipeline advancement. Consistent with the never-block decisions.
- **Declarative + extensible.** Tools live in `tool-registry.md` as data — "gh or anything required" is a
  new entry, not new code.
- **Stdlib in the hot path; fail-soft; never-raises.** The session-start hook reads a cached JSON file with
  stdlib only; `tool_preflight.py` and `check_docker_readiness.py` use PyYAML only in `scripts/` (fail-soft
  import) and degrade to no-op on any error. Missing binary → "not present"; unreadable registry/cache → no
  advisory. Default-quiet: present tools + no Docker ⇒ no output, no behavior change.

---

## 2. Functional Requirements

- **REQ-TR-001** — `references/tool-registry.md` declares tools in a YAML block: `name`, `which`, optional
  `version_probe` (argv list), `workflows` (list), `stages` (list of pipeline stage numbers), `required_when`
  (`always` | `docker_artifacts_present` | `release_stage`), and `install` mapping `darwin`/`linux`/`win32`
  to a command string. Seeded with `docker`, `docker compose`, `gh`. Unknown/missing fields fail soft
  (a malformed entry is skipped, not fatal).
- **REQ-TR-002** — `scripts/tool_preflight.py` provides pure detection: for each registry tool, `shutil.which`
  (+ optional `version_probe`) → present/absent + version; caches `{tool: {...}}` to `.forge/tool-status.json`
  with a 24h TTL and detached refresh; resolves `required` from `required_when` against project state
  (Docker artifacts present in `cwd`? current stage == release?). CLI: `check --cwd .` → JSON; `install
  <tool>` → the OS-appropriate install command **string only** (it never executes it). Never raises; a
  missing/unreadable registry or cache degrades to an empty/needs-refresh result. Stdlib + PyYAML (fail-soft
  import) in `scripts/`.
- **REQ-TR-003** — `scripts/doctor.py` gains `check_required_tools(forge_root, cwd) -> list[CheckResult]`
  returning one `CheckResult` per **missing required** tool, status `warn`, with the resolved install command
  as the `fix`; present/not-required tools produce no failing result. Wired into `run_checks()`. Doctor
  remains read-only (it reports; it does not install).
- **REQ-TR-004** — `hooks/session-start.py` injects a `_tool_preflight_block` after the lessons/rules blocks:
  one advisory line per missing required tool, read from the cached `.forge/tool-status.json` (stdlib only;
  the hook triggers the detached refresh but never runs detection inline). Budget-aware (dropped before
  lessons/rules under token pressure, holding the ≤2000-token session-start budget), fail-soft, and **silent**
  when nothing is missing, outside a Forge project, or the cache is unreadable. Never blocks startup.
- **REQ-TR-005** — `skills/forge-preflight/SKILL.md` (`name: preflight`) runs `tool_preflight.py check`,
  presents each missing required tool with its per-OS install command, and — **only after the user confirms**
  — runs that command via Bash. It never auto-runs an installer and never installs a tool the user declines.
  `allowed-tools: [Read, Bash]`.
- **REQ-DK-001** — `scripts/check_docker_readiness.py` (advisory) finds `Dockerfile*` / `docker-compose.yml`
  / `compose.yaml` (walking the tree, skipping ignore dirs) and reports hygiene findings: base image pinned
  (no `:latest`, no untagged `FROM`), `HEALTHCHECK` present, non-root `USER` directive, `.dockerignore`
  present, compose parses + has a `services:` key. It **exits 0 when no Docker artifacts are present**
  (no-op) and **exits 0 even when findings exist** (findings printed as `WARN:` lines) — purely advisory,
  never a blocking gate. Robust to unreadable files; stdlib + fail-soft PyYAML for the compose parse.
- **REQ-DK-002** — `skills/forge-deploy/SKILL.md` (stage 8) runs `check_docker_readiness.py --cwd .`
  **unconditionally** in pre-flight (it self-no-ops without Docker artifacts) and surfaces any `WARN:`
  findings to the user as advisory items — **without blocking** deploy. This gives every project, regardless
  of profile, the cross-cutting Docker hygiene surfacing.
- **REQ-DK-003** — `references/project-type-profiles.md` gains a `## Profile: docker` block:
  `stage_emphasis: high: [architecture, deploy]`; `stage_3.additional_concerns` (multi-stage builds,
  base-image/version strategy, build secrets + volumes, layer caching); `stage_8.additional_steps` (build,
  vulnerability scan, registry push) and `stage_8.additional_criteria` with `G8-DOCKER-001`
  (`check: script_returns_zero`, `args: {script: "scripts/check_docker_readiness.py"}`, `severity: warning`).
- **REQ-DK-004** — `scripts/detect-project-type.py` emits `has_docker: true` + `docker_indicators` (the
  artifacts found) whenever Docker artifacts are present, and adds `suggested_profile: "docker"` (+
  confidence/indicators, mirroring the `script` suggestion) **only when** the type is otherwise `unknown`
  and Docker artifacts dominate — **never** overriding `api`/`fullstack`/etc. `docker` is added to the
  `set-profile.py` valid-profile list and to the `load-profile` "all standard profiles" parity test.
- **REQ-DOC-001** — **ADR-012** records the architecture (cross-cutting Docker handling + opt-in profile;
  advisory hygiene; detect-in-hook/install-in-skill; declarative registry; sandboxed-execution and
  artifact-generation explicitly out of scope). The tool registry, `/forge:preflight`, and the advisory
  Docker handling are documented in a reference doc + README; ROADMAP + `progress.md` + `decisions.md` carry
  the v0.7.0 row.
- **REQ-REL-001** — Release v0.7.0: `bump-version.py 0.7.0`; CHANGELOG `[0.7.0]`; ROADMAP + progress rows;
  ADR-012; banner/social evergreen (no refresh). Pre-release green; PR→develop→main→tag
  `v0.7.0`→mirror both remotes→GitHub releases→delete branch.

---

## 3. Non-Functional Requirements

- **REQ-NF-042** — **Fail-soft; never-raises; never-block; stdlib in the hot path.** No script in this
  release exits non-zero as a blocking gate; the session-start advisory is pure-stdlib, budget-aware, and
  degrades to silence on any error (a missing/unreadable cache or registry never crashes or blocks the
  hook). `tool_preflight.py` and `check_docker_readiness.py` use PyYAML only in `scripts/` with a fail-soft
  import and never raise (missing binary → "not present"; unparseable file → skip). The only code that runs
  an installer is `/forge:preflight`, gated on explicit user confirmation. A project with no Docker artifacts
  and all required tools present is **byte-identical** in behavior to v0.6.1 (no advisory, no extra output).

---

## 4. Acceptance Criteria

- **AC-TR-001** (REQ-TR-001/002) — Given a registry with `docker`/`gh`, `tool_preflight.py check` reports
  each tool's presence (via a monkeypatched `shutil.which`), version (via the probe), and `required` per
  `required_when` (a Docker-artifact fixture marks `docker` required; a bare dir does not); the result is
  cached to `.forge/tool-status.json` and reused within the TTL; a missing/unreadable registry or cache
  yields a no-op result and never raises. `install docker` returns the platform's install string and runs
  nothing.
- **AC-TR-002** (REQ-TR-003) — `check_required_tools` returns a failing `CheckResult` (with the install
  command as `fix`) for a missing **required** tool and **no** failing result when the tool is present or
  not required; `/forge:doctor` surfaces it.
- **AC-TR-003** (REQ-TR-004) — With a missing required tool, session-start emits exactly one advisory line
  per tool pointing at `/forge:preflight`; under a constrained token budget the block is dropped before
  lessons/rules and session-start stays ≤2000 tokens; with all tools present, outside a Forge project, or an
  unreadable cache, session-start emits **no** tool advisory and never errors.
- **AC-TR-004** (REQ-TR-005) — Structural: `/forge:preflight`'s SKILL.md parses (frontmatter valid; no `: `
  YAML trap), declares `allowed-tools: [Read, Bash]`, documents the detect→confirm→install flow, and states
  it never auto-runs an installer.
- **AC-DK-001** (REQ-DK-001) — On a fixture with an unpinned `FROM image:latest`, no `HEALTHCHECK`, no
  `USER`, and a missing `.dockerignore`, the script prints the corresponding `WARN:` lines and **still exits
  0**; on a clean Dockerfile it prints a pass line and exits 0; on a dir with **no** Docker artifacts it
  no-ops and exits 0; unreadable files don't crash it.
- **AC-DK-002** (REQ-DK-002) — `skills/forge-deploy/SKILL.md` invokes `check_docker_readiness.py --cwd .`
  unconditionally in pre-flight and relays findings as advisory; the step is asserted present and worded as
  non-blocking (structural test).
- **AC-DK-003** (REQ-DK-003/004) — The `docker` profile loads via `load-profile.py` (parity test now covers
  all standard profiles **including `docker`**), `set-profile.py docker` is accepted, and `G8-DOCKER-001`
  appears in the profile's stage_8 `additional_criteria` with `severity: warning`.
- **AC-DK-004** (REQ-DK-004) — `detect-project-type.py` emits `has_docker: true` for a repo containing a
  `Dockerfile`; it adds `suggested_profile: "docker"` **only** when the type is `unknown` and Docker
  dominates; a FastAPI-in-Docker fixture still classifies as `api` (with `has_docker: true`) and is **never**
  auto-assigned the `docker` profile.
- **AC-REL-001** (REQ-REL-001) — Full unit suite green; `validate-plugin.py` 0; `full-pipeline.sh` 12/12;
  manifests `0.7.0`; `v0.7.0` tagged on origin + polygon with GitHub releases; ADR-012 present; two-remote
  parity.

---

## 5. Architecture notes (for ADR-012)

- **ADR-012 — Docker workflow enforcement: cross-cutting handling + an opt-in profile, advisory and
  never-blocking, with a declarative tool registry.** **Decisions:**
  - **Cross-cutting, not a mutually-exclusive profile.** Because `detect()` returns one type and Docker is
    orthogonal, Docker hygiene + tool checks attach to **any** project (via the self-no-op'ing
    `check_docker_readiness.py` run unconditionally at deploy, and the registry's `docker_artifacts_present`
    condition) rather than only to a `docker`-typed project. The `docker` profile is an **opt-in overlay**
    (emphasis + the advisory criterion) and a **suggestion-only** hint — it never auto-overrides a real app
    type. Rejected: a literal 9th cascade profile (would miss containerized apps); a hybrid two-path design
    (YAGNI for the rare pure-infra repo).
  - **Advisory, never block.** The hygiene check is **agent-surfaced** (via the deploy skill + the profile's
    `additional_criteria`), **not** a mechanical `gate-criteria.md` entry — so it can never fail the gate.
    The script exits 0 even with findings. Consistent with the never-block decisions.
  - **Detect in a hook; install in a skill.** Non-interactive hooks only detect + surface; `/forge:preflight`
    is the sole installer surface and runs only after explicit confirmation. Auto-install was rejected.
  - **Declarative + extensible registry.** Tools are data in `tool-registry.md`; the detection/cache/TTL
    machinery reuses the capability-probe pattern (`shutil.which` + `.forge/*.json` + 24h TTL + detached
    refresh).
  - **Out of scope (recorded):** running agents inside containers (sandboxed execution) and generating
    Dockerfiles/CI as the mandatory deploy output — both larger, separate tracks.

---

## 6. Roadmap context

v0.7.0 is a **new capability layer** (Docker + tooling preflight), orthogonal to the engine trio. Remaining
program order is unchanged from `srs-v0.6.0.md` §6: trio item 1b (per-branch reuse, measurement-gated) ·
trio item 2 (top-level LLM-generated workflows) · trio item 3 (pipeline-as-WorkflowSpec, stretch). A future
**containerized-execution** track (run agents inside Docker, akin to `worktree_isolation`) is noted as a
candidate but is **not** scheduled here. Standing non-goals (`srs-v0.4.1.md` §5.4) unchanged.

---

## 7. Traceability

| REQ-ID | Tasks (assigned in task-dag-v0.7.0) |
|--------|-------------------------------------|
| REQ-TR-001 | tool registry (`references/tool-registry.md`) |
| REQ-TR-002 | `scripts/tool_preflight.py` (detect + cache + CLI) |
| REQ-TR-003 | `doctor.py` `check_required_tools` |
| REQ-TR-004 | session-start advisory injection |
| REQ-TR-005 | `/forge:preflight` skill (offer-install) |
| REQ-DK-001 | `scripts/check_docker_readiness.py` (advisory) |
| REQ-DK-002 | `forge-deploy` cross-cutting wiring |
| REQ-DK-003 | `docker` profile block |
| REQ-DK-004 | detection (`has_docker` + suggestion) + set-profile + parity |
| REQ-DOC-001 | ADR-012 + reference / README / ROADMAP / progress |
| REQ-REL-001 | release v0.7.0 |
| REQ-NF-042 | every task (invariants) |
| ADR-012 | registry + docker-handling tasks |

---

## 8. References & provenance

- **Brainstorm 2026-06-24** — refined the user's intent into four decisions (docker profile · offer-install
  never-block · advisory hygiene gate · extensible registry) and the cross-cutting-vs-profile resolution.
- **`scripts/detect-project-type.py`** — the mutually-exclusive cascade + the `script` suggestion-hint
  pattern reused for `docker`.
- **`scripts/check-gate.py` + `scripts/load-profile.py` + `skills/forge-{eval,build,release,monitor}/SKILL.md`**
  — establish that profile `additional_criteria` are advisory/agent-surfaced, not mechanical — the native
  never-block path.
- **`scripts/check_store_readiness.py`** — the no-op-when-absent gate-script template for
  `check_docker_readiness.py`.
- **`hooks/_background_agent.py` + T-138 capability probe** — `shutil.which` + `.forge/*.json` + 24h TTL +
  detached refresh; the template for `tool_preflight.py`'s tool-status cache.
- **`scripts/doctor.py`** — the `CheckResult` registry + fix-command convention that `check_required_tools`
  extends.
- **Standing non-goals (`srs-v0.4.1.md` §5.4)** — unchanged; sandboxed execution + artifact generation are
  deferred to separate tracks.
