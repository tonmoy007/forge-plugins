"""Tests for hooks/_event_log.py — HMAC-chained event log."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hooks"))
import _event_log as event_log


def _append(forge_dir: Path, event_type: str = "TestEvent", stage: int = 1) -> None:
    event_log.append(
        forge_dir, event_type, "test-session", stage,
        {"key": "value"}, "accepted",
    )


class TestAppend:
    def test_creates_events_jsonl(self, tmp_path):
        forge_dir = tmp_path / ".forge"
        _append(forge_dir)
        assert (forge_dir / "events.jsonl").exists()

    def test_event_has_required_fields(self, tmp_path):
        forge_dir = tmp_path / ".forge"
        _append(forge_dir)
        line = (forge_dir / "events.jsonl").read_text().strip()
        event = json.loads(line)
        for field in ("id", "type", "session", "stage", "payload",
                      "validator_outcome", "occurred_at", "prev_hash", "signature"):
            assert field in event, f"missing field: {field}"

    def test_ids_increment(self, tmp_path):
        forge_dir = tmp_path / ".forge"
        _append(forge_dir)
        _append(forge_dir)
        _append(forge_dir)
        lines = (forge_dir / "events.jsonl").read_text().strip().splitlines()
        ids = [json.loads(ln)["id"] for ln in lines]
        assert ids == [1, 2, 3]

    def test_first_event_prev_hash_is_genesis(self, tmp_path):
        forge_dir = tmp_path / ".forge"
        _append(forge_dir)
        event = json.loads((forge_dir / "events.jsonl").read_text().strip())
        key = event_log._load_key(forge_dir)
        assert event["prev_hash"] == event_log._genesis_hash(key)

    def test_subsequent_prev_hash_chains(self, tmp_path):
        forge_dir = tmp_path / ".forge"
        _append(forge_dir)
        _append(forge_dir)
        lines = (forge_dir / "events.jsonl").read_text().strip().splitlines()
        line1, line2 = lines[0], lines[1]
        e2 = json.loads(line2)
        assert e2["prev_hash"] == event_log._line_hash(line1)


class TestVerify:
    def test_empty_log_verifies_ok(self, tmp_path):
        forge_dir = tmp_path / ".forge"
        forge_dir.mkdir()
        ok, reason = event_log.verify(forge_dir)
        assert ok
        assert reason == "no events"

    def test_valid_chain_verifies_ok(self, tmp_path):
        forge_dir = tmp_path / ".forge"
        for _ in range(3):
            _append(forge_dir)
        ok, reason = event_log.verify(forge_dir)
        assert ok, reason

    def test_tampered_payload_fails_verify(self, tmp_path):
        forge_dir = tmp_path / ".forge"
        _append(forge_dir)
        _append(forge_dir)
        path = forge_dir / "events.jsonl"
        lines = path.read_text().strip().splitlines()
        # Tamper the first event's payload
        e1 = json.loads(lines[0])
        e1["payload"] = {"key": "TAMPERED"}
        lines[0] = json.dumps(e1)
        path.write_text("\n".join(lines) + "\n")
        ok, reason = event_log.verify(forge_dir)
        assert not ok

    def test_tampered_prev_hash_fails_verify(self, tmp_path):
        forge_dir = tmp_path / ".forge"
        _append(forge_dir)
        _append(forge_dir)
        path = forge_dir / "events.jsonl"
        lines = path.read_text().strip().splitlines()
        e2 = json.loads(lines[1])
        e2["prev_hash"] = "deadbeef" * 8
        lines[1] = json.dumps(e2)
        path.write_text("\n".join(lines) + "\n")
        ok, reason = event_log.verify(forge_dir)
        assert not ok
        assert "prev_hash" in reason

    def test_invalid_json_line_fails_verify(self, tmp_path):
        forge_dir = tmp_path / ".forge"
        _append(forge_dir)
        path = forge_dir / "events.jsonl"
        path.write_text(path.read_text() + "not-json\n")
        ok, reason = event_log.verify(forge_dir)
        assert not ok
        assert "invalid JSON" in reason
