"""Tests for T-103 (REQ-NEXTHINT-001): next-step hint derived from the canonical table.

The 12 stage skills must NOT hardcode their next-step hint. The hint comes from
`references/stage-order.md` via `state-manager.py next-hint`, which reads
`_stage_table`. Two historical bugs this guards against:
  - forge-srs hinted `/forge:ux` (no such command; canonical is /forge:product)
  - forge-product hinted `/forge:architecture` (canonical is /forge:arch)
"""

from __future__ import annotations

import datetime
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
SCRIPT = str(SCRIPTS / "state-manager.py")
PYTHON = sys.executable

sys.path.insert(0, str(SCRIPTS))
import _stage_table as st  # noqa: E402

# Canonical stage -> skill directory under skills/.
STAGE_SKILL_DIR = {
    1: "forge-srs",
    2: "forge-product",
    3: "forge-arch",
    4: "forge-spec",
    5: "forge-plan",
    6: "forge-build",
    7: "forge-eval",
    8: "forge-deploy",
    9: "forge-monitor",
    10: "forge-feedback",
    11: "forge-resolve",
    12: "forge-release",
}

# Commands that never existed but were hardcoded as next-step hints.
DEAD_COMMANDS = ["/forge:ux", "/forge:architecture"]


def run(args: list[str], cwd: str = ".") -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, SCRIPT] + args, capture_output=True, text=True, cwd=cwd
    )


def _make_state(tmp_path: Path, current_stage: int) -> Path:
    (tmp_path / "pipeline").mkdir()
    state = tmp_path / "pipeline" / "state.md"
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state.write_text(
        "---\n"
        "schema_version: 1\n"
        "project_type: unknown\n"
        "cycle: 1\n"
        f"current_stage: {current_stage}\n"
        "current_task: null\n"
        "current_milestone: null\n"
        "total_tasks: null\n"
        f"last_updated: {now}\n"
        "blockers: []\n"
        "---\n\n# Pipeline State\n"
    )
    return state


# ---------- the helper returns the table's hint for every transition ----------

@pytest.mark.parametrize("n", list(range(1, 13)))
def test_explicit_stage_matches_table(n: int) -> None:
    result = run(["next-hint", "--stage", str(n)])
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == st.next_hint(n)


@pytest.mark.parametrize("n", list(range(1, 12)))
def test_hint_names_the_canonical_next_skill(n: int) -> None:
    """For stages 1..11 the hint text names the next stage's /forge: command."""
    out = run(["next-hint", "--stage", str(n)]).stdout
    assert st.next_skill(n) in out


def test_stage1_hint_names_product_not_architecture() -> None:
    """REQ-NEXTHINT-001: after 01-srs the hint names product/UX, not architecture."""
    out = run(["next-hint", "--stage", "1"]).stdout
    assert "/forge:product" in out
    assert "/forge:arch" not in out
    assert "/forge:ux" not in out


def test_stage12_hint_is_cycle_wrap() -> None:
    out = run(["next-hint", "--stage", "12"]).stdout
    assert "/forge:retro" in out


# ---------- current_stage fallback when --stage is omitted ----------

def test_defaults_to_current_stage_from_state(tmp_path: Path) -> None:
    _make_state(tmp_path, current_stage=3)
    result = run(["next-hint"], cwd=str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == st.next_hint(3)


def test_explicit_stage_overrides_state(tmp_path: Path) -> None:
    _make_state(tmp_path, current_stage=3)
    out = run(["next-hint", "--stage", "1"], cwd=str(tmp_path)).stdout
    assert out.strip() == st.next_hint(1)


# ---------- error paths ----------

@pytest.mark.parametrize("bad", ["0", "13", "-1", "99"])
def test_out_of_range_stage_errors(bad: str) -> None:
    result = run(["next-hint", "--stage", bad])
    assert result.returncode != 0
    assert "hint" in result.stderr.lower() or "stage" in result.stderr.lower()


# ---------- grep guards: no hardcoded next-step strings in stage skills ----------

def _skill_text(stage_dir: str) -> str:
    return (ROOT / "skills" / stage_dir / "SKILL.md").read_text()


def _next_step_section(text: str) -> str:
    """Return the body of the '## Next Step' section (up to the next H2 or EOF)."""
    m = re.search(r"^## Next Step\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return m.group(1) if m else ""


def test_no_dead_commands_in_next_step_sections() -> None:
    """No skill's '## Next Step' section may name a dead command.

    Note: forge-product / forge-arch legitimately document `/forge:ux` and
    `/forge:architecture` as recognized *input* aliases (prompt-submit.py maps
    "ux"->2 and "architecture"->3). Those are inputs the user may type, not
    forward hints, so they are allowed in descriptions / When-to-Use — but never
    as the command to run next.
    """
    offenders = []
    for path in (ROOT / "skills").glob("*/SKILL.md"):
        section = _next_step_section(path.read_text())
        for dead in DEAD_COMMANDS:
            if dead in section:
                offenders.append(f"{path.name}: {dead}")
    assert offenders == [], f"dead commands named as next step: {offenders}"


def test_status_stage_table_matches_canonical_skills() -> None:
    """forge-status's stage->command table must use the canonical skill per stage.

    This is the same source-of-truth invariant: the status dashboard's 'command
    for stage N' must equal stage_table.stage(N)['skill'] — not a dead alias.
    """
    text = _skill_text("forge-status")
    rows = dict(re.findall(r"^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|", text, re.MULTILINE))
    for n in range(1, 13):
        assert str(n) in rows, f"forge-status table missing stage {n}"
        assert rows[str(n)] == st.stage(n)["skill"], (
            f"forge-status stage {n} command {rows[str(n)]!r} != "
            f"canonical {st.stage(n)['skill']!r}"
        )


@pytest.mark.parametrize("n,stage_dir", sorted(STAGE_SKILL_DIR.items()))
def test_next_step_section_invokes_helper(n: int, stage_dir: str) -> None:
    section = _next_step_section(_skill_text(stage_dir))
    assert section, f"{stage_dir} has no '## Next Step' section"
    assert "state-manager.py next-hint" in section, (
        f"{stage_dir} Next Step does not call the next-hint helper"
    )
    assert f"--stage {n}" in section, (
        f"{stage_dir} Next Step does not pass its own stage number {n}"
    )


@pytest.mark.parametrize("stage_dir", sorted(STAGE_SKILL_DIR.values()))
def test_next_step_section_has_no_hardcoded_forge_command(stage_dir: str) -> None:
    """The only /forge:* token allowed in Next Step is none — the hint is derived."""
    section = _next_step_section(_skill_text(stage_dir))
    # The helper invocation references state-manager.py, not a /forge: command.
    assert not re.search(r"Run\s+`?/forge:", section), (
        f"{stage_dir} Next Step still hardcodes a 'Run /forge:' hint"
    )
