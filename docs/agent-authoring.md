# Forge Extension Guide: Agents, Stages, and Profiles

This guide walks you through the three ways to extend Forge. Each section is
self-contained: you should be able to complete the task by following only these
instructions and reading the files referenced here.

---

## Table of Contents

1. [Adding an Agent Persona](#1-adding-an-agent-persona)
2. [Adding a Stage](#2-adding-a-stage)
3. [Adding a Project-Type Profile Override](#3-adding-a-project-type-profile-override)

---

## 1. Adding an Agent Persona

An **agent persona** is a Markdown file in `agents/` that gives Claude a
specific role, goal, and workflow for one part of the pipeline. Stage skills
invoke personas by reading their file, which causes Claude to adopt the described
behaviour for that step.

### 1.1 File format

Every persona lives at `agents/<role>.md` and has this structure:

```markdown
---
name: <role>
description: <one-sentence description of when to invoke this agent>.
  Use when <trigger conditions>. Produces <primary output>.
allowed-tools: [Read, Write, ...]
---

# <Role Title>

## Role

<Two or three sentences. Who is this agent? What domain experience do they have?>

## Goal

<One paragraph. What must this agent produce? What does success look like?>

## Context Scope

You read ONLY:
- <file or dir> — <why>
- ...

Do NOT read <out-of-scope files> — <reason>.

## Output Contract

You MUST produce:
- `<output path>` containing:
  - <required section or field>
  - ...

You MUST NOT:
- <anti-pattern>
- ...

## Workflow

1. <Step one>
2. <Step two>
...
```

**Rules:**
- `name` must match the filename without `.md`.
- `allowed-tools` is the set of Claude Code tools the agent may use.
  Keep it minimal — if a step doesn't need `Bash`, omit it.
- Context Scope must be explicit. Agents that read too broadly produce
  inconsistent output. List only the files the agent actually needs.
- Output Contract must be testable. "Writes a good document" is not a
  contract; "writes `pipeline/01-srs/srs.md` with REQ-NNN IDs" is.

### 1.2 Example: adding a "security-reviewer" agent

**Goal**: A Stage 3 agent that reviews architecture for OWASP Top 10 risks.

**Step 1 — Create the persona file**

`agents/security-reviewer.md`:

```markdown
---
name: security-reviewer
description: Stage 3 sub-agent. Reviews architecture decisions for OWASP Top 10
  risks and produces a threat model section. Use when running /forge:arch in
  projects with auth, external APIs, or user data. Produces
  pipeline/03-architecture/threat-model.md.
allowed-tools: [Read, Write, WebSearch]
---

# Security Reviewer

## Role

Application security engineer with deep knowledge of OWASP Top 10, threat
modelling (STRIDE), and secure-by-default architecture patterns. You review
designs before implementation, not after.

## Goal

Identify the top 3–5 security risks in the proposed architecture and produce
a concise threat model with mitigations the team can act on before Stage 4.

## Context Scope

You read ONLY:
- `pipeline/03-architecture/architecture.md` — the design under review
- `pipeline/01-srs/srs.md` — constraints and compliance requirements
- `pipeline/state.md` — project type and current stage

Do NOT read code, build artefacts, or later-stage documents.

## Output Contract

You MUST produce:
- `pipeline/03-architecture/threat-model.md` containing:
  - A STRIDE category table for each trust boundary in the architecture
  - Top risks ranked by likelihood × impact
  - One concrete mitigation per risk
  - An explicit "Out of scope" section for risks deferred to later stages

You MUST NOT:
- List more than 7 risks (focus forces action)
- Recommend specific third-party libraries unless widely adopted and maintained

## Workflow

1. Read `pipeline/03-architecture/architecture.md`.
2. Identify trust boundaries (client→server, server→DB, third-party APIs, auth flows).
3. Apply STRIDE per boundary. Note risks with likelihood (H/M/L) and impact (H/M/L).
4. Rank by likelihood × impact (HH first, LL last). Keep top 5.
5. Write one mitigation per risk (design-level, not implementation-level).
6. Write `pipeline/03-architecture/threat-model.md`.
```

**Step 2 — Wire into the stage skill**

Open `skills/forge-arch/SKILL.md` and add a step that invokes the new persona
when the project type warrants a security review:

```markdown
## Steps

...
4. Read `agents/system-architect.md` and adopt that persona.
   Follow the architect workflow. Apply any profile overrides from pre-flight.
5. If the project type is `api` or `fullstack` (check `pipeline/state.md`
   `project_type`), also read `agents/security-reviewer.md` and produce
   `pipeline/03-architecture/threat-model.md` before the gate check.
...
```

**Step 3 — Add gate criteria (optional)**

If the threat model should be a gate blocker, add to `references/gate-criteria.md`:

```yaml
## Stage 3: Architecture

stage: 3
name: architecture
criteria:
  ...
  - id: G3-005
    description: Threat model present for API and fullstack projects
    check: file_exists
    args: { path: "pipeline/03-architecture/threat-model.md" }
    severity: warning
```

**Step 4 — Write a structural test**

`tests/unit/test_security_reviewer.py`:

```python
from pathlib import Path
import re, pytest

AGENT_PATH = Path(__file__).parent.parent.parent / "agents" / "security-reviewer.md"

@pytest.fixture(scope="module")
def text():
    return AGENT_PATH.read_text(encoding="utf-8")

@pytest.fixture(scope="module")
def frontmatter(text):
    end = text.find("\n---\n", 4)
    block = text[4:end]
    out = {}
    for line in block.splitlines():
        m = re.match(r"^([a-z_-]+):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out

def test_file_exists():
    assert AGENT_PATH.exists()

def test_name_matches_filename(frontmatter):
    assert frontmatter["name"] == "security-reviewer"

def test_required_sections(text):
    for section in ["## Role", "## Goal", "## Context Scope",
                    "## Output Contract", "## Workflow"]:
        assert section in text

def test_output_contract_names_file(text):
    assert "pipeline/03-architecture/threat-model.md" in text
```

Run: `python3 -m pytest tests/unit/test_security_reviewer.py -v`

### 1.3 Verification checklist

- [ ] `agents/<role>.md` exists with valid frontmatter (`name`, `description`,
      `allowed-tools`)
- [ ] All five sections present: Role, Goal, Context Scope, Output Contract,
      Workflow
- [ ] Output Contract names the exact file path the agent writes
- [ ] The invoking stage skill has a step that reads the persona file
- [ ] A structural test asserts the frontmatter contract
- [ ] `python3 -m pytest tests/ -q` passes

---

## 2. Adding a Stage

A **stage** is a numbered step in the 12-stage pipeline. Each stage has:

| Component | Location | Purpose |
|-----------|----------|---------|
| Skill file | `skills/forge-<name>/SKILL.md` | The `/forge:<name>` slash command |
| Gate criteria | `references/gate-criteria.md` | Exit criteria checked before advancing |
| Agent persona | `agents/<role>.md` | Optional; the persona the skill invokes |
| Profile overrides | `references/project-type-profiles.md` | Project-type-specific adjustments |

Forge's 12 built-in stages are numbered 1–12. Adding a **custom stage** means
adding a named skill that fits into that sequence (or extends beyond 12 for
specialist workflows). This walkthrough shows how to add a new stage 2.5 —
"UX Research" — inserted between Stage 2 (Product) and Stage 3 (Architecture).

### 2.1 Create the skill file

Skills are auto-discovered via the `skills/*` glob in `.claude-plugin/plugin.json`.
Create the directory and file:

```
skills/forge-ux-research/SKILL.md
```

**Frontmatter** (required fields):

```yaml
---
name: forge-ux-research
description: Run UX Research analysis between product definition and architecture.
  Use when the user says /forge:ux-research, wants to validate user journeys,
  or needs a usability risk assessment before committing to an architecture.
  Produces pipeline/02-product/ux-research.md.
allowed-tools: [Read, Write, WebSearch, Bash]
---
```

**Rules for `name`**: must match the directory name (`forge-ux-research`). This
is what the user types as the slash command (`/forge:ux-research`).

**Full SKILL.md template:**

```markdown
---
name: forge-ux-research
description: <one to two sentences. When does the user invoke this? What does it produce?>
allowed-tools: [Read, Write, Bash]
---

# /forge:ux-research — UX Research

## When to Use

- User runs `/forge:ux-research`
- Stage 2 (Product) is complete and architecture hasn't started yet
- User wants to validate user journeys before committing to a design

## Pre-flight

1. Read `pipeline/state.md` — confirm `current_stage` is 2 or higher.
2. Run the profile loader:
   ```bash
   python3 ${CLAUDE_PLUGIN_DIR}/scripts/load-profile.py --cwd . --stage 2
   ```
   Apply any `replace_with`, `skip`, or `additional_concerns` overrides.

## Steps

1. Read `agents/ux-researcher.md` to load the UX Researcher persona.
2. Adopt that persona.
3. Read `pipeline/02-product/product.md` for the product definition.
4. Identify top 3 user journeys. For each journey, assess:
   - Where users are most likely to drop off or make errors
   - Accessibility risks
   - Cognitive load at decision points
5. Write `pipeline/02-product/ux-research.md` per the Output Contract.
6. Run the gate check:
   ```bash
   python3 ${CLAUDE_PLUGIN_DIR}/scripts/check-gate.py --stage 2 --cwd .
   ```

## Verification

After running, confirm:
- `pipeline/02-product/ux-research.md` exists with at least 3 journey assessments
- Gate check exits 0 (or surfaces only warnings, not blockers)

## Next Step

"UX Research written. Run `/forge:arch` when ready to design the architecture."
```

### 2.2 Add gate criteria

Open `references/gate-criteria.md`. Find the stage block where your stage fits
and append a new `## Stage N: <name>` block (or add criteria to an existing
block):

```yaml
## Stage 2.5: UX Research

stage: 2
name: ux-research
criteria:
  - id: G2R-001
    description: UX research document exists
    check: file_exists
    args: { path: "pipeline/02-product/ux-research.md" }
    severity: blocker

  - id: G2R-002
    description: At least one user journey documented
    check: file_contains
    args:
      path: "pipeline/02-product/ux-research.md"
      pattern: "(?i)journey"
      min_matches: 1
    severity: blocker

  - id: G2R-003
    description: Accessibility risks addressed
    check: file_contains
    args:
      path: "pipeline/02-product/ux-research.md"
      pattern: "(?i)accessibilit"
      min_matches: 1
    severity: warning
```

**Check types supported by `check-gate.py`:**

| Type | Description | Required args |
|------|-------------|---------------|
| `file_exists` | Path must exist | `path` |
| `file_contains` | Regex match in file | `path`, `pattern`, `min_matches` |
| `script_returns_zero` | Helper script exits 0 | `script`, `argv` |
| `all_tests_pass` | `pytest` passes | `path` (test dir) |

**Severity:**
- `blocker` — prevents stage advancement
- `warning` — surfaced to the user but does not block

### 2.3 Create the agent persona (if needed)

If your stage has complex reasoning, give it a dedicated persona. Follow the
steps in §1 above. Otherwise, the skill can invoke an existing persona (e.g.,
the `system-architect` persona can be borrowed for quick analysis tasks).

### 2.4 Wire profile overrides (optional)

If any project type should behave differently in this stage, add a `stage_N`
key to the relevant profile in `references/project-type-profiles.md`:

```yaml
## Profile: fullstack

...
  stage_2:
    additional_concerns:
      - "Server-side rendering vs SPA trade-offs"
      - "Auth UX flow (session vs token)"
    stage_emphasis: high
```

Verify the YAML parses:

```bash
python3 scripts/load-profile.py \
  --cwd . \
  --stage 2 \
  --profiles-file references/project-type-profiles.md
```

The command prints the merged profile as Markdown. If the profile block has a
YAML syntax error, it will print a parse error and exit non-zero.

### 2.5 Write tests

**Structural test for the skill file** — assert the contract is intact:

```python
# tests/unit/test_forge_ux_research.py
from pathlib import Path
import re, pytest

SKILL_PATH = (Path(__file__).parent.parent.parent
              / "skills" / "forge-ux-research" / "SKILL.md")

@pytest.fixture(scope="module")
def text():
    return SKILL_PATH.read_text(encoding="utf-8")

@pytest.fixture(scope="module")
def frontmatter(text):
    end = text.find("\n---\n", 4)
    block = text[4:end]
    out = {}
    for line in block.splitlines():
        m = re.match(r"^([a-z_-]+):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out

def test_file_exists():
    assert SKILL_PATH.exists()

def test_name(frontmatter):
    assert frontmatter["name"] == "forge-ux-research"

def test_directory_name_matches(text):
    assert SKILL_PATH.parent.name == "forge-ux-research"

@pytest.mark.parametrize("section", [
    "## When to Use", "## Pre-flight", "## Steps", "## Verification",
])
def test_required_sections(text, section):
    assert section in text

def test_output_path_documented(text):
    assert "pipeline/02-product/ux-research.md" in text

def test_calls_load_profile(text):
    assert "load-profile.py" in text
```

Run: `python3 -m pytest tests/unit/test_forge_ux_research.py -v`

### 2.6 Verification checklist

- [ ] `skills/forge-<name>/SKILL.md` exists
- [ ] Frontmatter: `name` matches directory, `description` and `allowed-tools` set
- [ ] Sections: When to Use, Pre-flight (calls `load-profile.py`), Steps,
      Verification, Next Step
- [ ] Steps include agent persona invocation or inline reasoning
- [ ] Gate criteria block added to `references/gate-criteria.md`
- [ ] Profile overrides added (if relevant) and verified with `load-profile.py`
- [ ] Structural test added to `tests/unit/`
- [ ] `python3 -m pytest tests/ -q` passes
- [ ] `python3 scripts/validate-plugin.py` exits 0

---

## 3. Adding a Project-Type Profile Override

A **profile** adjusts how every stage behaves for a specific project type
(api, fullstack, ml-pipeline, cli, library). Overrides are layered on top of
the base stage definition — they add or replace, they don't delete.

### 3.1 Override schema

Each stage override lives under `stage_N:` inside a profile block:

```yaml
## Profile: <type>

```yaml
name: <type>
description: <one-sentence description>

stage_emphasis:
  high: [<stage-name>, ...]   # agent spends extra attention here
  low:  [<stage-name>, ...]

stage_1:
  additional_concerns:
    - "Extra concern surfaced to the agent at Stage 1"
  additional_criteria:
    - id: G1-ML-001
      description: <description>
      check: file_exists
      args: { path: "pipeline/01-srs/ml-constraints.md" }
      severity: blocker

stage_7:
  skip: false
  replace_with: null
  additional_artifacts:
    - "models/evaluation-report.md"
  additional_concerns:
    - "Drift detection strategy documented"
  additional_criteria:
    - id: G7-ML-005
      description: Drift detection strategy documented
      check: file_contains
      args:
        path: "pipeline/07-evaluation/eval-report.md"
        pattern: "(?i)drift"
        min_matches: 1
      severity: warning
  stage_emphasis: high
```
```

**Override keys:**

| Key | Effect |
|-----|--------|
| `additional_concerns` | Extra bullet points surfaced to the agent |
| `additional_criteria` | Extra gate criteria evaluated with `check-gate.py` |
| `additional_artifacts` | Extra output files the agent must produce |
| `stage_emphasis` | `high` / `low` — signals relative importance to the agent |
| `skip` | `true` — skip this stage entirely for this project type |
| `replace_with` | Name of an alternative skill to run instead |

### 3.2 Example: add a "data-contract" gate to the API profile at Stage 1

**Goal**: API projects must document their external data contracts in the SRS.

Open `references/project-type-profiles.md`, find `## Profile: api`, and add:

```yaml
  stage_1:
    additional_concerns:
      - "External data contracts (request/response schemas) documented in SRS"
      - "Rate limiting and pagination strategy present as NFR"
    additional_criteria:
      - id: G1-API-001
        description: API contract section present in SRS
        check: file_contains
        args:
          path: "pipeline/01-srs/srs.md"
          pattern: "(?i)api contract|data contract|openapi|swagger"
          min_matches: 1
        severity: warning
```

### 3.3 Verify the override loads

```bash
python3 scripts/load-profile.py \
  --cwd . \
  --stage 1 \
  --profiles-file references/project-type-profiles.md \
  --format markdown
```

The output should include your new concern under "Additional Concerns" and your
new criterion under "Additional Gate Criteria". If the YAML block has an error,
`load-profile.py` exits non-zero and prints the parse failure.

You can also run the full test suite — `test_load_profile.py` asserts that all
five required profiles parse with at least 3 stage overrides each.

### 3.4 Write a test

```python
# tests/unit/test_api_profile_stage1.py
import subprocess, json, sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent.parent.parent
SCRIPT = PLUGIN_DIR / "scripts" / "load-profile.py"
PROFILES = PLUGIN_DIR / "references" / "project-type-profiles.md"

def _load(stage: int, project_type: str) -> dict:
    env = {"project_type": project_type}  # load-profile.py reads pipeline/state.md;
    # for testing, write a temporary state.md or use --profiles-file only.
    # Simplest: assert the profiles file parses without error.
    result = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--cwd", str(PLUGIN_DIR),
         "--stage", str(stage),
         "--profiles-file", str(PROFILES),
         "--format", "json"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)

def test_api_stage1_additional_concern():
    data = _load(1, "api")
    concerns = " ".join(data.get("additional_concerns", []))
    assert "data contract" in concerns.lower() or "api contract" in concerns.lower()
```

### 3.5 Verification checklist

- [ ] Profile block exists in `references/project-type-profiles.md`
- [ ] YAML inside the code fence parses cleanly (run `load-profile.py`)
- [ ] Override is applied at the correct `stage_N` key
- [ ] `additional_criteria` IDs follow the `G<N>-<TYPE>-<NNN>` convention
- [ ] Test asserts the concern or criterion is surfaced
- [ ] `python3 -m pytest tests/ -q` passes

---

## Quick Reference

| Task | Key file | Verification command |
|------|----------|----------------------|
| Add agent | `agents/<role>.md` | Structural test in `tests/unit/` |
| Add stage skill | `skills/forge-<name>/SKILL.md` | `validate-plugin.py` + structural test |
| Add gate criteria | `references/gate-criteria.md` | `check-gate.py --stage N --cwd .` |
| Add profile override | `references/project-type-profiles.md` | `load-profile.py --stage N` |
| Add hook | `hooks/<event>.py` + `plugin.json` | `validate-plugin.py` |

Any question not answered here: read `CLAUDE.md` (development operating manual)
or `build/02-architecture/architecture.md` (design rationale).
