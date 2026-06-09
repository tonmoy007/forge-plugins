"""Guard against pipeline stage path drift (T-102, REQ-PATHS-001).

EF-005 plus the T-102 audit found stage skills + agent personas writing/reading
artifacts at directories and filenames the gates never check (e.g.
`04-technical-spec/` vs `04-spec/`, `deployment-plan.md` vs `deploy-plan.md`,
`triage-report.md` vs `triage.md`), silently wedging stages 4/8/9/10/11.

These tests assert that every `pipeline/NN-*` directory referenced by the live
plugin (stage skills, agent personas, and the init scaffold) is the canonical
directory defined in the stage-order table, and that none of the known drift
filenames reappear.

AC-PATHS-001a: nothing writes outside its canonical directory.
AC-PATHS-001b: no two directories correspond to the same stage.
"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _stage_table as st  # noqa: E402

# Live plugin surfaces that must use canonical stage paths.
_SCAN_FILES = (
    sorted((ROOT / "skills").glob("*/SKILL.md"))
    + sorted((ROOT / "agents").glob("*.md"))
    + [ROOT / "scripts" / "init-pipeline.sh"]
)

# Any pipeline/NN-<segment> directory reference.
_PIPELINE_DIR = re.compile(r"pipeline/(\d{2}-[a-z0-9-]+)")

# Canonical directories from the single source of truth.
CANONICAL_DIRS = {s["dir"] for s in st.stages()}

# Filenames retired by the T-102 reconciliation (old name -> canonical).
FORBIDDEN_FILENAMES = {
    "deployment-plan.md": "deploy-plan.md",
    "slo-definition.md": "observability.md",
    "resolution-log.md": "hotfixes.md",
    "triage-report.md": "triage.md",
}


def _iter_lines():
    for f in _SCAN_FILES:
        if not f.exists():
            continue
        for lineno, line in enumerate(f.read_text().splitlines(), start=1):
            yield f.relative_to(ROOT), lineno, line


def test_canonical_dirs_complete():
    # Sanity: the table yields exactly the 12 expected directory names.
    assert CANONICAL_DIRS == {
        "01-srs", "02-product-ux", "03-architecture", "04-spec", "05-plan",
        "06-implementation", "07-evaluation", "08-deploy", "09-monitor",
        "10-feedback", "11-resolve", "12-release",
    }


def test_no_noncanonical_pipeline_dirs():
    offenders = []
    for relpath, lineno, line in _iter_lines():
        for found in _PIPELINE_DIR.findall(line):
            if found not in CANONICAL_DIRS:
                offenders.append(f"{relpath}:{lineno}: pipeline/{found}")
    assert not offenders, "non-canonical stage directories found:\n" + "\n".join(offenders)


@pytest.mark.parametrize("bad_name", sorted(FORBIDDEN_FILENAMES))
def test_no_retired_filenames(bad_name):
    offenders = [
        f"{relpath}:{lineno}"
        for relpath, lineno, line in _iter_lines()
        if bad_name in line
    ]
    canonical = FORBIDDEN_FILENAMES[bad_name]
    assert not offenders, (
        f"retired filename {bad_name!r} (use {canonical!r}) still referenced:\n"
        + "\n".join(offenders)
    )


def test_init_scaffold_creates_canonical_dirs():
    init = (ROOT / "scripts" / "init-pipeline.sh").read_text()
    scaffolded = set(_PIPELINE_DIR.findall(init))
    # Every stage's canonical directory must be scaffolded by init.
    assert CANONICAL_DIRS <= scaffolded, (
        "init-pipeline.sh missing canonical dirs: "
        f"{sorted(CANONICAL_DIRS - scaffolded)}"
    )


def test_each_skill_writes_its_gate_blocker_dir():
    # Spot-check the stages that were wedged: the driving skill must reference
    # the canonical directory for its stage's primary artifact.
    checks = {
        "forge-spec": "04-spec",
        "forge-deploy": "08-deploy",
        "forge-monitor": "09-monitor",
        "forge-feedback": "10-feedback",
        "forge-resolve": "11-resolve",
    }
    for skill, expected_dir in checks.items():
        text = (ROOT / "skills" / skill / "SKILL.md").read_text()
        assert f"pipeline/{expected_dir}/" in text, f"{skill} missing {expected_dir}"
