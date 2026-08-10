# Tool Registry (REQ-TR-001)

Declarative registry of external CLIs a Forge workflow may need. A new tool is a
**data entry** here, not new code — `scripts/tool_preflight.py` reads this file.

Fields per entry:

- `name` — the tool's identifier (used as the key everywhere: cache, CLI, criteria).
- `which` — the binary `shutil.which` looks up.
- `version_probe` (optional) — argv run to confirm the specific capability is present
  (not just the binary) and to read a version string; a non-zero exit means the
  probed capability is absent even if `which` found the binary (e.g. `docker` present
  but the `compose` plugin isn't).
- `workflows` — informal tags for which Forge workflows use this tool.
- `stages` — pipeline stage numbers where this tool matters.
- `required_when` — `always` | `docker_artifacts_present` | `release_stage`.
- `install` — per-OS (`darwin`/`linux`/`win32`) install command **string**. Surfaced,
  never executed except by `/forge:preflight` after explicit user confirmation.

Malformed or incomplete entries (missing `name`/`which`) are skipped, not fatal —
the registry never blocks detection of the entries that do parse.

```yaml
tools:
  - name: docker
    which: docker
    version_probe: ["docker", "--version"]
    workflows: [build, deploy]
    stages: [8]
    required_when: docker_artifacts_present
    install:
      darwin: "brew install --cask docker"
      linux: "curl -fsSL https://get.docker.com | sh"
      win32: "winget install Docker.DockerDesktop"

  - name: docker compose
    which: docker
    version_probe: ["docker", "compose", "version"]
    workflows: [build, deploy]
    stages: [8]
    required_when: docker_artifacts_present
    install:
      darwin: "brew install --cask docker"
      linux: "sudo apt-get install docker-compose-plugin"
      win32: "winget install Docker.DockerDesktop"

  - name: gh
    which: gh
    version_probe: ["gh", "--version"]
    workflows: [release]
    stages: [12]
    required_when: release_stage
    install:
      darwin: "brew install gh"
      linux: "sudo apt-get install gh"
      win32: "winget install GitHub.cli"
```
