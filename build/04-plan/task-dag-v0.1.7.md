# Task DAG — Forge v0.1.7

> Scope locked 2026-06-09 (`build/01-srs/srs-v0.1.7.md` §6). 5 tasks across
> 2 milestones. Numbering continues from v0.1.6 (T-126..T-130); v0.1.7 is
> T-131..T-135.
>
> Format: `T-NNN [size] title`
> Size: S (small, ~30min), M (medium, ~2hr), L (large, ~half-day)
>
> **Theme**: three more project-type profiles — monorepo, mobile, data-contract —
> each with a real, deterministic gate executable.
>
> **Build order — SERIAL (not a fan-out).** T-131/132/133 all edit the SAME three
> shared files (`references/project-type-profiles.md`,
> `scripts/detect-project-type.py`, `tests/unit/test_detect_project_type.py`) and
> share one ordered `detect()` function, so they build one at a time in
> precedence order (each new gate script + its test ARE disjoint new files, but the
> shared detection trio forces serial). Keep the whole suite green after each task.

---

## Milestone 1: New profiles + gates (serial, in detection-precedence order)

> Detection precedence (OQ-1): **monorepo → mobile → data-contract →** existing
> checks. Each gate wires into its profile's `additional_criteria` as
> `check: script_returns_zero, args: { script: "scripts/<gate>.py" }`, and each new
> `scripts/check_*.py` must satisfy the runnable + has-tests meta-gates
> (NFR-GATEHYGIENE-001), stdlib-only with `main(argv) -> int`.

### T-131 [L] monorepo profile + dependency-graph gate
- **Description**: Add the `monorepo` profile + detection + gate.
  - **Detection** (specific — must not steal `fullstack`/`api`): any of
    `pnpm-workspace.yaml`, `lerna.json`, `turbo.json`, `nx.json`, a `workspaces`
    field in `package.json`, `[workspace]` in `Cargo.toml`, or `packages/`+`apps/`
    together. Insert at the TOP of `detect()`.
  - **Profile**: emphasize architecture + plan; stage_3 concerns (package
    boundaries/ownership, shared-dependency strategy, build orchestration, fixed
    vs independent versioning, circular-dep prevention); a `stage_7`
    `additional_criteria` G7-MONO-001 wired to `check_monorepo_graph.py`.
  - **Gate** `scripts/check_monorepo_graph.py`: discover internal workspace
    packages (package.json under `packages/`/`apps/` or pnpm-workspace globs),
    build the internal name→deps graph, DFS for a cycle; exit 1 naming the cycle,
    0 if acyclic / no packages. `--cwd` optional.
- **Files**: `references/project-type-profiles.md`, `scripts/detect-project-type.py`,
  `scripts/check_monorepo_graph.py` (new), `tests/unit/test_detect_project_type.py`,
  `tests/unit/test_check_monorepo_graph.py` (new)
- **Done when**: AC-MONOREPO-001a/b/c — workspace fixtures classify `monorepo`
  (precedence over contained fullstack/api); profile parses with the wired
  criterion; gate exits 0 acyclic / 1 on a cycle; meta-gates pass; existing
  detection tests still green.
- **Depends on**: none
- **REQ-IDs**: REQ-PROFILE-MONOREPO-001

### T-132 [L] mobile profile + store-readiness gate
- **Description**: Add the `mobile` profile + detection + gate.
  - **Detection**: `pubspec.yaml` (Flutter), `Podfile`/`*.xcodeproj`/`*.xcworkspace`
    (iOS), `android/`+`build.gradle` (Android), or `react-native` in `package.json`.
    Below monorepo, **above** fullstack/api (RN must not be `fullstack`).
  - **Profile**: product-ux high; stage_2 `design_system_mode: full` + platform-UX
    concerns (touch targets, offline/empty states, platform HIG/Material); stage_3
    concerns (offline sync, push, deep links, state restoration); a release-stage
    `additional_criteria` G12-MOBILE-001 wired to `check_store_readiness.py`.
  - **Gate** `scripts/check_store_readiness.py`: for the detected platform(s),
    require store metadata — iOS Info.plist `CFBundleIdentifier`+
    `CFBundleShortVersionString`; Android `applicationId`+`versionCode`+
    `versionName` in build.gradle; Flutter `version` in pubspec. Exit 1 listing
    missing items, 0 when present. `--cwd` optional.
- **Files**: `references/project-type-profiles.md`, `scripts/detect-project-type.py`,
  `scripts/check_store_readiness.py` (new), `tests/unit/test_detect_project_type.py`,
  `tests/unit/test_check_store_readiness.py` (new)
- **Done when**: AC-MOBILE-001a/b/c — Flutter/iOS/Android/RN classify `mobile`; RN
  not `fullstack`; profile parses with wired criterion; gate exits 0/1 on
  present/missing metadata; meta-gates pass; existing tests green.
- **Depends on**: T-131 (shared detection trio; serial)
- **REQ-IDs**: REQ-PROFILE-MOBILE-001

### T-133 [L] data-contract profile + schema-hygiene gate
- **Description**: Add the `data-contract` profile + detection + gate.
  - **Detection**: `.proto`, `.avsc`, `buf.yaml`, `dbt_project.yml`, a
    `schemas/`/`contracts/` dir, or `.graphql` SDL — with no application entry
    point. Below mobile, **above** api/library (schema-first beats api).
  - **Profile**: emphasize spec + architecture + evaluation; de-emphasize
    product-ux; stage_4 schema-definition emphasis; stage_7 `additional_criteria`
    G7-DC-001 wired to `check_schema_compat.py`; a compatibility-matrix
    `additional_artifact`.
  - **Gate** `scripts/check_schema_compat.py` (HYGIENE + POLICY, not a semantic
    version diff — state this in the docstring AND the criterion description):
    fail on a `.proto` with duplicate field numbers within a message, or a deleted
    field with no `reserved` range, or a `buf.yaml` lacking a breaking-change
    policy; exit 0 on clean schemas. `--cwd` optional.
- **Files**: `references/project-type-profiles.md`, `scripts/detect-project-type.py`,
  `scripts/check_schema_compat.py` (new), `tests/unit/test_detect_project_type.py`,
  `tests/unit/test_check_schema_compat.py` (new)
- **Done when**: AC-DATACONTRACT-001a/b/c — `.proto`/`schemas/` classify
  `data-contract` (not api/library); profile parses with wired criterion; gate
  exits 1 on a duplicate field number / 0 on clean; docstring states the limit;
  meta-gates pass; existing tests green.
- **Depends on**: T-132 (shared detection trio; serial)
- **REQ-IDs**: REQ-PROFILE-DATACONTRACT-001

---

## Milestone 2: Wiring + release

### T-134 [S] Profile parity + doc sync + tracking
- **Description**: Extend `test_load_profile.py`'s parametrized parity test to all
  8 named profiles (+ monorepo/mobile/data-contract). Confirm the Detection
  Heuristics YAML block in `project-type-profiles.md` lists the 3 new types
  consistently with the code. Update README's profile list if it enumerates
  profiles. Update `build/05-implementation/progress.md` (T-131..T-135) and
  `ROADMAP.md` (v0.1.7).
- **Files**: `tests/unit/test_load_profile.py`, `references/project-type-profiles.md`
  (doc-block only), `README.md` (if it lists profiles),
  `build/05-implementation/progress.md`, `ROADMAP.md`
- **Done when**: parity test enumerates all 8 profiles and passes; docs name the 3
  new profiles; progress + roadmap reflect v0.1.7; full suite green.
- **Depends on**: T-131, T-132, T-133
- **REQ-IDs**: NFR-GENERIC-001, NFR-NOREGRESS-001

### T-135 [S] Release v0.1.7 — version bump + CHANGELOG
- **Description**: `scripts/bump-version.py 0.1.7` (both manifests + CHANGELOG
  skeleton), fill the `## [0.1.7]` section (3 profiles + 3 gates), run full
  pre-release verification. PR→develop→main→tag→mirror follows interactively.
- **Files**: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `CHANGELOG.md`
- **Done when**: both manifests at `0.1.7`; CHANGELOG `## [0.1.7]` on top;
  `pytest tests/ -q` green, `validate-plugin.py` exit 0, `full-pipeline.sh` 12/12.
- **Depends on**: T-134
- **REQ-IDs**: —

---

## Dependency graph

```
T-131 → T-132 → T-133 → T-134 → T-135      (fully serial — shared detection trio)
```
