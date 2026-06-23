"""T-218 / ADR-010 + REQ-NF-038: per-node session-reuse docs are present and wired.

The v0.6.0 reuse feature ships behind the `orchestration.session_reuse` toggle. Its
docs are part of the deliverable; this test pins them so a future edit cannot silently
drop the ADR, the toggle row, or the cross-doc wiring.

- ADR-010 exists at the repo ADR path/format and records the load-bearing decisions
  (within-node only, admission stays fresh, default-off, verifier never reused,
  fallback-to-fresh).
- `references/workflow-engine.md` documents the `session_reuse` toggle (incl. a row in
  the toggle table) and the within-node reuse semantics.
- README carries a session-reuse line.
- ROADMAP / progress / decisions carry the v0.6.0 row and link ADR-010.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ADR = ROOT / "build" / "02-architecture" / "adr" / "010-session-reuse.md"
WORKFLOW_REF = ROOT / "references" / "workflow-engine.md"
README = ROOT / "README.md"
ROADMAP = ROOT / "ROADMAP.md"
PROGRESS = ROOT / "build" / "05-implementation" / "progress.md"
DECISIONS = ROOT / "build" / "05-implementation" / "decisions.md"


def test_adr_010_present_and_records_decisions() -> None:
    assert ADR.exists(), "ADR-010 must live at build/02-architecture/adr/010-session-reuse.md"
    text = ADR.read_text()
    # Title + status header, matching the ADR-008/009 format.
    assert text.startswith("# ADR-010: ")
    assert "**Status**: Accepted" in text
    # The five load-bearing decisions (SRS §5 / ADR-010).
    assert "session_reuse" in text
    assert "within-node" in text.lower()
    assert "FRESH_FLOOR_USD" in text          # admission stays on the fresh floor
    assert "RESUME_FLOOR_USD" in text          # reuse charges the cheaper floor
    assert "default off" in text.lower() or "default-off" in text.lower()
    assert "verifier" in text.lower()          # verifier never reused (REQ-WF-002)
    assert "REQ-WF-002" in text
    assert "fall" in text.lower() and "fresh" in text.lower()  # fallback-to-fresh
    assert "AC-WF-014" in text                 # admission invariance preserved


def test_workflow_reference_documents_toggle_and_semantics() -> None:
    text = WORKFLOW_REF.read_text()
    # Toggle table row.
    assert "`session_reuse`" in text
    # Within-node reuse semantics: retry + heal reuse, verifier fresh, fallback.
    assert "RESUME_FLOOR_USD" in text
    assert "retry" in text.lower() and "heal" in text.lower()
    assert "ADR-010" in text


def test_readme_mentions_session_reuse() -> None:
    text = README.read_text()
    assert "session_reuse" in text
    assert "v0.6.0" in text


def test_roadmap_progress_decisions_carry_v060_row() -> None:
    roadmap = ROADMAP.read_text()
    assert "v0.6.0" in roadmap
    assert "session reuse" in roadmap.lower()
    assert "ADR-010" in roadmap
    # Deferred follow-ups recorded.
    assert "per-branch" in roadmap.lower()
    assert "caveman" in roadmap.lower()

    decisions = DECISIONS.read_text()
    assert "ADR-010" in decisions
    assert "T-218" in decisions or "T-216" in decisions

    progress = PROGRESS.read_text()
    assert "T-218" in progress
    assert "ADR-010" in progress
