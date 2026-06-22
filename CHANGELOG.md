# Changelog

All notable changes to Forge are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Claude Code marketplace publication (pending marketplace availability)

---

## [0.5.0] — 2026-06-22

**Unified `~/.forge` graduation layer.** Forge already promoted the best *lessons* across
projects; now **skills** and **workflows** graduate too — through one shared, tier-agnostic
core instead of three bespoke promoters. Each tier has a promotion gate matched to its nature
(cross-project breadth for emergent lessons; quality + an existing approval/validation gate for
deliberate skills and workflows), and **a project's own artifact always wins on conflict** — the
global store is a fallback library, never an override. Promotion runs automatically and silently
at session-start; a new `/forge:graduate` exposes dry-run / list / force-scan. Zero regression to
the lesson path: `promote-lessons.py` is *refactored* onto the core, not rewritten — same CLI,
byte-identical `global-lessons.yaml`, existing tests unchanged. stdlib + PyYAML, atomic,
fail-soft per tier, never-raising.

### Added

- **Shared graduation core** (REQ-GR-001, T-207) — `scripts/_graduation.py`: the project registry
  (`~/.forge/projects.yaml`), atomic `write_atomic`, the shared 30-day `is_stale` TTL, an idempotent
  keyed `merge_by_key`, a `Tier` protocol (collect/gate/key/promote/recall), and a `graduate()`
  driver that scans `registered-projects × tiers` isolating each tier (one tier's fault degrades only
  that tier) and **never raises**.
- **Skills graduation tier** (REQ-GR-003, T-208) — `_graduation_skills.SkillTier`: gate = locally
  approved **AND** ExpeL `weight > 0` **AND** `use ≥ 2`; promote the skill dir to
  `~/.forge/skills/<slug>/` + `global-skills.yaml`; recall by **symlink** into the plugin `skills/`
  path with project/plugin-wins, no-clobber, and a copy fallback (ADR-009).
- **Workflows graduation tier** (REQ-GR-004, T-209) — `_graduation_workflows.WorkflowTier`: gate =
  validates clean **AND** ≥ 2 successful `workflow_run` records in `.forge/events.jsonl`; promote the
  YAML to `~/.forge/workflows/<name>.yaml` + `global-workflows.yaml`; recall via
  `workflow_loader.resolve_workflows` (project-wins on name, TTL-filtered) so `/forge:flow` lists and
  runs graduated flows.
- **Automatic session-start graduation** (REQ-GR-006, T-210) — `hooks/session-start.py` registers the
  project and runs `graduate()` over all three tiers (skill symlinks land via per-tier recall),
  silent, bounded, and fail-soft; `FORGE_NO_GRADUATE=1` disables it.
- **`/forge:graduate` skill + thin CLI** (REQ-GR-007, T-211) — `--dry-run` previews each tier's
  would-promote set, `list` enumerates the `~/.forge` store per tier, a force scan promotes — all over
  the same core (no second promotion path).
- **ADR-008 + ADR-009 + reference docs** (T-212) — the graduation model (shared core + per-tier gates +
  project-wins) and skill-recall-by-symlink decisions, plus `references/graduation-layer.md`.

### Changed

- **`promote-lessons.py` re-expressed as `LessonTier` over the core** (REQ-GR-002, T-207) —
  behavior-preserving: same `--register`/`--promote`/`--global-dir`/`--threshold`/`--dry-run` CLI,
  same breadth ≥ 3 + frequency ≥ 2 gate, byte-identical `global-lessons.yaml`. The refactor is a
  separate commit from new-tier behavior (REQ-NF-036).

### Fixed

- **Two SKILL.md frontmatter descriptions broke YAML parsing** — `forge-why` and
  `forge-health-check` each had an unquoted `: ` (colon-space) inside a multi-line
  `description:`, which YAML reads as a nested mapping. `validate-plugin.py` only checks
  `plugin.json`, so the breaks shipped green; rewritten so all 34 skill frontmatters parse.

---

## [0.4.1] — 2026-06-21

**Operable engine.** A hardening release that makes the v0.4.0 dynamic-workflow engine
observable, auditable, and cost-predictable — with **zero change to what it computes**. The
byte-identical-result invariant is untouched: all new output is a side channel (stderr or a
`.forge/` append), the stdout result is byte-for-byte the same with observability on or off, and
every new path is stdlib + fail-soft and **never raises** into the engine. No new engine
capability, no new node type, no change to scheduling/admission/verify/merge.

### Added

- **Live run narration** (REQ-WF-011, T-202) — `run_workflow` / `parallel_build` emit `[Forge]`
  progress to **stderr**: a per-wave header, per-node `start` / `done` / `dropped: <reason>` with
  cost, and a deterministic id-ordered end-of-run summary block. Default on; silenced by the new
  `orchestration.narrate: false` config key or `FORGE_WF_QUIET=1`. Stdout is byte-identical with
  narration on vs off; a narration failure degrades to silence.
- **`events.jsonl` audit record** (REQ-WF-012, T-203) — every run appends **exactly one**
  schema-versioned, PII-free `workflow_run` line to `.forge/events.jsonl` via the rotation-aware
  atomic writer: `ts`, `name`, `nodes`, `waves`, id-ordered `completed` / `dropped:[{id,reason}]`
  / `admitted`, `total_cost_usd`, and `verdicts`. Over-cap and invalid-spec runs still write;
  an unwritable `.forge` degrades silently.
- **Cost pre-flight estimator** (REQ-WF-013, T-204) — a **pure** `estimate_admission(spec,
  cap-state)` replays the *same* topological pre-allocation `run_workflow` uses (shared
  `_preallocate`) against the single `_cost_cap` source — zero dispatch — returning
  `estimate ≈ admitted × FRESH_FLOOR_USD` and the deterministic admitted-vs-dropped split plus
  cap headroom. `/forge:flow` surfaces it **before** running; a runtime admission drop fires a
  loud narration line. The split is identical, node-for-node, to what the run drops.
- **Dogfood example + integration test** (REQ-WF-014, T-205) — ships a validated in-repo
  `.forge/workflows/doc-review.yaml` (a `split → {reviewer-a, reviewer-b} → synthesize` diamond)
  and a `tests/integration/` test that drives the parallel-build path against
  `examples/sample-todo-api/` end-to-end with an **injected fake dispatcher** (no spend): fan-out
  → adversarial-verify join → merge → worktree teardown.

### Changed

- `WorkflowResult` gained additive `admitted` / `drops` views (defaults keep every existing
  serializer byte-identical) feeding the audit record and the estimator's run-equality check.
- README + `references/workflow-engine.md` document the `.forge/workflows/*.yaml` schema, the four
  `orchestration:` toggles + `narrate`, the per-node fresh-session cost-sizing rule, and a new
  Observability section. `ROADMAP.md` consolidates the program-wide future roadmap + standing
  non-goals (SRS-v0.4.1 §5), replacing the deferred-work sections scattered across prior docs.

---

## [0.4.0] — 2026-06-21

Dynamic workflow engine. Forge's orchestration generalizes from two hardcoded layers
(a flat homogeneous fan-out + a linear stage sequencer) into a general **topological
DAG executor** — arbitrary graphs of heterogeneous agent steps with per-node
prompt/schema/model, `depends_on` edges, dependency-wave scheduling, bounded parallel
fan-out, inter-step data passing, and per-node verification. Built **on** the mature
single-step `claude -p` dispatch adapter (cost-gated, deterministic, never-raises).
Every capability on top is an **independent opt-in toggle, all default off**, so a
project that enables none sees zero behavior change from v0.3.6. Grounded in a research
review of Claude Code's own Dynamic Workflows + Agent SDK, durable/graph orchestration
(LangGraph, Temporal), and the automatic-workflow-generation literature (AFlow, ADAS,
DSPy) — field consensus is **hybrid**: a curated backbone with generation confined to
validated slots.

### Added
- **Workflow DAG engine** (`scripts/_workflow.py`) — `WorkflowNode`
  (id / `build_prompt(upstream)` / `depends_on` / `output_schema` / `model` / `validate`
  / `verify` / per-node `cwd`), `WorkflowSpec`, `validate_spec` (dup-id / unknown-dep /
  cycle), `plan_waves` (Kahn), and `run_workflow` (validate-first; topological waves;
  bounded parallel per wave; data passing; retry-once-then-drop; id-ordered,
  byte-identical parallel/sequential; never-raises). Threads `max_budget_usd` + `resume`
  into every dispatch with **deterministic budget-aware admission** (topological
  pre-allocation, so cap pressure drops a fixed set). (REQ-WF-001, NF-026, NF-029)
- **Shared per-node verify/heal** (`scripts/_verify.py`) — extracted from autopilot and
  imported by both; a node with a `VerifySpec` gets a fresh-session, schema-constrained
  pass/fail verdict gating its result (drop-with-reason or one heal). (REQ-WF-002)
- **`orchestration:` config block** — independent toggles `flows_enabled`,
  `parallel_build`, `worktree_isolation`, `allow_generated_subdags` (all default false)
  + tunables `max_parallel` (4), `max_total` (64), `max_budget_usd`; fail-soft. (REQ-WF-003)
- **User-defined flows** (`flows_enabled`) — `.forge/workflows/*.yaml` loader
  (`scripts/workflow_loader.py`, with `{{upstream_id}}` `prompt_template` interpolation)
  + the `/forge:flow` skill (list / run / `--plan`), human-in-the-loop via
  Proposal→Validator→Executor. (REQ-WF-005, 006)
- **Per-stage parallel build** (`parallel_build`) — fans independent, ready task-DAG
  nodes out in parallel via the engine, each with its own `cwd`. (REQ-WF-007)
- **Git-worktree isolation** (`worktree_isolation`, `scripts/_worktree.py`) — each
  parallel mutating node runs on its own `forge/wt/<node>` branch (never `main`/`develop`)
  from a clean base; conflicts surface at the merge (never silent clobber); worktrees torn
  down on success **and** on failure; degrades to sequential when unavailable. (REQ-WF-008)
- **Adversarial-verify join** — before merging parallel build outputs, N skeptics (each
  prompted to refute) gate admission by **majority of *dispatched* skeptics** (a cost-cap
  drop can't silently lower the bar). (REQ-WF-009)
- **Hybrid sub-DAG generation** (`allow_generated_subdags`) — an optional `decompose`
  node generates a sub-DAG validated by `validate_spec` + a node-count cap + a
  deterministic token-budget proxy **before any child dispatches**. (REQ-WF-010)
- `references/workflow-engine.md` + `references/orchestration-config.md`.

### Changed
- **Forge's own fan-outs run on the engine** — `_orchestrate.fan_out` is now the
  single-wave special case of `run_workflow`; `/forge:review`, `/forge:adopt`, and
  `/forge:why` route through it with **behavior preserved** (their tests pass unchanged).
  (REQ-WF-004)
- **README** rewritten — leaner and scannable, with mermaid flow diagrams (gated
  pipeline, the learning loop, a workflow DAG); deep detail deferred to `references/`.

### Fixed
- Decompose generation now routes a **malformed-parser exception** to the deterministic
  fallback (sub-DAG admission moved inside the generation guard) instead of dropping the
  node with no fallback — closing a REQ-WF-010 edge case found in adversarial verification.

---

## [0.3.6] — 2026-06-16

Context-aware autopilot. A long hands-off run now survives a context boundary —
**checkpoint → compact → continue** — instead of degrading or losing its place.
Opt-in (off until `autopilot.context_window_size` is set), default 80% threshold.
Grounded in a research review of Claude Code compaction + hooks, the API/SDK
context-management primitives, and long-run agent frameworks (Letta, OpenHands,
Cline, Roo, Cognition/Devin, Anthropic harness guidance).

### Added
- **Context-pressure session rotation (background)** — `should_rotate_for_context`
  rotates the reused `claude -p` session to a fresh one (a clean "compact →
  continue") once a dispatch's `usage.input_tokens` crosses
  `autopilot.context_threshold_percent` of `autopilot.context_window_size`. For a
  resumed session, `input_tokens` ≈ current context size — a real pressure signal,
  not just a dispatch count. OR-combines with the existing
  `session_max_dispatches`. (REQ-CTX-001..003)
- **Durable checkpoint artifact** — `.forge/autopilot-checkpoint.json` (atomic,
  schema-versioned): current stage, remaining stages, next action, written before a
  context boundary. New `autopilot.py checkpoint` subcommand. Stage-level
  idempotency stays in the run-log + `--resume`, so resume never redoes work.
  (REQ-CTX-004, 005, 008)
- **PreCompact hook** (`hooks/pre-compact.py`) — checkpoints an active autopilot run
  before Claude Code's native in-session compaction; never blocks, never raises.
  (REQ-CTX-006)
- **Post-compaction resume injection** — `SessionStart(source=compact)` re-injects
  "resume at stage N — do not redo completed stages" when a run is active.
  (REQ-CTX-007)
- `references/autopilot-context.md` documenting both substrates and the config knobs.

### Changed
- `_background_agent` dispatch results surface `input_tokens`; the autopilot
  dispatch/heal CLI gains `--last-input-tokens`; `/forge:autopilot` documents the
  context-check loop step and the opt-in config.

---

## [0.3.5] — 2026-06-16

Semantic skill mining. Forge's skill-miner no longer guesses from tool-name
n-grams (`Bash`/`Read`/`Write` co-occurrence is noise); it now detects genuine
*problem-solving workflows* and authors them into real skills, human-approved
throughout. Grounded in a research review of Agent Workflow Memory,
Stitch/babble anti-unification, ExpeL/TroVE, LILO, Nous Hermes Agent, and
Xiaomi MiMo Code.

### Added
- **Semantic miner core** — tool calls are enriched into intent verbs and
  segmented into outcome-bounded *episodes* (`scripts/_trace_semantics.py`);
  recurring workflows are found by **anti-unification** (`scripts/_antiunify.py`)
  and promoted only when ≥3 *distinct, successful* episodes share a coherent
  parameterized shape (`scripts/skill_miner_v2.py`). Frequency alone is never
  sufficient. (REQ-SM-001..004)
- **LLM induction with graceful degradation** — a cheap-model structured-output
  pass names and documents each candidate and cites the source trace lines;
  degrades to the deterministic anti-unified skeleton when background/LLM is
  unavailable or `FORGE_NO_BACKGROUND=1`. (REQ-SM-005)
- **`/forge:skill-creator`** — authors a candidate into a tested, well-described
  skill in-session (capture → write → test → grade → improve →
  optimize-description), gated by the existing approval flow. (REQ-SM-007)
- **agentskills.io `SKILL.md` emission** — proposals carry frontmatter +
  *When to Use / Procedure / Pitfalls / Verification / Provenance*; never
  unnamed. (REQ-SM-006)
- **Replay verification** (`scripts/skill_verify.py`) — a candidate is admitted
  only if its source episodes reproduce the successful red→green outcome; critic
  fallback when no runnable oracle. (REQ-SM-008)
- **Library curation** (`scripts/skill_curate.py`) — ExpeL-style voting
  (ADD/UPVOTE/DOWNVOTE/EDIT, prune at weight 0), TroVE frequency trim, and a
  `/dream`-style maintenance pass that merges near-duplicates, prunes stale
  skills, and flags dangling file references. (REQ-SM-009)
- `references/skill-mining.md` documenting the semantic pipeline.

### Changed
- The Stop hook and `/forge:retro` now drive the semantic miner
  (`skill_miner_bg.py` → `skill_miner_v2.py`) instead of the n-gram path.
  Proposals still land at `.forge/proposed-skills/<slug>/SKILL.md` and flow
  through the same approval/blacklist gate (clean migration). (REQ-SM-010)

### Fixed
- `agents/skill-miner.md` doc-drift: it referenced a non-existent
  `.forge/proposals.jsonl`; corrected to `.forge/proposed-skills/<slug>/SKILL.md`.

### Deprecated
- The v1 tool-name n-gram miner (`scripts/mine-skills.py`) and its
  `.forge/patterns.jsonl` bus are retained for back-compat but are off all
  active skill-mining paths.

---

## [0.3.4] — 2026-06-15

**Sprint planning + cross-machine guidance (M4).** Closes the long-deferred v0.2 M4
backlog (originally scoped as v0.2.3): a sprint view over the task DAG, `~/.forge` sync
guidance with opt-in local-only telemetry, and a Windows-timeout fix.

### Added
- **`/forge:sprint`** (`scripts/sprint.py`, `skills/forge-sprint/`, T-153,
  REQ-F-044..048): a deterministic **view over the task DAG** (no LLM). `plan` groups the
  next ready tasks (dependency order, target `--size`, optional `--milestone`) into
  `pipeline/05-plan/sprint-NN.md` — **carry-over first**, preserving T-IDs across sprints;
  `review` reports done/carried/blockers into `pipeline/12-release/sprint-NN-review.md`;
  `list` shows progress. Fully opt-in — a project that never runs it sees no change.
- **Opt-in, local-only telemetry** (`scripts/telemetry.py`, T-154, REQ-F-053):
  skill-mining telemetry is **off by default**; when enabled it records to
  `.forge/telemetry.jsonl` **on the local machine only** and leaves solely via an explicit
  `export`. `enable`/`disable`/`status`/`summary`/`export` CLI. Forge has no telemetry
  network path. The skill-miner records a fail-soft `skills_mined` event when opted in.
- **`docs/forge-sync.md`** (T-154, REQ-F-052): a conflict-safe layout for syncing
  `~/.forge` (global lessons) across machines with no server — what to sync, what to keep
  machine-local, and a private-git-repo recommendation.

### Changed
- README: sprint coverage; ROADMAP/progress reflect the M4 release.

### Fixed
- **Cross-platform hook timeout** (`scripts/_hook_runner.py`, T-155, REQ-F-054 /
  NFR-COMPAT-001): Windows lacks `signal.SIGALRM`/`setitimer`, which crashed `run_hook` on
  the first hook event. The runner now degrades to **no wall-clock kill** on such platforms
  (still exception-isolated; explicit `exit 2` still blocks) instead of crashing. See
  `build/06-evaluation/spike-windows.md`.

---

## [0.3.3] — 2026-06-15

**Complete (local) autonomy + modernized harness (v0.3).** Two things land together:
(1) the autopilot/orchestration substrate is rebuilt onto current Claude Code primitives,
each verified against the live CLI and degrading gracefully when unavailable
(REQ-NF-013); and (2) autopilot graduates from *hands-off but supervised* to
*self-healing, self-verifying, and unattended* — without weakening the safety posture
(never forces a gate without explicit opt-in; everything bounded and reversible).

### Added
- **Structured outputs** (`hooks/_background_agent.py`, `scripts/_orchestrate.py`, T-167):
  orchestrated dispatches can request schema-constrained JSON via the CLI's
  `--json-schema` (Claude Code 2.1.177+); the parse/validate/retry/drop path remains the
  fallback. Consumers (`/forge:review`, `/forge:adopt`, `/forge:why`) opt in per call.
- **Per-dispatch budget ceiling** (T-168): `--max-budget-usd` on `claude -p` (config
  `autopilot.max_budget_usd`), complementing the `_cost_cap` daily/monthly ledger gate.
- **Per-stage model routing** (T-169): `autopilot.models` maps stages (numeric key or
  command word, e.g. `build`/`eval`) to models — a capable model for hard stages, a cheap
  one for gate-checks/narration.
- **Long-run session rotation** (T-170): `autopilot.session_max_dispatches` rotates a
  reused background session to a fresh one to bound context growth (the CLI auto-compacts
  *within* a session; this bounds reuse *across* dispatches).
- **Self-heal loop** (`scripts/autopilot.py`, T-172, REQ-AUTO-001/002): on a blocking
  gate, autopilot makes a bounded fix attempt via the Stage-11 resolver
  (`autopilot.max_heal_attempts`, default 1; `0` = classic stop-on-gate) and re-checks the
  gate before giving up. `run_heal()` + a `heal` CLI command dispatch `/forge:resolve`
  headlessly in background mode; it never force-advances on its own.
- **Self-verification** (T-173, REQ-AUTO-003): with `autopilot.verify: true`, a passing
  gate is double-checked by an **independent fresh-context verifier** (schema-constrained
  verdict); a `fail` routes back into the self-heal loop. A broken/unavailable verifier
  degrades to no-op (never blocks an already-passing gate).
- **`--unattended` mode** (T-174, REQ-AUTO-004/005): a hands-free run with no per-stage
  checkpoints, bounded by the full safety envelope (budget, cost cap, max-heal,
  max-stages/stop-before, kill switch, stop flag). Interactive stages use a pre-supplied
  `.forge/autopilot-answers.{json,yaml}` or record **explicit assumptions** in the
  run-log — never a silent guess. Any bound STOPS cleanly with a resumable run-log.
- **Enforcing rules** (`scripts/rules.py`, `hooks/pre-tool-write.py`, T-175,
  REQ-AUTO-006): a `glob` rule with `enforce: true` (+ `severity`) **blocks** a matching
  write (`pre-tool-write` exit 2) — the governance guardrail for unattended autonomy
  (e.g. fence off lockfiles/secrets). Advisory remains the default; absent rules dir is a
  clean no-op.

### Changed
- `.forge/config.yaml` `autopilot:` gains `max_budget_usd`, `models`,
  `session_max_dispatches`, `max_heal_attempts`, and `verify` (all read fail-soft;
  absent ⇒ prior behavior).
- `/forge:autopilot` skill: self-heal + self-verify steps, `--unattended` flow, and
  updated safety rails. `references/rules-format.md` documents enforcing rules.

### Fixed

---

## [0.3.1] — 2026-06-15

**Autopilot (v0.3 Milestone 2 — autonomy).** Hand Forge the wheel: `/forge:autopilot`
runs pipeline stages back-to-back — per stage it runs the agent, checks the gate, and
**advances only on a pass, stopping at the first blocker** (it never forces past a gate).
Bounded, interruptible, and a clean no-op outside a pipeline. Generalizes
`/forge:force-advance` (one gated advance) and `/forge:build --milestone` (within-stage).

### Added
- **Autopilot planner** (`scripts/autopilot.py`, T-162, REQ-AP-001..003): deterministic,
  no-LLM stage-plan generator from the canonical stage table + state. Targets
  `--to N` / `--stages K` / `--until-gate`; clamps to cycle entry/exit, stage bounds, and
  config `autopilot.stop_before` / `max_stages`. `--resume` skips stages already recorded
  in `.forge/autopilot-runs.jsonl`; `--dry-run`/`--json`. Never raises (malformed state →
  empty plan).
- **`/forge:autopilot` skill** (`skills/forge-autopilot/`, T-163, REQ-AP-004/005/008/009):
  walks the plan in-session — run stage agent → `check-gate.py` → advance on a clean gate
  via `state-manager.py`, or **STOP** on a blocker (never forces unless
  `autopilot.allow_force` + a reason). Narrates each step and records a run-log row.
- **Background substrate** (`run_stage(mode="background")` + `autopilot.py dispatch`,
  T-164, REQ-AP-006): per-stage `claude -p` dispatch via the single `_background_agent`
  wrapper — cost-gated, capability-gated, session-reused; a clean `unavailable` no-op
  under `FORGE_NO_BACKGROUND=1` or when no background capability is present.
- **`/forge:autopilot-stop` + session model** (`skills/forge-autopilot-stop/`, T-165,
  REQ-AP-007): cooperative cancel via `.forge/autopilot-session.json` — `start` is
  idempotent (warns if already running), `stop` sets a flag the loop honors between
  stages (current stage finishes; nothing forced), `finish` idles and clears the flag.

### Changed
- `.forge/config.yaml` gains an optional `autopilot:` block (`max_stages`, `stop_before`,
  `checkpoint`, `allow_force`, `model`), read fail-soft like `cost_cap`.

### Fixed

---

## [0.3.0] — 2026-06-15

**Project Rules (v0.3 Milestone 1 — governance).** A user-authored constraints surface
that steers Forge's agents, in the spirit of Cursor's `.cursor/rules`. Rules live in
`.forge/rules/*.md` (YAML frontmatter + a markdown body), are **advisory** (they never
block a write), and degrade to a clean no-op when the directory is absent. This is the
first phase of the v0.3 "Hands-off Forge" program; Autopilot follows in v0.3.1.

### Added
- **Rules loader** (`scripts/rules.py`, T-157, REQ-RULES-001..004): parses
  `.forge/rules/*.md` with a scope model — `always`, `stage`, `glob`, `manual` —
  exposing `load_rules` / `select` / budget-bounded `render`. Frontmatter is split with
  a stdlib fence parser + fail-soft PyYAML (no third-party `frontmatter` dependency);
  globs use `fnmatch` with sensible `**` handling. Malformed files are skipped and an
  absent directory yields nothing — it **never raises** (it is imported by hooks).
- **`/forge:rules` skill** (`skills/forge-rules/`, T-158, REQ-RULES-005..008):
  `init` (idempotent scaffold of `.forge/rules/` with a README + example) / `add` (from a
  template, never clobbers) / `list` / `validate`. Documented in
  `references/rules-format.md`.
- **Glob-rule injection on writes** (`hooks/pre-tool-write.py`, T-160, REQ-RULES-010):
  user `glob` rules matching the written file surface as advisory `additionalContext`
  for **any** file type, alongside the existing design-system feedback. Never blocks.

### Changed
- **Session-start injects rules** (`hooks/session-start.py`, T-159, REQ-RULES-009): the
  context block now includes `always` + current-`stage` rules, kept within the existing
  ≤2000-token budget (lessons trim first, then rules drop as a last resort).

### Fixed

---

## [0.2.3] — 2026-06-11

**Background daemons (v0.2 Milestone 2).** With the O-2 cost gate cleared in v0.2.2,
the spike-gated daemons land: Observer, Dreamer, and Health, plus the production async
skill-miner and log rotation. Every daemon pins a cheap model and reuses one session
(the spike's cost rule), is capability-gated (a clean no-op when background agents are
unavailable), and never raises.

### Added
- **Observer daemon** (`scripts/observer.py`, `/forge:watch` + `/forge:watch-stop`,
  T-142): a reused-session Stage-9 watcher that records findings
  (`{ts,severity,source,message}`) to `.forge/observer-findings.jsonl`. Idempotent
  start (warns instead of double-spawning); `watch-stop` preserves the last poll
  output. Unread findings surface at session start (cursor-tracked) and in
  `/forge:status`; a lazy ≥30-min poll is fired detached from session start. Writes
  only under `.forge/` — never pipeline artifacts. + `agents/observer.md`,
  `references/daemon-bus.md`.
- **Dreamer daemon** (`scripts/dreamer.py`, `/forge:dreamer-run`, T-143): lesson
  consolidation — confidence decay (lessons <0.3 → dormant), duplicate detection
  (Jaccard ≥0.8 on trigger+rule) and contradiction detection, both **flag-only**
  (never auto-merged/resolved). Writes an idempotent daily digest to
  `pipeline/log/daily-<date>.md`; atomic `lessons.yaml` writes. Optional cheap-model
  consolidation summary when background is available. + `agents/dreamer.md`.
- **Health daemon** (`scripts/health_check.py`, `/forge:health-check`, T-144):
  aggregates hook unit-test results + lesson-store integrity (missing fields,
  out-of-range confidence, malformed YAML, broken `[[xref]]`s) into a
  `healthy|degraded|failing` status. Auto-disable requires an explicit
  `health.auto_disable_hooks: true` policy and is **never silent** — it logs to
  `.forge/events.jsonl` and writes `.forge/health-surface.txt`, surfaced at the next
  session start; a recovered run clears it. + `agents/health.md`.
- **Size-bounded log rotation** (`hooks/_error_log.py`, T-146, REQ-F-049): a shared,
  stdlib-only, never-raises primitive (`rotate_if_needed` + `append_jsonl`) that rolls
  append-only `.forge` logs to numbered backups at a byte ceiling, each step a single
  atomic `os.replace`. Wired into the hook error log (`FORGE_LOG_MAX_BYTES` override)
  and reused by the Observer findings log.

### Changed
- **Async skill-miner is now the production path** (T-145, REQ-F-027): when background
  capability is present, the background miner drafts `.forge/proposed-skills/<slug>/
  SKILL.md` — the **same** artifact the inline `mine-skills.py` produces — so both
  paths feed the identical approval flow. (It previously wrote a dead-end
  `proposals.jsonl` that nothing consumed.)

---

## [0.2.2] — 2026-06-11

**Skill-miner cost fix — clears the spike's O-2 gate, unlocking the M2 daemons.** A
patch release: the background skill-miner now pins a cheap model, bringing
background-agent cost back inside budget and clearing the last gate on the daemon
build-out.

### Fixed
- **Background skill-miner pinned to a cheap model** (`scripts/skill_miner_bg.py`,
  `MINER_MODEL = "haiku"`; override via `--model`). Real-usage testing exposed that an
  unpinned dispatch falls back to the session default (Opus-class) at **~$1.07/run** —
  ~20× the spike's haiku estimate and well over the O-2 budget. Pinned, six live
  dispatches completed **6/6 at ~$0.022/run** ($0.073 fresh, ~$0.011 resumed via
  `--resume`), clearing the spike's **O-2** gate (≥90% completion **and** ≤$0.10/session).
  The cost cap proved its worth in the same test — the lone $1.07 run tripped the daily
  cap and would have blocked the next dispatch. **Consequence: the M2 background daemons
  (Observer / Dreamer / Health) are unblocked.**
- **Date-robust over-cap test** (`tests/unit/test_skill_miner_bg.py`). The over-cap
  skip test seeded the cost-ledger with a frozen date; once the calendar rolled past it,
  the entry aged out of `_cost_cap`'s real-clock "today" window and the suite failed a
  day later. Now stamped with the real current UTC time, matching the existing pattern
  in `test_background_agent.py`.

### Docs
- **Hero banner + social preview** for the README, with stats verified against the
  tree (1,100+ tests passing, 70%+ coverage).

---

## [0.2.1] — 2026-06-10

**Orchestration + brownfield (v0.2 Milestone 3).** In-session, deterministic
multi-agent fan-out and the features it unlocks. Not spike-gated — it builds only on
the v0.2.0 cost cap, so it ships ahead of the background daemons (which remain gated
on the O-2 completion-rate and will land in a later release).

### Added
- **Orchestration primitive** (`scripts/_orchestrate.py`, T-148): fan a work-list out
  across bounded parallel agent dispatches and return results **ordered by input
  index**, so the parallel and sequential paths are byte-identical (determinism is a
  test invariant). Each call delegates to the single `_background_agent.dispatch`
  wrapper (cost-gated); malformed output is retried once then dropped with a logged
  reason — never silently truncated. Bounded by `max_parallel` (4) + `max_total` (64),
  with key-based dedup.
- **`/forge:review`** (`scripts/review_synthesize.py`, T-149): the first consumer —
  fans four reviewers (correctness, security, performance, conventions) out in
  parallel over a diff/file and synthesizes one deduplicated, severity-sorted report.
  A malformed dimension is dropped without sinking the review.
- **`/forge:adopt`** (`scripts/adopt.py`, T-150) — **brownfield onboarding** (closes
  tester finding EF-014): detect the project type, sample a bounded file set, fan out
  extractors to infer SRS + architecture drafts (marked **INFERRED** with confidence +
  provenance), seed `state.md`, and enter the pipeline at Stage 1 for confirmation.
  Read-only to user source (writes only under `pipeline/` + `.forge/`); `--dry-run`
  previews without spending; refuses an already-initialized project.
- **`/forge:why` LLM fallback** (T-151): when deterministic ID lookup misses and
  background capability is available, one orchestrated subagent offers a best-effort
  explanation, clearly marked as non-authoritative. Behavior is unchanged without
  capability.

### Changed
- ADR-006 corrected: a `scripts/` primitive cannot drive Claude's in-session Agent
  tool, so the orchestration primitive delegates each call to `claude -p` (keeping a
  single host call site). Synchronous orchestration stays decoupled from the daemon
  spike gate.

---

## [0.2.0] — 2026-06-10

**v0.2 foundation — background intelligence groundwork.** The first phase of the
v0.2 program ("a system that works alongside you"). This release lands the P0
building blocks the daemons, orchestration, and brownfield features will rest on —
all additive, all degrading to a clean no-op when the background capability is
absent. v0.1 behavior is unchanged.

The background-agent feasibility spike **passed**: `claude -p --output-format json`
dispatches headlessly and returns actual cost; session reuse (`--resume`) cuts
per-poll cost ~10×. The one remaining spike gate — background skill-miner
completion-rate over ≥5 real sessions — is **instrumented and accruing**; the P1
daemons wait on it.

### Added
- **Cost cap + ledger** (`hooks/_cost_cap.py`, T-136): a hard-prerequisite spend
  gate. Daily/monthly caps from `.forge/config.yaml` (default $0.50/day), an
  append-only `.forge/cost-ledger.jsonl` recording API-reported actual cost, and a
  pre-dispatch check that skips + logs over-cap instead of spending. Never raises.
- **Background adapter dispatch** (`hooks/_background_agent.dispatch`, T-137):
  headless `claude -p --output-format json` with mandatory session reuse
  (`--resume`), cost-gated through the cap, correlation via the returned
  `session_id`. The single call site for the background API.
- **Capability probe wiring** (T-138): `session-start` maintains a cached
  `.forge/capabilities.json` via a detached refresh — the slow probe never blocks
  the hook. New `FORGE_NO_BACKGROUND=1` kill switch disables all background work.
- **Background skill-miner** (`scripts/skill_miner_bg.py`, T-139): `stop-reflect`
  offloads skill-mining to a background subagent when capable (inline
  `mine-skills.py` fallback otherwise), instrumented with completion + cost markers.
- **`/forge:set-profile <type>`** (T-140): switch the project-type profile at
  runtime (validated against the 10 known profiles; atomic state.md update;
  `--dry-run`).

### Changed
- `stop-reflect.py` Step 4 now branches between the background and inline
  skill-miner based on `.forge/capabilities.json`. Both paths remain detached — the
  Stop hook never waits.

---

## [0.1.7] — 2026-06-09

**Three more project-type profiles.** Forge now ships 10 profiles. Each new
profile auto-detects and carries a real, deterministic gate executable (run via
`check-gate.py`); profiles load generically through `load-profile.py`, so they
apply across all 12 stages with no per-skill wiring.

### Added
- **monorepo** profile (REQ-PROFILE-MONOREPO-001, T-131) — multi-package
  workspaces (pnpm/yarn/npm workspaces, Nx, Turborepo, Lerna, Cargo workspace).
  Detected ahead of single-package signals. Gate `check_monorepo_graph.py`
  fails on a cycle in the internal package dependency graph.
- **mobile** profile (REQ-PROFILE-MOBILE-001, T-132) — Flutter / React Native /
  native iOS / native Android (React Native is no longer mistaken for fullstack).
  Product-ux stays high. Gate `check_store_readiness.py` requires per-platform
  store metadata (iOS bundle id+version; Android applicationId+versionCode+
  versionName; Flutter version).
- **data-contract** profile (REQ-PROFILE-DATACONTRACT-001, T-133) — schema-first
  repos (Protobuf / Avro / GraphQL SDL / dbt), guarded so a service that also
  ships `.proto` stays `api`. Gate `check_schema_compat.py` enforces schema
  hygiene + policy (no duplicate protobuf field numbers; a buf breaking-change
  policy when `buf.yaml` is present) — explicitly *not* a semantic cross-version
  diff (which needs the prior schema version).

### Changed
- `load-profile.py` parity test now covers all 8 standard profiles; the monorepo
  profile gained a stage_5 (plan) override. README + Detection Heuristics doc
  list the 3 new profiles.

---

## [0.1.6] — 2026-06-09

**Make Forge interactive.** The three interactive behaviors decomposed from
REQ-INTERACTIVE-001 (T-122) and deferred from v0.1.5 are now implemented:
clarify before scoping, confirm before expensive writes, narrate during builds.
Acceptance is structural (the directive is present and bounded in the skill/agent
instruction), consistent with the existing agent-content tests.

### Added
- **CLARIFY** (REQ-INTERACTIVE-CLARIFY-001, T-126) — `/forge:srs` asks one
  bounded clarifying-question round (a single batch, not a drip) before writing
  `srs.md`, and records explicit assumptions for anything left unanswered.
- **CONFIRM** (REQ-INTERACTIVE-CONFIRM-001, T-127) — `/forge:spec` and
  `/forge:plan` present a short outline / table of contents and pause for
  confirmation before generating the full technical spec / task DAG, so the user
  can redirect before the expensive write.
- **NARRATE** (REQ-INTERACTIVE-NARRATE-001, T-128) — `/forge:build` narrates
  progress at each task boundary (starting → result → next); `build-batch.py`
  emits a per-task `[Forge] task T-XXX — starting` line to stderr so a
  `--milestone N` batch is observable at the tool layer (stdout stays the
  machine-readable id list).

### Changed
- Clarification bound reconciled repo-wide from "max 3 rounds" to "one bounded
  round (a single batch, not a drip)" in `agents/requirements-analyst.md`,
  `build/02-architecture/architecture.md`, `references/pipeline-stages.md`, and
  `references/agent-format.md`, consistent with the new REQ.

### Release infrastructure
- CI gates (`.github/workflows/tests.yml`) are now hard fails: coverage is
  measured with subprocess instrumentation (real ~72%, gated at 70) and
  integration is no longer `continue-on-error`.
- `scripts/bump-version.py` — one-command version bump across both manifests with
  an auto-inserted, newest-on-top CHANGELOG skeleton (first used to cut this
  release).

---

## [0.1.5.1] — 2026-06-09

Hotfix. Forge hooks crashed with a `ModuleNotFoundError` traceback at import time
when **PyYAML was not installed** in the user's Python (e.g. a bare conda env) —
every Stop/SessionStart/etc. event spammed the session. Same dependency-not-
installed failure mode as the v0.1.3.1 `python-frontmatter` bug, moved to `yaml`.

### Fixed
- The 6 active hooks (`session-start`, `prompt-submit`, `pre-tool-write`,
  `post-tool-use`, `stop-reflect`, `session-end`) now **fail soft** when PyYAML is
  absent: they print one actionable line — `[Forge] PyYAML is not installed —
  Forge hooks are inactive. Fix: pip install pyyaml (then run /forge:doctor).` —
  and exit 0 instead of crashing with a traceback. The guard runs at import time,
  before `_state_lib` (which requires PyYAML) is imported. `/forge:doctor` already
  detects the missing dependency.
- `tests/unit/test_pyyaml_missing.py` — shadows `yaml` with an ImportError shim
  and asserts every guarded hook exits 0 with the message and no traceback.

### Note
- This does not make Forge *function* without PyYAML (it remains a required
  runtime dependency, checked by `/forge:doctor`); it stops the crash-spam and
  tells the user exactly how to fix it.

## [0.1.5] — 2026-06-09

Bug-fix-heavy release driven by two on-project testers (EF-001…027). Theme: sand
off the v0.1.3 sharp edges and kill the **surface-healthy / substance-inert**
antipattern family at every layer (state, hook, doctor, gate-config, lesson-store),
plus small UX nudges. 25 tasks across 7 milestones; full unit + integration suite
green and the Forge-on-Forge pipeline passes its own gates.

> **Version history note**: there is no `0.1.4` tag. v0.1.4's scope (the dogfood
> ceremony) was **amended, not executed** — see `build/01-srs/srs-v0.1.4.md` §9
> Amendment — once two real testers existed. v0.1.5 supersedes it directly from
> v0.1.3.1.

### Fixed
- `tests/unit/test_force_advance.py` — replaced 4 `import frontmatter` calls with
  `_state_lib.read_state()` / `_state_lib._split_frontmatter()`. No longer requires
  `python-frontmatter` to run tests (EF-021).
- `hooks/post-tool-use.py` — added `isinstance` guard for string `tool_input` / `tool_response`
  payloads from Bash/Read events. Hook no longer crashes on non-Write tool events (EF-022).
- `hooks/pre-tool-write.py` — added `isinstance` guard for string `tool_input` payloads
  from inline Write events (EF-023).
- **Stage path collision (EF-005, REQ-PATHS-001, T-102)** — stage skills and agent
  personas wrote/read artifacts at directories and filenames the gates never checked,
  silently wedging stages 4, 8, 9, 10, and 11. Canonicalized every stage path to the
  single source of truth (`references/stage-order.md` + `gate-criteria.md`):
  `04-technical-spec/`→`04-spec/`, `08-deployment/`→`08-deploy/`,
  `09-monitoring/`→`09-monitor/`, `11-resolution/`→`11-resolve/`;
  `deployment-plan.md`→`deploy-plan.md`, `slo-definition.md`→`observability.md`,
  `resolution-log.md`→`hotfixes.md`, `triage-report.md`→`triage.md`. `/forge:feedback`
  now also writes `feedback-log.md` and `/forge:resolve` now also writes
  `backlog-updates.md` (both are gate blockers that were never produced).
  `tests/unit/test_canonical_paths.py` guards against re-drift.

  > **Migration note**: projects created with v0.1.3.x may have artifacts under the
  > old directories (`pipeline/04-technical-spec/`, `08-deployment/`, `09-monitoring/`,
  > `11-resolution/`) or old filenames. Move them to the canonical names above so the
  > gate checks find them; otherwise the affected stage gate will report the artifact
  > missing.
- **Wrong / dead next-step hints (REQ-NEXTHINT-001, T-103)** — every stage skill
  hardcoded its `## Next Step` hint; two named commands that don't exist:
  `/forge:srs` pointed at `/forge:ux` and `/forge:product` pointed at
  `/forge:architecture` (canonical commands are `/forge:product` and `/forge:arch`).
  After `01-srs` the hint now correctly names **product/UX**, not architecture.
  Added a `next-hint` subcommand to `scripts/state-manager.py` that reads the
  canonical hint from `references/stage-order.md`; all 12 stage skills now invoke
  it instead of embedding a literal string. Also corrected the `forge-status`
  stage→command table (stage 2/3 named the same dead commands).
  `tests/unit/test_next_hint.py` enumerates all 12 transitions and guards against
  re-drift.

### Added
- Comprehensive external test findings to `build/06-evaluation/v0.1.3.1-early-feedback.md`:
  7 new entries (EF-021 through EF-027) covering 3 hotfixes and 4 fix-v0.1.5 items.

### Changed
- `build/06-evaluation/v0.1.3.1-early-feedback.md` — tally updated from 20 → 27 total
  findings across all buckets.

### Added — state machine & entry gates (M2)
- **Stage bounds + cycle-wrap (REQ-PIPEBOUNDS-001, T-104)** —
  `_state_lib.advance_stage` rejects out-of-range jumps and wraps past stage 12 to
  `(cycle+1, stage 0)`; `set current_stage` to `-1/99/13` is rejected, never
  persisted. (EF-024)
- **Pre-flight entry gates for stages 2–11 (REQ-GATE-ENTRY-001, T-105)** — each
  stage refuses to start when its prior-stage artifact is missing
  (`state-manager.py preflight`); multi-stage skips require `/forge:force-advance`.

### Added — fail-loud surfacing (M3)
- **State-read failures surface (REQ-SILENTSTATE-001, T-106)** — hooks stop
  swallowing `read_state` errors; visible warning, `inconclusive` gate output,
  `/forge:doctor` callout, and a session-end footer. (EF-007)
- **Doctor runs the current-stage gate inline (REQ-DOCTOR-001, T-107)** — top-line
  status is `healthy` / `wedged` / `broken`; doctor can't contradict status. (EF-017)
- **check-gate fails loud on missing scripts (REQ-GATESTUB-001, T-108)** — a
  criterion pointing at a missing script is `inconclusive`, promoted to blocker,
  and exits non-zero; doctor/status show an "N criteria unimplemented" banner. (EF-019)

### Added — gate scripts (M4)
- **All 15 gate scripts implemented (REQ-GATESTUB-001, T-109–T-111)**:
  `check_srs_acceptance`, `traceability-check`, `spec-coverage`,
  `check_dag_completeness`, `check_dag_completion`, `token-audit`, `check_coverage`,
  `check_todos`, `check_progress_sync`, `check_nfr_coverage`, `check_open_bugs`,
  `check_health`, `check_hotfix_tests`, `check_git_tag`. `some_check.py` is a
  doc-only format example (not a real criterion).
- **Gate-criteria audit (T-112)** — `test_gate_criteria_audit.py` fails if any
  `script_returns_zero` criterion references a missing script.

### Added — lesson capture (M5)
- **`extract-lessons.py --cwd` (REQ-EXTRACT-CWD-001, T-113)** — derives input/output
  from `--cwd`. (EF-027)
- **Implicit lesson-signal producers (REQ-LESSON-SOURCES-001, T-114)** — five
  producers turn hook-error clusters, repeated design violations, heredoc bypass,
  gate pass→wedge, and state-read regressions into lessons automatically. (EF-018)
- **Global-lessons TTL + promotion gate (REQ-LESSON-SOURCES-001 / EF-026, T-115)** —
  promote only at frequency ≥ 2; stale (> 30-day) global lessons decay out of recall.

### Added — UX nudges (M6)
- **`/forge:build --milestone N` (REQ-BUILDBATCH-001, T-116)** — milestone-scoped
  batch builds with per-task commits, pause-on-failure, and `--resume`. (EF-020)
- **Case-insensitive `/forge:why` gate-ID lookup (REQ-WHYCI-001, T-117)**. (EF-025)
- **`session.jsonl` enrichment (REQ-SESSIONLOG-001, T-118)** — versioned, PII-free
  rows with commands, tokens, and `reflection_ref`.
- **Per-stage reflection rollup (REQ-STAGEREFLECT-001, T-119)** —
  `pipeline/0X-stage/reflection.md` on stage exit.
- **Pattern-bus schema (REQ-PATTERN-001, T-120)** — versioned `patterns.jsonl` +
  `references/pattern-schema.md`. (EF-008)
- **WebSearch for research/spec agents (REQ-WEBSEARCH-001, T-121)** — cite-or-skip
  rule; planner excluded.

### Added — conventions & docs (M7)
- **REQ-INTERACTIVE-001 decomposed (T-122)** into CLARIFY / CONFIRM / NARRATE-001
  (scheduled for v0.1.6). (EF-013)
- **Large-document split convention (REQ-LARGEDOC-001, T-123)** —
  `references/large-doc-layout.md` + `scripts/read-doc.py` resolver. (EF-006)
- **Third-party-hook troubleshooting (REQ-DOCS-001, T-124)** +
  `.github/ISSUE_TEMPLATE/forge-feedback.md` (REQ-FEEDBACK-001). (EF-003)

### Changed — fixtures
- Harmonized the `sample-todo-api` fixture IDs (eval-report `REQ-F`/`REQ-NF` → canonical
  `REQ`/`NFR`; stray `REQ-NF-003` in architecture; added a stage-9 `health-report.md`)
  so the Forge-on-Forge `full-pipeline` passes all 12 gates.

---

## [0.1.3.1] — 2026-05-24

Hotfix release. Removes the runtime dependency on the `python-frontmatter` PyPI
package, which silently broke every external install: Claude Code plugin installs
do not run `pip install`, and the bare PyPI name `frontmatter` resolves to an
unrelated package (no `.load()`), so users who tried to self-remediate hit
`AttributeError: module 'frontmatter' has no attribute 'load'`. State management
now uses PyYAML + a stdlib frontmatter splitter; PyYAML is already a documented
runtime dep checked by `/forge:doctor`.

### Fixed
- `scripts/_state_lib.py` — replaced `import frontmatter` and all `frontmatter.load`
  / `frontmatter.dumps` calls with stdlib parsing of the `---` fence + PyYAML for
  the YAML block. On-disk `pipeline/state.md` byte layout preserved.
- `scripts/load-profile.py` — `_read_project_type()` now delegates to
  `_state_lib.read_state` instead of importing `frontmatter` directly.

### Added
- 3 regression tests in `tests/unit/test_state_manager.py` (`TestNoFrontmatterDependency`)
  that shadow `frontmatter` with an `ImportError`-raising shim and assert read/set/
  advance still work. Catches future re-introductions of the dep.
- One lesson in `tasks/lessons.md` capturing the dep-vs-package-name foot-gun.

### User impact
- External users on v0.1.3 hit `ModuleNotFoundError: No module named 'frontmatter'`
  in every `state-manager.py` invocation (SessionStart, UserPromptSubmit, Stop hooks,
  and `/forge:init` post-setup). v0.1.3.1 makes a clean install work end-to-end with
  only PyYAML installed.

---

---

## [0.1.3] — 2026-05-19

First-run hardening release. Theme: make the first ten minutes — install, init,
first gate failure, recovery, uninstall — hard to mess up, and make a Forge bug
never break the user's Claude Code session.

### Added

- **Hook resilience wrapper** (`scripts/_hook_runner.py`, T-100) — all 7 lifecycle
  hooks wrapped: top-level exception barrier (logs JSONL to
  `.forge/hook-errors.log`, exits 0), per-hook `SIGALRM` timeout, blocking hooks
  never block on internal failure, non-blocking hooks suppress accidental exit 2.
  POSIX-only (documented).
- **`/forge:doctor`** (`scripts/doctor.py` + skill, T-101) — 13 deterministic
  checks across environment/plugin/project/global, each failing check carries a
  literal fix command. `--json`/`--quiet`/`--cwd`.
- **`/forge:uninstall`** (`scripts/uninstall.py` + skill, T-102) — filesystem
  state removal with mandatory `--dry-run` preview, `--keep-artifacts`,
  `--include-global` (separate confirmation), idempotent re-runs.
- **`/forge:init --dry-run` and `--manifest-only`** (T-103) — preview-only mode
  that writes nothing; JSON manifest drives the post-init `.gitignore` prompt.
- **Gate result formatter** (`scripts/format-gate-result.py`, T-104) — renders
  `check-gate.py` JSON as readable text grouped by severity with per-criterion
  fix hints (longest-prefix lookup over all 12 stages + profile families).
- **`/forge:force-advance`** (`scripts/force-advance.py` + skill, T-105) —
  override a blocking gate; `--reason` (≥10 chars) required and recorded as a
  `force-advance` lesson with the overridden blocker IDs. Override is
  per-advancement, not per-criterion.
- **`/forge:why`** (`scripts/why.py` + skill, T-106) — explains a gate ID,
  lesson tag, stage number, or the current blocker(s). Deterministic lookup.
- **`script` project profile** (T-107) — 6th profile for sub-500-LOC projects
  (4 active stages). `suggest_only` flag: `script` is never auto-assigned, only
  prompted. New `check-script-runnable.py` / `check-script-has-tests.py` gate
  scripts (G6-SCRIPT-001 / G7-SCRIPT-001).
- **First-run round-trip integration test**
  (`tests/integration/test_v013_first_run.sh`, T-108) — exercises doctor → init
  dry-run → init → gate failure → why → force-advance → uninstall →
  idempotent re-run. Passes on a clean checkout.
- **`docs/gate-philosophy.md`** — when to resolve a blocker vs. override it.
- ~158 new unit tests (hook_runner 25, doctor 35, uninstall 21,
  format-gate-result 17, force-advance 17, why 26, plus detect-project-type
  additions). Total unit suite: **690 passing**.

### Changed

- `README.md` now leads with discipline + traceability (gates and REQ-ID chains)
  instead of memory; test badge updated to 690.
- `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` version
  bumped to `0.1.3`.

### Known limitations

- POSIX-only (hook resilience uses `SIGALRM`); Windows deferred to v0.2.
- Hook-error log has a per-record cap but no rotation yet (deferred to v0.2).
- Animated traceability walkthrough in the README is still pending (text
  diagram in place); deferred to v0.1.4.
- **No external-user dogfood gate for this release.** v0.1.3 ships on
  engineering + integration evidence by explicit decision; real-user testing
  is a non-waivable acceptance gate in v0.1.4. Recovery surface for early
  external users: `/forge:doctor`, `/forge:why`, `/forge:force-advance`, and
  hook crash isolation.

---

---

## [0.1.2] — 2026-05-14

Patch release: skill-miner noise filter and `--cwd` positional fix for AI-callable CLIs.

### Fixed
- `scripts/mine-skills.py` — `_is_substantive()` filter blocks spurious proposals generated by
  same-tool bursts. A 5-Bash burst produced 3 overlapping sliding-window records with identical
  signature, hitting count=3 from one session in 8 seconds. New filter requires ≥2 distinct tool
  types, ≥2 distinct sessions (relaxed when `--session` is active), and ≥60s first-to-last span.
- `scripts/state-manager.py` — `--cwd` now accepted in any argument position. Previous
  `parents=[common]` approach caused subparser `default=os.getcwd()` to overwrite the main
  parser's parsed value when `--cwd` appeared before the subcommand. Fix: subparsers use
  `default=argparse.SUPPRESS` so the namespace value is never silently overwritten.

### Added
- 12 new tests: 8 `_is_substantive` unit tests (including the exact `forge-bash-bash-bash`
  noise scenario), 4 `TestCwdPositioning` CLI tests covering pre- and post-subcommand placement.
- `.forge/skill-blacklist.txt` — `3287e5ddb4be` (forge-bash-bash-bash noise proposal) blacklisted.
- Two new lessons in `tasks/lessons.md` documenting both root causes.

---

---

## [0.1.1] — 2026-05-14

Patch release: corrected plugin manifest, added marketplace support, updated install docs.

### Added
- `.claude-plugin/marketplace.json` — registry file enabling two-step install:
  `/plugin marketplace add tonmoy007/forge-plugins` then `/plugin install forge@forge-plugins`
- `README.md` Install section updated with correct marketplace commands

### Changed
- `.claude-plugin/plugin.json` — fixed `$schema` URL to schemastore, renamed plugin
  `sdlc-orchestrator` → `forge`, removed invalid fields (`displayName`, `claude_code_version`,
  `engines`), removed unsupported glob declarations for skills/agents (auto-discovery used
  instead), fixed hook env var `CLAUDE_PLUGIN_DIR` → `CLAUDE_PLUGIN_ROOT`

### Removed
- `docs/superpowers/specs/2026-05-11-extract-lessons-design.md` — vendored Superpowers spec
  removed; plugin now uses the installed Superpowers plugin directly

---

---

## [0.1.0] — 2026-05-12

First stable release. Full 12-stage SDLC pipeline with hooks, agents, memory, and
auto-skill creation — validated end-to-end on the sample Todo API project (532 tests pass).

### Added

**M1: Core Skeleton**
- `plugin.json` — Claude Code plugin manifest wiring all hooks and skills
- `/forge:init` skill — detects project type, scaffolds `pipeline/`, writes `state.md`
- `state-manager.py` — CLI for reading and updating pipeline state (36 tests)
- `/forge:status` skill — shows current stage, task, blockers, recent history
- `gate-criteria.md` — machine-readable exit criteria for all 12 stages (60 criteria)
- `check-gate.py` — evaluates `file_exists`, `file_contains`, `script_returns_zero`,
  `all_tests_pass` checks; always exits 0 and outputs JSON (14 tests)

**M2: Hook System**
- `session-start.py` — injects stage context and top lessons at session open (≤ 2 000 tokens; 17 tests)
- `prompt-submit.py` — detects stage intent and flags user corrections (16 tests)
- `stop-reflect.py` — evaluates output against gate criteria; surfaces skill proposals (48 tests)
- `session-end.py` — writes session summary to `.forge/sessions/` (18 tests)
- `pre-tool-write.py` — enforces design token compliance, traceability, naming conventions (35 tests)
- `post-tool-use.py` — logs tool use to `patterns.jsonl` for skill mining (18 tests)
- `subagent-stop.py` — captures cross-stage agent reflections

**M3: Specialized Agents**
- 12 stage agent personas (SRS analyst through release manager)
- 4 cross-stage agents: reflector, lesson-extractor, skill-miner, gate-checker
- `context-pruner.py` — stage-aware artifact selection within token budget (35 tests)
- `/forge:resume` skill — restores context after session restart

**M4: Memory + Lessons**
- `extract-lessons.py` — rule-based correction extraction → structured YAML lessons (43 tests)
- `sync-lessons.py` — mirrors `lessons.md` to `.forge/lessons.yaml` (37 tests)
- `promote-lessons.py` — promotes high-frequency lessons to `~/.forge/global-lessons.yaml` (39 tests)
- Session-start lesson injection: filters by stage tags and project type, sorted by frequency, capped at 5

**M5: Adaptive Workflow**
- `detect-project-type.py` — detects `api`, `fullstack`, `ml-pipeline`, `cli`, `library` types (10 tests)
- `project-type-profiles.md` — per-type gate overrides and stage emphasis rules (5 profiles, ≥3 overrides each)
- `load-profile.py` — applies profile overrides to stage skill context (24 tests)
- All 12 stage skills profile-aware (skip/replace_with/add_step)

**M6: Auto-Skill Creation**
- Sliding 3-tool window pattern tracker with SHA-1 signature stability detection (22 tests)
- `mine-skills.py` — aggregates patterns (frequency ≥ 3) → SKILL.md drafts with name/description/steps (33 tests)
- `skill-approval.py` — list/approve/modify/reject mined proposals (22 tests)
- `/forge:retro` skill — cycle-completion retrospective writing to `pipeline/12-release/retro.md`

**M7: Polish + Documentation**
- `README.md` — user-facing install, quickstart, full 12-stage command reference, hook table, config docs
- `CONTRIBUTING.md` — contributor guide with dev workflow, commit format, PR checklist
- `docs/agent-authoring.md` — step-by-step walkthroughs for adding agents, stages, and profiles
- `tests/integration/full-pipeline.sh` — end-to-end test: 29 artifacts, 12/12 gate checks, traceability chain
- `examples/sample-todo-api/fixtures/` — 29 pre-populated stage artifacts for e2e validation
- `scripts/check_dir_nonempty.py` — gate helper for ADR directory non-empty check (G3-005)

### Tests

532 unit + integration tests. Coverage spans all hooks, scripts, and integration paths.

---
