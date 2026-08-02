# Orchestration config (`.forge/config.yaml` → `orchestration:`)

> Loaded on demand. Documents the opt-in `orchestration:` block that gates the v0.4.0 dynamic
> workflow engine's higher-level capabilities (REQ-WF-003). Loaded by
> `scripts/_workflow_config.py:load_orchestration_config`. **Opt-in**: every toggle defaults to
> `false`, so with no block (or an empty one) Forge behaves exactly as v0.3.6 (REQ-NF-025).

## What the engine is vs. what the toggles gate

The DAG engine itself (`scripts/_workflow.py`) is **always available** — there is no toggle to
turn it on. The `orchestration:` toggles gate the *features built on top of it*: user-defined
flows, per-stage parallel build, worktree isolation, and generated sub-DAGs. They are
**independent** — any combination is valid; turning one on never implies another.

## The block

```yaml
orchestration:
  # --- independent capability toggles (all default false) ---
  flows_enabled: false           # enable /forge:flow + .forge/workflows/*.yaml  (T-195)
  parallel_build: false          # fan out independent build tasks in parallel    (T-196)
  worktree_isolation: false      # each parallel mutating node in its own worktree (T-197)
  allow_generated_subdags: false # permit the validated `decompose` sub-DAG node   (T-200)

  # --- engine tunables ---
  max_parallel: 4                # max concurrent dispatches per wave
  max_total: 64                  # hard cap on total nodes admitted per run
  max_budget_usd:                # optional per-run spend ceiling (omit / null = no cap)
```

## Defaults & coercion

| Key                       | Type   | Default | Notes |
|---------------------------|--------|---------|-------|
| `flows_enabled`           | bool   | `false` | only a real bool `true` enables it (`1`/`"yes"` do **not**) |
| `parallel_build`          | bool   | `false` | same strict `is True` semantics |
| `worktree_isolation`      | bool   | `false` | same |
| `allow_generated_subdags` | bool   | `false` | same |
| `max_parallel`            | int ≥1 | `4`     | non-positive / non-int → default |
| `max_total`               | int ≥1 | `64`    | non-positive / non-int → default |
| `max_budget_usd`          | float  | `null`  | unparseable → `null` (no cap) |

## Fail-soft guarantees

Loading mirrors `autopilot.load_config` exactly: an absent `config.yaml`, malformed YAML, or a
non-mapping `orchestration:` value all yield **all-default** config. An invalid **individual**
value falls back to that key's default while valid sibling keys survive — e.g.
`max_parallel: banana` with `max_total: 100` yields `max_parallel=4, max_total=100`. PyYAML is
guarded: if the library is unavailable, the loader returns defaults rather than raising. The
loader **never raises** (REQ-NF-024).
