"""T-120 / REQ-PATTERN-001: pattern.jsonl carries actionable, schema-valid events.

AC-PATTERN-001a: after a real session, patterns.jsonl is non-empty and every line
                 parses against the documented schema (references/pattern-schema.md).
AC-PATTERN-001b: a signature repeated >= 3 times (substantive) fires a skill-miner
                 proposal.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
POST_TOOL = str(ROOT / "hooks" / "post-tool-use.py")
MINE = str(ROOT / "scripts" / "mine-skills.py")
PYTHON = sys.executable


def _validate_record(rec: dict) -> None:
    assert rec["schema_version"] == 1
    assert isinstance(rec["ts"], str) and rec["ts"].endswith("Z")
    assert isinstance(rec["kind"], str) and rec["kind"].startswith("tool_seq_")
    assert isinstance(rec["session"], str)
    if rec["kind"] == "tool_seq_3":
        assert isinstance(rec["tools"], list) and len(rec["tools"]) == 3
        assert all(isinstance(t, str) and t for t in rec["tools"])
        assert isinstance(rec["signature"], str) and len(rec["signature"]) == 12


def _post(tmp_path: Path, tool: str, session: str = "s-1") -> None:
    payload = json.dumps({
        "cwd": str(tmp_path), "session_id": session, "tool_name": tool,
        "tool_input": {"file_path": "x.py"}, "tool_response": {"success": True},
    })
    subprocess.run([PYTHON, POST_TOOL], input=payload, capture_output=True, text=True)


# ---------- AC-PATTERN-001a ----------

def test_real_session_produces_schema_valid_patterns(tmp_path: Path) -> None:
    for tool in ("Read", "Edit", "Bash", "Read"):
        _post(tmp_path, tool)
    patterns = tmp_path / ".forge" / "patterns.jsonl"
    assert patterns.exists()
    lines = [l for l in patterns.read_text().splitlines() if l.strip()]
    assert lines, "patterns.jsonl is empty after a multi-tool session"
    for line in lines:
        _validate_record(json.loads(line))


# ---------- AC-PATTERN-001b ----------

def test_three_use_signature_fires_proposal(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir()
    # 3 occurrences of one substantive signature: >=2 tool types, >=2 sessions,
    # first->last span >= 60s (mine-skills._is_substantive).
    records = [
        {"schema_version": 1, "ts": "2026-06-09T10:00:00Z", "kind": "tool_seq_3",
         "tools": ["Read", "Edit", "Bash"], "signature": "sig123456789", "session": "s-1"},
        {"schema_version": 1, "ts": "2026-06-09T10:01:30Z", "kind": "tool_seq_3",
         "tools": ["Read", "Edit", "Bash"], "signature": "sig123456789", "session": "s-2"},
        {"schema_version": 1, "ts": "2026-06-09T10:03:00Z", "kind": "tool_seq_3",
         "tools": ["Read", "Edit", "Bash"], "signature": "sig123456789", "session": "s-1"},
    ]
    forge.joinpath("patterns.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in records)
    )
    r = subprocess.run(
        [PYTHON, MINE, "--cwd", str(tmp_path), "--plugin-dir", str(ROOT)],
        capture_output=True, text=True,
    )
    # mine-skills exit code = number of proposals written; a proposal dir appears.
    proposals = list((forge / "proposed-skills").glob("*/SKILL.md")) if (forge / "proposed-skills").exists() else []
    assert r.returncode >= 1 or proposals, f"no proposal fired: {r.stdout}\n{r.stderr}"
