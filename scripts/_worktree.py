#!/usr/bin/env python3
"""Git-worktree isolation + lifecycle for parallel build (v0.4.0, REQ-WF-008 / T-197).

When the build stage fans independent task-DAG nodes out in parallel (`parallel_build.py`), two
nodes mutating the same file in one checkout would silently clobber each other. These helpers give
each file-mutating node its **own git worktree** on a **branch-per-node** (NEVER `main`/`develop`,
per the repo branch rules) created from a clean committed base; the node commits its work there;
results merge back at a join where **git surfaces conflicts** (a conflicting merge fails loudly and
is aborted — never silent last-write-wins). Worktrees are torn down on success AND on any
drop/crash, so there are no orphaned `.git/worktrees` entries.

Design rules (REQ-NF-024/028):
  - Stdlib only (subprocess, shutil). **Never raises** — every helper returns a `WorktreeResult`
    (or, for `add`, a `WorktreeHandle`) with `ok`/`reason`. A timeout, OS error, or git failure is
    a structured non-ok result, not an exception.
  - Capability-gated: `worktrees_available` probes; the caller degrades to a single shared worktree
    (sequential) when worktrees are unavailable.
  - The branch name is derived from the node id but always namespaced under `forge/wt/…`, so it can
    never collide with — or move — a protected branch.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Per-node branches/worktrees live under this namespace so they can never be (or move) a protected
# branch — even a node literally named "main" becomes `forge/wt/main`, distinct from `main`.
_BRANCH_PREFIX = "forge/wt/"
_WORKTREE_DIRNAME = ".forge-worktrees"  # sibling-of-repo holding per-node checkouts
_GIT_TIMEOUT = 60.0


@dataclass
class WorktreeHandle:
    """A created (or failed) per-node worktree."""

    node_id: str
    path: str
    branch: str
    ok: bool
    reason: str = ""


@dataclass
class WorktreeResult:
    """Outcome of a commit / merge / remove. `conflict` distinguishes a merge conflict (the
    intended loud-failure path) from other failures."""

    ok: bool
    reason: str = ""
    conflict: bool = False


def _git(repo, *args: str, timeout: float = _GIT_TIMEOUT) -> tuple:
    """Run a git command in `repo`. Returns (returncode, stdout, stderr); never raises."""
    bin_ = shutil.which("git")
    if not bin_:
        return 127, "", "git not found on PATH"
    try:
        proc = subprocess.run(
            [bin_, *args], cwd=str(repo), stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "git timeout"
    except OSError as exc:  # noqa: BLE001 — missing/unexecutable binary, bad cwd, etc.
        return 127, "", str(exc)


def worktrees_available(repo) -> bool:
    """True when `repo` is inside a git work tree and git is present. Never raises."""
    rc, out, _ = _git(repo, "rev-parse", "--is-inside-work-tree")
    return rc == 0 and out.strip() == "true"


def _safe_node_segment(node_id: str) -> str:
    """A filesystem/branch-safe segment derived from a node id (git refs forbid many chars)."""
    seg = re.sub(r"[^A-Za-z0-9._-]", "-", str(node_id)).strip("-/.") or "node"
    return seg


def _current_branch(repo) -> Optional[str]:
    rc, out, _ = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    return out.strip() if rc == 0 else None


def add(repo, node_id: str, *, base: Optional[str] = None) -> WorktreeHandle:
    """Create a worktree for `node_id` on a fresh branch-per-node off `base` (default: HEAD of
    `repo`). The branch is namespaced under ``forge/wt/`` so it is never `main`/`develop`. The
    worktree checkout lives under ``<repo>/.forge-worktrees/<node>``. Never raises — any failure
    yields a handle with ``ok=False`` and a reason and no partial worktree left behind."""
    repo = Path(repo)
    branch = _BRANCH_PREFIX + _safe_node_segment(node_id)
    wt_path = repo / _WORKTREE_DIRNAME / _safe_node_segment(node_id)

    if not worktrees_available(repo):
        return WorktreeHandle(node_id, str(wt_path), branch, ok=False,
                              reason="worktrees unavailable (not a git work tree)")

    start_point = base if base is not None else "HEAD"
    # `git worktree add -b <branch> <path> <start>` creates the branch AND checkout atomically;
    # it refuses if <branch> already exists, so a stale run is reported (not silently reused).
    rc, _out, err = _git(repo, "worktree", "add", "-b", branch, str(wt_path), start_point)
    if rc != 0:
        detail = (err or "").strip().splitlines()
        return WorktreeHandle(node_id, str(wt_path), branch, ok=False,
                              reason=f"worktree add failed: {detail[0] if detail else f'exit {rc}'}")
    return WorktreeHandle(node_id, str(wt_path), branch, ok=True)


def commit(handle: WorktreeHandle, *, message: str) -> WorktreeResult:
    """Stage and commit all of the node's work in its own worktree. An empty change set is a
    clean no-op (``ok=True``), not a failure — a node may legitimately mutate nothing. Never
    raises."""
    if not handle.ok:
        return WorktreeResult(False, "handle is not ok")
    wt = handle.path
    rc, _o, err = _git(wt, "add", "-A")
    if rc != 0:
        return WorktreeResult(False, f"git add failed: {(err or '').strip()[:200]}")
    # Nothing staged ⇒ a clean no-op (not an error). `git diff --cached --quiet` exits 1 when
    # there ARE staged changes, 0 when there are none.
    rc_diff, _o2, _e2 = _git(wt, "diff", "--cached", "--quiet")
    if rc_diff == 0:
        return WorktreeResult(True, "nothing to commit")
    rc_c, _o3, err_c = _git(wt, "commit", "-m", message)
    if rc_c != 0:
        return WorktreeResult(False, f"commit failed: {(err_c or '').strip()[:200]}")
    return WorktreeResult(True, "committed")


def merge(repo, handle: WorktreeHandle, *, into: Optional[str] = None) -> WorktreeResult:
    """Merge the node's branch into `into` (default: the repo's current branch) at the join. A
    clean merge applies the node's commits; a **conflicting** merge fails loudly — it is aborted
    (`git merge --abort`) so the base ref is left untouched (never silent last-write-wins) and
    `conflict=True` is returned. Never raises."""
    if not handle.ok:
        return WorktreeResult(False, "handle is not ok")
    repo = Path(repo)

    if into is not None:
        cur = _current_branch(repo)
        if cur != into:
            rc_co, _o, err_co = _git(repo, "checkout", into)
            if rc_co != 0:
                return WorktreeResult(False, f"checkout {into} failed: {(err_co or '').strip()[:200]}")

    # `--no-ff` keeps the join explicit; a conflict returns non-zero and leaves the tree
    # conflicted, which we then abort so the base is untouched.
    rc, _out, err = _git(repo, "merge", "--no-ff", "-m",
                         f"merge {handle.branch}", handle.branch)
    if rc == 0:
        return WorktreeResult(True, "merged")

    # Distinguish a true conflict (the loud-failure path) from other merge failures.
    rc_ls, ls_out, _ = _git(repo, "ls-files", "--unmerged")
    conflicted = bool(ls_out.strip())
    files = sorted({line.split("\t")[-1] for line in ls_out.strip().splitlines() if "\t" in line})
    _git(repo, "merge", "--abort")  # restore the base — never silent clobber
    reason = (f"merge conflict in: {', '.join(files)}" if conflicted
              else f"merge failed: {(err or '').strip().splitlines()[:1]}")
    return WorktreeResult(False, reason, conflict=conflicted)


def remove(repo, handle: WorktreeHandle) -> WorktreeResult:
    """Tear down the node's worktree and branch (lifecycle teardown). Force-removes the checkout
    even with uncommitted changes (a dropped/crashed node), then deletes the per-node branch.
    Idempotent and fail-soft — removing an already-gone worktree is not an error. Never raises."""
    repo = Path(repo)
    # Force-remove the worktree (uncommitted work in a dropped node must not block teardown).
    _git(repo, "worktree", "remove", "--force", handle.path)
    # Prune any stale administrative entry, then drop the per-node branch (no orphaned refs).
    _git(repo, "worktree", "prune")
    _git(repo, "branch", "-D", handle.branch)
    # Belt-and-suspenders: if the checkout dir somehow survived, remove it.
    try:
        p = Path(handle.path)
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    except OSError:
        pass
    return WorktreeResult(True, "removed")
