"""End-to-end integration test for the per-stage parallel-build path (v0.4.1, T-205 / REQ-WF-014).

Drives `parallel_build.run_parallel_build` against the canonical sample project
(`examples/sample-todo-api/`) with `parallel_build` AND `worktree_isolation` ON and adversarial
skeptics enabled — exercising the whole chain: fan-out (each ready task dispatches in its own git
worktree) → adversarial-verify join → clean merge → worktree teardown.

A single **injected fake `dispatch_fn`** stands in for `claude -p`: it routes by prompt — a build
node writes a distinct file in its own worktree (so merges are conflict-free), an adversarial
skeptic returns a schema-constrained `pass` verdict. No real `claude`, no network, no spend, fully
deterministic. The live-dispatch path stays capability-gated and out of CI (REQ-NF-024).
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_root = Path(__file__).resolve().parent.parent.parent
_SAMPLE = _root / "examples" / "sample-todo-api"

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _root / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load the engine + helpers by file path (hyphen-safe importlib pattern, per lessons.md).
_verify = _load("_verify", "scripts/_verify.py")
_wf = _load("_workflow", "scripts/_workflow.py")
_cfg = _load("_workflow_config", "scripts/_workflow_config.py")
_pb = _load("parallel_build", "scripts/parallel_build.py")


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def _seed_repo(tmp_path):
    """Init a git repo seeded with the sample-todo-api content as its base commit."""
    repo = tmp_path / "sample-todo-api"
    repo.mkdir()
    # Copy the sample project in as the working base (fall back to a stub if it is ever absent).
    if _SAMPLE.is_dir():
        for item in _SAMPLE.iterdir():
            dst = repo / item.name
            if item.is_dir():
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)
    else:  # pragma: no cover - sample is shipped in-repo
        (repo / "README.md").write_text("sample todo api\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "checkout", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base: sample-todo-api")
    return repo


def _tid_of(prompt: str) -> str:
    import re
    m = re.search(r"\bT\d+\b", prompt)
    return m.group(0) if m else "node"


def _fake_dispatch(recorded: dict):
    """One injected dispatcher for the whole flow. Routes by prompt:
      - adversarial skeptic  → schema-constrained `pass` verdict (admits the node)
      - build node           → write a DISTINCT file in this node's worktree, return ok
    Records what it saw so the test can assert fan-out + skeptics actually ran. No spend."""

    def dispatch(prompt, **kwargs):
        if "adversarial skeptic" in prompt:
            recorded.setdefault("skeptics", []).append(_tid_of(prompt))
            return SimpleNamespace(status="ok", result=json.dumps({"verdict": "pass"}),
                                   cost_usd=0.002, raw={"is_error": False})
        tid = _tid_of(prompt)
        recorded.setdefault("builds", []).append(tid)
        wt = kwargs.get("cwd")
        if wt:
            (Path(wt) / f"impl_{tid}.py").write_text(f"# implementation of {tid}\n")
        return SimpleNamespace(status="ok", result=json.dumps({"task": tid, "files": [f"impl_{tid}.py"]}),
                               cost_usd=0.01, raw={"is_error": False})

    return dispatch


@needs_git
def test_parallel_build_e2e_fanout_join_merge_teardown(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_WF_QUIET", "1")  # keep test output clean; narration tested elsewhere
    repo = _seed_repo(tmp_path)
    forge = tmp_path / ".forge"

    # Three independent ready tasks (no edges) → all fan out in one wave.
    tasks = [_pb.TaskNode(id="T1"), _pb.TaskNode(id="T2"), _pb.TaskNode(id="T3")]
    cfg = _cfg.OrchestrationConfig(
        parallel_build=True, worktree_isolation=True, max_parallel=3)

    recorded: dict = {}
    res = _pb.run_parallel_build(
        tasks, done=set(), config=cfg, forge_dir=forge, feature="build-stage",
        dispatch_fn=_fake_dispatch(recorded), repo=repo, adversarial_skeptics=2,
    )

    # Fan-out: every task dispatched (in its own worktree).
    assert sorted(recorded["builds"]) == ["T1", "T2", "T3"]
    # Adversarial join: 2 skeptics per admitted node actually ran (3 nodes × 2 = 6).
    assert len(recorded["skeptics"]) == 6
    # Merge: all three nodes merged cleanly, each file landed on the base checkout.
    assert res.completed == 3
    for tid in ("T1", "T2", "T3"):
        assert (repo / f"impl_{tid}.py").read_text() == f"# implementation of {tid}\n"
    # Per-node adversarial verdicts captured for the audit record (T-203).
    assert set(res.drops) == set()  # no drops
    # Worktree teardown: no orphaned worktrees or branches after the run (success path).
    assert ".forge-worktrees" not in _git(repo, "worktree", "list").stdout
    assert _git(repo, "branch", "--list", "forge/wt/*").stdout.strip() == ""


@needs_git
def test_parallel_build_e2e_writes_one_audit_record(tmp_path, monkeypatch):
    """The e2e build leaves exactly one events.jsonl audit record carrying its admitted set and
    adversarial verdicts (ties the dogfood path to REQ-WF-012)."""
    monkeypatch.setenv("FORGE_WF_QUIET", "1")
    repo = _seed_repo(tmp_path)
    forge = tmp_path / ".forge"
    tasks = [_pb.TaskNode(id="T1"), _pb.TaskNode(id="T2")]
    cfg = _cfg.OrchestrationConfig(parallel_build=True, worktree_isolation=True, max_parallel=2)

    _pb.run_parallel_build(
        tasks, done=set(), config=cfg, forge_dir=forge, feature="build-stage",
        dispatch_fn=_fake_dispatch({}), repo=repo, adversarial_skeptics=1,
    )
    lines = [json.loads(l) for l in (forge / "events.jsonl").read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    rec = lines[0]
    assert rec["event"] == "workflow_run"
    assert rec["completed"] == ["T1", "T2"]
    assert rec["verdicts"]  # per-node adversarial outcomes present
    assert set(rec["verdicts"]) == {"T1", "T2"}
