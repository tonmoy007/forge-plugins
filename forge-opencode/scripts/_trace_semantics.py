#!/usr/bin/env python3
"""Semantic enrichment + episode segmentation for the v0.3.5 skill miner.

This is a **stdlib-only, never-raises LIBRARY** — the deterministic foundation
the rest of the semantic miner (T-178+) imports. It turns the raw tool-call
stream that `hooks/post-tool-use.py` writes to `.forge/session-log.jsonl` into
something a miner can reason about:

  1. `read_session_log(path)` — fail-soft reader. Missing/empty/malformed input
     yields `[]` or skips the offending line; it never raises.
  2. `enrich(calls)` — canonicalize each raw call into an `EnrichedCall`
     `(verb, args, outcome)` via a SMALL, explicit, data-driven rule table
     mapping `(tool, arg-pattern, exit/result, stage) -> intent verb`
     (REQ-SM-001). Differing literals (file name, command, error string) are
     preserved inside `args` so a later pass can anti-unify them.
  3. `segment(enriched)` — split the enriched stream into outcome-bounded
     `Episode`s (REQ-SM-002). A new user turn / session starts one; a terminal
     success ends one; we segment at outcome transitions, treating the
     **failure->fix delta** as the highest-signal boundary.

Why semantics over tool names: `Bash`, `Read`, `Write`, `Edit` appear in every
workflow, so tool-name n-grams are semantically empty. The verb stream
(`run-tests(fail) -> inspect -> patch -> run-tests(pass) -> add-regression-test`)
is the actual problem-solving shape the miner needs.

REQ-IDs: REQ-SM-001, REQ-SM-002. NF: REQ-NF-016 (stdlib, never-raises).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Outcomes (small, closed vocabulary)
# ---------------------------------------------------------------------------

OUTCOME_PASS = "pass"
OUTCOME_FAIL = "fail"
OUTCOME_NEUTRAL = "neutral"  # actions that are neither a success nor a failure signal

GENERIC_VERB = "act"  # unknown calls map here, never raise


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class EnrichedCall:
    """A single tool call lifted into semantic terms.

    `verb` is the canonical intent (e.g. `run-tests`, `patch`, `inspect`).
    `args` preserves the differing literals (file, command, ...) so a later
    anti-unification pass can lift them to parameters.
    `outcome` is one of pass / fail / neutral.
    """

    verb: str
    args: dict[str, str]
    outcome: str
    tool: str
    session: str = ""


@dataclass
class Episode:
    """An outcome-bounded slice of the enriched stream.

    `outcome` is "success" if the episode ended on a passing outcome, else
    "incomplete". `has_fix_boundary` is True when the episode contains a
    failure followed by a recovery (the failure->fix delta) — the
    highest-signal motif for skill mining.
    """

    calls: list[EnrichedCall] = field(default_factory=list)
    outcome: str = "incomplete"
    session: str = ""
    has_fix_boundary: bool = False


# ---------------------------------------------------------------------------
# Fail-soft reader
# ---------------------------------------------------------------------------


def read_session_log(path: Path) -> list[dict]:
    """Read `.forge/session-log.jsonl`. Never raises.

    Missing file -> []. Blank/malformed lines are skipped. Any unexpected I/O
    or decode error yields [] (or the records parsed so far).
    """
    try:
        path = Path(path)
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — hot/background path must never raise
        return []
    records: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            records.append(obj)
    return records


# ---------------------------------------------------------------------------
# Canonicalization rule table (REQ-SM-001)
# ---------------------------------------------------------------------------

# Heuristic markers, kept small and explicit.
_TEST_CMD_RE = re.compile(
    r"\b(pytest|unittest|jest|vitest|go\s+test|cargo\s+test|npm\s+(?:run\s+)?test|tox|nose)\b",
    re.IGNORECASE,
)
_TEST_FILE_RE = re.compile(r"(?:^|/)(test_[^/]+|[^/]+_test|.*\.test\.[a-z]+|.*\.spec\.[a-z]+)$")
_SOURCE_EXT = (
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".c",
    ".cc", ".cpp", ".h", ".hpp", ".cs", ".kt", ".swift", ".php", ".scala",
)


def _is_test_command(command: str) -> bool:
    return bool(command) and bool(_TEST_CMD_RE.search(command))


def _is_test_file(file: str) -> bool:
    return bool(file) and bool(_TEST_FILE_RE.search(file))


def _is_source_file(file: str) -> bool:
    return bool(file) and file.endswith(_SOURCE_EXT) and not _is_test_file(file)


def _outcome_of(success: bool) -> str:
    return OUTCOME_PASS if success else OUTCOME_FAIL


def canonicalize(call: dict, prior_outcome: Optional[str]) -> EnrichedCall:
    """Map one raw session-log record to an `EnrichedCall`. Never raises.

    `prior_outcome` is the outcome of the most recent test run seen so far in
    the stream (pass / fail / None) — context that distinguishes an `Edit`
    that is a `patch` (after a failing test) from one that is a plain edit.

    Rule table (tool, arg-pattern, exit/result, stage) -> intent verb:
      - Bash running a test command, exit != 0   -> run-tests (fail)
      - Bash running a test command, exit == 0    -> run-tests (pass)
      - Edit/Write to a source file after a fail  -> patch
      - Write to a test_* file after green         -> add-regression-test
      - Read                                       -> inspect
      - Edit/Write (other)                         -> edit
      - Bash (non-test)                            -> run-command
      - anything else / unknown                    -> act (generic)
    """
    if not isinstance(call, dict):
        return EnrichedCall(verb=GENERIC_VERB, args={}, outcome=OUTCOME_NEUTRAL, tool="")

    tool = str(call.get("tool", "") or "")
    file = str(call.get("file", "") or "")
    command = str(call.get("command", "") or "")
    session = str(call.get("session", "") or "")
    success = bool(call.get("success", True))

    args: dict[str, str] = {}
    if file:
        args["file"] = file
    if command:
        args["command"] = command

    # --- Bash: distinguish test runs from plain commands.
    if tool == "Bash":
        if _is_test_command(command):
            return EnrichedCall(
                verb="run-tests",
                args=args,
                outcome=_outcome_of(success),
                tool=tool,
                session=session,
            )
        return EnrichedCall(
            verb="run-command",
            args=args,
            outcome=OUTCOME_NEUTRAL,
            tool=tool,
            session=session,
        )

    # --- Read: always inspection.
    if tool == "Read":
        return EnrichedCall(
            verb="inspect", args=args, outcome=OUTCOME_NEUTRAL, tool=tool, session=session
        )

    # --- Edit / Write: intent depends on target file + prior test outcome.
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        if tool in ("Write", "MultiEdit") and _is_test_file(file) and prior_outcome == OUTCOME_PASS:
            return EnrichedCall(
                verb="add-regression-test",
                args=args,
                outcome=OUTCOME_NEUTRAL,
                tool=tool,
                session=session,
            )
        if _is_source_file(file) and prior_outcome == OUTCOME_FAIL:
            return EnrichedCall(
                verb="patch", args=args, outcome=OUTCOME_NEUTRAL, tool=tool, session=session
            )
        if _is_test_file(file):
            return EnrichedCall(
                verb="write-test", args=args, outcome=OUTCOME_NEUTRAL, tool=tool, session=session
            )
        return EnrichedCall(
            verb="edit", args=args, outcome=OUTCOME_NEUTRAL, tool=tool, session=session
        )

    # --- Unknown / unhandled tool -> generic verb, never raise.
    return EnrichedCall(
        verb=GENERIC_VERB, args=args, outcome=OUTCOME_NEUTRAL, tool=tool, session=session
    )


def enrich(calls: list[dict]) -> list[EnrichedCall]:
    """Canonicalize a stream of raw records into EnrichedCalls. Never raises.

    Carries the most recent test outcome forward as context so `patch` and
    `add-regression-test` can be distinguished from plain edits.
    """
    if not calls:
        return []
    enriched: list[EnrichedCall] = []
    prior_test_outcome: Optional[str] = None
    for call in calls:
        ec = canonicalize(call, prior_test_outcome)
        if ec.verb == "run-tests":
            prior_test_outcome = ec.outcome
        enriched.append(ec)
    return enriched


# ---------------------------------------------------------------------------
# Episode segmentation (REQ-SM-002)
# ---------------------------------------------------------------------------


def _finalize(calls: list[EnrichedCall], ended_on_pass: bool) -> Episode:
    """Build an Episode from accumulated calls, computing its boundary flags."""
    saw_fail = False
    has_fix_boundary = False
    for ec in calls:
        if ec.verb == "run-tests":
            if ec.outcome == OUTCOME_FAIL:
                saw_fail = True
            elif ec.outcome == OUTCOME_PASS and saw_fail:
                # A failing test recovered to a passing one — the failure->fix
                # delta, the highest-signal boundary for skill mining.
                has_fix_boundary = True
    session = calls[0].session if calls else ""
    return Episode(
        calls=list(calls),
        outcome="success" if ended_on_pass else "incomplete",
        session=session,
        has_fix_boundary=has_fix_boundary,
    )


# Verbs that semantically belong to the just-closed fix episode when they
# directly follow a passing test (e.g. writing the regression test that proves
# the fix). They extend the episode rather than starting a fresh one.
_TRAILING_VERBS = ("add-regression-test", "write-test")


def segment(enriched: list[EnrichedCall]) -> list[Episode]:
    """Split the enriched stream into outcome-bounded episodes. Never raises.

    Boundaries:
      - a terminal success (a passing `run-tests`) ends the current episode —
        but a directly-following regression/test-writing step is pulled into
        that episode first, since it belongs to the fix it proves;
      - a session change starts a new episode (a new user turn / task);
      - the failure->fix transition within an episode is detected and flagged
        (`has_fix_boundary`) rather than split, since the fix delta is the
        coherent unit a skill should capture.
    """
    if not enriched:
        return []
    episodes: list[Episode] = []
    current: list[EnrichedCall] = []
    current_session: Optional[str] = None
    reached_pass = False

    for ec in enriched:
        # Session boundary: a new task starts -> close any open episode.
        if current and ec.session != current_session:
            episodes.append(_finalize(current, ended_on_pass=reached_pass))
            current = []
            current_session = None
            reached_pass = False

        # A new non-trailing call after the episode already passed begins a
        # fresh episode (e.g. a second failure->fix cycle in the same session).
        if current and reached_pass and ec.verb not in _TRAILING_VERBS:
            episodes.append(_finalize(current, ended_on_pass=True))
            current = []
            current_session = None
            reached_pass = False

        if current_session is None:
            current_session = ec.session
        current.append(ec)

        # Terminal success: a passing test marks the episode resolved. The
        # episode is not closed immediately — a directly-following regression /
        # test-writing step (the test that proves the fix) is pulled in first;
        # the next non-trailing call (or end of stream) closes it.
        if ec.verb == "run-tests" and ec.outcome == OUTCOME_PASS:
            reached_pass = True

    if current:
        episodes.append(_finalize(current, ended_on_pass=reached_pass))
    return episodes
