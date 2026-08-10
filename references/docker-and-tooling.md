# Docker and Tooling (v0.7.0)

A fail-soft, never-block capability layer: a declarative tool registry + preflight
(detect missing CLIs, offer to install in a confirmed skill turn, never auto-run), an
advisory Docker hygiene check wired cross-cutting into deploy, and an opt-in `docker`
profile. See ADR-012 for the full design rationale.

## Tool Registry (`references/tool-registry.md`)

Declares each external CLI Forge workflows may need as a YAML data entry — `name`,
`which` (binary), an optional `version_probe` (to confirm a specific capability, not
just the binary — e.g. the `docker compose` plugin), `required_when`
(`always` | `docker_artifacts_present` | `release_stage`), and per-OS `install`
commands. Adding a new required tool ("gh or anything required") is a registry entry,
not new code.

## Detection (`scripts/tool_preflight.py`)

Pure, never-raising detection: `shutil.which` plus the optional version probe, cached
to `.forge/tool-status.json` with a 24h TTL and a detached refresh — the same pattern
`hooks/_background_agent.py` already uses for the background-capability probe (T-138).
`required_when` is resolved against project state (`docker_artifacts_present` walks the
tree for Docker artifacts; `release_stage` reads `pipeline/state.md`'s
`current_stage`). The CLI (`check` / `install` / `refresh`) never runs an install
command — `install` only ever returns the resolved string.

## Surfacing

- **`hooks/session-start.py`** injects one advisory line per missing required tool,
  read from the cache with stdlib only. It is the first thing dropped under token
  pressure — ahead of lessons and rules — and stays silent when nothing is missing,
  outside a Forge project, or the cache is unreadable.
- **`scripts/doctor.py`** reports one `warn`-level result per missing required tool
  with the install command as the fix. Doctor stays read-only.

## Installing (`/forge:preflight`)

The **only** surface that runs an installer. It shows each missing required tool's
exact per-OS install command and runs it via Bash only after the user explicitly
confirms that specific tool. A declined tool is never installed.

## Docker Hygiene (`scripts/check_docker_readiness.py`)

Advisory only — it exits 0 whether or not Docker artifacts are present, and exits 0
even when it reports findings. Checks, per `Dockerfile` found: the base image is
pinned (a digest pin or a reference to an earlier build stage both count; an untagged
or `:latest` registry image doesn't), a `HEALTHCHECK` instruction is present, and the
last `USER` directive isn't root. Project-level: `.dockerignore` exists, and each
compose file parses with a top-level `services:` key.

`skills/forge-deploy/SKILL.md` runs this check **unconditionally** in pre-flight —
every project gets it, regardless of profile, since the check self-no-ops without
Docker artifacts. Findings are relayed as advisory `WARN:` notes; they never block
deployment.

## The `docker` Profile

An opt-in overlay (`references/project-type-profiles.md`, `## Profile: docker`) —
select it with `/forge:set-profile docker`, or accept the suggestion
`detect-project-type.py` offers when a project has Docker artifacts and no other
profile matched. **Never auto-assigned** over a real app type: a Dockerized FastAPI
service still classifies as `api` and still gets the cross-cutting hygiene check —
the profile only adds architecture/deploy emphasis and the `G8-DOCKER-001` advisory
criterion on top.

## Out of Scope

Running agents **inside** Docker containers (sandboxed execution — a separate,
larger track); auto-installing tools without confirmation; a mechanical/blocking
Docker gate in base `references/gate-criteria.md`; generating Dockerfiles/compose/CI
as Forge's mandatory deploy output.
