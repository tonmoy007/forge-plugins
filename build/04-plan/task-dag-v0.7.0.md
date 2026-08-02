# Task DAG — Forge v0.7.0 (Docker workflow enforcement + extensible tooling preflight)

> **Status**: **Ready to build** (2026-06-24). Derived from `build/01-srs/srs-v0.7.0.md`.
> Numbering continues from v0.6.1 (T-220..T-226); this is **T-227..T-234**. A **fail-soft / never-block**
> capability layer: a declarative tool registry + preflight (detect missing CLIs, offer-install in a skill,
> never auto-run), an **advisory** Docker hygiene check wired **cross-cutting** into deploy, and an **opt-in
> `docker` profile** that never auto-overrides `api`/`fullstack`. Docker handling is cross-cutting — it
> attaches to any project with Docker artifacts, not only `docker`-typed ones.
>
> Format: `T-NNN [size] title` — Size: S (~30min), M (~2hr), L (~half-day).
>
> | Milestone | Tag | Gate |
> |-----------|-----|------|
> | M1 Detection core (registry + preflight + hygiene) | — | v0.6.1 landed |
> | M2 Surfacing + offer-install + profile | — | M1 landed |
> | M3 Docs + ADR | — | M2 landed |
> | M4 Release | v0.7.0 | M1–M3 landed |
>
> **Invariants** (every task): **never-block** (no script exits non-zero as a gate; the hygiene check exits 0
> even with findings); **fail-soft + never-raises** (missing binary → "not present"; unreadable
> registry/cache → no-op; the session-start advisory degrades to silence); **stdlib in the hot path** (the
> hook reads cached JSON with stdlib only; PyYAML used only in `scripts/`, fail-soft import); **detect in a
> hook, install only in a skill after explicit confirmation** (no auto-install); **no-Docker + all-tools-present
> ⇒ byte-identical to v0.6.1**; the `docker` profile is **suggestion-only / opt-in**, never auto-assigned over
> a real app type; TDD **red-first**; full unit suite + `validate-plugin.py` 0 + `full-pipeline.sh` **12/12**
> green per task. Baseline before T-227: **1783 unit tests** (post-v0.6.1). Reuses the capability-probe
> pattern (`hooks/_background_agent.py` `shutil.which` + `.forge/*.json` + 24h TTL + detached refresh,
> T-138), the gate-script template (`scripts/check_store_readiness.py`, no-op-when-absent), the advisory
> profile-criteria path (`scripts/load-profile.py` + the stage skills), and the `doctor.py` `CheckResult` +
> fix-command convention.

---

## Milestone 1: Detection core

### T-227 [M] Tool registry + `scripts/tool_preflight.py` (detect + cache + CLI)
- **Description**: Add `references/tool-registry.md` (markdown-with-YAML; per-tool `name`/`which`/
  `version_probe`/`workflows`/`stages`/`required_when`/per-OS `install`; seeded `docker`, `docker compose`,
  `gh`). New `scripts/tool_preflight.py`: pure detection via `shutil.which` + optional `version_probe`,
  cached to `.forge/tool-status.json` with a 24h TTL + detached refresh (mirror the capability probe);
  `required_when` (`always`|`docker_artifacts_present`|`release_stage`) resolved against project state; CLI
  `check --cwd .` → JSON, `install <tool>` → install-command **string only** (never executes). Never raises;
  stdlib + fail-soft PyYAML.
- **Files**: `references/tool-registry.md` (new), `scripts/tool_preflight.py` (new),
  `tests/unit/test_tool_preflight.py` (new)
- **Done when**: AC-TR-001 — registry parses; presence/version via monkeypatched `shutil.which` + probe;
  `required` per `required_when` (Docker-artifact fixture marks `docker` required, bare dir does not); TTL
  cache reused; missing/unreadable registry or cache → no-op, never raises; `install` returns the string and
  runs nothing.
- **Depends on**: none (v0.6.1 landed)
- **REQ-IDs**: REQ-TR-001, REQ-TR-002, NF-042

### T-228 [M] `scripts/check_docker_readiness.py` advisory hygiene check
- **Description**: New advisory script (mirrors `check_store_readiness.py`): walk the tree (skip ignore
  dirs), find `Dockerfile*` / `docker-compose.yml` / `compose.yaml`; report hygiene findings (base image
  pinned — no `:latest`/untagged `FROM`; `HEALTHCHECK` present; non-root `USER`; `.dockerignore` present;
  compose parses + has `services:`). **Exit 0 when no Docker artifacts** (no-op) and **exit 0 even with
  findings** (`WARN:` lines) — never a blocking gate. Robust to unreadable files; stdlib + fail-soft PyYAML
  for the compose parse.
- **Files**: `scripts/check_docker_readiness.py` (new), `tests/unit/test_check_docker_readiness.py` (new)
- **Done when**: AC-DK-001 — unpinned/no-healthcheck/no-user/no-dockerignore fixture → `WARN:` lines, exit
  0; clean Dockerfile → pass line, exit 0; no-Docker dir → no-op, exit 0; unreadable files don't crash.
- **Depends on**: none (parallelizable with T-227 — disjoint files)
- **REQ-IDs**: REQ-DK-001, NF-042

---

## Milestone 2: Surfacing + offer-install + profile

### T-229 [S] `doctor.py` `check_required_tools` integration
- **Description**: Add `check_required_tools(forge_root, cwd) -> list[CheckResult]` returning one failing
  (`warn`) `CheckResult` per **missing required** tool with the resolved install command as its `fix`
  (present/not-required tools → no failing result); wire into `run_checks()`. Doctor stays read-only.
- **Files**: `scripts/doctor.py`, `tests/unit/test_doctor.py`
- **Done when**: AC-TR-002 — a missing required tool yields a failing CheckResult with the install command;
  a present or not-required tool yields none; `/forge:doctor` surfaces it.
- **Depends on**: T-227
- **REQ-IDs**: REQ-TR-003, NF-042

### T-230 [M] `session-start.py` tool-advisory injection (cached read + detached refresh)
- **Description**: Inject a `_tool_preflight_block` after the lessons/rules blocks: one advisory line per
  missing required tool (pointing at `/forge:preflight`), read from the cached `.forge/tool-status.json`
  (**stdlib only** — the hook triggers the detached refresh, never runs detection inline). Budget-aware
  (dropped before lessons/rules under token pressure; hold ≤2000-token session-start budget), fail-soft,
  **silent** when nothing missing / outside a Forge project / cache unreadable. Never blocks startup.
- **Files**: `hooks/session-start.py`, `tests/unit/test_session_start.py`
- **Done when**: AC-TR-003 — advisory line per missing tool; dropped first under constrained budget
  (≤2000 tokens held); no advisory + no error when all present / non-Forge dir / unreadable cache.
- **Depends on**: T-227
- **REQ-IDs**: REQ-TR-004, NF-042

### T-231 [S] `/forge:preflight` skill (offer-install, confirm-then-run)
- **Description**: New `skills/forge-preflight/SKILL.md` (`name: preflight`, `allowed-tools: [Read, Bash]`):
  run `tool_preflight.py check`, present each missing required tool + its per-OS install command, and run
  that command via Bash **only after the user confirms**. Never auto-runs; never installs a declined tool.
  Watch the `: ` YAML-trap in a wrapped `description:` (lessons 2026-06-22).
- **Files**: `skills/forge-preflight/SKILL.md` (new), `tests/unit/test_preflight_skill.py` (new, structural)
- **Done when**: AC-TR-004 — frontmatter parses (no `: ` trap), `allowed-tools: [Read, Bash]`, documents
  detect→confirm→install, states it never auto-runs.
- **Depends on**: T-227
- **REQ-IDs**: REQ-TR-005, NF-042

### T-232 [M] `docker` profile + cross-cutting deploy wiring + detection
- **Description**: Add `## Profile: docker` to `references/project-type-profiles.md` (`stage_emphasis: high:
  [architecture, deploy]`; stage_3 concerns: multi-stage builds, base-image strategy, build secrets/volumes,
  layer caching; stage_8 steps: build/scan/registry-push + `additional_criteria` `G8-DOCKER-001` →
  `check_docker_readiness.py`, `severity: warning`). Wire `skills/forge-deploy/SKILL.md` to run
  `check_docker_readiness.py --cwd .` **unconditionally** in pre-flight and relay `WARN:` findings as
  advisory (never block). Add `docker` to `set-profile.py`'s valid list + the `load-profile` "all standard
  profiles" parity test. In `detect-project-type.py`, emit `has_docker`/`docker_indicators` when Docker
  artifacts present and `suggested_profile: "docker"` **only** when type is `unknown` and Docker dominates
  (mirror the `script` suggestion) — never auto-assign over `api`/`fullstack`.
- **Files**: `references/project-type-profiles.md`, `skills/forge-deploy/SKILL.md`, `scripts/set-profile.py`,
  `scripts/detect-project-type.py`, `tests/unit/test_load_profile.py`, `tests/unit/test_set_profile.py`,
  `tests/unit/test_detect_project_type.py`, `tests/unit/test_deploy_skill.py` (or existing skill-structural test)
- **Done when**: AC-DK-002 (deploy skill runs the check unconditionally, worded non-blocking) + AC-DK-003
  (docker profile loads; parity covers it; `set-profile docker` accepted; `G8-DOCKER-001` warning present) +
  AC-DK-004 (`has_docker` emitted; `suggested_profile: docker` only when unknown+dominant; FastAPI-in-Docker
  stays `api`, never auto-assigned).
- **Depends on**: T-228 (the hygiene script it references)
- **REQ-IDs**: REQ-DK-002, REQ-DK-003, REQ-DK-004, NF-042

---

## Milestone 3: Docs + ADR

### T-233 [S] ADR-012 + reference / README / ROADMAP / progress docs
- **Description**: Write **ADR-012** (cross-cutting Docker handling + opt-in profile; advisory hygiene;
  detect-in-hook/install-in-skill; declarative registry; sandboxed-execution + artifact-generation out of
  scope). Document the tool registry, `/forge:preflight`, and the advisory Docker handling in a reference doc
  (`references/docker-and-tooling.md` or a section of an existing ref) + README (commands/hooks rows, a
  Docker + tooling-preflight bullet); record the v0.7.0 row in `ROADMAP.md`,
  `build/05-implementation/progress.md`, `decisions.md`. No code change (validate 0).
- **Files**: `build/02-architecture/adr/012-docker-and-tooling.md` (new), `references/docker-and-tooling.md`
  (new or section), `README.md`, `ROADMAP.md`, `build/05-implementation/progress.md`,
  `build/05-implementation/decisions.md`
- **Done when**: REQ-DOC-001 — ADR-012 present + linked; registry/preflight/Docker-handling documented;
  ROADMAP/progress carry the v0.7.0 row; validate 0.
- **Depends on**: T-229, T-230, T-231, T-232
- **REQ-IDs**: REQ-DOC-001, ADR-012

---

## Milestone 4: Release

### T-234 [S] Release v0.7.0
- **Description**: `bump-version.py 0.7.0`; CHANGELOG `[0.7.0]`; ROADMAP + progress rows; banner/social
  evergreen (no refresh). Pre-release green; PR→develop→main→tag `v0.7.0`→mirror both remotes→GitHub
  releases→delete branch. (Dispatch `release.yml` with `-f title="v0.7.0 — Docker workflow enforcement"`.)
- **Files**: `.claude-plugin/*`, `CHANGELOG.md`, `ROADMAP.md`, `build/05-implementation/progress.md`,
  `README.md`
- **Done when**: AC-REL-001 — suite green, validate 0, full-pipeline 12/12, manifests 0.7.0, tags + GitHub
  releases on both remotes; two-remote parity.
- **Depends on**: T-227..T-233
- **REQ-IDs**: REQ-REL-001

---

## Critical path

```
T-227 (registry + preflight) ┐
                             ├→ T-229 (doctor) ┐
                             ├→ T-230 (session-start) ┤
                             └→ T-231 (preflight skill) ┤
T-228 (hygiene check) ───────→ T-232 (profile + deploy wiring + detect) ┤
                                                                        └→ T-233 (ADR + docs) → T-234 (v0.7.0)
```

T-227 and T-228 are disjoint (registry/preflight vs the hygiene script) and parallelize. T-229/T-230/T-231
all consume `tool_preflight.py` (T-227) and touch disjoint files (doctor / session-start / a new skill) —
parallelizable after T-227. T-232 depends on T-228 (it references the hygiene script) and touches the
profile/detect/deploy surfaces. T-233 documents the landed behavior; T-234 releases.

---

## Acceptance gate (v0.7.0)

**AC-REL-001**: full unit suite green; `validate-plugin.py` 0; `full-pipeline.sh` **12/12**; `v0.7.0` tagged
on origin + polygon with GitHub releases; manifests `0.7.0`. Plus AC-TR-001..004 and AC-DK-001..004 — in
particular the **never-block** invariants (**AC-DK-001** the hygiene check exits 0 even with findings;
**AC-TR-003** session-start stays silent/budgeted and never blocks) and **AC-DK-004** (`docker` is never
auto-assigned over a real app type).

---

## Risk register

| ID | Risk | Impact | Likelihood | Mitigation |
|----|------|--------|------------|------------|
| R-1 | A `docker` profile mis-routes a containerized app (FastAPI-in-Docker → `docker` not `api`) | M | M | Cross-cutting handling, not a cascade profile; `docker` is suggestion-only and never auto-assigned; AC-DK-004 asserts FastAPI-in-Docker stays `api`. |
| R-2 | Session-start hook slows or crashes startup on tool detection | H | L | Hook reads a **cached** JSON file with stdlib only (detection runs detached); fail-soft to silence; AC-TR-003 asserts no-error + budget hold. |
| R-3 | The hygiene check blocks deploy on a finding | H | L | Script exits 0 even with findings; surfaced as advisory only; not in base `gate-criteria.md`; AC-DK-001/002. |
| R-4 | `/forge:preflight` runs an installer without consent | H | L | Skill runs the install command **only after explicit confirmation**; never auto-runs; AC-TR-004 asserts the wording. |
| R-5 | Per-OS install commands are wrong/unsafe on a platform | M | M | Install command is **surfaced** (and only run on confirm); registry data reviewed; user sees the exact command before it runs. |
| R-6 | Registry/cache parse error breaks detection | M | L | Fail-soft PyYAML import + per-entry skip; unreadable cache → refresh; `tool_preflight.py` never raises (AC-TR-001). |

---

## Out of scope (this release)

Running agents **inside** Docker containers (sandboxed execution — a separate track, akin to
`worktree_isolation`); **generating** Dockerfiles/compose/CI as the mandatory deploy output; **auto-installing**
tools without confirmation; a **mechanical/blocking** Docker gate in base `gate-criteria.md`; the engine trio
(`srs-v0.6.0.md` §6). Consolidated there + the standing non-goals in `srs-v0.4.1.md` §5.4.
