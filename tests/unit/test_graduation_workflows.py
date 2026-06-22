"""Unit tests for scripts/_graduation_workflows.py — the workflows tier (T-209).

AC-GR-003 (REQ-GR-004 / GR-005 / NF-035 / NF-037):
  - a workflow <name>.yaml that validates clean AND has >=2 successful
    `workflow_run` records in events.jsonl is promoted to ~/.forge/workflows/ +
    indexed in global-workflows.yaml;
  - invalid YAML, <2 successful runs, or runs with no completed node / a failing
    verify verdict do NOT promote; a malformed events.jsonl line is skipped;
  - the loader resolves a graduated <name> from a DIFFERENT project, and a
    project-local <name>.yaml shadows the global one (project-wins on name);
  - a second scan with no new artifacts is idempotent.

All filesystem touch is confined to tmp dirs + a fake ~/.forge; nothing writes
the real ~/.forge or the real plugin.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


gr = _load("_graduation", SCRIPTS / "_graduation.py")
wt = _load("_graduation_workflows", SCRIPTS / "_graduation_workflows.py")
loader = _load("workflow_loader", SCRIPTS / "workflow_loader.py")

_TODAY = datetime.date(2026, 6, 9)

_VALID_WF = "name: {name}\nnodes:\n  - id: a\n    prompt: \"do a\"\n"
_INVALID_WF = "name: {name}\nnodes: [oops\n"  # malformed YAML


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _write_workflow(project: Path, name: str, *, valid: bool = True) -> Path:
    d = project / ".forge" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    body = (_VALID_WF if valid else _INVALID_WF).format(name=name)
    p = d / f"{name}.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def _run_record(name: str, *, ts: str, completed=("a",), verdicts=None) -> dict:
    return {
        "schema_version": 1, "ts": ts, "event": "workflow_run", "name": name,
        "nodes": 1, "waves": 1, "completed": list(completed), "dropped": [],
        "total_cost_usd": 0.01, "verdicts": verdicts or {}, "admitted": ["a"],
    }


def _write_events(project: Path, records: list, *, extra_lines: list = ()) -> None:
    d = project / ".forge"
    d.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r) for r in records] + list(extra_lines)
    (d / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _good_runs(name: str, n: int) -> list:
    return [_run_record(name, ts=f"2026-06-0{i+1}T10:00:00Z") for i in range(n)]


def _tier(**kw):
    return wt.WorkflowTier(today=_TODAY, **kw)


def _index(global_dir: Path) -> list:
    p = global_dir / "global-workflows.yaml"
    if not p.exists():
        return []
    return yaml.safe_load(p.read_text())["workflows"]


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_workflow_tier_satisfies_protocol():
    assert isinstance(_tier(), gr.Tier)


def test_key_returns_name():
    t = _tier()
    assert t.key({"name": "foo"}) == "foo"
    assert t.key(wt.WorkflowRecord("bar", "/p.yaml", 2, None, "/p", True)) == "bar"


# ---------------------------------------------------------------------------
# collect + gate
# ---------------------------------------------------------------------------


class TestCollectGate:
    def test_collect_counts_successful_runs(self, tmp_path):
        proj = tmp_path / "p"
        _write_workflow(proj, "flow")
        _write_events(proj, _good_runs("flow", 3))
        recs = _tier().collect(str(proj))
        assert len(recs) == 1
        assert recs[0].name == "flow" and recs[0].valid is True
        assert recs[0].runs == 3
        assert recs[0].last_used == "2026-06-03T10:00:00Z"

    def test_collect_marks_invalid_yaml(self, tmp_path):
        proj = tmp_path / "p"
        _write_workflow(proj, "flow", valid=False)
        _write_events(proj, _good_runs("flow", 3))
        recs = _tier().collect(str(proj))
        assert len(recs) == 1 and recs[0].valid is False

    def test_collect_ignores_no_completed_runs(self, tmp_path):
        proj = tmp_path / "p"
        _write_workflow(proj, "flow")
        _write_events(proj, [_run_record("flow", ts="2026-06-01T10:00:00Z", completed=[])
                             for _ in range(3)])
        assert _tier().collect(str(proj))[0].runs == 0

    def test_collect_ignores_failing_verdict_runs(self, tmp_path):
        proj = tmp_path / "p"
        _write_workflow(proj, "flow")
        _write_events(proj, [_run_record("flow", ts="2026-06-01T10:00:00Z",
                                         verdicts={"skeptic": "fail"}) for _ in range(3)])
        assert _tier().collect(str(proj))[0].runs == 0

    def test_collect_skips_malformed_events_line(self, tmp_path):
        proj = tmp_path / "p"
        _write_workflow(proj, "flow")
        _write_events(proj, _good_runs("flow", 2),
                      extra_lines=["not json", "{bad", '{"event": "other"}'])
        assert _tier().collect(str(proj))[0].runs == 2  # good lines still counted

    def test_collect_missing_project_empty(self, tmp_path):
        assert _tier().collect(str(tmp_path / "nope")) == []

    def test_gate_passes_valid_and_min_runs(self):
        rec = wt.WorkflowRecord("flow", "/p.yaml", 2, "2026-06-01T10:00:00Z", "/p", True)
        assert _tier().gate([rec]) == [rec]

    def test_gate_blocks_invalid(self):
        rec = wt.WorkflowRecord("flow", "/p.yaml", 5, "2026-06-01T10:00:00Z", "/p", False)
        assert _tier().gate([rec]) == []

    def test_gate_blocks_under_min_runs(self):
        rec = wt.WorkflowRecord("flow", "/p.yaml", 1, "2026-06-01T10:00:00Z", "/p", True)
        assert _tier().gate([rec]) == []


# ---------------------------------------------------------------------------
# promote (via the unified driver) — AC-GR-003
# ---------------------------------------------------------------------------


class TestPromote:
    def test_clean_workflow_promoted_and_indexed(self, tmp_path):
        gdir = tmp_path / ".forge_global"
        projs = []
        for i in range(2):
            p = tmp_path / f"p{i}"
            _write_workflow(p, "flow")
            _write_events(p, _good_runs("flow", 2))
            gr.register_project(gdir, p)
            projs.append(p)
        result = gr.graduate(gdir, [_tier()])
        assert [r["name"] for r in result["workflows"]] == ["flow"]
        # copied to the global store
        copied = gdir / "workflows" / "flow.yaml"
        assert copied.exists()
        assert loader.load_workflow_file(copied).ok
        # indexed with both projects, runs summed across them
        idx = _index(gdir)
        assert idx[0]["name"] == "flow"
        assert set(idx[0]["projects"]) == {str(p.resolve()) for p in projs}
        assert idx[0]["runs"] == 4  # 2 per project

    def test_invalid_yaml_not_promoted(self, tmp_path):
        gdir = tmp_path / ".forge_global"
        p = tmp_path / "p"
        _write_workflow(p, "flow", valid=False)
        _write_events(p, _good_runs("flow", 5))
        gr.register_project(gdir, p)
        result = gr.graduate(gdir, [_tier()])
        assert result["workflows"] == []
        assert not (gdir / "workflows" / "flow.yaml").exists()

    def test_under_min_runs_not_promoted(self, tmp_path):
        gdir = tmp_path / ".forge_global"
        p = tmp_path / "p"
        _write_workflow(p, "flow")
        _write_events(p, _good_runs("flow", 1))
        gr.register_project(gdir, p)
        assert gr.graduate(gdir, [_tier()])["workflows"] == []

    def test_no_successful_runs_not_promoted(self, tmp_path):
        gdir = tmp_path / ".forge_global"
        p = tmp_path / "p"
        _write_workflow(p, "flow")
        _write_events(p, [_run_record("flow", ts="2026-06-01T10:00:00Z", completed=[])
                          for _ in range(3)])
        gr.register_project(gdir, p)
        assert gr.graduate(gdir, [_tier()])["workflows"] == []

    def test_dry_run_writes_nothing(self, tmp_path):
        gdir = tmp_path / ".forge_global"
        p = tmp_path / "p"
        _write_workflow(p, "flow")
        _write_events(p, _good_runs("flow", 2))
        gr.register_project(gdir, p)
        result = gr.graduate(gdir, [_tier()], dry_run=True)
        assert [r["name"] for r in result["workflows"]] == ["flow"]
        assert not (gdir / "workflows" / "flow.yaml").exists()
        assert not (gdir / "global-workflows.yaml").exists()

    def test_second_scan_idempotent(self, tmp_path):
        gdir = tmp_path / ".forge_global"
        p = tmp_path / "p"
        _write_workflow(p, "flow")
        _write_events(p, _good_runs("flow", 2))
        gr.register_project(gdir, p)
        gr.graduate(gdir, [_tier()])
        first_idx = (gdir / "global-workflows.yaml").read_text()
        first_yaml = (gdir / "workflows" / "flow.yaml").read_text()
        gr.graduate(gdir, [_tier()])
        assert (gdir / "global-workflows.yaml").read_text() == first_idx  # NF-037
        assert (gdir / "workflows" / "flow.yaml").read_text() == first_yaml


# ---------------------------------------------------------------------------
# recall = loader search path (project-wins on name) — AC-GR-003 / GR-005
# ---------------------------------------------------------------------------


class TestLoaderRecall:
    def _graduate_flow(self, tmp_path):
        gdir = tmp_path / ".forge_global"
        src = tmp_path / "src"
        _write_workflow(src, "flow")
        _write_events(src, _good_runs("flow", 2))
        gr.register_project(gdir, src)
        gr.graduate(gdir, [_tier()])
        return gdir

    def test_graduated_workflow_visible_from_other_project(self, tmp_path):
        gdir = self._graduate_flow(tmp_path)
        other = tmp_path / "other"
        (other / ".forge" / "workflows").mkdir(parents=True)
        resolved = loader.resolve_workflows(
            other / ".forge" / "workflows", gdir / "workflows"
        )
        assert "flow" in resolved
        assert resolved["flow"] == gdir / "workflows" / "flow.yaml"
        assert loader.load_workflow_file(resolved["flow"]).ok

    def test_project_local_shadows_global(self, tmp_path):
        gdir = self._graduate_flow(tmp_path)
        other = tmp_path / "other"
        local = _write_workflow(other, "flow")  # same name, local copy
        resolved = loader.resolve_workflows(
            other / ".forge" / "workflows", gdir / "workflows"
        )
        assert resolved["flow"] == local  # project-wins on name

    def test_fresh_global_names_excludes_stale(self, tmp_path):
        gdir = tmp_path / ".forge_global"
        (gdir / "workflows").mkdir(parents=True)
        gr.write_atomic(
            gdir / "global-workflows.yaml",
            yaml.dump({"schema_version": 1, "workflows": [
                {"name": "fresh", "projects": ["/p"], "runs": 3, "last_used": "2026-06-01T0:0:0Z"},
                {"name": "stale", "projects": ["/p"], "runs": 3, "last_used": "2026-04-01T0:0:0Z"},
            ]}, sort_keys=False),
        )
        fresh = _tier().fresh_global_names(gdir)
        assert fresh == {"fresh"}

    def test_resolve_with_fresh_filter_skips_stale(self, tmp_path):
        gdir = tmp_path / ".forge_global"
        wf = gdir / "workflows"
        wf.mkdir(parents=True)
        (wf / "fresh.yaml").write_text(_VALID_WF.format(name="fresh"))
        (wf / "stale.yaml").write_text(_VALID_WF.format(name="stale"))
        proj_dir = tmp_path / "p" / ".forge" / "workflows"
        proj_dir.mkdir(parents=True)
        resolved = loader.resolve_workflows(proj_dir, wf, fresh_names={"fresh"})
        assert set(resolved) == {"fresh"}  # stale global filtered out

    def test_recall_is_noop_and_never_raises(self, tmp_path):
        # workflow recall is the loader search path, not a per-project fs action
        assert _tier().recall(tmp_path / "nope", str(tmp_path / "p")) is None


# ---------------------------------------------------------------------------
# never-raises (REQ-NF-034)
# ---------------------------------------------------------------------------


class TestFailSoft:
    def test_collect_malformed_events_no_raise(self, tmp_path):
        proj = tmp_path / "p"
        _write_workflow(proj, "flow")
        (proj / ".forge" / "events.jsonl").write_text("\x00 not json at all\n{")
        recs = _tier().collect(str(proj))
        assert recs[0].runs == 0  # unparseable → zero, no raise

    def test_graduate_isolates_workflow_tier_failure(self, tmp_path):
        gdir = tmp_path / ".forge_global"
        gr.register_project(gdir, tmp_path / "p")

        class _Boom(wt.WorkflowTier):
            name = "workflows"

            def collect(self, project_path):
                raise RuntimeError("collect exploded")

        result = gr.graduate(gdir, [_Boom(today=_TODAY)])
        assert result["workflows"] == []

    def test_resolve_missing_dirs_no_raise(self, tmp_path):
        assert loader.resolve_workflows(tmp_path / "a", tmp_path / "b") == {}
