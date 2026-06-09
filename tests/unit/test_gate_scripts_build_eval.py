"""T-110 / REQ-GATESTUB-001 (implement half): build + evaluation gate scripts."""

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


# ---------- token-audit.py ----------

def test_token_audit_pass_no_ui(tmp_path: Path) -> None:
    _mkfile(tmp_path, "main.py", "print('hi')\n")
    assert run("token-audit.py", [], tmp_path).returncode == 0


def test_token_audit_pass_tokens(tmp_path: Path) -> None:
    _mkfile(tmp_path, "src/app.css", ".x { color: var(--brand); }\n")
    assert run("token-audit.py", [], tmp_path).returncode == 0


def test_token_audit_fail_raw_hex(tmp_path: Path) -> None:
    _mkfile(tmp_path, "src/app.css", ".x { color: #ff0000; }\n")
    r = run("token-audit.py", [], tmp_path)
    assert r.returncode == 1
    assert "hex" in r.stderr


# ---------- check_coverage.py ----------

def test_coverage_pass_above(tmp_path: Path) -> None:
    _mkfile(tmp_path, "coverage.xml", '<coverage line-rate="0.95"></coverage>\n')
    assert run("check_coverage.py", ["--min", "80"], tmp_path).returncode == 0


def test_coverage_fail_below(tmp_path: Path) -> None:
    _mkfile(tmp_path, "coverage.xml", '<coverage line-rate="0.50"></coverage>\n')
    r = run("check_coverage.py", ["--min", "80"], tmp_path)
    assert r.returncode == 1
    assert "below" in r.stderr


def test_coverage_pass_when_no_report(tmp_path: Path) -> None:
    assert run("check_coverage.py", ["--min", "80"], tmp_path).returncode == 0


# ---------- check_todos.py ----------

def test_todos_pass_ticketed(tmp_path: Path) -> None:
    _mkfile(tmp_path, "a.py", "# TODO(T-123): finish later\nx = 1\n")
    assert run("check_todos.py", [], tmp_path).returncode == 0


def test_todos_fail_bare(tmp_path: Path) -> None:
    _mkfile(tmp_path, "a.py", "# TODO: finish\nx = 1\n")
    r = run("check_todos.py", [], tmp_path)
    assert r.returncode == 1
    assert "TODO" in r.stderr


# ---------- check_progress_sync.py ----------

def test_progress_sync_pass(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/05-plan/task-dag.md", "## T-001\n## T-002\n")
    _mkfile(tmp_path, "pipeline/06-implementation/progress.md", "T-001 done; T-002 wip\n")
    assert run("check_progress_sync.py", [], tmp_path).returncode == 0


def test_progress_sync_fail_missing(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/05-plan/task-dag.md", "## T-001\n## T-002\n")
    _mkfile(tmp_path, "pipeline/06-implementation/progress.md", "T-001 done\n")
    r = run("check_progress_sync.py", [], tmp_path)
    assert r.returncode == 1
    assert "T-002" in r.stderr


# ---------- check_nfr_coverage.py ----------

def test_nfr_coverage_pass(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/01-srs/srs.md", "NFR-001 latency\nNFR-002 uptime\n")
    _mkfile(tmp_path, "pipeline/07-evaluation/eval-report.md",
            "NFR-001: pass\nNFR-002: pass\n")
    assert run("check_nfr_coverage.py", [], tmp_path).returncode == 0


def test_nfr_coverage_fail_unevaluated(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/01-srs/srs.md", "NFR-001 a\nNFR-002 b\n")
    _mkfile(tmp_path, "pipeline/07-evaluation/eval-report.md", "NFR-001: pass\n")
    r = run("check_nfr_coverage.py", [], tmp_path)
    assert r.returncode == 1
    assert "NFR-002" in r.stderr


def test_nfr_coverage_pass_no_nfrs(tmp_path: Path) -> None:
    _mkfile(tmp_path, "pipeline/01-srs/srs.md", "REQ-001 only\n")
    assert run("check_nfr_coverage.py", [], tmp_path).returncode == 0


# ---------- wiring ----------

@pytest.mark.parametrize("script", [
    "token-audit.py", "check_coverage.py", "check_todos.py",
    "check_progress_sync.py", "check_nfr_coverage.py",
])
def test_script_exists_and_referenced(script: str) -> None:
    assert (SCRIPTS / script).exists()
    assert f"scripts/{script}" in (ROOT / "references" / "gate-criteria.md").read_text()
