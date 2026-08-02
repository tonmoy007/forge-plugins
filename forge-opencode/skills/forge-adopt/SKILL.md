---
name: forge-adopt
description: >
  Onboard an EXISTING codebase into Forge (brownfield adoption). Use when the
  user runs /forge:adopt, wants to start using Forge on a project that already has code,
  says "adopt this repo", "set up Forge on my existing project", "reverse-engineer the
  requirements/architecture", or asks to bring a legacy/brownfield codebase into the
  pipeline. Pass --dry-run to preview without writing. Distinct from /forge:init, which
  scaffolds a greenfield pipeline.
tools:
  read: true
  write: true
  bash: true
  web-search: true
  web-fetch: true
---

# forge-adopt

Bring an existing codebase into the Forge pipeline. Adopt detects the project type,
samples a bounded set of files, fans out extractors to **infer** an SRS and an
architecture map, seeds `pipeline/state.md`, and enters the normal 12-stage flow at
Stage 1 so you confirm the inferred artifacts before building on them.

## When to Use

- User runs `/forge:adopt` on a repo that already has code
- User wants reverse-engineered SRS / architecture drafts to start from
- The project predates Forge and needs onboarding (not greenfield `/forge:init`)

## Guarantees

- **Read-only to your source.** Adopt writes ONLY under `pipeline/` and `.forge/` — it
  never modifies your code.
- **Everything is marked INFERRED** with a confidence score and the files it was derived
  from. Forge proposes; you confirm.
- **Bounded.** Sampling is capped (`adopt.max_files`, default 40); what was sampled vs
  skipped is reported — no silent truncation.
- Refuses if `pipeline/state.md` already exists (that project is already initialized).

## How to run

Preview first — `--dry-run` reports the plan and spends nothing:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/adopt.py --cwd . --dry-run
```

Then run it for real (fans the extractors out via the orchestration primitive; the
dimensions are cost-gated):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/adopt.py --cwd .
```

It prints a JSON summary (`project_type`, `sampled`/`skipped`, `written`,
`dropped_aspects`, `cost_usd`). Relay it, then tell the user the inferred drafts under
`pipeline/01-srs/` and `pipeline/03-architecture/` are **drafts to confirm**, and that
the pipeline is seeded at Stage 1. If any aspect was dropped, say so — don't imply full
coverage. From here, `/forge:srs` / `/forge:architecture` refine the drafts with gates
intact.
