"""Tests for hooks/_error_log.py — size-bounded log rotation (T-146, REQ-F-049).

Append-only `.forge` logs (hook-errors.log, daemon findings) grow unbounded without
rotation. `rotate_if_needed` rolls a log to numbered backups (.1, .2, …) once it hits a
byte ceiling, keeping at most `keep` backups; `append_jsonl` rotates-then-appends. Both
must be atomic-per-rename and never raise (they run on the hot hook path).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
_mod_path = _root / "hooks" / "_error_log.py"
_spec = importlib.util.spec_from_file_location("_error_log", _mod_path)
_el = importlib.util.module_from_spec(_spec)
sys.modules["_error_log"] = _el
_spec.loader.exec_module(_el)


# --- rotate_if_needed -------------------------------------------------------

def test_no_rotation_below_threshold(tmp_path: Path) -> None:
    p = tmp_path / "x.log"
    p.write_text("a\n")
    assert _el.rotate_if_needed(p, max_bytes=1000) is False
    assert p.read_text() == "a\n"
    assert not (tmp_path / "x.log.1").exists()


def test_rotates_at_threshold(tmp_path: Path) -> None:
    p = tmp_path / "x.log"
    p.write_text("x" * 100)
    assert _el.rotate_if_needed(p, max_bytes=50, keep=1) is True
    # live log moved to .1; original gone so the next append starts fresh (no data loss)
    assert not p.exists()
    assert (tmp_path / "x.log.1").read_text() == "x" * 100


def test_keep_multiple_backups_drops_oldest(tmp_path: Path) -> None:
    p = tmp_path / "x.log"
    (tmp_path / "x.log.1").write_text("one")
    (tmp_path / "x.log.2").write_text("two")  # oldest; with keep=2 it is dropped
    p.write_text("live" * 50)
    assert _el.rotate_if_needed(p, max_bytes=10, keep=2) is True
    assert not p.exists()
    assert (tmp_path / "x.log.1").read_text() == "live" * 50  # live -> .1
    assert (tmp_path / "x.log.2").read_text() == "one"        # old .1 -> .2
    assert not (tmp_path / "x.log.3").exists()                # old .2 dropped


def test_keep_zero_truncates_without_backup(tmp_path: Path) -> None:
    p = tmp_path / "x.log"
    p.write_text("x" * 100)
    assert _el.rotate_if_needed(p, max_bytes=10, keep=0) is True
    assert not p.exists()
    assert not (tmp_path / "x.log.1").exists()


def test_missing_file_is_safe(tmp_path: Path) -> None:
    assert _el.rotate_if_needed(tmp_path / "nope.log", max_bytes=1) is False


def test_disabled_when_max_bytes_nonpositive(tmp_path: Path) -> None:
    p = tmp_path / "x.log"
    p.write_text("x" * 100)
    assert _el.rotate_if_needed(p, max_bytes=0) is False
    assert p.read_text() == "x" * 100  # untouched


def test_never_raises_on_directory_path(tmp_path: Path) -> None:
    d = tmp_path / "adir"
    d.mkdir()
    # A directory where a file is expected must not raise — just no-op.
    assert _el.rotate_if_needed(d, max_bytes=1) in (True, False)


# --- append_jsonl -----------------------------------------------------------

def test_append_jsonl_creates_and_appends(tmp_path: Path) -> None:
    p = tmp_path / "f.jsonl"
    _el.append_jsonl(p, {"a": 1}, max_bytes=1_000_000)
    _el.append_jsonl(p, {"a": 2}, max_bytes=1_000_000)
    rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    assert rows == [{"a": 1}, {"a": 2}]


def test_append_jsonl_rotates_then_appends(tmp_path: Path) -> None:
    p = tmp_path / "f.jsonl"
    p.write_text("x" * 100)
    _el.append_jsonl(p, {"a": 1}, max_bytes=50, keep=1)
    assert (tmp_path / "f.jsonl.1").read_text() == "x" * 100  # old content preserved
    assert p.read_text() == json.dumps({"a": 1}) + "\n"        # fresh file, one record
