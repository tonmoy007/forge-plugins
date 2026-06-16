"""Tests for scripts/skill_miner_bg.py.

The background skill-miner now DRIVES the v0.3.5 semantic miner
(scripts/skill_miner_v2.py) over .forge/session-log.jsonl, having retired the v1
n-gram dispatch (T-183, REQ-SM-010). It reads the session log, enriches it into
semantic verb episodes, gates on success + anti-unification, induces (LLM, gated +
degrading), and emits .forge/proposed-skills/<slug>/SKILL.md — the same canonical
artifact the approval flow consumes.

It remains instrumented for the spike's O-2 number: every run records a completion
marker + cost to .forge/skill-miner-runs.jsonl; completion_stats() reads those
markers. Must never raise.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
_mod_path = _root / "scripts" / "skill_miner_bg.py"
_spec = importlib.util.spec_from_file_location("skill_miner_bg", _mod_path)
_smb = importlib.util.module_from_spec(_spec)
sys.modules["skill_miner_bg"] = _smb
_spec.loader.exec_module(_smb)

NOW = dt.datetime(2026, 6, 10, 12, 0, 0, tzinfo=dt.timezone.utc)


# --- session-log fixtures ---------------------------------------------------

def _call(tool: str, file: str = "", success: bool = True,
          session: str = "s1", command: str = "") -> dict:
    rec: dict = {
        "ts": "2026-06-16T12:00:00Z",
        "session": session,
        "tool": tool,
        "file": file,
        "success": success,
        "stage": 6,
    }
    if command:
        rec["command"] = command
    return rec


def _fix_episode(src: str, test_cmd: str, test_file: str, session: str) -> list[dict]:
    """A successful failure->fix->regression episode (ends green)."""
    return [
        _call("Bash", success=False, session=session, command=test_cmd),
        _call("Read", file=src, session=session),
        _call("Edit", file=src, session=session),
        _call("Bash", success=True, session=session, command=test_cmd),
        _call("Write", file=test_file, session=session),
    ]


def _write_log(forge: Path, records: list[dict]) -> None:
    forge.mkdir(parents=True, exist_ok=True)
    (forge / "session-log.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )


# --- completion stats math (unchanged contract) ----------------------------

def test_completion_stats_excludes_skipped(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    for _ in range(4):
        _smb.record_run(forge, "s", "completed", 0.005, now=NOW)
    _smb.record_run(forge, "s", "failed", 0.0, now=NOW)
    for _ in range(5):
        _smb.record_run(forge, "s", "skipped", 0.0, now=NOW)
    stats = _smb.completion_stats(forge)
    assert stats["completed"] == 4
    assert stats["failed"] == 1
    assert stats["skipped"] == 5
    assert stats["completion_rate"] == 0.8  # 4 / (4+1), skipped excluded


def test_completion_stats_empty_is_safe(tmp_path: Path) -> None:
    stats = _smb.completion_stats(tmp_path / ".forge")
    assert stats["n"] == 0
    assert stats["completion_rate"] is None  # no runs yet → undefined, not a crash


def test_completion_stats_90_boundary(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    for _ in range(9):
        _smb.record_run(forge, "s", "completed", 0.005, now=NOW)
    _smb.record_run(forge, "s", "failed", 0.0, now=NOW)
    assert _smb.completion_stats(forge)["completion_rate"] == 0.9


# --- run() drives the v2 pipeline ------------------------------------------

def test_run_empty_log_completes_no_proposals(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    # No session-log → fail-soft read → zero episodes → zero candidates.
    status = _smb.run(forge, session_id="sess", cwd=str(tmp_path), now=NOW)
    assert status == "completed"
    assert not (forge / "proposed-skills").exists() or not list(
        (forge / "proposed-skills").glob("*/SKILL.md")
    )
    runs = [json.loads(l) for l in (forge / "skill-miner-runs.jsonl").read_text().splitlines() if l.strip()]
    assert runs[-1]["status"] == "completed"


def test_run_emits_deterministic_proposal_when_background_off(
    tmp_path: Path, monkeypatch
) -> None:
    # FORGE_NO_BACKGROUND forces the deterministic path: the miner still mines the
    # semantic episodes and emits a skeleton proposal — no LLM, no crash.
    monkeypatch.setenv("FORGE_NO_BACKGROUND", "1")
    forge = tmp_path / ".forge"
    records: list[dict] = []
    # Three distinct SUCCESSFUL fix episodes with differing names → one candidate.
    for i in range(3):
        records += _fix_episode(f"src/a{i}.py", "pytest", f"test_a{i}.py", session=f"s{i}")
    _write_log(forge, records)

    status = _smb.run(forge, session_id="sess", cwd=str(tmp_path), now=NOW)
    assert status == "completed"

    proposals = list((forge / "proposed-skills").glob("*/SKILL.md"))
    assert proposals, "deterministic miner should emit at least one proposal"
    body = proposals[0].read_text()
    assert "status: proposed" in body
    assert "source: deterministic" in body  # degraded, never an LLM call


def test_run_honors_blacklist(tmp_path: Path, monkeypatch) -> None:
    # Clean migration: a blacklisted motif signature is not re-proposed.
    monkeypatch.setenv("FORGE_NO_BACKGROUND", "1")
    forge = tmp_path / ".forge"
    records: list[dict] = []
    for i in range(3):
        records += _fix_episode(f"src/a{i}.py", "pytest", f"test_a{i}.py", session=f"s{i}")
    _write_log(forge, records)

    # First run to discover the signature this stream produces, then blacklist it.
    _smb.run(forge, session_id="sess", cwd=str(tmp_path), now=NOW)
    first = sorted((forge / "proposed-skills").glob("*/SKILL.md"))
    assert first
    sig_line = next(
        ln for ln in first[0].read_text().splitlines() if "Pattern signature:" in ln
    )
    signature = sig_line.split("`")[1]

    # New forge dir, same stream, signature blacklisted → nothing emitted.
    forge2 = tmp_path / ".forge2"
    _write_log(forge2, records)
    forge2.mkdir(parents=True, exist_ok=True)
    (forge2 / "skill-blacklist.txt").write_text(signature + "\n", encoding="utf-8")
    _smb.run(forge2, session_id="sess", cwd=str(tmp_path), now=NOW)
    assert not list((forge2 / "proposed-skills").glob("*/SKILL.md"))


def test_run_preserves_existing_proposal_dir(tmp_path: Path, monkeypatch) -> None:
    # Clean migration: an existing proposed-skills/<slug>/ (e.g. a user edit) is
    # never clobbered by a re-mine.
    monkeypatch.setenv("FORGE_NO_BACKGROUND", "1")
    forge = tmp_path / ".forge"
    records: list[dict] = []
    for i in range(3):
        records += _fix_episode(f"src/a{i}.py", "pytest", f"test_a{i}.py", session=f"s{i}")
    _write_log(forge, records)
    _smb.run(forge, session_id="sess", cwd=str(tmp_path), now=NOW)
    slug_dir = sorted((forge / "proposed-skills").glob("*"))[0]
    sentinel = slug_dir / "SKILL.md"
    sentinel.write_text("USER EDIT", encoding="utf-8")

    _smb.run(forge, session_id="sess", cwd=str(tmp_path), now=NOW)
    assert sentinel.read_text() == "USER EDIT"  # untouched


def test_run_never_raises_on_garbage_log(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "session-log.jsonl").write_text("not json\n{broken\n", encoding="utf-8")
    status = _smb.run(forge, session_id="sess", cwd=str(tmp_path), now=NOW)
    # Malformed lines are skipped by the fail-soft reader; run still completes.
    assert status == "completed"


def test_run_no_longer_references_ngram_artifact() -> None:
    # T-183 regression guard: the dead-end proposals.jsonl / patterns.jsonl n-gram
    # path must be fully retired from the worker.
    src = _mod_path.read_text()
    assert "proposals.jsonl" not in src
    assert "patterns.jsonl" not in src
    assert "skill_miner_v2" in src  # drives v2


def test_main_cli_smoke(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    rc = _smb.main(["--forge-dir", str(forge), "--session", "s", "--cwd", str(tmp_path)])
    assert rc == 0
    assert (forge / "skill-miner-runs.jsonl").exists()
