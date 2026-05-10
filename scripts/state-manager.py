#!/usr/bin/env python3
"""CLI for reading and writing pipeline/state.md.

Usage:
    python scripts/state-manager.py [--cwd PATH] <subcommand> [options]

Subcommands:
    read [--field FIELD]
    advance [--to N]
    set --field FIELD --value VALUE
    reflect TEXT
    history-add --stage N --result RESULT [--note NOTE]
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

# Ensure _state_lib is importable regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _state_lib as lib


def cmd_read(args: argparse.Namespace, cwd: str) -> None:
    state = lib.read_state(cwd)
    if args.field:
        if args.field not in state:
            print(f"error: unknown field '{args.field}'", file=sys.stderr)
            sys.exit(1)
        print(state[args.field])
    else:
        print(json.dumps(state, indent=2, default=str))


def cmd_advance(args: argparse.Namespace, cwd: str) -> None:
    new_state = lib.advance_stage(cwd, to=args.to)
    print(json.dumps(new_state, indent=2, default=str))


def cmd_set(args: argparse.Namespace, cwd: str) -> None:
    if args.field not in lib.REQUIRED_FIELDS:
        print(f"error: unknown field '{args.field}'", file=sys.stderr)
        sys.exit(1)
    state = lib.read_state(cwd)
    expected = lib.REQUIRED_FIELDS[args.field]
    types = expected if isinstance(expected, tuple) else (expected,)
    value: object = args.value
    if type(None) in types and args.value.lower() in ("null", "none", ""):
        value = None
    elif int in types:
        try:
            value = int(args.value)
        except ValueError:
            pass
    state[args.field] = value
    lib.write_state(cwd, state)
    print(f"set {args.field} = {value!r}", file=sys.stderr)


def cmd_reflect(args: argparse.Namespace, cwd: str) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lib.append_to_section(cwd, "Last Reflection", f"{now}: {args.text}")
    print("reflected", file=sys.stderr)


def cmd_history_add(args: argparse.Namespace, cwd: str) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    row = f"| {args.stage} | {now} | | {args.result} | {args.note} |"
    lib.append_to_section(cwd, "Stage History", row)
    print(f"added history row for stage {args.stage}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="state-manager.py",
        description="Read and write pipeline/state.md",
    )
    parser.add_argument(
        "--cwd",
        default=os.getcwd(),
        metavar="PATH",
        help="project root containing pipeline/state.md (default: cwd)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_read = sub.add_parser("read", help="print state frontmatter as JSON")
    p_read.add_argument("--field", metavar="FIELD", help="print just this field's value")

    p_adv = sub.add_parser("advance", help="increment current_stage")
    p_adv.add_argument("--to", type=int, metavar="N", help="jump to stage N instead of +1")

    p_set = sub.add_parser("set", help="set a single frontmatter field")
    p_set.add_argument("--field", required=True, metavar="FIELD")
    p_set.add_argument("--value", required=True, metavar="VALUE")

    p_ref = sub.add_parser("reflect", help="append text to Last Reflection section")
    p_ref.add_argument("text", help="reflection content")

    p_hist = sub.add_parser("history-add", help="append a row to Stage History table")
    p_hist.add_argument("--stage", required=True, type=int, metavar="N")
    p_hist.add_argument("--result", required=True, metavar="RESULT")
    p_hist.add_argument("--note", default="", metavar="NOTE")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {
        "read": cmd_read,
        "advance": cmd_advance,
        "set": cmd_set,
        "reflect": cmd_reflect,
        "history-add": cmd_history_add,
    }
    dispatch[args.command](args, args.cwd)


if __name__ == "__main__":
    main()
