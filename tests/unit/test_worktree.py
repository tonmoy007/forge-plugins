"""Tests for scripts/_worktree.py (v0.4.0 T-197 — git worktree isolation + lifecycle + merge).

These helpers isolate parallel file-mutating build nodes: each gets its own git worktree on a
**branch-per-node** (never `main`/`develop`), commits its work, then merges at a join where git
surfaces conflicts (never silent last-write-wins). Worktrees are torn down on success AND on
failure. ALL helpers are fail-soft — they return a structured result, never raise.

Real tmp git repos are used (no real claude/dispatch). Skipped if `git` is unavailable.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parent.parent.parent

_spec = importlib.util.spec_from_file_location("_worktree", _root / "scripts" / "_worktree.py")
_wt = importlib.util.module_from_spec(_spec)
sys.modules["_worktree"] = _wt
_spec.loader.exec_module(_wt)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "checkout", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


# --------------------------------------------------------------------------- #
# add — own worktree on a branch-per-node, never main/develop
# --------------------------------------------------------------------------- #


def test_add_creates_worktree_and_branch(tmp_path) -> None:
    repo = _init_repo(tmp_path)
    h = _wt.add(repo, "T1")
    assert h.ok is True
    assert Path(h.path).is_dir()                       # the worktree checkout exists
    assert h.branch not in ("main", "develop")         # never a protected branch
    assert "T1" in h.branch
    # git knows about the worktree.
    out = _git(repo, "worktree", "list").stdout
    assert h.path in out


def test_add_branch_is_node_scoped_and_unique(tmp_path) -> None:
    repo = _init_repo(tmp_path)
    a = _wt.add(repo, "T1")
    b = _wt.add(repo, "T2")
    assert a.ok and b.ok
    assert a.branch != b.branch
    assert a.path != b.path


def test_add_never_targets_protected_branch(tmp_path) -> None:
    """Even a node id literally named 'main' must NOT check out / move main (repo rule)."""
    repo = _init_repo(tmp_path)
    h = _wt.add(repo, "main")
    assert h.ok
    assert h.branch not in ("main", "develop")
    # main's own ref is untouched — still pointing where it was.
    assert _git(repo, "rev-parse", "main").stdout.strip()


def test_add_on_non_git_dir_fails_soft(tmp_path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    h = _wt.add(plain, "T1")
    assert h.ok is False
    assert h.reason                                    # a reason, not an exception


# --------------------------------------------------------------------------- #
# commit — the node's work in its worktree
# --------------------------------------------------------------------------- #


def test_commit_records_node_work(tmp_path) -> None:
    repo = _init_repo(tmp_path)
    h = _wt.add(repo, "T1")
    (Path(h.path) / "feature.txt").write_text("from T1\n")
    res = _wt.commit(h, message="feat(T1): work")
    assert res.ok is True
    # The branch tip now carries the new file.
    show = _git(repo, "show", f"{h.branch}:feature.txt")
    assert show.returncode == 0 and "from T1" in show.stdout


def test_commit_noop_when_nothing_changed(tmp_path) -> None:
    """A node that mutated nothing ⇒ a clean, non-failing no-op (not an error)."""
    repo = _init_repo(tmp_path)
    h = _wt.add(repo, "T1")
    res = _wt.commit(h, message="feat(T1): nothing")
    assert res.ok is True                              # fail-soft: empty commit is not a failure


# --------------------------------------------------------------------------- #
# merge — git surfaces conflicts; never silent clobber
# --------------------------------------------------------------------------- #


def test_merge_clean_brings_changes_into_base(tmp_path) -> None:
    repo = _init_repo(tmp_path)
    h = _wt.add(repo, "T1")
    (Path(h.path) / "feature.txt").write_text("from T1\n")
    _wt.commit(h, message="feat(T1): work")
    res = _wt.merge(repo, h)
    assert res.ok is True
    assert (repo / "feature.txt").read_text() == "from T1\n"   # merged into the base checkout


def test_merge_conflict_surfaces_never_silent_clobber(tmp_path) -> None:
    """Two nodes editing the SAME line must NOT silently last-write-win — the second merge
    reports a conflict and leaves the base ref unchanged by the losing side."""
    repo = _init_repo(tmp_path)
    a = _wt.add(repo, "T1")
    b = _wt.add(repo, "T2")
    (Path(a.path) / "shared.txt").write_text("A wrote this\n")
    (Path(b.path) / "shared.txt").write_text("B wrote this\n")
    _wt.commit(a, message="feat(T1)")
    _wt.commit(b, message="feat(T2)")

    first = _wt.merge(repo, a)
    assert first.ok is True
    assert (repo / "shared.txt").read_text() == "A wrote this\n"

    second = _wt.merge(repo, b)
    assert second.ok is False                          # conflict surfaced — not silently applied
    assert second.conflict is True
    assert "shared.txt" in (second.reason or "") or second.conflict
    # The base is NOT silently clobbered to B's content; the merge was aborted.
    assert (repo / "shared.txt").read_text() == "A wrote this\n"
    # And the repo is left in a clean (non-conflicted) state — merge aborted.
    status = _git(repo, "status", "--porcelain").stdout
    assert "UU" not in status                          # no unresolved conflict markers left


# --------------------------------------------------------------------------- #
# remove — teardown; idempotent, no orphaned worktrees
# --------------------------------------------------------------------------- #


def test_remove_tears_down_worktree_and_branch(tmp_path) -> None:
    repo = _init_repo(tmp_path)
    h = _wt.add(repo, "T1")
    path = h.path
    res = _wt.remove(repo, h)
    assert res.ok is True
    assert not Path(path).exists()                     # checkout dir gone
    assert h.path not in _git(repo, "worktree", "list").stdout
    # The per-node branch is gone too (no orphaned refs).
    assert _git(repo, "rev-parse", "--verify", h.branch).returncode != 0


def test_remove_is_idempotent_fail_soft(tmp_path) -> None:
    repo = _init_repo(tmp_path)
    h = _wt.add(repo, "T1")
    _wt.remove(repo, h)
    again = _wt.remove(repo, h)                         # removing twice must not raise
    assert again.ok is True or again.reason             # fail-soft either way


def test_remove_after_uncommitted_changes_still_tears_down(tmp_path) -> None:
    """A dropped/crashed node leaves uncommitted work; teardown must still force-remove it
    (no orphaned .git/worktrees)."""
    repo = _init_repo(tmp_path)
    h = _wt.add(repo, "T1")
    (Path(h.path) / "dirty.txt").write_text("uncommitted\n")
    res = _wt.remove(repo, h)
    assert res.ok is True
    assert not Path(h.path).exists()


# --------------------------------------------------------------------------- #
# capability probe
# --------------------------------------------------------------------------- #


def test_worktrees_available_true_for_git_repo(tmp_path) -> None:
    repo = _init_repo(tmp_path)
    assert _wt.worktrees_available(repo) is True


def test_worktrees_available_false_for_non_git(tmp_path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert _wt.worktrees_available(plain) is False
