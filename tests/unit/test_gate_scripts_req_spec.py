"""T-109 / REQ-GATESTUB-001 (implement half): requirements + spec gate scripts.

Each script exits 0 on a passing fixture and non-zero on a failing one, and is
referenced by the matching gate-criteria.md entry.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
PYTHON = sys.executable


def run(script: str, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(SCRIPTS / script)] + args,
        capture_output=True, text=True, cwd=str(cwd),
    )


def _mkfile(base: Path, rel: str, content: str) -> Path:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


# ---------- check_srs_acceptance.py ----------

def test_srs_acceptance_pass(tmp_path: Path) -> None:
    srs = _mkfile(tmp_path, "srs.md",
                  "## REQ-001\nThe system shall X.\n**Acceptance**: AC-001a works.\n"
                  "## REQ-002\nShall Y.\nAcceptance: it does Y.\n")
    assert run("check_srs_acceptance.py", [str(srs)], tmp_path).returncode == 0


def test_srs_acceptance_fail_missing(tmp_path: Path) -> None:
    srs = _mkfile(tmp_path, "srs.md",
                  "## REQ-001\nShall X with AC-001.\n## REQ-002\nShall Y. (no criteria)\n")
    r = run("check_srs_acceptance.py", [str(srs)], tmp_path)
    assert r.returncode == 1
    assert "REQ-002" in r.stderr


def test_srs_acceptance_fail_no_reqs(tmp_path: Path) -> None:
    srs = _mkfile(tmp_path, "srs.md", "# SRS\nnothing here\n")
    assert run("check_srs_acceptance.py", [str(srs)], tmp_path).returncode == 1


# ---------- traceability-check.py ----------

def test_traceability_pass(tmp_path: Path) -> None:
    _mkfile(tmp_path, "srs.md", "REQ-001 foo\nREQ-002 bar\n")
    _mkfile(tmp_path, "dag.md", "## T-001\nimplements REQ-001\n## T-002\ncovers REQ-002\n")
    r = run("traceability-check.py", ["--from", "dag.md", "--to", "srs.md"], tmp_path)
    assert r.returncode == 0, r.stderr


def test_traceability_fail_dangling(tmp_path: Path) -> None:
    _mkfile(tmp_path, "srs.md", "REQ-001 foo\n")
    _mkfile(tmp_path, "dag.md", "## T-001\nimplements REQ-999\n")
    r = run("traceability-check.py", ["--from", "dag.md", "--to", "srs.md"], tmp_path)
    assert r.returncode == 1
    assert "REQ-999" in r.stderr


def test_traceability_fail_task_without_ref(tmp_path: Path) -> None:
    _mkfile(tmp_path, "srs.md", "REQ-001 foo\n")
    _mkfile(tmp_path, "dag.md", "## T-001\nimplements REQ-001\n## T-002\nno reference here\n")
    r = run("traceability-check.py", ["--from", "dag.md", "--to", "srs.md"], tmp_path)
    assert r.returncode == 1
    assert "T-002" in r.stderr


# ---------- spec-coverage.py ----------

def test_spec_coverage_pass(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/03-architecture/architecture.md",
            "## Components\n### AuthService\n### PaymentGateway\n")
    _mkfile(tmp_path, "pipeline/04-spec/technical-spec.md",
            "AuthService interface ...\nPaymentGateway contract ...\n")
    assert run("spec-coverage.py", [], tmp_path).returncode == 0


def test_spec_coverage_fail_uncovered(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/03-architecture/architecture.md",
            "### AuthService\n### PaymentGateway\n")
    _mkfile(tmp_path, "pipeline/04-spec/technical-spec.md", "AuthService only\n")
    r = run("spec-coverage.py", [], tmp_path)
    assert r.returncode == 1
    assert "PaymentGateway" in r.stderr


# ---------- check_dag_completeness.py ----------

def test_dag_completeness_pass(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/05-plan/task-dag.md",
            "## T-001\n- Done when: tests pass\n## T-002\nDone: shipped\n")
    assert run("check_dag_completeness.py", [], tmp_path).returncode == 0


def test_dag_completeness_fail(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/05-plan/task-dag.md",
            "## T-001\n- Done when: ok\n## T-002\nno criteria\n")
    r = run("check_dag_completeness.py", [], tmp_path)
    assert r.returncode == 1
    assert "T-002" in r.stderr


# ---------- check_dag_completion.py ----------

def test_dag_completion_pass(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/05-plan/task-dag.md", "## T-001\nx\n## T-002\ny\n")
    _mkfile(tmp_path, "pipeline/06-implementation/progress.md",
            "| T-001 | 🟢 done | ... |\n| T-002 | ✅ done | ... |\n")
    assert run("check_dag_completion.py", [], tmp_path).returncode == 0


def test_dag_completion_fail(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/05-plan/task-dag.md", "## T-001\nx\n## T-002\ny\n")
    _mkfile(tmp_path, "pipeline/06-implementation/progress.md",
            "| T-001 | 🟢 done | ... |\n| T-002 | 🔲 todo | ... |\n")
    r = run("check_dag_completion.py", [], tmp_path)
    assert r.returncode == 1
    assert "T-002" in r.stderr


# ---------- wiring: every script referenced by gate-criteria.md ----------

@pytest.mark.parametrize("script", [
    "check_srs_acceptance.py", "traceability-check.py", "spec-coverage.py",
    "check_dag_completeness.py", "check_dag_completion.py",
])
def test_script_exists_and_referenced(script: str) -> None:
    assert (SCRIPTS / script).exists()
    assert f"scripts/{script}" in (ROOT / "references" / "gate-criteria.md").read_text()
