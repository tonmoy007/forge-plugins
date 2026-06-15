# Forge across machines — `~/.forge` sync + telemetry

> v0.3.4 (M4). Forge has **no server** and phones home for **nothing**. This doc explains
> which Forge state is safe to sync across your machines, and how the (default-off,
> local-only) skill-mining telemetry works. Both are entirely opt-in.

---

## What Forge stores, and where

Forge keeps two kinds of state:

| Scope | Location | What | Sync? |
| --- | --- | --- | --- |
| **Global (cross-project)** | `~/.forge/` | `global-lessons.yaml`, `projects.yaml` | **Yes — portable** |
| **Per-project** | `<project>/.forge/` | caches, ledgers, run-logs, telemetry | **No — machine-local** |
| **Per-project (versioned)** | `<project>/pipeline/`, `.forge/rules/` | pipeline artifacts, user rules | Already in git |

`pipeline/` and `.forge/rules/` ride in your repo, so they sync the normal way (commit +
push). This doc is about the rest.

---

## Syncing `~/.forge/` (global lessons + registry)

`~/.forge/` accumulates lessons that have graduated to cross-project scope
(`promote-lessons.py`) plus the registry of projects they came from. These are the files
worth carrying between machines:

```
~/.forge/
├── global-lessons.yaml   # portable — graduated cross-project lessons
└── projects.yaml         # registry of project paths (see caveat below)
```

### A conflict-safe layout (no server)

You can sync `~/.forge/` with any file-sync tool (Syncthing, Dropbox, a private git repo,
`rsync`). To keep it conflict-safe:

1. **Sync `global-lessons.yaml`; treat `projects.yaml` as machine-local.** The registry
   holds **absolute project paths**, which differ per machine (`/home/you/...` vs
   `/Users/you/...`). Syncing it creates dangling entries. Prefer re-running
   `promote-lessons.py --register <path>` on each machine, or keep a per-machine
   `projects.yaml`.

2. **Sync at rest, not mid-write.** Forge writes `global-lessons.yaml` atomically (temp +
   `os.replace`), so a sync that copies the whole file is always internally consistent.
   Avoid syncing during an active `/forge:*` run if your tool does partial-file deltas.

3. **On a conflict, merge by lesson identity.** `global-lessons.yaml` is a flat
   `lessons:` list keyed by trigger text. If two machines edit it, keep the **union** of
   lessons (drop exact-duplicate triggers); no entry depends on another, so a union never
   corrupts the file. Re-running `promote-lessons.py` afterward re-derives counts cleanly.

4. **A private git repo is the most robust option** — `cd ~/.forge && git init`, commit
   `global-lessons.yaml`, and let git's 3-way merge handle the list. Add `projects.yaml`,
   `*.tmp`, and any caches to `.gitignore`.

Recommended `~/.forge/.gitignore`:

```gitignore
projects.yaml      # machine-local absolute paths
*.tmp
```

### Do **not** sync per-project `.forge/`

Each project's `.forge/` is **machine-local scratch** and should stay out of sync (and out
of git — Forge's `.gitignore` already excludes it):

- `capabilities.json` — probed per machine/CLI version
- `cost-ledger.*` — local spend accounting
- `autopilot-runs.jsonl`, `autopilot-session.json` — local run state
- `telemetry.jsonl`, `telemetry-enabled` — see below
- `hook-errors.log`

Syncing these across machines produces misleading caches and ledgers. Leave them local.

---

## Skill-mining telemetry (opt-in, local-only)

Forge can mine repeated tool sequences into proposed skills. **By default it records no
telemetry about this.** If you want local insight into what gets mined and which proposals
you accept, you can opt in — the data **never leaves your machine** unless you explicitly
export it.

```bash
# Status (default: disabled)
python3 scripts/telemetry.py status --cwd .

# Opt in / out (writes/removes .forge/telemetry-enabled)
python3 scripts/telemetry.py enable  --cwd .
python3 scripts/telemetry.py disable --cwd .

# While enabled, the skill-mining path records events to .forge/telemetry.jsonl
python3 scripts/telemetry.py summary --cwd .     # local counts by event

# The ONLY way data leaves the machine — you run it, you see it, you decide:
python3 scripts/telemetry.py export  --cwd . > my-telemetry.json
```

You can also opt in via config instead of the marker file:

```yaml
# .forge/config.yaml
telemetry:
  enabled: true
```

### Guarantees

- **Default off.** No opt-in → `record()` is a no-op and no `telemetry.jsonl` is created.
- **Local-only.** Events are appended to `.forge/telemetry.jsonl` in your project. Forge
  has no network code path for telemetry; nothing is transmitted, ever.
- **Explicit export.** Data leaves the machine only through `telemetry.py export`, which
  prints to stdout for you to redirect — never automatically.
- **Fail-soft.** Telemetry recording never raises and never blocks the skill-mining path;
  a write failure is silently dropped.

Since `telemetry.jsonl` lives in the per-project `.forge/` (machine-local, not synced),
your telemetry stays on the machine that produced it.
