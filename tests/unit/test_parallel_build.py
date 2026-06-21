"""Tests for scripts/parallel_build.py (v0.4.0 T-196 — per-stage parallel build fan-out).

The parallel-build helper maps *ready* task-DAG nodes (those whose `depends_on` are all already
done) to a `WorkflowSpec` and runs them through the engine: in parallel when the `parallel_build`
toggle is on, sequentially (max_parallel=1) when off. A fake dispatch_fn is injected — no real
claude / subprocess is touched. Per-node `cwd` (T-196) lets each node run in its own directory.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

_root = Path(__file__).resolve().parent.parent.parent

_vspec = importlib.util.spec_from_file_location("_verify", _root / "scripts" / "_verify.py")
_verify = importlib.util.module_from_spec(_vspec)
sys.modules["_verify"] = _verify
_vspec.loader.exec_module(_verify)

_wspec = importlib.util.spec_from_file_location("_workflow", _root / "scripts" / "_workflow.py")
_wf = importlib.util.module_from_spec(_wspec)
sys.modules["_workflow"] = _wf
_wspec.loader.exec_module(_wf)

_cspec = importlib.util.spec_from_file_location(
    "_workflow_config", _root / "scripts" / "_workflow_config.py")
_cfg = importlib.util.module_from_spec(_cspec)
sys.modules["_workflow_config"] = _cfg
_cspec.loader.exec_module(_cfg)

_pspec = importlib.util.spec_from_file_location(
    "parallel_build", _root / "scripts" / "parallel_build.py")
_pb = importlib.util.module_from_spec(_pspec)
sys.modules["parallel_build"] = _pb
_pspec.loader.exec_module(_pb)

FORGE = Path("/tmp/does-not-matter")  # fake dispatch ignores it


def _ok(result_obj: dict, cost: float = 0.01) -> SimpleNamespace:
    return SimpleNamespace(status="ok", result=json.dumps(result_obj),
                           cost_usd=cost, raw={"is_error": False})


def _echo_dispatch(prompt, **kwargs):
    return _ok({"prompt": prompt, "cwd": kwargs.get("cwd")})


def _spy_dispatch(recorded: list):
    def dispatch(prompt, **kwargs):
        recorded.append({"prompt": prompt, **kwargs})
        return _ok({"prompt": prompt})
    return dispatch


def _task(tid, deps=None):
    return _pb.TaskNode(id=tid, depends_on=deps or [])


# --------------------------------------------------------------------------- #
# ready_nodes — only tasks whose deps are all done are ready
# --------------------------------------------------------------------------- #


def test_ready_nodes_filters_by_unmet_deps() -> None:
    tasks = [_task("T1"), _task("T2"), _task("T3", ["T1"]), _task("T4", ["T1", "T2"])]
    assert _pb.ready_nodes(tasks, done=set()) == ["T1", "T2"]
    assert _pb.ready_nodes(tasks, done={"T1"}) == ["T2", "T3"]
    # T1/T2 done ⇒ excluded; T3 (dep T1) and T4 (deps T1,T2) are now ready.
    assert _pb.ready_nodes(tasks, done={"T1", "T2"}) == ["T3", "T4"]


def test_ready_nodes_excludes_already_done() -> None:
    """A task already in `done` is not 'ready to run' — it is finished."""
    tasks = [_task("T1"), _task("T2", ["T1"])]
    assert _pb.ready_nodes(tasks, done={"T1"}) == ["T2"]
    assert _pb.ready_nodes(tasks, done={"T1", "T2"}) == []


def test_ready_nodes_sorted_deterministic() -> None:
    tasks = [_task("T9"), _task("T1"), _task("T5")]
    assert _pb.ready_nodes(tasks, done=set()) == ["T1", "T5", "T9"]


# --------------------------------------------------------------------------- #
# AC-WF-007 — toggle on ⇒ N ready nodes fan out in parallel with per-node cwd
# --------------------------------------------------------------------------- #


def test_parallel_on_fans_out_ready_nodes() -> None:
    cfg = _cfg.OrchestrationConfig(parallel_build=True, max_parallel=4)
    tasks = [_task("T1"), _task("T2"), _task("T3", ["T1"])]  # T3 not ready
    recorded: list = []
    res = _pb.run_parallel_build(
        tasks, done=set(), config=cfg, forge_dir=FORGE, feature="t",
        dispatch_fn=_spy_dispatch(recorded),
    )
    assert res.completed == 2                       # only the two ready nodes ran
    assert set(res.results) == {"T1", "T2"}
    assert "T3" not in res.results                  # unmet dependency ⇒ not dispatched
    assert len(recorded) == 2


def test_parallel_per_node_cwd_applied() -> None:
    """Each fanned-out node dispatches in its OWN cwd via the `cwd_for` mapping (the seam T-197
    uses to hand each node its worktree)."""
    cfg = _cfg.OrchestrationConfig(parallel_build=True, max_parallel=4)
    tasks = [_task("T1"), _task("T2")]
    recorded: list = []
    _pb.run_parallel_build(
        tasks, done=set(), config=cfg, forge_dir=FORGE, feature="t",
        dispatch_fn=_spy_dispatch(recorded),
        cwd_for=lambda tid: f"/wt/{tid}",
    )
    by_prompt = {c["cwd"] for c in recorded}
    assert by_prompt == {"/wt/T1", "/wt/T2"}


def test_parallel_threads_max_parallel_and_budget() -> None:
    """Engine tunables from the config (max_parallel/max_total/max_budget_usd) reach run_workflow;
    the budget ceiling is threaded into every dispatch."""
    cfg = _cfg.OrchestrationConfig(parallel_build=True, max_parallel=2, max_budget_usd=5.0)
    tasks = [_task(f"T{i}") for i in range(3)]
    recorded: list = []
    _pb.run_parallel_build(
        tasks, done=set(), config=cfg, forge_dir=FORGE, feature="t",
        dispatch_fn=_spy_dispatch(recorded),
    )
    assert recorded
    for c in recorded:
        assert c["max_budget_usd"] == 5.0


# --------------------------------------------------------------------------- #
# AC-WF-007 — toggle off ⇒ today's sequential behavior (max_parallel == 1)
# --------------------------------------------------------------------------- #


def test_parallel_off_runs_sequential() -> None:
    """With `parallel_build` off, ready nodes still run (the engine is always on) but the result
    is the SAME as a parallel run — byte-identical engine result (REQ-NF-026a)."""
    tasks = [_task("T1"), _task("T2"), _task("T3")]
    off = _pb.run_parallel_build(
        tasks, done=set(), config=_cfg.OrchestrationConfig(parallel_build=False),
        forge_dir=FORGE, feature="t", dispatch_fn=_echo_dispatch)
    on = _pb.run_parallel_build(
        tasks, done=set(), config=_cfg.OrchestrationConfig(parallel_build=True, max_parallel=8),
        forge_dir=FORGE, feature="t", dispatch_fn=_echo_dispatch)
    assert off.completed == on.completed == 3
    assert json.dumps(off.results, sort_keys=True) == json.dumps(on.results, sort_keys=True)


def test_parallel_off_uses_single_worker() -> None:
    """The off path runs the engine with max_parallel=1 (sequential), the documented degrade."""
    captured: dict = {}
    real_run = _wf.run_workflow

    def spy_run(spec, **kwargs):
        captured["max_parallel"] = kwargs.get("max_parallel")
        return real_run(spec, **kwargs)

    _pb._wf.run_workflow = spy_run
    try:
        _pb.run_parallel_build(
            [_task("T1")], done=set(),
            config=_cfg.OrchestrationConfig(parallel_build=False),
            forge_dir=FORGE, feature="t", dispatch_fn=_echo_dispatch)
        assert captured["max_parallel"] == 1
    finally:
        _pb._wf.run_workflow = real_run


# --------------------------------------------------------------------------- #
# never-raises + empty input
# --------------------------------------------------------------------------- #


def test_no_ready_nodes_is_noop() -> None:
    """No ready nodes (all blocked or all done) ⇒ an empty, non-raising result with no dispatch."""
    recorded: list = []
    res = _pb.run_parallel_build(
        [_task("T2", ["T1"])], done=set(),  # T2 blocked on undone T1
        config=_cfg.OrchestrationConfig(parallel_build=True),
        forge_dir=FORGE, feature="t", dispatch_fn=_spy_dispatch(recorded))
    assert res.completed == 0
    assert recorded == []


def test_default_build_prompt_mentions_task_id() -> None:
    """The default per-task build prompt embeds the task id so the agent knows which task to build."""
    cfg = _cfg.OrchestrationConfig(parallel_build=True)
    recorded: list = []
    _pb.run_parallel_build(
        [_task("T42")], done=set(), config=cfg, forge_dir=FORGE, feature="t",
        dispatch_fn=_spy_dispatch(recorded))
    assert any("T42" in c["prompt"] for c in recorded)


# --------------------------------------------------------------------------- #
# AC-WF-008 / T-197 — git worktree isolation + lifecycle + merge join
# --------------------------------------------------------------------------- #

import shutil  # noqa: E402
import subprocess  # noqa: E402

import pytest  # noqa: E402

_needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def _init_repo(tmp_path):
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


def _writer_dispatch(filename_for, content_for):
    """A fake dispatch that simulates a build node mutating a file IN ITS OWN cwd (worktree),
    then returns ok. `filename_for(prompt)`/`content_for(prompt)` derive the write from the task."""

    def dispatch(prompt, **kwargs):
        wt = kwargs.get("cwd")
        if wt:
            (Path(wt) / filename_for(prompt)).write_text(content_for(prompt))
        return _ok({"prompt": prompt})

    return dispatch


def _tid_of(prompt):
    """Extract the Tnn id the default build prompt embeds (`Implement task T1 ...`)."""
    import re
    m = re.search(r"\bT\d+\b", prompt)
    return m.group(0) if m else "node"


@_needs_git
def test_worktree_each_node_gets_own_worktree_and_branch(tmp_path) -> None:
    repo = _init_repo(tmp_path)
    cfg = _cfg.OrchestrationConfig(parallel_build=True, worktree_isolation=True, max_parallel=4)
    tasks = [_task("T1"), _task("T2")]
    # Each node writes a DISTINCT file → clean, independent merges.
    dispatch = _writer_dispatch(lambda p: f"{_tid_of(p)}.txt", lambda p: f"{_tid_of(p)}\n")
    res = _pb.run_parallel_build(
        tasks, done=set(), config=cfg, forge_dir=FORGE, feature="t",
        dispatch_fn=dispatch, repo=repo)
    assert res.completed == 2
    # Both nodes' files merged into the base checkout.
    assert (repo / "T1.txt").read_text() == "T1\n"
    assert (repo / "T2.txt").read_text() == "T2\n"
    # Lifecycle: every worktree torn down on success — no orphaned worktrees / branches.
    assert ".forge-worktrees" not in _git(repo, "worktree", "list").stdout
    branches = _git(repo, "branch", "--list", "forge/wt/*").stdout.strip()
    assert branches == ""


@_needs_git
def test_worktree_conflict_excludes_node_never_silent_clobber(tmp_path) -> None:
    """Two nodes writing the SAME line conflict at the join: the loser is EXCLUDED from the merge
    with a reason (never silently overwriting the winner)."""
    repo = _init_repo(tmp_path)
    cfg = _cfg.OrchestrationConfig(parallel_build=True, worktree_isolation=True, max_parallel=2)
    tasks = [_task("T1"), _task("T2")]
    # Both write the SAME file with DIFFERENT content → second merge conflicts.
    dispatch = _writer_dispatch(lambda p: "shared.txt", lambda p: f"{_tid_of(p)} content\n")
    res = _pb.run_parallel_build(
        tasks, done=set(), config=cfg, forge_dir=FORGE, feature="t",
        dispatch_fn=dispatch, repo=repo)
    # Exactly one node merges cleanly; the other is excluded (conflict).
    merged = set(res.results)
    assert len(merged) == 1                                   # one winner only
    assert res.dropped >= 1
    assert any("conflict" in r.lower() for r in res.dropped_reasons)
    # The base file holds the winner's content (a real line), not a silent clobber / merge marker.
    content = (repo / "shared.txt").read_text()
    assert "content" in content and "<<<<<<<" not in content
    # No orphaned worktrees even though a node was excluded.
    assert ".forge-worktrees" not in _git(repo, "worktree", "list").stdout


@_needs_git
def test_worktree_torn_down_on_dropped_node(tmp_path) -> None:
    """A node whose dispatch fails (dropped) still has its worktree + branch removed (teardown on
    failure, not only success) — no orphaned `.git/worktrees`."""
    repo = _init_repo(tmp_path)
    cfg = _cfg.OrchestrationConfig(parallel_build=True, worktree_isolation=True, max_parallel=2)
    tasks = [_task("T1"), _task("T2")]

    def dispatch(prompt, **kwargs):
        if "T2" in prompt:
            raise RuntimeError("boom")                       # T2 always fails
        wt = kwargs.get("cwd")
        if wt:
            (Path(wt) / "T1.txt").write_text("T1\n")
        return _ok({"prompt": prompt})

    res = _pb.run_parallel_build(
        tasks, done=set(), config=cfg, forge_dir=FORGE, feature="t",
        dispatch_fn=dispatch, repo=repo)
    assert "T1" in res.results
    assert "T2" not in res.results
    # Both worktrees (including the dropped node's) are gone.
    assert ".forge-worktrees" not in _git(repo, "worktree", "list").stdout
    assert _git(repo, "branch", "--list", "forge/wt/*").stdout.strip() == ""


@_needs_git
def test_worktree_unavailable_degrades_to_sequential(tmp_path) -> None:
    """With worktrees unavailable (a non-git dir) and isolation on, the build degrades to a
    sequential single-worktree run — no per-node worktree, no raise."""
    plain = tmp_path / "plain"
    plain.mkdir()
    cfg = _cfg.OrchestrationConfig(parallel_build=True, worktree_isolation=True, max_parallel=4)
    recorded: list = []
    res = _pb.run_parallel_build(
        [_task("T1"), _task("T2")], done=set(), config=cfg, forge_dir=FORGE, feature="t",
        dispatch_fn=_spy_dispatch(recorded), repo=plain, cwd=str(plain))
    assert res.completed == 2                                 # still ran (degraded)
    # Degraded: every dispatch ran in the single shared cwd, not a per-node worktree.
    assert all(c["cwd"] == str(plain) for c in recorded)


@_needs_git
def test_worktree_isolation_off_does_not_create_worktrees(tmp_path) -> None:
    """`worktree_isolation` off ⇒ no worktrees created even when the repo supports them."""
    repo = _init_repo(tmp_path)
    cfg = _cfg.OrchestrationConfig(parallel_build=True, worktree_isolation=False, max_parallel=4)
    _pb.run_parallel_build(
        [_task("T1")], done=set(), config=cfg, forge_dir=FORGE, feature="t",
        dispatch_fn=_echo_dispatch, repo=repo)
    assert ".forge-worktrees" not in _git(repo, "worktree", "list").stdout


# --------------------------------------------------------------------------- #
# AC-WF-009 / T-198 — adversarial-verify join (N skeptics, refute; majority of DISPATCHED)
# --------------------------------------------------------------------------- #


def _skeptic_dispatch(verdicts: list, recorded: list = None):
    """A dispatch_fn for skeptic verifiers: each call pops the next verdict from `verdicts`.
    A verdict of `"skip"` simulates a cost-cap drop (status='skipped' — NOT dispatched). Any other
    value (`pass`/`fail`/garbage) is returned as a verifier envelope."""
    seq = list(verdicts)

    def dispatch(prompt, **kwargs):
        if recorded is not None:
            recorded.append({"prompt": prompt, **kwargs})
        v = seq.pop(0) if seq else "pass"
        if v == "skip":
            return SimpleNamespace(status="skipped", reason="cost cap", result=None, cost_usd=0.0)
        if v == "garbage":
            return SimpleNamespace(status="ok", reason="", result="not json", cost_usd=0.001)
        return SimpleNamespace(status="ok", reason="dispatched",
                               result=json.dumps({"verdict": v}), cost_usd=0.002)

    return dispatch


def test_adversarial_admit_majority_pass_admits() -> None:
    """3 skeptics, 2 admit (pass) + 1 refute (fail) ⇒ majority of 3 dispatched ⇒ admitted."""
    verdict = _pb.adversarial_admit(
        {"work": "x"}, node_id="T1", skeptics=3,
        dispatch_fn=_skeptic_dispatch(["pass", "fail", "pass"]),
        forge_dir=FORGE, feature="t")
    assert verdict.admitted is True
    assert verdict.dispatched == 3
    assert verdict.refutations == 1


def test_adversarial_admit_majority_refute_excludes() -> None:
    """2 of 3 refute ⇒ no majority to admit ⇒ excluded with a reason."""
    verdict = _pb.adversarial_admit(
        {"work": "x"}, node_id="T1", skeptics=3,
        dispatch_fn=_skeptic_dispatch(["fail", "fail", "pass"]),
        forge_dir=FORGE, feature="t")
    assert verdict.admitted is False
    assert verdict.dispatched == 3
    assert verdict.refutations == 2
    assert "refut" in verdict.reason.lower() or "majority" in verdict.reason.lower()


def test_adversarial_admit_tie_is_not_majority() -> None:
    """A tie (1 admit / 1 refute of 2 dispatched) is NOT a strict majority ⇒ excluded."""
    verdict = _pb.adversarial_admit(
        {"work": "x"}, node_id="T1", skeptics=2,
        dispatch_fn=_skeptic_dispatch(["pass", "fail"]),
        forge_dir=FORGE, feature="t")
    assert verdict.admitted is False
    assert verdict.dispatched == 2


def test_adversarial_cap_dropped_skeptic_does_not_lower_denominator() -> None:
    """AC-WF-009 core: 5 intended, 1 cap-dropped ⇒ denominator is the 4 DISPATCHED, so a
    3-of-4 admit majority is required — a cap drop must NOT silently lower the bar.

    Here: 4 dispatched (1 skipped); verdicts pass,pass,fail,fail ⇒ 2 admit of 4 ⇒ NOT majority.
    If the dropped skeptic had (wrongly) lowered the denominator to 3-of-5-intended logic, the
    bar could be gamed; the denominator MUST be the 4 actually dispatched."""
    verdict = _pb.adversarial_admit(
        {"work": "x"}, node_id="T1", skeptics=5,
        dispatch_fn=_skeptic_dispatch(["pass", "pass", "fail", "fail", "skip"]),
        forge_dir=FORGE, feature="t")
    assert verdict.dispatched == 4                       # the cap-dropped skeptic is excluded
    assert verdict.admitted is False                     # 2 admit of 4 is not a majority
    # And the denominator is NOT 5 (intended) — it's the 4 dispatched.
    assert verdict.skeptics_intended == 5


def test_adversarial_cap_drop_with_admit_majority_of_dispatched() -> None:
    """5 intended, 1 cap-dropped ⇒ 4 dispatched; 3 admit / 1 refute ⇒ 3-of-4 IS a majority."""
    verdict = _pb.adversarial_admit(
        {"work": "x"}, node_id="T1", skeptics=5,
        dispatch_fn=_skeptic_dispatch(["pass", "pass", "pass", "fail", "skip"]),
        forge_dir=FORGE, feature="t")
    assert verdict.dispatched == 4
    assert verdict.refutations == 1
    assert verdict.admitted is True


def test_adversarial_all_skeptics_dropped_degrades_to_admit(tmp_path=None) -> None:
    """If EVERY skeptic is cost-cap dropped (zero dispatched), the verifier is unavailable —
    degrade to admit (an unavailable extra check must not block, REQ-NF-013), never raise."""
    verdict = _pb.adversarial_admit(
        {"work": "x"}, node_id="T1", skeptics=3,
        dispatch_fn=_skeptic_dispatch(["skip", "skip", "skip"]),
        forge_dir=FORGE, feature="t")
    assert verdict.dispatched == 0
    assert verdict.admitted is True                      # degrade-to-admit, not block


def test_adversarial_skeptics_run_fresh_session_to_refute() -> None:
    """Each skeptic dispatches fresh-session (resume forced None) and is prompted to refute."""
    recorded: list = []
    _pb.adversarial_admit(
        {"work": "x"}, node_id="T1", skeptics=2,
        dispatch_fn=_skeptic_dispatch(["pass", "pass"], recorded),
        forge_dir=FORGE, feature="t", resume="STAGE-SESSION")
    assert len(recorded) == 2
    for c in recorded:
        assert c["resume"] is None                       # fresh session — independence
        assert "refute" in c["prompt"].lower()           # adversarial framing


# --- adversarial join wired into the isolated build: refuted nodes excluded from merge ---


@_needs_git
def test_adversarial_join_excludes_refuted_node_from_merge(tmp_path) -> None:
    """With `adversarial_verify` configured, a node a majority of skeptics refute is EXCLUDED from
    the merge (its file never lands), while an admitted node merges."""
    repo = _init_repo(tmp_path)
    cfg = _cfg.OrchestrationConfig(parallel_build=True, worktree_isolation=True, max_parallel=2)

    def dispatch(prompt, **kwargs):
        if "refute" in prompt.lower():                   # skeptic verifier
            # Refute only T2; admit T1.
            verdict = "fail" if "T2" in prompt else "pass"
            return SimpleNamespace(status="ok", reason="", result=json.dumps({"verdict": verdict}),
                                   cost_usd=0.001)
        wt = kwargs.get("cwd")                            # build node
        if wt:
            (Path(wt) / f"{_tid_of(prompt)}.txt").write_text(f"{_tid_of(prompt)}\n")
        return _ok({"prompt": prompt})

    res = _pb.run_parallel_build(
        [_task("T1"), _task("T2")], done=set(), config=cfg, forge_dir=FORGE, feature="t",
        dispatch_fn=dispatch, repo=repo, adversarial_skeptics=3)
    assert "T1" in res.results                            # admitted ⇒ merged
    assert "T2" not in res.results                        # refuted ⇒ excluded
    assert (repo / "T1.txt").exists()
    assert not (repo / "T2.txt").exists()                 # refuted node's work never landed
    assert any("T2" in r and ("refut" in r.lower() or "adversar" in r.lower())
               for r in res.dropped_reasons)
