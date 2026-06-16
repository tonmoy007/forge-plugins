# Skill Mining — semantic, success-gated workflow induction (v0.3.5)

> Loaded on demand. Defines how Forge mines reusable skills from your own session
> traces: the **semantic, success-gated, anti-unification** pipeline that replaced
> the v1 tool-name n-gram miner (REQ-SM-001…010). Driven by `scripts/skill_miner_bg.py`
> (dispatched detached by `hooks/stop-reflect.py`); deterministic stages live in
> `scripts/_trace_semantics.py` + `scripts/skill_miner_v2.py`. Proposals are
> reviewed with `scripts/skill-approval.py`.

## What it does

When a Claude turn ends, Forge looks at what you *actually did* and asks: did a
coherent, repeatable, **successful** workflow recur? If so, it drafts a reusable
skill and surfaces it for approval. Nothing installs without you.

The richer signal it mines is captured by `hooks/post-tool-use.py`, which writes
`.forge/session-log.jsonl` (`{tool, file, command, success, stage, session}` per
call). The miner reads that log — not the opaque tool-name stream — so it can
reason about *intent*, not just *which tool ran*.

## The pipeline

```
.forge/session-log.jsonl
   │  read_session_log        (fail-soft reader)
   ▼
enrich                        (tool call → semantic verb)
   │   e.g. pytest exit≠0           → run-tests(fail)
   │        Edit(src/*) after fail  → patch
   │        Write(test_*) after green → add-regression-test
   ▼
segment                       (outcome-bounded episodes; failure→fix is the boundary)
   ▼
mine_candidates               (success + distinct-recurrence + anti-unification gate)
   ▼
induce                        (cheap-model de-specialization → named, documented skill;
   │                           degrades to deterministic skeleton)
   ▼
write_proposals               (.forge/proposed-skills/<slug>/SKILL.md)
```

| stage | module | REQ |
| --- | --- | --- |
| enrich + segment | `scripts/_trace_semantics.py` | REQ-SM-001, 002 |
| mine_candidates | `scripts/skill_miner_v2.py` (+ `_antiunify.py`) | REQ-SM-003, 004 |
| induce | `scripts/skill_miner_v2.py` | REQ-SM-005 |
| write_proposals | `scripts/skill_miner_v2.py` | REQ-SM-006 |
| drive (detached) | `scripts/skill_miner_bg.py` | REQ-SM-010 |

## The gates (why most things are *not* mined)

A motif becomes a candidate only when **all three** hold:

1. **Success.** Its source episodes ended in success (a passing test run, per
   `session-log` `success`/exit). A motif that recurs only in failed episodes is
   never promoted — bare frequency is never sufficient (REQ-SM-004).
2. **Distinct recurrence.** It recurs across **≥3 distinct successful episodes**
   (`MIN_DISTINCT_EPISODES`), not 3 occurrences in one run.
3. **Anti-unification coherence.** Its instances must anti-unify into a coherent
   parameterized skeleton — differing literals (file names, test names, error
   strings) lift to parameters; identical diverging values map to the same
   variable. *If a recurring fragment cannot anti-unify into a coherent procedure,
   it is not a skill.* This is the filter that replaces n-gram counting:
   `Bash/Read/Write` that merely co-occur with no shared shape produce nothing
   (REQ-SM-003).

## The proposal artifact

Each promoted candidate is written as **`.forge/proposed-skills/<slug>/SKILL.md`**
in the agentskills.io format:

```markdown
---
name: <kebab-case-name>
description: <one-line, THIRD-PERSON — what it does AND when to use it>
status: proposed
---

# <name> (proposed)

## When to Use
## Procedure
## Pitfalls
## Verification
## Provenance
- Pattern signature: `<verb->verb->verb motif>`
- Distinct successful episodes: N
- Source-trace citations: ...
```

- The **`description`** is the retrieval key — third-person, discoverable. Forge
  never stores an anonymous abstraction (LILO); every proposal is named and
  documented, with citations to the source trace lines that justify it.
- The **`Pattern signature:`** line (the verb motif) is what the blacklist keys on,
  so rejecting a proposal blocks that motif from being re-proposed.

There is **no `.forge/proposals.jsonl`** — that was a documentation artifact that
never existed in code. The canonical (and only) proposal artifact is the
`SKILL.md` above.

## Approval flow

The Stop hook lists pending proposals at the end of a turn; review and act:

```bash
# inspect: .forge/proposed-skills/<slug>/SKILL.md
python3 scripts/skill-approval.py approve --slug <slug>   # install into skills/
python3 scripts/skill-approval.py reject  --slug <slug>   # blacklist the signature
```

Nothing installs without explicit approval (REQ-NF-019).

## Graceful degradation (the non-negotiables)

- **Deterministic core, never raises.** Enrichment, segmentation, and
  anti-unification are pure stdlib and run on the hot/background path. A missing,
  empty, or malformed `session-log.jsonl` yields zero proposals, never an exception
  (REQ-NF-016).
- **LLM induction is an enhancement, not a dependency.** With no background/LLM
  capability, under `FORGE_NO_BACKGROUND=1`, or on any dispatch failure, the
  deterministic anti-unified **skeleton** is emitted as the proposal
  (`source: deterministic`) — still named, still inspectable (REQ-NF-017).
- **Bounded & gated.** The single induction call is pinned to a cheap model
  (`haiku`), capped by `_cost_cap` + `--max-budget-usd`, and writes only under
  `.forge/` (REQ-NF-018).
- **Clean migration.** Existing `.forge/proposed-skills/` directories are preserved
  (a slug that already exists is never overwritten) and
  `.forge/skill-blacklist.txt` signatures are honored — so retiring the n-gram path
  loses no prior state (REQ-SM-010).

## Relationship to other Forge mechanisms

- **Lessons** (`tasks/lessons.md`) capture *corrections* to avoid; mined **skills**
  capture *successful procedures* to reuse. Different signals, both human-gated.
- **Gates** (`references/gate-criteria.md`) block stage exit; skill mining is purely
  advisory — it proposes, it never blocks.
- **`/forge:skill-creator`** (REQ-SM-007) takes a candidate and runs the author →
  test → optimize-description loop **in-session** (ADR-006: hooks/scripts cannot
  spawn the authoring agent), since the description is the retrieval key.
