"""T-118 / REQ-SESSIONLOG-001: session.jsonl enrichment.

AC-SESSIONLOG-001a: a session produces a session.jsonl row with commands, tokens,
                    and reflection_ref.
AC-SESSIONLOG-001b: a consumer rebuilds a session timeline from session.jsonl alone.
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
HOOK = str(ROOT / "hooks" / "session-end.py")
PYTHON = sys.executable
SESSION = "sess-118"


def _project(tmp_path: Path) -> Path:
    (tmp_path / "pipeline").mkdir(parents=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "pipeline" / "state.md").write_text(
        "---\nschema_version: 1\nproject_type: api\ncycle: 1\n"
        "current_stage: 6\ncurrent_task: T-007\ncurrent_milestone: M2\n"
        f"total_tasks: 10\nlast_updated: {now}\nblockers: []\n---\n\n# s\n"
    )
    forge = tmp_path / ".forge"
    forge.mkdir()
    # seed a session-log so commands can be derived
    forge.joinpath("session-log.jsonl").write_text(
        json.dumps({"ts": now, "session": SESSION, "tool": "Write", "file": "a.py"}) + "\n"
        + json.dumps({"ts": now, "session": SESSION, "tool": "Bash", "file": ""}) + "\n"
        + json.dumps({"ts": now, "session": "other", "tool": "Read", "file": "x"}) + "\n"
    )
    return tmp_path


def _run(tmp_path: Path, tokens=None) -> subprocess.CompletedProcess:
    payload = {"cwd": str(tmp_path), "session_id": SESSION}
    if tokens is not None:
        payload["usage"] = tokens
    return subprocess.run([PYTHON, HOOK], input=json.dumps(payload),
                          capture_output=True, text=True)


def _last_record(tmp_path: Path) -> dict:
    rows = (tmp_path / ".forge" / "session.jsonl").read_text().splitlines()
    return json.loads(rows[-1])


# ---------- AC-SESSIONLOG-001a ----------

def test_record_has_required_fields(tmp_path: Path) -> None:
    _project(tmp_path)
    r = _run(tmp_path, tokens={"input": 1200, "output": 800})
    assert r.returncode == 0, r.stderr
    rec = _last_record(tmp_path)
    assert rec["schema_version"] == 1
    assert rec["session_id"] == SESSION
    assert rec["commands"] == ["Write", "Bash"]          # this session's tools only
    assert rec["tokens"] == {"input": 1200, "output": 800}
    assert rec["reflection_ref"] == SESSION
    assert rec["stage"] == 6 and rec["project_type"] == "api"


def test_tokens_absent_is_empty_not_error(tmp_path: Path) -> None:
    _project(tmp_path)
    assert _run(tmp_path).returncode == 0
    assert _last_record(tmp_path)["tokens"] == {}


def test_no_pii_only_known_keys(tmp_path: Path) -> None:
    _project(tmp_path)
    _run(tmp_path, tokens={"total": 10})
    rec = _last_record(tmp_path)
    allowed = {"schema_version", "session_id", "ended_at", "stage", "project_type",
               "commands", "tokens", "reflection_ref", "lessons_added", "files_modified"}
    assert set(rec) == allowed  # no prompt text, no file paths


# ---------- AC-SESSIONLOG-001b: rebuild a timeline from the log alone ----------

def test_timeline_rebuildable_from_log_alone(tmp_path: Path) -> None:
    _project(tmp_path)
    _run(tmp_path, tokens={"total": 5})
    _run(tmp_path, tokens={"total": 7})
    rows = [json.loads(l) for l in
            (tmp_path / ".forge" / "session.jsonl").read_text().splitlines()]
    # a consumer can order by ended_at and read stage/commands/tokens/reflection_ref
    timeline = [(r["ended_at"], r["session_id"], r["stage"], r["reflection_ref"]) for r in rows]
    assert len(timeline) == 2
    assert all(t[1] == SESSION and t[2] == 6 for t in timeline)
    assert all(r["reflection_ref"] == r["session_id"] for r in rows)  # join key holds
