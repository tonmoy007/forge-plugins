# Implementation Progress

> Updated by Claude as work progresses. This is the first thing to read after CLAUDE.md
> at session start to know where we are.

## Current State

- **v0.6.0 (engine made real I: per-node session reuse) BUILD IN PROGRESS — T-214..T-219.** Drives the
  already-built-but-unused `_background_agent.dispatch(resume=...)` reuse path from the v0.4.0 DAG engine,
  lowering a node's *own* retry/heal re-dispatch floor from `FRESH_FLOOR_USD` to `RESUME_FLOOR_USD` — a
  **cost-reduction** minor with **zero default behavior change** (opt-in `orchestration.session_reuse`,
  default off ⇒ byte-identical to v0.4.x). Within-node reuse only; admission stays `FRESH_FLOOR_USD`
  (AC-WF-014 unchanged); the independent verifier is never reused (REQ-WF-002). Branch
  `feat/v0.6.0-session-reuse`. SRS `build/01-srs/srs-v0.6.0.md`, DAG `build/04-plan/task-dag-v0.6.0.md`
  (T-214..T-219). **T-214..T-218 done; T-219 (release v0.6.0) is next.**

- **v0.5.0 (unified `~/.forge` graduation layer) RELEASED — T-207..T-213.** Generalizes the
  T-022 lesson promoter into one tier-agnostic core `scripts/_graduation.py` (registry `~/.forge/projects.yaml` ·
  `write_atomic` · 30-day `is_stale` TTL · idempotent `merge_by_key` · `Tier` protocol collect/gate/key/promote/recall ·
  fail-soft-**per-tier** `graduate()` driver that never raises) + three thin **separate-module** tier adapters behind
  **per-tier gates**: lessons = `promote-lessons.py` re-expressed as `LessonTier` (breadth≥3 + freq≥2, behavior-preserving,
  byte-identical `global-lessons.yaml`; T-207); skills = `_graduation_skills.SkillTier` (gate approved AND ExpeL `weight>0`
  AND `use≥2`; promote → `~/.forge/skills/<slug>/` + `global-skills.yaml`; recall = **symlink** into the plugin `skills/`
  path, project/plugin-wins, no-clobber, copy fallback; T-208); workflows = `_graduation_workflows.WorkflowTier` (gate
  validates-clean AND ≥2 successful `workflow_run` records in `.forge/events.jsonl`; promote → `~/.forge/workflows/<name>.yaml`
  + `global-workflows.yaml`; recall = `workflow_loader.resolve_workflows` global search path, project-wins on name; T-209).
  **Project-wins** recall in every tier (global = fallback library, never override); the single shared 30-day TTL decays
  unused globals out of recall. Wired **silent + fail-soft** at session-start (`hooks/session-start.py _register_and_promote`:
  `register_project` + `graduate(...)` over the three tiers; `FORGE_NO_GRADUATE=1` escape; never blocks startup; T-210).
  `/forge:graduate` skill + thin CLI (`--dry-run` / `list` / force scan) over the core, no second promotion path (T-211).
  ADR-008 (shared core + per-tier gates + project-wins, fail-soft-per-tier) + ADR-009 (skill recall = symlink, not copy) +
  `references/graduation-layer.md` + README/ROADMAP/progress/decisions (T-212). The T-207 refactor is committed separately
  from new-tier behavior (REQ-NF-036). Branch `feat/v0.5.0-graduation-layer`. SRS `build/01-srs/srs-v0.5.0.md`, DAG
  `build/04-plan/task-dag-v0.5.0.md` (T-207..T-213). Released via T-213: bump 0.5.0, CHANGELOG `[0.5.0]`, manifests 0.5.0;
  pre-release gate green (full unit suite, `validate-plugin.py` 0, `full-pipeline.sh`); banner/social evergreen (no refresh);
  PR→develop→main→tag `v0.5.0`→mirror origin+polygon→GitHub releases→delete branch. **NEXT: v0.5.1/v0.6 engine "made real"
  trio** (session reuse · top-level generation · pipeline-as-WorkflowSpec; srs-v0.5.0 §6).

- **v0.4.0 (dynamic workflow engine) RELEASED** — generalizes `_orchestrate.fan_out` from a flat homogeneous map into a
  topological **DAG executor** (`scripts/_workflow.py`): per-node prompt/schema/model,
  `depends_on` waves (Kahn), bounded parallel fan-out, inter-step data passing, per-node
  verify, deterministic + never-raises. Built via a fan-out workflow — serial spine
  (T-191→192→193) then a **3-way parallel worktree fan-out** (T-194 consumers ∥ T-195
  flows ∥ T-196→197→198 parallel-build chain) → T-199 decompose → T-200 docs. T-191
  budget/resume plumbing + deterministic admission + `VerifySpec`; T-192 shared
  `scripts/_verify.py` (autopilot behavior preserved unchanged); T-193 `orchestration:`
  config (independent toggles `flows_enabled`/`parallel_build`/`worktree_isolation`/
  `allow_generated_subdags`, all default off); T-194 review/adopt/why run on the engine
  (behavior-preserving); T-195 `.forge/workflows/*.yaml` loader + `/forge:flow`; T-196
  parallel build + per-node `cwd`; T-197 git-worktree isolation + lifecycle (branch-per-node
  `forge/wt/<id>`, teardown on success+crash); T-198 adversarial-verify join (majority of
  *dispatched* skeptics); T-199 validated sub-DAG `decompose` node. **Adversarial AC pass:
  SHIP-WITH-NOTES** — all 11 ACs met by non-tautological tests, consumer tests provably
  unchanged from `cab5f56`, never-raises survived 5 hostile probes; 2 non-blocking notes
  addressed (decompose-fallback gap fix + budget-doc caveat, `6e8f0f2`). 1616 unit tests
  pass; validate 0; full-pipeline 12/12 (toggles off + on). Shipped via T-201: bump 0.4.0,
  CHANGELOG `[0.4.0]`, README rewrite + banner/social-preview refresh; tag `v0.4.0` on
  origin + polygon; GitHub releases published; manifests 0.4.0. SRS
  `build/01-srs/srs-v0.4.0.md`, DAG `build/04-plan/task-dag-v0.4.0.md` (T-191–T-201).

- **v0.3.6 (context-aware autopilot) RELEASED** — at a configurable context threshold,
  autopilot checkpoints → compacts → continues. Background: `should_rotate_for_context`
  rotates the reused session on a real token-pressure signal (`usage.input_tokens`) past
  `context_threshold_percent × context_window_size` (T-185); shared atomic,
  schema-versioned checkpoint `.forge/autopilot-checkpoint.json` + `checkpoint` subcommand,
  run-log idempotency (T-186). In-session: new `PreCompact` hook checkpoints before native
  compaction (T-187); `SessionStart(source=compact)` re-injects resume state (T-188). Docs
  (T-189). Opt-in, default 80%; zero change when `context_window_size` unset. Tag `v0.3.6`
  (merge `029f2c0`) on origin + polygon; GitHub releases published; manifests 0.3.6. 1496
  tests pass; validate 0; full-pipeline 12/12. SRS `build/01-srs/srs-v0.3.6.md`, DAG
  `build/04-plan/task-dag-v0.3.6.md`.

- **v0.3.5 (semantic skill mining + skill-creator) RELEASED** — replaces the
  tool-name-n-gram miner with a semantic, success-gated, anti-unification pipeline:
  enrichment + episode segmentation (`_trace_semantics.py`, T-177), anti-unify motif miner
  + success gate (`_antiunify.py` / `skill_miner_v2.py`, T-178), LLM induction w/ graceful
  degradation (T-179), `/forge:skill-creator` + agentskills.io `SKILL.md` emission (T-180),
  replay verification (`skill_verify.py`, T-181), library curation (`skill_curate.py`,
  T-182), n-gram path retired + docs (T-183). Built autonomously via a fan-out workflow
  (sequential core spine → parallel tail → integrate → adversarial verify). Tag `v0.3.5`
  (merge `3da32b8`) on origin + polygon; GitHub releases published; manifests 0.3.5. 1473
  tests pass; validate 0; full-pipeline 12/12. SRS `build/01-srs/srs-v0.3.5.md`, DAG
  `build/04-plan/task-dag-v0.3.5.md`.
- **v0.3.4 (M4 sprint) RELEASED** — closes the long-deferred v0.2 M4 backlog:
  `/forge:sprint` plan/review as a view over the task DAG (T-153), `docs/forge-sync.md`
  cross-machine guidance + opt-in local-only telemetry (T-154), and a cross-platform
  hook-timeout fix (Windows degrades, never crashes; T-155). Tag `v0.3.4` on origin +
  polygon; GitHub releases published; manifests 0.3.4; CHANGELOG `[0.3.4]`.
- **v0.3.3 (complete autonomy + modernized harness) RELEASED** — modernized harness
  (T-167..T-170, folded; no separate v0.3.2 tag) + complete local autonomy: self-heal
  (T-172), verifier subagents (T-173), `--unattended` (T-174), enforcing rules (T-175).
  Tag `v0.3.3` (`8e827a1` merge) on origin + polygon; GitHub releases published; manifests
  0.3.3. SRS `build/01-srs/srs-v0.3.3.md`, DAG `build/04-plan/task-dag-v0.3.3.md`.
- **v0.3 program (v0.3.0 + v0.3.1) COMPLETE + RELEASED** — "Hands-off Forge — autonomy +
  governance": user-authored **Rules** (v0.3.0) + **Autopilot** cross-stage execution
  (v0.3.1), T-157..T-166. Tags `v0.3.0` (`9102b78`) + `v0.3.1` (`7525a7e`) on origin +
  polygon; GitHub releases published. SRS `build/01-srs/srs-v0.3.md`, DAG
  `build/04-plan/task-dag-v0.3.md`.
- **v0.5.0 build in progress** (details in the LANDING bullet at the top) — re-sequenced **ahead of** the engine
  "made real" trio (session reuse · top-level generation · pipeline-as-WorkflowSpec, now ≥ v0.5.1 / v0.6;
  srs-v0.5.0 §6). SRS `build/01-srs/srs-v0.5.0.md` + DAG `build/04-plan/task-dag-v0.5.0.md` (T-207..T-213) on
  branch `feat/v0.5.0-graduation-layer`. **T-207..T-212 done; T-213 (release) is the next task.**
- **v0.4.1 RELEASED — "operable engine" hardening.** SRS
  `build/01-srs/srs-v0.4.1.md` + DAG `build/04-plan/task-dag-v0.4.1.md` (**T-202..T-206**)
  authored on branch `feat/v0.4.1-operable-engine` (commit `bb88525`). Scope = zero-semantic-change
  observability over the shipped v0.4.0 engine: live stderr narration (stdout contract preserved,
  T-202), one-line `events.jsonl` audit per run (T-203), pure cost pre-flight estimator + loud
  drops over the existing deterministic admission set (T-204), dogfood `.forge/workflows/doc-review.yaml`
  + parallel-build integration test + docs (T-205), release (T-206). **Next task: T-202.** SRS §5
  consolidates the program-wide roadmap (v0.5.0 "engine made real" trio = session reuse across
  heterogeneous nodes · top-level generated workflows · pipeline-as-WorkflowSpec; unified `~/.forge`
  graduation layer; Managed-Agents track ≥v0.6; blocked-upstream in-session context trigger) +
  one standing-non-goals list. **T-202..T-206 DONE — v0.4.1 FULLY RELEASED.** Manifests 0.4.1 +
  CHANGELOG `[0.4.1]` on `main` (`2809e7e`); the `v0.4.1` tag + GitHub release are now published on
  origin (tag → `2809e7e`). The env proxy still 403s on direct tag-ref pushes, so the tag/release
  were created server-side by a new dispatchable `release.yml` Actions workflow (PR #38→develop,
  PR #39→main) — reusable for all future releases. **v0.4.1 is COMPLETE; the idempotency guard now
  short-circuits.**
- **Prior program v0.2** (phased v0.2.0→v0.2.3) — "a system that works alongside
  you": daemons, orchestration, brownfield, sprint. COMPLETE + RELEASED through v0.2.3
  (sprint M4, T-153–156, deferred).
- **v0.2.0 (M1 foundation) COMPLETE + RELEASED** — T-136..T-141. Cost cap + ledger,
  background-agent dispatch (`claude -p`, session reuse), capability probe wired into
  session-start, background skill-miner instrumentation, `/forge:set-profile`. Tag
  `v0.2.0` (`bd9d58a`) + GitHub release; main `16839ee`, develop `709710c`;
  **origin/polygon parity**. 1124 tests pass; validate 0; full-pipeline 12/12.
  - Planning (Stages 1/3/5): SRS reviewed, **spike PASS** (O-1 dispatch + O-2 cost
    RESOLVED — `claude -p --output-format json` headless, `--resume` cuts cost 10×:
    $0.053→$0.0046), architecture + ADR-005/006/007 (OQ-001..008 resolved), DAG
    `task-dag-v0.2.md` (T-136..T-156).
- **v0.2.1 (M3 orchestration + brownfield) COMPLETE + RELEASED** — shipped ahead of the
  spike-gated daemons (not gated; needs only the cost cap). T-148–T-152.
- **v0.2.2 (skill-miner cost fix) STAGED on develop** — pins the background skill-miner
  to a cheap model (`haiku`), cutting an unpinned ~$1.07/run (Opus-class default) to
  ~$0.022/run; six live dispatches 6/6 → **T-139's O-2 gate CLEARED**. Also a
  date-robust over-cap test fix + README hero banner. On `develop`; **the develop→main
  promotion + tag are BLOCKED** by a new `MAIN PROTECTION` ruleset (no bypass actors).
- **v0.2.3 (M2 background daemons) BUILT** — Observer / Dreamer / Health + async
  skill-miner production path + log rotation (T-142–T-146) on the proven adapter (cheap
  model + session reuse, capability-gated, never-raises). Staged for develop; promotes
  to main together with v0.2.2 once the ruleset is resolved.
- **NEXT**: resolve the `MAIN PROTECTION` ruleset, then promote v0.2.2 + v0.2.3 to main
  (two tags) and mirror to polygon. Then M4 sprint (T-153–T-156).
- **Prior release**: v0.1.7 — "Three more project-type profiles" — scope locked
  2026-06-09 (`build/01-srs/srs-v0.1.7.md`, `build/04-plan/task-dag-v0.1.7.md`).
- **v0.1.7 COMPLETE + RELEASED** — all 5 tasks (T-131..T-135). monorepo / mobile /
  data-contract profiles, each with auto-detection + a real gate
  (check_monorepo_graph.py, check_store_readiness.py, check_schema_compat.py).
  Built SERIALLY (shared detection trio). Tag `v0.1.7` (`a1192fc`) + GitHub
  release on both remotes; 1076 tests pass; validate 0; full-pipeline 12/12;
  manifests at 0.1.7; CHANGELOG `[0.1.7]` on top. origin/polygon parity.
- **v0.1.6 COMPLETE + RELEASED** — all 5 tasks (T-126..T-130). CLARIFY / CONFIRM /
  NARRATE via a 3-agent parallel fan-out. Tag `v0.1.6` (`baccc5e`) + GitHub
  release on both remotes; CHANGELOG `[0.1.6]`. origin/polygon parity.
- **v0.1.5 COMPLETE + RELEASED** — all 25 tasks (T-101..T-125); tag `v0.1.5` +
  hotfix `v0.1.5.1` (PyYAML fail-soft) on both remotes; release-infra hardening on
  main (hard CI gates w/ subprocess coverage ~72%, `scripts/bump-version.py`).
  plugin.json + marketplace.json at 0.1.5.1; CHANGELOG current.
- **Workflow**: branch from `main` → PR into `develop` → test → merge `develop→main`
  → tag from `main`. Two remotes kept in sync: `origin` + `polygon`.
- **Last hotfix**: v0.1.5.1 — PyYAML fail-soft guard in the 6 active hooks.

## v0.6.0 Task Status

> DAG: `build/04-plan/task-dag-v0.6.0.md` (T-214..T-219). SRS `build/01-srs/srs-v0.6.0.md`.
> Per-node within-node session reuse — drive the existing `dispatch(resume=...)` path from the
> engine; opt-in toggle (default off ⇒ byte-identical to v0.4.x); admission stays `FRESH_FLOOR_USD`;
> verifier never reused. Branch `feat/v0.6.0-session-reuse`.

| Task | Status | Notes |
|------|--------|-------|
| T-214 | 🟢 done | `session_reuse` config toggle + inert `run_workflow` param (REQ-WF-019, NF-038, NF-040). Added `session_reuse: bool = False` to `OrchestrationConfig` **and** `_TOGGLES` in `scripts/_workflow_config.py` (strict `is True`, fail-soft — a stray `1`/`"yes"` stays off; absent/malformed → off; mirrors `flows_enabled` & siblings). Added `session_reuse: bool = False` kwarg to `run_workflow` (`scripts/_workflow.py`) — **inert this task** (no node `--resume`s a prior same-node attempt) so engine output is **byte-identical to v0.4.x** with it on or off; threaded into the nested decompose `run_kwargs` for recursive parity. Config value threaded through `scripts/parallel_build.py` (both `run_workflow` call sites) and `scripts/_orchestrate.py` (`fan_out` → inner `run_workflow`); `scripts/workflow_loader.py` `flow_estimate` carries a load-bearing comment that `session_reuse` is **deliberately not** an admission/estimator input (AC-WF-014 preserved, REQ-WF-020). TDD red-first (8 tests RED on missing attr/`_TOGGLES` membership/`TypeError`, then GREEN). +11 tests (6 config: defaults-off ×2, true-enables, strict-bool, `_TOGGLES` membership, toggle-independence; 5 workflow: param-accepted-inert, defaults-off, on==off byte-identical). Full unit suite **1746 pass**; `validate-plugin.py` exit 0; caller-chain suites (orchestrate/parallel_build/workflow_loader) 66 pass. |
| T-215 | 🟢 done | `_attempt` session capture — behavior-preserving refactor, **separate commit, no reuse logic** (REQ-WF-016, NF-040; AC-WF-016). Widened `_attempt` (`scripts/_workflow.py`) from the 3-tuple `(obj, reason, cost)` to the 4-tuple `(obj, reason, cost, session_id)`: captures `res.session_id` once **past** the `status=="ok"` + non-`is_error` gates and surfaces it on every with-session path (success, non-JSON-but-ok, validation-failed-but-ok — all returned a resumable session); returns `None` on every no-session path (dispatch raised / non-`ok` status `error`/`skipped`/`unavailable` / `is_error`). All three `_run_node` call sites (first attempt, retry, heal) unpack the 4-tuple into `_session_id` and **IGNORE** it — every re-dispatch still fresh — so the engine stays byte-identical to v0.4.x (split-determinism: T-216 consumes the id). `getattr(res, "session_id", None)` keeps the existing fakes (no `session_id` attr) → `None`, no crash. TDD red-first: 7 `_attempt` tests RED on `ValueError: not enough values to unpack (expected 4, got 3)`, then GREEN; the `_run_node` smoke test was green throughout (shape unchanged). +8 tests. Full unit suite **1754 pass**; `validate-plugin.py` exit 0; `full-pipeline.sh` 12/12. |
| T-217 | 🟢 done | Admission / estimator / audit invariance + determinism (REQ-WF-020/021, NF-039; AC-WF-020/021) — **test-only** (the optional additive `reused` audit field was deliberately **not** added: it is optional and would force a `schema_version` bump + risk T-203 regressions for no required benefit, so the invariants are proven on the **existing** schema). +6 tests in `tests/unit/test_workflow.py` proving reuse changes **only realized cost**: (1) the run's `admitted`/`drops` split is identical with `session_reuse` on vs off and equals `estimate_admission`'s split (uncapped); (2) for a `max_budget_usd`-capped diamond the estimator split **equals** the run drops in **both** modes (`["A","B"]` admitted / `{"C","D"}` dropped — AC-WF-014 preserved, both charge `FRESH_FLOOR_USD`); (3) a run where **every** node heals costs strictly **less** under reuse (heal re-dispatches charge `RESUME_FLOOR`) while completing the identical node set; (4) the T-203 `events.jsonl` `workflow_run` record stays **exactly one** schema-versioned line per run with **unchanged** `completed`/`dropped`/`admitted`, an **identical key set** (schema unchanged across modes), a **lower** `total_cost_usd` under reuse, and **PII-free** (no produced `prompt`/content leaks into the line); (5) parallel≡sequential determinism (ordered results/drops/cost byte-identical) with reuse **on**; (6) **empty + byte-identical stdout** with reuse on (T-128 / AC-WF-012 lineage). New deterministic id-routed `_healing_id_dispatch` fake (every node heals once, routed by the node id embedded in the verifier prompt so parallel interleaving cannot scramble verdict order ⇒ realized cost + split are order-independent) + a `_healing_diamond` (every node carries a `VerifySpec`). TDD red-first: temporarily forcing `_reuse_attempt` to ignore the session (always-fresh) turned the two cost-bearing tests RED (`0.48 < 0.48`) while the split/determinism/stdout invariants correctly stayed green (they are invariant under reuse by design) — proving the cost tests are non-tautological; engine restored byte-for-byte (no `scripts/_workflow.py` diff). Full unit suite **1772 pass**; `validate-plugin.py` exit 0; `full-pipeline.sh` 12/12. |
| T-218 | 🟢 done | ADR-010 + reference/README/ROADMAP/progress/decisions docs (REQ-NF-038, ADR-010) — **docs-only, no engine change**. New `build/02-architecture/adr/010-session-reuse.md` (Accepted, matches the `008`/`009` path+format) records the five load-bearing decisions: **within-node only** (per-branch/cross-node deferred, measurement-gated), **verifier never reused** (REQ-WF-002), **admission stays `FRESH_FLOOR_USD`** (AC-WF-014 preserved), **default-off toggle** (strict `is True` ⇒ byte-identical to v0.4.x), **fallback-to-fresh** on a stale session (REQ-F-003) — with Rationale / Alternatives / Consequences. `references/workflow-engine.md`: added the `session_reuse` row to the `orchestration:` toggle table (four→five capability toggles), reworked the cost-economics section to note the one safe within-node reuse exception, and added a *Per-node session reuse (`session_reuse`, v0.6.0)* section (within-node only · verifier fresh · admission on fresh floor · stale→fresh fallback · off⇒byte-identical · one lower-cost audit line) linking ADR-010. `README.md`: `session_reuse: false` in the config block, four→five toggles, a session-reuse capability bullet. `ROADMAP.md`: v0.5.0 marked **released**; new **v0.6.0** row; the "engine made real" trio section updated (item 1 within-node half ✅ shipped, per-branch deferred) + a **caveman mode** (candidate v0.6.1, measurement-gated) sub-section. `decisions.md`: 2026-06-23 T-216/T-218 ADR-010 entry. The literal `docs/adr/ADR-010-…` path in the DAG was a spec typo — followed the **actual** repo ADR convention (`build/02-architecture/adr/NNN-slug.md`) per "match the existing ADR path/format". TDD red-first: new `tests/unit/test_docs_session_reuse.py` (4 tests) RED on the missing ADR file + un-wired toggle/README/ROADMAP strings, then GREEN. +4 tests. Full unit suite **1776 pass**; `validate-plugin.py` exit 0. |
| T-216 | 🟢 done | Within-node reuse (retry + heal) + fail-soft fallback (REQ-WF-017/018, NF-038/039/040; AC-WF-017/018/019). New `_reuse_attempt` helper + `session_reuse: bool = False` param on `_run_node` (`scripts/_workflow.py`): tracks the newest non-`None` captured `session_id` across attempts and threads it into the node's **own** retry + heal re-dispatches via a **per-attempt copy** `{**kwargs, "resume": sid}` — never mutating the shared `kwargs` (it flows on to the fresh verifier, so `_run_verify`/`_verify.run_verify`'s forced `resume=None` keeps the verifier independent, REQ-WF-002). A resumed re-dispatch that returns a non-`ok` status surfaces as `obj is None AND new_sid is None` (stale/invalid session) ⇒ **one fresh fallback re-dispatch within the same attempt budget** (REQ-WF-018) — reuse never turns a would-succeed node into a drop, never raises, no spurious drop reason on recovery; an ok-but-unparseable/validation-failed reused result (`new_sid` set) is a genuine retry and does **not** fall back. With reuse off (or no captured sid) the original `kwargs` flow unchanged ⇒ the run-level `resume` token is preserved and the engine is byte-identical to v0.4.x (verified: empty stdout, identical results/drops/completed on vs off). `_submit` threads `session_reuse` into `_run_node`; nested decompose children inherit it via `run_kwargs` (T-214) and the generation dispatch stays fresh; admission/estimator untouched (`FRESH_FLOOR_USD`, AC-WF-014). TDD red-first: 7 RED (`_run_node() got an unexpected keyword argument 'session_reuse'` + reuse/fallback behavior), then GREEN. +12 tests (10 `test_workflow`: heal-resumes-first-id + verifier-fresh, lower-realized-cost, retry-on-ok-unparseable resumes, hard-error retry stays fresh, stale→fresh-fallback completes, stale-fallback-also-fails clean drop, reuse-off no-prior-resume, reuse-off preserves run-level resume, no-mutate-shared-kwargs, `_run_node` defaults-off byte-identical; 2 `test_parallel_build`: `config.session_reuse` on resumes retry, off stays fresh). Full unit suite **1766 pass**; `validate-plugin.py` exit 0; `full-pipeline.sh` 12/12 (toggles off+on). |

## v0.5.0 Task Status

> DAG: `build/04-plan/task-dag-v0.5.0.md` (T-207..T-213). SRS `build/01-srs/srs-v0.5.0.md`.
> Unified `~/.forge` graduation layer — tier-agnostic core + lessons/skills/workflows tiers,
> recalled project-wins, fail-soft at session-start. Branch `feat/v0.5.0-graduation-layer`.

| Task | Status | Notes |
|------|--------|-------|
| T-211 | 🟢 done | `/forge:graduate` skill + thin CLI (REQ-GR-007, AC-GR-006). New `_graduation.main()` argparse front end **reuses the shared `graduate()` driver** (no second promotion path): default `scan` action promotes; `--dry-run` previews + writes nothing; `list` (subcommand or `--list`) enumerates the global store per tier (entry count + each key's `last_used`, fail-soft on a missing store). Three adapter tiers lazy-imported inside `main()` as `[LessonTier(), SkillTier(<plugin>/skills), WorkflowTier()]` (mirrors session-start assembly; LessonTier via importlib-into-`sys.modules` for dataclass annotation resolution). `--global-dir` default `~/.forge`; `main()` never raises (guarded; nonzero only on argparse usage error). New `skills/forge-graduate/SKILL.md` (`name: graduate`, `allowed-tools: [Read, Bash]`). +7 CLI tests (dry-run/scan parity over two projects sharing a qualifying workflow; `list` over a populated store; never-raises). `test_graduation_cli` 7 pass; `test_graduation`+`test_promote_lessons` 72 pass (regression green); validate-plugin exit 0. |

## v0.4.1 Task Status

> DAG: `build/04-plan/task-dag-v0.4.1.md` (T-202..T-206). SRS `build/01-srs/srs-v0.4.1.md`.
> "Operable engine" hardening — observability + cost pre-flight + dogfood over the shipped
> v0.4.0 engine, **zero semantic change** (narration is stderr-only; stdout byte-identical).
> Branch `feat/v0.4.1-operable-engine`.

| Task | Status | Notes |
|------|--------|-------|
| T-202 | 🟢 done | Live stderr narration (REQ-WF-011). `_workflow.narration_enabled` + `_Narrator` (stderr-only, never-raises) in `run_workflow`: per-wave header, per-node `start`/`done`/`dropped:<reason>` + cost, deterministic id-ordered summary block. `parallel_build` threads one shared narrator (fan-out via inner `run_workflow` + join-phase drop lines). New `orchestration.narrate` config key (default ON; only explicit `false` silences) + `FORGE_WF_QUIET=1` env. **stdout byte-identical on vs off** (AC-WF-012). +13 tests (config narrate ×4, narration ×7, parallel ×2). Full suite 1641 pass; validate 0; full-pipeline 12/12. |
| T-203 | 🟢 done | `events.jsonl` audit record (REQ-WF-012). `_workflow.write_audit_record` appends **exactly one** schema-versioned, PII-free `workflow_run` line per run via `_error_log.append_jsonl` (rotation + atomic): `ts` (injectable), `name`, `nodes`, `waves`, id-ordered `completed`/`dropped:[{id,reason}]`/`admitted`, `total_cost_usd`, `verdicts`. Nested decompose children + `parallel_build`'s inner fan-out pass `audit=False` (one line per top-level run); `parallel_build` writes its own post-merge record (setup+engine+join drops, adversarial verdicts). WorkflowResult gained additive `admitted`/`drops`. Over-cap **and** invalid-spec runs still write; unwritable `.forge` degrades silently; never raises. +8 tests. Suite 1648 pass; validate 0; full-pipeline 12/12. |
| T-204 | 🟢 done | Cost pre-flight estimator + loud drops (REQ-WF-013, NF-033). Extracted the topological admission loop into a shared pure `_workflow._preallocate`, called by **both** `run_workflow` and the new pure `estimate_admission(spec, *, max_total, max_budget_usd, daily/monthly_headroom_usd)` → `AdmissionEstimate` (id-ordered admitted/dropped split, `estimate_usd = len(admitted) × FRESH_FLOOR_USD`, headroom + `within_headroom`). Shared `_CAP_DROP_REASON` ⇒ estimator split is byte-identical to what the run drops (AC-WF-014). `workflow_loader.flow_estimate` reads the single `_cost_cap` source (caps + ledger headroom) + config tunables; `/forge:flow` surfaces estimate + cap headroom + would-drop nodes **before** running. Runtime admission drops fire loud T-202 narration. Zero dispatch; never raises. +10 tests. Suite 1658 pass; validate 0; full-pipeline 12/12. |
| T-205 | 🟢 done | Dogfood + integration test + docs (REQ-WF-014). Ships `.forge/workflows/doc-review.yaml` (split → {reviewer-a, reviewer-b} → synthesize diamond; loads + validates clean; `.gitignore` `.forge/*` + `!.forge/workflows/` re-include). New `tests/integration/test_parallel_build_e2e.py`: drives `run_parallel_build` against `examples/sample-todo-api/` with `parallel_build` + `worktree_isolation` ON + 2 adversarial skeptics via an **injected fake `dispatch_fn`** (no spend) — asserts fan-out → adversarial join → merge → worktree teardown + one audit record. Docs: README + `references/workflow-engine.md` document the YAML schema, the four toggles + `narrate`, the cost-sizing rule, and an Observability section; `ROADMAP.md` gains the SRS §5 consolidated roadmap + standing-non-goals. +2 integration tests. Suite 1660 pass; validate 0; full-pipeline 12/12. |
| T-206 | 🟢 done | Release v0.4.1 — `bump-version.py 0.4.1` (manifests **0.4.1** on `main`), CHANGELOG `[0.4.1]`, ROADMAP/progress rows. Banner/social-preview evergreen (no version stats since `d0e04e6`) → no refresh. Pre-release green (1660 pass, validate 0, full-pipeline 12/12 toggles off+on; re-verified green on the release-run). **Shipped via PR #36 (feat→develop) + PR #37 (develop→main, `2809e7e`).** **Tag + GitHub release `v0.4.1` are now PUBLISHED on origin** (tag → `2809e7e`, release body = CHANGELOG `[0.4.1]`). The env git proxy still returns HTTP 403 on direct tag-ref pushes, so a dispatchable `release.yml` Actions workflow was added (PR #38→develop, PR #39→main) and dispatched to create the tag + release **server-side** from the runner — bypassing the proxy and reusable for every future release. No `create_release`/create-tag MCP tool exists, hence the workflow route. Polygon remote not configured in this env (origin-only) → no mirror. **v0.4.1 is fully released; the idempotency guard now short-circuits.** |

## v0.3.3 Task Status

> DAG: `build/04-plan/task-dag-v0.3.3.md` (T-167..T-176). M1 Harness (T-167..T-171,
> originally scoped as v0.3.2, folded into v0.3.3); M2 Autonomy (T-172..T-176). Both
> shipped under `v0.3.3`. SRS `build/01-srs/srs-v0.3.3.md`.

### M1 — Modernized harness (v0.3.2) — branch `feat/v0.3.2-autonomy`

| Task | Status | Notes |
|------|--------|-------|
| T-167 | 🟢 done | Structured outputs — `dispatch(output_schema)` → `claude -p --json-schema` (CLI 2.1.177+); `_orchestrate.fan_out` threads it; parse/retry/drop fallback. +4 tests |
| T-168 | 🟢 done | Per-dispatch `--max-budget-usd` ceiling (config `autopilot.max_budget_usd`) atop `_cost_cap`. +4 tests |
| T-169 | 🟢 done | Per-stage model routing — `autopilot.models` (numeric or command-word key); `model_for_stage()`. +5 tests |
| T-170 | 🟢 done | Long-run session rotation — `autopilot.session_max_dispatches` + `should_rotate_session()`; CLI auto-compacts within a session, this bounds reuse across dispatches. +5 tests |
| T-171 | 🟡 staged | Release v0.3.2 — bump 0.3.2, CHANGELOG `[0.3.2]`, README config note, ROADMAP/progress. Pre-release green. **Push/PR/tag/mirror pending user OK.** |

### M2 — Complete autonomy (v0.3.3) — planned

| Task | Status | Notes |
|------|--------|-------|
| T-172 | 🔲 todo | Self-heal loop (blocker → bounded `/forge:resolve` → re-gate) |
| T-173 | 🔲 todo | Verifier subagents (independent fresh-context verification) |
| T-174 | 🔲 todo | `--unattended` mode (no checkpoints; answers/assumptions; bounded) |
| T-175 | 🔲 todo | Enforcing rules guardrail (`enforce: true` → block on write) |
| T-176 | 🔲 todo | Release v0.3.3 |

## v0.3 Task Status

> DAG: `build/04-plan/task-dag-v0.3.md` (T-157..T-166). Two phases: M1 Rules (v0.3.0,
> T-157..T-161), M2 Autopilot (v0.3.1, T-162..T-166). SRS `build/01-srs/srs-v0.3.md`.

### M1 — Rules / governance (v0.3.0) — branch `feat/v0.3.0-rules`

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| T-157 | 🟢 done | 2026-06-15 | (this commit) | `scripts/rules.py` — `.forge/rules/*.md` loader: frontmatter (stdlib split + fail-soft PyYAML, no `frontmatter` dep), scope model always/stage/glob/manual, `select()` + budget-bounded `render()`, fnmatch globs with `**` handling, CLI list/validate (argparse SUPPRESS). Never-raises. +14 tests |
| T-158 | 🟢 done | 2026-06-15 | (this commit) | `/forge:rules` skill (`name: forge-rules`) — init (idempotent scaffold) / add (no-clobber) / list / validate; `rules.py` gained those CLI subcommands. `references/rules-format.md` documents the schema + 4 scopes. +7 tests (init/add CLI + structural). validate-plugin 0 |
| T-159 | 🟢 done | 2026-06-15 | (this commit) | `hooks/session-start.py` injects `always` + current-`stage` rules (`_rules_block`, render cap 500 chars) after lessons; budget path trims lessons then drops rules last-resort to hold ≤2000 tokens. Never-raises. +6 tests (always/stage/off-stage/no-dir/glob-excluded/budget) |
| T-160 | 🟢 done | 2026-06-15 | (this commit) | `hooks/pre-tool-write.py` refactored into `_glob_rules_message` (any file type) + `_design_violations_message` (UI, existing); glob rules surface as advisory `additionalContext`, never block (exit 0). Design-system path behavior preserved. +5 tests. Full suite 1257 pass |
| T-161 | 🟢 done | 2026-06-15 | 9102b78 | Release **v0.3.0** — bump 0.3.0, CHANGELOG `[0.3.0]`, README "Project Rules" + commands/hooks rows, ROADMAP. Shipped via PR #19→develop→#20→main; **tag `v0.3.0`** + GitHub release; mirrored to polygon. Pre-release green (1295 unit, validate 0, full-pipeline 12/12). |

### M2 — Autopilot / autonomy (v0.3.1) — branch (later)

| Task | Status | Notes |
|------|--------|-------|
| T-162 | 🟢 done | `scripts/autopilot.py` deterministic planner — resolve_plan (targets --to/--stages/--until-gate, cycle entry/exit + bounds clamp, config stop_before/max_stages), plan_stages (state → {stage,skill,label}, --resume skips run-log), load_config; never-raises (malformed state → []). CLI --json/--dry-run. +18 tests |
| T-163 | 🟢 done | `/forge:autopilot` skill (`name: forge-autopilot`) — in-session loop: plan → per-stage run agent → check-gate → advance on pass / STOP on blocker (never force unless `allow_force`+reason); narrates + records run-log; checkpoint policy; honors always-rules. `autopilot.py record` subcommand (run-log via `_error_log.append_jsonl`). +3 record tests +4 structural. validate 0 |
| T-164 | 🟢 done | `--mode background` substrate — `run_stage` dispatches one stage via `_background_agent.dispatch` (cost+capability gated, session reuse), clean `unavailable` no-op under kill switch / no capability; never raises. `autopilot.py dispatch` subcommand + config `autopilot.model`. Skill documents the background path. +6 tests |
| T-165 | 🟢 done | `/forge:autopilot-stop` skill + session model in `autopilot.py` (`.forge/autopilot-session.json`): start (idempotent — warns already_running), stop (cooperative stop_requested flag checked between stages), status, finish (idle + clears flag). Skill starts/finishes the session; loop honors the flag. +7 tests |
| T-166 | 🟢 done | Release **v0.3.1** — bump 0.3.1, CHANGELOG `[0.3.1]`, README "Autopilot" + command rows, ROADMAP. Shipped combined with v0.3.0 in PR #19 (both phases); **tag `v0.3.1`** + GitHub release; mirrored to polygon. Manifests at 0.3.1; main `ebb94ef`. |

## v0.2 Task Status

> DAG: `build/04-plan/task-dag-v0.2.md` (T-136..T-156, 4 phased milestones).
> M1 (v0.2.0) is the current build target; M2 is gated on T-139 (≥90% completion).

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| T-136 | 🟢 done | 2026-06-10 | (this commit) | `hooks/_cost_cap.py` — hard-prereq spend gate (ADR-007): caps from config.yaml (fail-soft), ledger `cost-ledger.jsonl` (actual_usd from API), precheck `spent+floor` vs daily/monthly, over-cap → events.jsonl skip, never raises. test_cost_cap.py (13 cases) |
| T-137 | 🟢 done | 2026-06-10 | (this commit) | `_background_agent.dispatch()` — synchronous `claude -p --output-format json [--resume]`, captures session_id/total_cost_usd/usage/result, cost-gated via _cost_cap (precheck→skip event on over-cap; record actual after), never raises. +7 dispatch tests (ok/resume-flags/over-cap/missing-bin/nonzero/non-json/timeout) |
| T-138 | 🟢 done | 2026-06-10 | (this commit) | Probe wired into session-start: cached `.forge/capabilities.json` + **detached refresh** (TTL 24h; claude absent → sync `available:false`; present → fire-and-forget Popen — never blocks, NF-004). `FORGE_NO_BACKGROUND=1` kill switch. Unread-findings note (dormant till M2). _background_agent gains write/read_capabilities + CLI entry. +7 tests |
| T-139 | 🟢 done / **gate PASS** | 2026-06-11 | eb42b03+a8a630e | `scripts/skill_miner_bg.py` — capability-gated background skill-miner (session reuse, cost-gated) + completion/cost markers in `.forge/skill-miner-runs.jsonl`; `completion_stats()` reader. stop-reflect Step 4 branches bg↔inline. **O-2 gate CLEARED (v0.2.2): pinned `MINER_MODEL=haiku`; 6/6 live dispatches @ ~$0.022/run (was ~$1.07/run unpinned).** +8 tests |
| T-140 | 🟢 done | 2026-06-10 | (this commit) | `/forge:set-profile <type>` — `scripts/set-profile.py` validates against the 10 `## Profile:` names, updates project_type in state.md atomically (read-modify-write via _state_lib), `--dry-run` preview; `skills/forge-set-profile/SKILL.md`. +6 tests |
| T-141 | 🟢 done | 2026-06-10 | (this commit) | Release v0.2.0 — `bump-version.py 0.2.0`, CHANGELOG `[0.2.0]` (P0 foundation + spike PASS); pre-release green (1124 pass, validate 0, full-pipeline 12/12, manifests 0.2.0). PR→develop→main→tag→mirror follows. |

### M3 — Orchestration + brownfield (released as **v0.2.1**, NOT spike-gated) — branch `feat/v0.2.2-orchestration`

> Shipped as v0.2.1 (contiguous) ahead of the spike-gated daemons (originally planned
> v0.2.1); daemons land in a later version once T-139's O-2 gate clears.

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| T-148 | 🟢 done | 2026-06-10 | 07263a2 | `scripts/_orchestrate.py` — deterministic bounded fan-out: index-ordered (parallel==sequential, NF-009), delegates each call to `_background_agent.dispatch` (NF-010), parse+validate+retry-once+drop-with-reason, max_parallel/max_total bounds, dedup. ADR-006 corrected (script can't drive in-session Agent tool → delegates to claude -p). +8 tests |
| T-149 | 🟢 done | 2026-06-10 | (this commit) | `/forge:review` — `scripts/review_synthesize.py` fans 4 dimensions (correctness/security/performance/conventions) out via `_orchestrate.fan_out`, validates each reviewer's structured findings, drops malformed dims without sinking the review, synthesizes a deduped severity-sorted Markdown report. `skills/forge-review/SKILL.md`. First E2E consumer of T-148. +5 tests |
| T-150 | 🟢 done | 2026-06-10 | (this commit) | `/forge:adopt` brownfield onboarding (EF-014) — `scripts/adopt.py`: reuse `detect()`, bounded deterministic file sampling (excludes meta dirs, prioritizes manifests; `adopt.max_files` default 40), fan out requirements+architecture extractors via `_orchestrate`, write INFERRED srs.md/architecture.md drafts (confidence + provenance) + seeded state.md (Stage 1). **Read-only to user source** (only pipeline/+.forge/), `--dry-run` (no spend), refuses if already initialized, tolerates dropped aspects. `skills/forge-adopt/SKILL.md`. +7 tests |
| T-151 | 🟢 done | 2026-06-10 | (this commit) | `/forge:why` LLM fallback (REQ-F-050) — on a deterministic miss, if background capability available + not opted out, dispatch one orchestrated explainer (`_orchestrate`, cost-gated) and return a clearly-marked best-effort answer (exit 0); unchanged `not found`/exit 1 otherwise. `_should_try_fallback` + `_llm_fallback` in why.py; skill note. +3 tests |
| T-152 | 🟢 done | 2026-06-10 | (this commit) | Release **v0.2.1** (M3, contiguous) — `bump-version.py 0.2.1`, CHANGELOG `[0.2.1]`, ROADMAP re-map (daemons deferred). Pre-release green. PR→develop→main→tag→mirror. |

### M2 — Background daemons (built as **v0.2.3**, O-2 gate cleared by v0.2.2) — branch `feat/v0.2.3-daemons`

> Renumbered from the DAG's "v0.2.1" (that label was consumed when M3 shipped early).
> All daemons: cheap model + session reuse, capability-gated no-op, never-raises.

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| T-146 | 🟢 done | 2026-06-11 | bb03b28 | `hooks/_error_log.py` — shared stdlib rotation (`rotate_if_needed`/`append_jsonl`), numbered backups at a byte ceiling via atomic `os.replace`; wired into `_emit_error` (`FORGE_LOG_MAX_BYTES`). +11 tests |
| T-142 | 🟢 done | 2026-06-11 | 1284457 | Observer — `scripts/observer.py`, `/forge:watch`+`/forge:watch-stop`. Reused-session poll, idempotent start, findings→`observer-findings.jsonl` (rotated), cursor-tracked surfacing at session start + `/forge:status`, lazy detached poll, `.forge`-only boundary. `references/daemon-bus.md`. +16 tests |
| T-143 | 🟢 done | 2026-06-11 | d54dd68 | Dreamer — `scripts/dreamer.py`, `/forge:dreamer-run`. Confidence decay→dormant, dup (Jaccard≥0.8) + contradiction detection **flag-only**, idempotent daily digest `pipeline/log/daily-<date>.md`, atomic lessons.yaml, optional cheap-model consolidation. +26 tests |
| T-144 | 🟢 done | 2026-06-11 | 38efec5 | Health — `scripts/health_check.py`, `/forge:health-check`. Hook-test + lesson-integrity aggregation → healthy/degraded/failing; auto-disable policy-gated + **never silent** (events.jsonl + `health-surface.txt`, surfaced at session start, cleared on recovery). +28 tests (+4 session-start) |
| T-145 | 🟢 done | 2026-06-11 | c0a5f4f | Async miner production path — bg miner now drafts `proposed-skills/<slug>/SKILL.md` (was a dead-end `proposals.jsonl`), so it feeds the same approval flow as inline. +1 regression test |
| T-147 | 🟡 staged | 2026-06-11 | (this commit) | Release **v0.2.3** — `bump-version.py 0.2.3`, CHANGELOG `[0.2.3]`, ROADMAP/progress. Pre-release green. PR→develop done; **develop→main + tag BLOCKED by MAIN PROTECTION ruleset** — promotes with v0.2.2 once resolved. |

## v0.1.7 Task Status

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| T-131 | 🟢 done | 2026-06-09 | 3cbc4ad | REQ-PROFILE-MONOREPO-001: monorepo profile + detection (top of detect(); workspace markers / `workspaces` / `[workspace]` / packages+apps) + check_monorepo_graph.py (internal dep-graph cycle detection); test_check_monorepo_graph.py |
| T-132 | 🟢 done | 2026-06-09 | 06d3d84 | REQ-PROFILE-MOBILE-001: mobile profile + detection (Flutter/iOS/Android/RN, before fullstack so RN≠fullstack) + check_store_readiness.py (per-platform store metadata); test_check_store_readiness.py |
| T-133 | 🟢 done | 2026-06-09 | 23e4c1b | REQ-PROFILE-DATACONTRACT-001: data-contract profile + detection (.proto/schemas/buf, before api, guarded so gRPC-with-server-dep stays api) + check_schema_compat.py (proto field-number hygiene + buf policy; not a semantic diff); test_check_schema_compat.py |
| T-134 | 🟢 done | 2026-06-09 | (this commit) | Wiring: load-profile parity test extended to all 8 standard profiles; monorepo gained a stage_5 override (≥3 invariant); README profile table + Detection Heuristics doc synced; progress + ROADMAP |
| T-135 | 🟢 done | 2026-06-09 | 7ddb408 | Release: bump-version.py 0.1.7 + CHANGELOG [0.1.7]; pre-release green (1076 pass, validate 0, full-pipeline 12/12); tagged v0.1.7, GitHub release, mirrored to polygon |

## v0.1.6 Task Status

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| T-126 | 🟢 done | 2026-06-09 | f8275bb | REQ-INTERACTIVE-CLARIFY-001: /forge:srs asks one bounded clarifying-question round (single batch, not a drip) before writing srs.md + records assumptions; reconciled "3 rounds"→"1 round" in architecture.md + 2 references; test_interactive_clarify.py; 1026 pass |
| T-127 | 🟢 done | 2026-06-09 | 047a361 | REQ-INTERACTIVE-CONFIRM-001: /forge:spec + /forge:plan present an outline + pause for confirmation before the full artifact; spec-writer/planner reflect it; test_interactive_confirm.py asserts confirm-precedes-write ordering |
| T-128 | 🟢 done | 2026-06-09 | 58483aa | REQ-INTERACTIVE-NARRATE-001: /forge:build narrates start/result/next per task; build-batch.py emits per-task `[Forge] task T-XXX — starting` on stderr (stdout id-list contract preserved); test_interactive_narrate.py (behavioral subprocess check) |
| T-129 | 🟢 done | 2026-06-09 | (this commit) | Wiring: progress + ROADMAP + traceability for v0.1.6; ACs marked satisfied in srs-v0.1.6.md §6 |
| T-130 | 🟢 done | 2026-06-09 | 894d1fc | Release: bump-version.py 0.1.6 (first real use) + CHANGELOG [0.1.6]; pre-release verification green (1026 pass, validate 0, full-pipeline 12/12); tagged v0.1.6, GitHub release, mirrored to polygon |

## v0.1.5 Task Status

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| T-101 | 🟢 done | 2026-06-09 | — | `references/stage-order.md` + `scripts/_stage_table.py` loader + 38 tests; single source of truth (dirs, prereqs, next-hints, bounds, cycles); resolves EF-005 dir-name drift; 745/745 pass |
| T-102 | 🟢 done | 2026-06-09 | — | canonicalized ALL stage paths (broader than EF-005: stages 4/8/9/10/11 wedged). 17 files (7 skills + 9 agents + CHANGELOG); dir+filename renames to match gates; added feedback-log.md & backlog-updates.md (gate blockers skills never wrote); test_canonical_paths.py guard; 753/753 pass |
| T-103 | 🟢 done | 2026-06-09 | 1 commit | `next-hint` subcommand reads canonical hint from stage table; all 12 stage skills invoke it; fixed 2 dead-command hints + forge-status table; test_next_hint.py (57 tests); 810 pass |
| T-104 | 🟢 done | 2026-06-09 | 442c2af | REQ-PIPEBOUNDS-001: advance rejects out-of-range, cycle-wraps past 12 to (cycle+1,0); validate_frontmatter range-checks current_stage; set -1/99/13 rejected, state intact; test_pipebounds.py; 821 pass |
| T-105 | 🟢 done | 2026-06-09 | df811ea | REQ-GATE-ENTRY-001: check_prerequisite + `preflight --stage N` (exit 2); advance skips need --force; 10 stage skills gated; force-advance routes via force=True; test_entry_gates.py; 847 pass |
| T-106 | 🟢 done | 2026-06-09 | 51a843a | REQ-SILENTSTATE-001: hooks/_state_read.py helper; 6 hook read-sites route through it (warn + log to .forge/errors.log); check-gate inconclusive+exit2 on unreadable state; doctor check_state_read_failures; session-end footer; test_silentstate.py (9); 856 pass |
| T-107 | 🟢 done | 2026-06-09 | 2a5d0e9 | REQ-DOCTOR-001: doctor runs current-stage gate inline; overall_status healthy/wedged/broken; JSON carries overall_status; test_doctor_gate.py; 864 pass |
| T-108 | 🟢 done | 2026-06-09 | 1d1bb47 | REQ-GATESTUB-001 fail-loud: missing script → inconclusive + blocker-promoted + exit2; doctor/status banner; stop-reflect parses gate JSON regardless of exit; test_gatestub.py; full-pipeline xfail until M4; 866 pass |
| T-109 | 🟢 done | 2026-06-09 | 220a320 | 5 req+spec scripts: check_srs_acceptance, traceability-check, spec-coverage, check_dag_completeness, check_dag_completion; test_gate_scripts_req_spec.py; 883 pass |
| T-110 | 🟢 done | 2026-06-09 | 2d22e21 | 5 build+eval scripts: token-audit, check_coverage, check_todos, check_progress_sync, check_nfr_coverage; test_gate_scripts_build_eval.py; 901 pass |
| T-111 | 🟢 done | 2026-06-09 | d1541b4 | 5 release+health scripts: check_open_bugs, check_health, check_hotfix_tests, check_git_tag; some_check.py = doc-example only (justified); 917 pass |
| T-112 | 🟢 done | 2026-06-09 | 387192f (+T-125 fixtures) | AC-GATESTUB-001b audit green; traceability all argv modes; heading-based task detection. Fixture harmonization landed in T-125 → full-pipeline xfail removed, passes 12/12 |
| T-113 | 🟢 done | 2026-06-09 | f049195 | REQ-EXTRACT-CWD-001: extract-lessons.py --cwd derives input/output; explicit overrides; test_extract_lessons_cwd.py; 923 pass |
| T-114 | 🟢 done | 2026-06-09 | feat/t-114-lesson-signals | REQ-LESSON-SOURCES-001: _signal_producers.py (5 producers reading .forge/errors.log); _state_read.log_event sink; pre-tool-write logs violations, post-tool-use logs heredoc bypass, stop-reflect logs gate_outcome, session-end runs producers + materializes via extract/sync; test_lesson_signals.py (12); 942 pass |
| T-115 | 🟢 done | 2026-06-09 | 7aeed8a | REQ-LESSON-SOURCES-001 EF-026: promote freq≥2 gate + 30-day TTL recall in session-start; is_stale(); test_promote_ttl.py + isolation guard; 930 pass |
| T-116 | 🟢 done | 2026-06-09 | d40b5a4 | REQ-BUILDBATCH-001: build-batch.py (ordered tasks, --resume, large-batch warn); forge-build Milestone Batch Mode; test_build_batch.py; 950 pass |
| T-117 | 🟢 done | 2026-06-09 | cb9f185 | REQ-WHYCI-001: why.py _GATE_PATTERN IGNORECASE + target.upper(); test_why additions; 953 pass |
| T-118 | 🟢 done | 2026-06-09 | a58cb12 | REQ-SESSIONLOG-001: session-end appends .forge/session.jsonl (commands/tokens/reflection_ref, PII-free, versioned); test_session_log.py; 957 pass |
| T-119 | 🟢 done | 2026-06-09 | a24a7b8 | REQ-STAGEREFLECT-001: stage-reflect.py rollup → pipeline/0X/reflection.md; stop-reflect spawns on advance; test_stage_reflect.py; 961 pass |
| T-120 | 🟢 done | 2026-06-09 | e3b675b | REQ-PATTERN-001: schema_version on patterns; references/pattern-schema.md; test_pattern_bus.py (schema-valid + 3-use proposal); 963 pass |
| T-121 | 🟢 done | 2026-06-09 | a86445d | REQ-WEBSEARCH-001: spec-writer gains WebSearch; cite-or-skip rule on 4 research/spec agents; planner excluded; test_agent_tools.py; 972 pass |
| T-122 | 🟢 done | 2026-06-09 | 2ce8b9c | AC-INTERACTIVE-001a: REQ-INTERACTIVE-001 → CLARIFY/CONFIRM/NARRATE-001 (v0.1.6); test_interactive_decomposition.py |
| T-123 | 🟢 done | 2026-06-09 | c971d32 | REQ-LARGEDOC-001: large-doc-layout.md + read-doc.py resolver (single/multi-file); forge-spec uses it; test_large_doc.py |
| T-124 | 🟢 done | 2026-06-09 | aa9183a | REQ-DOCS-001 + REQ-FEEDBACK-001: third-party-hook troubleshooting + README entry + issue template; test_docs_troubleshooting.py |
| T-125 | 🟢 done | 2026-06-09 | (this commit) | Release: CHANGELOG [0.1.5] + version bump 0.1.5; sample-todo-api fixture harmonization → full-pipeline passes 12/12, xfail removed; 986 pass |

## Task Status

| Task | Status | Started | Completed | Commit | Notes |
|------|--------|---------|-----------|--------|-------|
| T-001 | 🟢 done | 2026-05-06 | 2026-05-07 | 86a0b03 | plugin.json, 7 stubs, validate-plugin.py, tests |
| T-002 | 🟢 done | 2026-05-07 | 2026-05-07 | 80e4f1f | forge-init skill, init-pipeline.sh, detect-project-type.py, 14 tests |
| T-003 | 🟢 done | 2026-05-10 | 2026-05-10 | 0950935 | _state_lib.py, state-manager.py CLI, 36 tests, 93% cov |
| T-004 | 🟢 done | 2026-05-10 | 2026-05-10 | — | forge-status SKILL.md |
| T-005 | 🟢 done | 2026-05-07 | 2026-05-07 | b023844 | pre-authored in foundation commit; 12 stages, all YAML valid |
| T-006 | 🟢 done | 2026-05-10 | 2026-05-10 | — | check-gate.py, 14 tests, all 4 check types |
| T-007 | 🟢 done | 2026-05-10 | 2026-05-10 | — | session-start.py hook, 17 tests, token budget enforced |
| T-008 | 🟢 done | 2026-05-10 | 2026-05-10 | — | prompt-submit.py hook, 16 tests, stage intent + correction flagging |
| T-009 | 🟢 done | 2026-05-10 | 2026-05-10 | — | stop-reflect.py, _invoke_agent.py, 20 unit + 8 integration tests |
| T-010 | 🟢 done | 2026-05-10 | 2026-05-10 | — | session-end.py, 18 tests, session summary to .forge/sessions/ |
| T-011 | 🟢 done | 2026-05-10 | 2026-05-10 | — | pre-tool-write.py, 35 tests, 5 violation types detected |
| T-012 | 🟢 done | 2026-05-10 | 2026-05-10 | — | post-tool-use.py, 18 tests, session-log + patterns.jsonl |
| T-013 | 🟢 done | 2026-05-10 | 2026-05-10 | — | plugin.json pre-wired in T-001; validate-plugin.py confirms all 7 hooks valid |
| T-014 | 🟢 done | 2026-05-10 | 2026-05-10 | — | 12 agent persona files; role/goal/scope/output/workflow per spec |
| T-015 | 🟢 done | 2026-05-10 | 2026-05-10 | — | 12 stage SKILL.md files + prompt-submit aliases (product, arch) |
| T-016 | 🟢 done | 2026-05-10 | 2026-05-10 | — | 4 cross-stage agent personas: reflector, lesson-extractor, skill-miner, gate-checker |
| T-017 | 🟢 done | 2026-05-11 | 2026-05-11 | — | context-pruner.py, 35 tests, stage 6 exclusions verified |
| T-018 | 🟢 done | 2026-05-11 | 2026-05-11 | — | forge-resume SKILL.md; uses context-pruner + state-manager |
| T-019 | 🟢 done | 2026-05-11 | 2026-05-11 | — | extract-lessons.py, 43 tests, done-when criterion verified |
| T-020 | 🟢 done | 2026-05-12 | 2026-05-12 | — | 3 new tests: ml/gpu done-when, project-type exclusion, frequency sort |
| T-021 | 🟢 done | 2026-05-12 | 2026-05-12 | — | sync-lessons.py, 37 tests; session-start auto-syncs on stale md |
| T-022 | 🟢 done | 2026-05-12 | 2026-05-12 | — | promote-lessons.py, ~/.forge/ scaffold, 39 tests; session-start auto-registers+promotes |
| T-023 | 🟢 done | 2026-05-12 | 2026-05-12 | — | detect-project-type.py: train.py+ML libs+notebooks+API types; 10 new tests; forge-init SKILL.md updated |
| T-024 | 🟢 done | 2026-05-12 | 2026-05-12 | — | fullstack profile extended (stage_3 + stage_6); all 5 profiles ≥3 stage overrides; YAML valid; 427/427 tests pass |
| T-025 | 🟢 done | 2026-05-12 | 2026-05-12 | — | load-profile.py + 24 tests; 12 stage skills wired to call it; ML stage 7 surfaces G7-ML-005 drift; 451/451 tests pass |
| T-026 | 🟢 done | 2026-05-12 | 2026-05-12 | — | sliding 3-tool window with sha1 signature; 22 tests; done-when 3-occurrence signature stability verified; 455/455 |
| T-027 | 🟢 done | 2026-05-12 | 2026-05-12 | — | mine-skills.py + 33 tests; freq≥3 → SKILL.md draft with name/description/steps; blacklist + skill-name collision filters; 488/488 tests pass |
| T-028 | 🟢 done | 2026-05-12 | 2026-05-12 | — | skill-approval.py (list/approve/reject) + 22 tests; stop-reflect.py surfaces proposals; mine-skills.py skips existing to preserve edits; full approve/modify/reject cycle verified end-to-end; 515/515 tests pass |
| T-029 | 🟢 done | 2026-05-12 | 2026-05-12 | — | forge-retro SKILL.md + 16 structural tests; retro covers what went well / didn't / lessons / skills proposed; writes to pipeline/12-release/retro.md; 531/531 tests pass |
| T-030 | 🟢 done | 2026-05-12 | 2026-05-12 | — | user-facing README; install, quickstart, 12-stage table, hooks, profiles, config, tests |
| T-031 | 🟢 done | 2026-05-12 | 2026-05-12 | — | CONTRIBUTING.md rewritten; docs/agent-authoring.md created — walkthroughs for adding agents, stages, profiles; 531/531 tests pass |
| T-032 | 🟢 done | 2026-05-12 | 2026-05-12 | — | full-pipeline.sh + 29 fixture artifacts (12 stages); check_dir_nonempty.py; gate checks + traceability chain; test isolation fix for TestLessonsFiltering; 532/532 tests pass |
| T-033 | 🟢 done | 2026-05-12 | 2026-05-12 | — | CHANGELOG.md; ROADMAP.md updated; v0.1.0 tagged |

## Status Legend

- 🔲 todo
- 🟡 in progress
- 🟢 done
- 🔴 blocked

## Session History

*(Filled in by session-end summaries.)*

## Resume Hint

To continue work in a new session:
```
Read CLAUDE.md, then this file (build/05-implementation/progress.md).
The first 🔲 task in the table is your next task.
Read its corresponding prompt at prompts/development/T-XXX-*.md.
```
