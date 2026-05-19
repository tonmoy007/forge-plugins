# T-002: forge-init Skill

## Context

T-001 created the plugin scaffolding. Now we need the first user-facing command:
`/forge:init` — which scaffolds a Forge-managed pipeline in a target project.

Read before starting:
- `build/01-srs/srs.md` REQ-001, REQ-002, REQ-060
- `build/02-architecture/architecture.md` §3 (data flow) and §4 (memory architecture)
- `build/03-spec/technical-spec.md` §4 (skill file contracts)
- `tasks/lessons.md` if any lessons exist from T-001

A skill in Claude Code is a folder with `SKILL.md`. The folder name becomes the slash command
(folder `forge-init/` → `/forge:init` because of the `forge-` prefix convention).

## Task

Create the `/forge:init` command that scaffolds a Forge pipeline in any project.

**Files to create**:

1. **`skills/forge-init/SKILL.md`** — the skill definition:
   - Frontmatter with `name`, `description` (pushy phrasing for triggering)
   - `allowed-tools: [Read, Write, Bash, Glob]`
   - Description must mention: "Use whenever a user wants to start using Forge in a project,
     or mentions 'init', 'initialize', 'set up Forge', or describes starting a new project
     they want orchestrated."
   - Body instructs Claude to:
     1. Run `bash ${CLAUDE_PLUGIN_ROOT}/scripts/init-pipeline.sh` to create directory structure
     2. Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/detect-project-type.py` to identify the type
     3. Write the initial `pipeline/state.md` with detected type
     4. Print a welcome message confirming what was created
     5. Suggest the next command (`/forge:srs` or `/forge:resume`)

2. **`scripts/init-pipeline.sh`** — bash script that creates:
   ```
   pipeline/
   ├── state.md (with default frontmatter)
   ├── 01-srs/
   ├── 02-product-ux/wireframes/
   ├── 03-architecture/adr/
   ├── 04-spec/
   ├── 05-plan/
   ├── 06-implementation/
   ├── 07-evaluation/
   ├── 08-deploy/
   ├── 09-monitor/
   ├── 10-feedback/
   ├── 11-resolve/
   └── 12-release/
   tasks/
   ├── todo.md (empty template)
   └── lessons.md (empty template)
   .forge/
   ├── lessons.yaml (schema_version: 1, lessons: [])
   ├── patterns.jsonl (empty)
   └── sessions/
   ```
   - Idempotent: re-running doesn't overwrite existing files
   - Creates `.gitkeep` in empty dirs
   - Outputs created paths to stdout for verification

3. **`scripts/detect-project-type.py`** (basic version — full impl is T-023):
   - Detects from file presence:
     - `package.json` + `next.config.*` → fullstack
     - `package.json` only → fullstack (default)
     - `requirements.txt`/`pyproject.toml` with `torch|transformers|tensorflow` → ml-pipeline
     - `Cargo.toml` or `go.mod` with `cli` patterns → cli
     - Setup.py/pyproject without app entry point → library
     - Nothing matches → unknown (user picks)
   - Output: JSON `{"type": "fullstack", "confidence": 0.8, "indicators": ["..."]}`
   - Use stdlib only

4. **`tests/unit/test_init_pipeline.py`** — tests for init-pipeline.sh:
   - Run on empty dir → all dirs created
   - Run twice on same dir → idempotent (no errors, no overwrites)
   - Run on dir with existing files → don't overwrite

5. **`tests/unit/test_detect_project_type.py`** — tests for type detection:
   - Empty dir → unknown
   - Dir with package.json → fullstack
   - Dir with torch in requirements → ml-pipeline

## Definition of Done

- [ ] `skills/forge-init/SKILL.md` exists with valid frontmatter
- [ ] `scripts/init-pipeline.sh` creates the full directory structure
- [ ] `scripts/detect-project-type.py` correctly identifies at least 3 project types
- [ ] Both scripts have unit tests that pass
- [ ] Running `bash scripts/init-pipeline.sh` in `/tmp/test-forge` creates all expected dirs
- [ ] `pipeline/state.md` is created with valid YAML frontmatter (matches architecture.md §4.2 schema)

## Verification

```bash
# 1. Skill validates
python scripts/validate-plugin.py  # should still pass after adding skill

# 2. Init script works in fresh dir
mkdir -p /tmp/test-forge && cd /tmp/test-forge
bash $OLDPWD/scripts/init-pipeline.sh
ls -la pipeline/ tasks/ .forge/
cat pipeline/state.md

# 3. Idempotent
bash $OLDPWD/scripts/init-pipeline.sh   # should not error or overwrite
diff <(cat pipeline/state.md) <(cat pipeline/state.md)  # nothing should have changed

# 4. Type detection
echo '{}' > /tmp/test-forge/package.json
python $OLDPWD/scripts/detect-project-type.py --cwd /tmp/test-forge
# Expect: {"type": "fullstack", ...}

# 5. Tests pass
cd $OLDPWD
pytest tests/unit/test_init_pipeline.py tests/unit/test_detect_project_type.py -v

# Cleanup
rm -rf /tmp/test-forge
```

## Commit

```
feat(T-002): forge-init skill scaffolds pipeline

- skills/forge-init/SKILL.md
- scripts/init-pipeline.sh (idempotent directory creation)
- scripts/detect-project-type.py (basic detection)
- Unit tests for both scripts

Ref: T-002
REQ: REQ-001, REQ-002, REQ-060
```

## Update Trail

1. `build/05-implementation/progress.md`: mark T-002 done, set current to T-003
2. `tasks/todo.md`: archive T-002, activate T-003
3. Lessons if anything surprising
4. Decisions log if you made non-obvious choices (e.g., where exactly state.md lives, what default frontmatter to use)

## Notes

- The full project type detection is T-023; here we just need basic detection.
- `state.md` initial content should leave `current_stage: 0` (not started) and empty history.
- The skill should NOT advance to Stage 1 — that's `/forge:srs`'s job.
