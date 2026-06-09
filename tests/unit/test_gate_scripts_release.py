"""T-111 / REQ-GATESTUB-001 (implement half): release + health gate scripts.

Note on some_check.py: it appears only in the `### script_returns_zero` *format
example* block of gate-criteria.md (no `stage:` / no real criterion list), so it
is intentionally not implemented. The T-112 audit only scans real criteria.
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


# ---------- check_open_bugs.py ----------

def test_open_bugs_pass_all_resolved(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/10-feedback/triage.md",
            "| FB-001 | P0 | resolved |\n| FB-002 | P1 | closed |\n")
    assert run("check_open_bugs.py", ["--severity", "P0,P1"], tmp_path).returncode == 0


def test_open_bugs_fail_open_p0(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/10-feedback/triage.md",
            "| FB-001 | P0 | open |\n| FB-002 | P2 | open |\n")
    r = run("check_open_bugs.py", ["--severity", "P0,P1"], tmp_path)
    assert r.returncode == 1


def test_open_bugs_pass_no_triage(tmp_path: Path) -> None:
    assert run("check_open_bugs.py", ["--severity", "P0,P1"], tmp_path).returncode == 0


# ---------- check_health.py ----------

def test_health_pass(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/09-monitor/health-report.md",
            "# Health\nAll systems operational. Status: healthy.\n")
    assert run("check_health.py", [], tmp_path).returncode == 0


def test_health_fail_unhealthy(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/09-monitor/health-report.md",
            "# Health\nDatabase: DOWN (critical)\n")
    assert run("check_health.py", [], tmp_path).returncode == 1


def test_health_fail_missing(tmp_path: Path) -> None:
    assert run("check_health.py", [], tmp_path).returncode == 1


# ---------- check_hotfix_tests.py ----------

def test_hotfix_tests_pass(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/11-resolve/hotfixes.md",
            "## FB-001 fix\nPatched X. Regression test: test_x.py added.\n")
    assert run("check_hotfix_tests.py", [], tmp_path).returncode == 0


def test_hotfix_tests_fail_no_test(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/11-resolve/hotfixes.md",
            "## FB-001 fix\nPatched X via a one-line change. Shipped.\n")
    r = run("check_hotfix_tests.py", [], tmp_path)
    assert r.returncode == 1
    assert "FB-001" in r.stderr


def test_hotfix_tests_pass_no_hotfixes(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/11-resolve/hotfixes.md", "# Hotfixes\n_(none this cycle)_\n")
    assert run("check_hotfix_tests.py", [], tmp_path).returncode == 0


# ---------- check_git_tag.py ----------

def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, check=True)


def test_git_tag_pass(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "f.txt").write_text("x")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "init")
    _git(tmp_path, "tag", "v0.1.5")
    assert run("check_git_tag.py", [], tmp_path).returncode == 0


def test_git_tag_fail_no_tag(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    assert run("check_git_tag.py", [], tmp_path).returncode == 1


# ---------- wiring ----------

@pytest.mark.parametrize("script", [
    "check_open_bugs.py", "check_health.py", "check_hotfix_tests.py", "check_git_tag.py",
])
def test_script_exists_and_referenced(script: str) -> None:
    assert (SCRIPTS / script).exists()
    assert f"scripts/{script}" in (ROOT / "references" / "gate-criteria.md").read_text()


def test_some_check_is_doc_example_only() -> None:
    """some_check.py is a format example, not a real criterion — not implemented."""
    assert not (SCRIPTS / "some_check.py").exists()
