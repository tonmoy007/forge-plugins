---
name: forge-release
description: Run Stage 12 of the Forge pipeline — release preparation. Use when the
  user says /forge:release, wants to cut a version, write a changelog, or prepare
  release notes. Requires Stage 11 or passing eval. Invokes the release-manager persona.
allowed-tools: [Read, Write, Bash]
---

# /forge:release — Release

## When to Use

- User says `/forge:release`
- User wants to cut a release, bump the version, write a changelog, or prepare release notes
- Working in a Forge project at Stage 11 or 12

## Pre-flight Check

1. Read `pipeline/state.md` — confirm Forge project.
2. Confirm `pipeline/07-evaluation/eval-report.md` exists and shows overall pass.
   If not: "A passing evaluation (Stage 7) is required before cutting a release."
3. Check that no critical or high-severity items from triage remain unresolved.
4. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/load-profile.py --cwd . --stage 12` to load project-type release criteria. For library projects this surfaces G12-LIB-001 (Keep a Changelog format), G12-LIB-002 (semver enforced — breaking changes → major bump), and G12-LIB-003 (migration guide for breaking changes) — all must be addressed in the release artifacts.

## Steps

1. Read `agents/release-manager.md` to load the Release Manager persona.
2. Adopt that persona — you are now the Release Manager.
3. Run `git log` via Bash to enumerate commits since the last release tag.
4. Follow the Release Manager workflow: classify changes, determine version bump, write changelog and release notes. Address every profile `additional_criteria` from pre-flight as a deliverable.
5. Write `pipeline/12-release/CHANGELOG.md` and `pipeline/12-release/release-notes.md` (plus a migration guide when the profile requires it).
6. Bump version fields in the project's version files (package.json, pyproject.toml, etc.).
7. Write `pipeline/12-release/post-release-checklist.md`.
8. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state-manager.py advance --to 12` to mark Stage 12 active.

## Verification

After running, confirm:
- `pipeline/12-release/CHANGELOG.md` exists with semantic version and categorized changes
- `pipeline/12-release/release-notes.md` exists (user-facing language)
- Version bumped consistently across all version files
- `pipeline/state.md` shows `current_stage: 12`

## Next Step

"Release prepared. Tag the commit (`git tag v[X.Y.Z]`) and push to ship."
