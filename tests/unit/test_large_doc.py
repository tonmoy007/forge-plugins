"""T-123 / REQ-LARGEDOC-001: large-document split convention.

AC-LARGEDOC-001a: the convention is documented in references/large-doc-layout.md.
AC-LARGEDOC-001b: a reader resolves either single-file or multi-file layout, and
                  a stage skill (forge:spec) reads inputs through it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
READ_DOC = str(ROOT / "scripts" / "read-doc.py")
PYTHON = sys.executable


def run(arg: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([PYTHON, READ_DOC, arg], capture_output=True, text=True, cwd=str(cwd))


# ---------- AC-LARGEDOC-001a: documented ----------

def test_convention_documented() -> None:
    doc = (ROOT / "references" / "large-doc-layout.md").read_text()
    assert "index.md" in doc and "REQ-LARGEDOC-001" in doc


# ---------- AC-LARGEDOC-001b: resolver reads either layout ----------

def test_reads_single_file(tmp_path: Path) -> None:
    spec = tmp_path / "pipeline" / "04-spec"
    spec.mkdir(parents=True)
    (spec / "technical-spec.md").write_text("# Spec\nSingle-file body.\n")
    r = run("pipeline/04-spec/technical-spec", tmp_path)
    assert r.returncode == 0
    assert "Single-file body" in r.stdout


def test_reads_multi_file_in_manifest_order(tmp_path: Path) -> None:
    d = tmp_path / "pipeline" / "04-spec" / "technical-spec"
    d.mkdir(parents=True)
    (d / "index.md").write_text(
        "# Manifest\n\n1. [B](02-second.md)\n2. [A](01-first.md)\n"  # deliberately B then A
    )
    (d / "01-first.md").write_text("FIRST-CONTENT")
    (d / "02-second.md").write_text("SECOND-CONTENT")
    r = run("pipeline/04-spec/technical-spec", tmp_path)
    assert r.returncode == 0
    # manifest order (B before A), not filename order
    assert r.stdout.index("SECOND-CONTENT") < r.stdout.index("FIRST-CONTENT")


def test_suffix_optional(tmp_path: Path) -> None:
    spec = tmp_path / "pipeline" / "04-spec"
    spec.mkdir(parents=True)
    (spec / "technical-spec.md").write_text("BODY")
    assert run("pipeline/04-spec/technical-spec.md", tmp_path).returncode == 0


def test_missing_document_reports_not_found(tmp_path: Path) -> None:
    r = run("pipeline/04-spec/technical-spec", tmp_path)
    assert r.returncode == 1


def test_spec_skill_uses_resolver() -> None:
    skill = (ROOT / "skills" / "forge-spec" / "SKILL.md").read_text()
    assert "read-doc.py" in skill
    assert "large-doc-layout.md" in skill
