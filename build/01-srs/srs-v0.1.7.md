# SRS — Forge v0.1.7 (delta, locked)

> **Status**: **Scope locked 2026-06-09.** Composes with `srs.md`, `srs-v0.1.3.md`,
> `srs-v0.1.4.md`, `srs-v0.1.5.md`, `srs-v0.1.6.md`. Implements the
> "Additional project-type profiles" backlog item from `[Unreleased]`, **with real
> gate scripts** for each new profile's headline criterion.
>
> **Theme**: "Three more project-type profiles, each with a working gate." Forge
> ships 7 profiles today (api, fullstack, ml-pipeline, cli, library, script,
> unknown). This release adds **data-contract**, **mobile**, and **monorepo** —
> each a profile definition + auto-detection + a deterministic gate executable +
> tests. No new pipeline stages; profiles load generically through the existing
> `load-profile.py`, and the gates run through the existing `check-gate.py`
> `script_returns_zero` mechanism.

---

## 1. Scope

**In scope (firm)**:

- **data-contract** profile — schema-first projects (Protobuf / Avro / JSON
  Schema / GraphQL SDL / dbt) where the deliverable is data contracts, not a UI
  or a running service (REQ-PROFILE-DATACONTRACT-001).
- **mobile** profile — iOS / Android / React Native / Flutter apps
  (REQ-PROFILE-MOBILE-001).
- **monorepo** profile — multi-package workspaces (pnpm/yarn/npm workspaces,
  Nx, Turborepo, Lerna, Cargo workspace) (REQ-PROFILE-MONOREPO-001).
- Each profile ships: a `## Profile: <name>` block in
  `references/project-type-profiles.md` (stage_emphasis + stage_overrides +
  `additional_criteria` wired to its gate), a Detection Heuristics entry, a
  detection branch in `scripts/detect-project-type.py`, **a gate executable in
  `scripts/`**, and tests for both detection and the gate.
- Wiring: extend the `test_load_profile.py` parity test to all profiles; keep the
  Detection Heuristics doc block in sync with the code; progress/roadmap; release.

**Gate scripts (firm scope + honest limits)**:

- `check_monorepo_graph.py` — builds the **internal** package dependency graph
  (workspace packages referencing each other) and fails on a cycle. Real and
  deterministic (stdlib).
- `check_store_readiness.py` — fails if the detected mobile platform is missing
  required store metadata (iOS `CFBundleIdentifier`+version; Android
  `applicationId`+`versionCode`+`versionName`; Flutter `version`). Presence/field
  checks, deterministic.
- `check_schema_compat.py` — **schema hygiene + policy**, not a full cross-version
  semantic differ (true backward-compat needs the prior schema version, which a
  stdlib gate can't fetch). Fails on within-file hazards (duplicate Protobuf field
  numbers in a message; deleted fields without a `reserved` range) and on a
  missing compatibility policy when `buf.yaml` is present. This limit is stated in
  the script docstring and the profile criterion description.

**Out of scope (firm)**:

- Full semantic schema diffing against a prior version (see limit above).
- Runtime profile switching (`forge:set-profile`) — separate backlog item.
- Any change to the 7 existing profiles' behavior (no regressions).

---

## 2. Requirements

### REQ-PROFILE-MONOREPO-001 — monorepo profile + dependency-graph gate

**Trigger**: `/forge:init` on a multi-package workspace: `pnpm-workspace.yaml`,
`lerna.json`, `turbo.json`, `nx.json`, a `workspaces` field in `package.json`,
`[workspace]` in `Cargo.toml`, or `packages/` + `apps/` together.

**Behavior**: Detected as `monorepo` **before** single-package signals (it wraps
them); the profile emphasizes architecture + planning, adds package-boundary /
shared-dependency / build-orchestration / versioning concerns, and an evaluation
criterion that runs `check_monorepo_graph.py`.

**Acceptance**:
- **AC-MONOREPO-001a** — `detect()` returns `type == "monorepo"` for a fixture
  with a workspace marker, taking precedence over the `fullstack`/`api` it contains.
- **AC-MONOREPO-001b** — a `## Profile: monorepo` block exists, parses via
  `load-profile.py`, has `stage_emphasis` and an `additional_criteria` entry whose
  `args.script` is `scripts/check_monorepo_graph.py`.
- **AC-MONOREPO-001c** — `check_monorepo_graph.py` exits 0 on an acyclic workspace
  fixture and 1 (naming the cycle) on a fixture with a circular internal
  dependency; it has unit tests and is import/runnable-clean.

### REQ-PROFILE-MOBILE-001 — mobile profile + store-readiness gate

**Trigger**: `/forge:init` on a mobile app repo: `pubspec.yaml` (Flutter),
`Podfile`/`*.xcodeproj`/`*.xcworkspace` (iOS), `android/` + `build.gradle`
(Android), or `react-native` in `package.json`.

**Behavior**: Detected as `mobile`; the profile keeps product-ux high, sets a full
design-system mode with platform-UX concerns (touch targets, offline states),
adds architecture concerns (offline sync, push, deep links), and a release
criterion that runs `check_store_readiness.py`.

**Acceptance**:
- **AC-MOBILE-001a** — `detect()` returns `type == "mobile"` for Flutter
  (`pubspec.yaml`+`lib/`), iOS (`Podfile`/`.xcodeproj`), Android
  (`android/`+`build.gradle`), or React Native (`react-native` dep) fixtures, and
  **does not** misclassify a React Native repo as `fullstack`.
- **AC-MOBILE-001b** — a `## Profile: mobile` block exists, parses, keeps
  product-ux in `stage_emphasis.high`, has a platform-UX `stage_2` override, and an
  `additional_criteria` entry wired to `scripts/check_store_readiness.py`.
- **AC-MOBILE-001c** — `check_store_readiness.py` exits 0 when the detected
  platform has its required store metadata and 1 (listing what's missing)
  otherwise; it has unit tests and is import/runnable-clean.

### REQ-PROFILE-DATACONTRACT-001 — data-contract profile + schema-hygiene gate

**Trigger**: `/forge:init` on a schema-first repo (`.proto`, `.avsc`, `buf.yaml`,
`dbt_project.yml`, a `schemas/`/`contracts/` dir, or `.graphql` SDL) with no
application entry point.

**Behavior**: Detected as `data-contract` (before api/library); the profile
emphasizes spec + architecture + evaluation, de-emphasizes product-ux, adds
schema compatibility/versioning concerns, and an evaluation criterion that runs
`check_schema_compat.py`.

**Acceptance**:
- **AC-DATACONTRACT-001a** — `detect()` returns `type == "data-contract"` for a
  fixture carrying a primary schema signal (e.g. a `.proto` file or `schemas/`
  dir) and no server/UI manifest; it is not classified `api`/`library`.
- **AC-DATACONTRACT-001b** — a `## Profile: data-contract` block exists, parses,
  has `stage_emphasis` and an `additional_criteria` entry wired to
  `scripts/check_schema_compat.py`.
- **AC-DATACONTRACT-001c** — `check_schema_compat.py` exits 1 on a `.proto` with a
  duplicate field number (or a deleted field lacking `reserved`, or a `buf.yaml`
  with no breaking-change policy) and 0 on a clean schema; the docstring + the
  profile criterion state it is hygiene + policy, not a semantic version diff. It
  has unit tests and is import/runnable-clean.

---

## 3. Non-functional

- **NFR-NOREGRESS-001**: the 7 existing profiles' detection is unchanged — every
  pre-existing `test_detect_project_type.py` and `test_load_profile.py` case stays
  green. New detection branches must be specific enough not to steal existing
  fixtures.
- **NFR-GENERIC-001**: profiles remain data-only (markdown). No new per-profile
  code paths in skills; `load-profile.py` loads the new profiles unmodified.
- **NFR-GATEHYGIENE-001**: each new `scripts/check_*.py` satisfies the existing
  meta-gates — has a unit test (`check-script-has-tests.py`) and is runnable
  (`check-script-runnable.py`), stdlib-only.

---

## 4. Traceability

| REQ-ID                       | Task  | Gate script | Test |
|------------------------------|-------|-------------|------|
| REQ-PROFILE-MONOREPO-001     | T-131 | check_monorepo_graph.py | test_detect_project_type.py, test_check_monorepo_graph.py |
| REQ-PROFILE-MOBILE-001       | T-132 | check_store_readiness.py | test_detect_project_type.py, test_check_store_readiness.py |
| REQ-PROFILE-DATACONTRACT-001 | T-133 | check_schema_compat.py | test_detect_project_type.py, test_check_schema_compat.py |
| NFR-NOREGRESS-001            | T-131..T-134 | — | existing detection + load-profile suites green |
| NFR-GENERIC-001             | T-134 | — | test_load_profile parity over all profiles |
| NFR-GATEHYGIENE-001         | T-131..T-133 | — | check-script-has-tests / runnable meta-gates |

---

## 5. Open questions

- **OQ-1**: Detection precedence — confirmed: **monorepo → mobile → data-contract
  → (existing: ml-pipeline → fullstack → api → cli/library → …)**. Structural
  (monorepo) and platform (mobile) signals are more specific than framework/library
  signals; schema-first beats api. NFR-NOREGRESS is the backstop.

## 6. Acceptance Definition (release is done when)

- All three REQ acceptance criteria (a/b/c) pass — detection, profile-parse, and
  gate-script behavior.
- Each new gate script passes the runnable + has-tests meta-gates (stdlib-only).
- Full suite green, `validate-plugin.py` exit 0, `full-pipeline.sh` 12/12.
- `test_load_profile.py` parity test covers all 8 named profiles.
- `.claude-plugin/plugin.json` + `marketplace.json` at `0.1.7`; CHANGELOG
  `## [0.1.7]` on top.
