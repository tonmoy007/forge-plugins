"""Tests for scripts/check_schema_compat.py (T-133 / REQ-PROFILE-DATACONTRACT-001).

The gate is schema HYGIENE + POLICY, not a semantic cross-version diff:
  - protobuf: no duplicate field numbers within a message/enum scope
  - buf.yaml (if present): must declare a `breaking:` policy
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_script = Path(__file__).resolve().parent.parent.parent / "scripts" / "check_schema_compat.py"
_spec = importlib.util.spec_from_file_location("check_schema_compat", _script)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def _run(cwd: Path) -> int:
    return _mod.main(["--cwd", str(cwd)])


def test_clean_proto_passes(tmp_path: Path) -> None:
    (tmp_path / "user.proto").write_text(
        'syntax = "proto3";\n'
        "message User {\n"
        "  string id = 1;\n"
        "  string name = 2;\n"
        "  repeated string tags = 3;\n"
        "}\n"
    )
    assert _run(tmp_path) == 0


def test_duplicate_field_number_fails(tmp_path: Path) -> None:
    (tmp_path / "bad.proto").write_text(
        "message Bad {\n"
        "  string a = 1;\n"
        "  string b = 1;\n"   # duplicate field number
        "}\n"
    )
    assert _run(tmp_path) == 1


def test_duplicate_across_nested_messages_is_ok(tmp_path: Path) -> None:
    # Each message has its own field-number space — number 1 in two different
    # messages is fine, not a duplicate.
    (tmp_path / "nested.proto").write_text(
        "message Outer {\n"
        "  string a = 1;\n"
        "  message Inner {\n"
        "    string b = 1;\n"
        "  }\n"
        "}\n"
    )
    assert _run(tmp_path) == 0


def test_buf_without_breaking_policy_fails(tmp_path: Path) -> None:
    (tmp_path / "buf.yaml").write_text("version: v1\nlint:\n  use: [DEFAULT]\n")
    assert _run(tmp_path) == 1


def test_buf_with_breaking_policy_passes(tmp_path: Path) -> None:
    (tmp_path / "buf.yaml").write_text("version: v1\nbreaking:\n  use: [FILE]\n")
    assert _run(tmp_path) == 0


def test_no_schemas_is_noop_pass(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("nothing to gate here\n")
    assert _run(tmp_path) == 0


def test_oneof_fields_share_message_number_space(tmp_path: Path) -> None:
    # A oneof's fields belong to the enclosing message's number space, so a
    # collision between a plain field and a oneof field must be caught.
    (tmp_path / "of.proto").write_text(
        "message M {\n"
        "  string a = 1;\n"
        "  oneof choice {\n"
        "    string b = 1;\n"   # collides with `a`
        "  }\n"
        "}\n"
    )
    assert _run(tmp_path) == 1
