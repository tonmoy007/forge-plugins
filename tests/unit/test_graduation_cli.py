"""Unit tests for the ``/forge:graduate`` CLI in scripts/_graduation.py (T-211).

Covers AC-GR-006: the thin argparse front end reuses the SAME ``graduate()``
driver (no second promotion path), so a ``--dry-run`` predicts exactly what a
forced scan then promotes, and ``list`` reflects the real global store. All
filesystem effects are confined to a tmp ``--global-dir``; ``main()`` is invoked
in-process with patched ``argv`` and its stdout captured via capsys.

The dry-run/scan parity case drives the WORKFLOWS tier end to end: two registered
projects each contribute the same valid workflow with >= 2 successful
``workflow_run`` records, so the cross-project flow qualifies. We assert the
preview names the workflow and writes NOTHING, then a forced scan promotes exactly
that workflow (store + copied file now exist).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # @dataclass / Protocol need the module registered
    spec.loader.exec_module(mod)
    return mod


gr = _load("_graduation", SCRIPTS / "_graduation.py")


# ---------------------------------------------------------------------------
# Fixtures: a project contributing a valid, run-proven workflow
# ---------------------------------------------------------------------------

_VALID_WF = 'name: {name}\nnodes:\n  - id: a\n    prompt: "do a"\n'


def _run_record(name: str, ts: str) -> dict:
    return {
        "schema_version": 1,
        "ts": ts,
        "event": "workflow_run",
        "name": name,
        "nodes": 1,
        "waves": 1,
        "completed": ["a"],
        "dropped": [],
        "total_cost_usd": 0.01,
        "verdicts": {},
        "admitted": ["a"],
    }


def _make_workflow_project(root: Path, name: str, wf_name: str, *, runs: int) -> Path:
    """A project with a valid ``wf_name`` workflow and ``runs`` successful runs."""
    proj = root / name
    forge = proj / ".forge"
    wf_dir = forge / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / f"{wf_name}.yaml").write_text(_VALID_WF.format(name=wf_name), encoding="utf-8")
    records = [_run_record(wf_name, ts=f"2026-06-0{i + 1}T10:00:00Z") for i in range(runs)]
    (forge / "events.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )
    return proj


def _run_cli(argv, capsys) -> tuple[int, str]:
    """Invoke ``main(argv)`` in-process and return ``(exit_code, stdout)``."""
    code = gr.main(argv)
    out = capsys.readouterr().out
    return code, out


# ---------------------------------------------------------------------------
# AC-GR-006: --dry-run previews + writes nothing; forced scan promotes the same set
# ---------------------------------------------------------------------------


class TestDryRunThenScanParity:
    def _register_two_projects(self, tmp_path: Path) -> Path:
        """Two projects sharing a qualifying ``shipit`` workflow. Returns global_dir."""
        global_dir = tmp_path / "globalforge"
        src = tmp_path / "src"
        for i in range(2):
            proj = _make_workflow_project(src, f"proj{i}", "shipit", runs=2)
            gr.register_project(global_dir, proj)
        return global_dir

    def test_dry_run_previews_workflow_and_writes_nothing(self, tmp_path, capsys):
        global_dir = self._register_two_projects(tmp_path)

        code, out = _run_cli(["--global-dir", str(global_dir), "--dry-run"], capsys)

        assert code == 0
        # The preview must name the qualifying workflow under the workflows tier.
        assert "shipit" in out
        assert "workflows" in out
        # NOTHING is written: no global index, no copied workflow file.
        assert not (global_dir / "global-workflows.yaml").exists()
        assert not (global_dir / "workflows" / "shipit.yaml").exists()

    def test_forced_scan_promotes_exactly_the_dry_run_set(self, tmp_path, capsys):
        global_dir = self._register_two_projects(tmp_path)

        # Dry-run prediction: which workflows would promote.
        gr.main(["--global-dir", str(global_dir), "--dry-run"])
        capsys.readouterr()  # discard preview output

        # Forced (non-dry-run) scan: it should now actually promote those.
        code, out = _run_cli(["--global-dir", str(global_dir)], capsys)

        assert code == 0
        assert "shipit" in out
        # The store and the copied workflow file now exist (real promotion).
        index_path = global_dir / "global-workflows.yaml"
        assert index_path.exists()
        names = [r.get("name") for r in yaml.safe_load(index_path.read_text())["workflows"]]
        assert names == ["shipit"]  # exactly the predicted set
        assert (global_dir / "workflows" / "shipit.yaml").exists()

    def test_scan_subcommand_equivalent_to_default(self, tmp_path, capsys):
        global_dir = self._register_two_projects(tmp_path)

        code, out = _run_cli(["--global-dir", str(global_dir), "scan"], capsys)

        assert code == 0
        assert (global_dir / "global-workflows.yaml").exists()
        assert "shipit" in out


# ---------------------------------------------------------------------------
# AC-GR-006: list reflects the real store entries / counts
# ---------------------------------------------------------------------------


class TestListView:
    def test_list_missing_store_is_failsoft_zero_counts(self, tmp_path, capsys):
        global_dir = tmp_path / "empty"

        code, out = _run_cli(["--global-dir", str(global_dir), "list"], capsys)

        assert code == 0
        # Fail-soft: every tier reports zero rather than crashing on a missing store.
        assert "lessons: 0" in out
        assert "skills: 0" in out
        assert "workflows: 0" in out

    def test_list_reflects_populated_store(self, tmp_path, capsys):
        global_dir = tmp_path / "globalforge"
        global_dir.mkdir(parents=True)
        (global_dir / "global-workflows.yaml").write_text(
            yaml.dump(
                {
                    "schema_version": 1,
                    "workflows": [
                        {"name": "shipit", "projects": ["/p"], "runs": 4, "last_used": "2026-06-02"},
                        {"name": "deploy", "projects": ["/p"], "runs": 2, "last_used": "2026-06-01"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        (global_dir / "global-skills.yaml").write_text(
            yaml.dump(
                {
                    "schema_version": 1,
                    "skills": [
                        {"slug": "lint-fix", "projects": ["/p"], "weight": 3, "use": 5,
                         "last_used": "2026-06-03"},
                    ],
                }
            ),
            encoding="utf-8",
        )

        code, out = _run_cli(["--global-dir", str(global_dir), "list"], capsys)

        assert code == 0
        # Real counts per tier.
        assert "workflows: 2 entries" in out
        assert "skills: 1 entry" in out
        assert "lessons: 0 entries" in out
        # Each entry's key + last_used surface.
        assert "shipit" in out and "deploy" in out
        assert "lint-fix" in out
        assert "2026-06-03" in out

    def test_list_flag_equivalent_to_subcommand(self, tmp_path, capsys):
        global_dir = tmp_path / "empty"

        code, out = _run_cli(["--global-dir", str(global_dir), "--list"], capsys)

        assert code == 0
        assert "workflows: 0" in out


# ---------------------------------------------------------------------------
# Robustness: main() never raises out
# ---------------------------------------------------------------------------


class TestNeverRaises:
    def test_scan_on_unwritable_global_dir_does_not_raise(self, tmp_path, capsys):
        # A bogus global dir (parent is a regular file) must degrade cleanly.
        afile = tmp_path / "afile"
        afile.write_text("x")
        bogus = afile / ".forge"

        code, out = _run_cli(["--global-dir", str(bogus)], capsys)

        assert code == 0  # clean, no traceback escaped
        assert out  # something was printed
