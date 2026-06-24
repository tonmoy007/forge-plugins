#!/usr/bin/env python3
"""Caveman mode (v0.6.1, REQ-CM-001) — opt-in terse-output preamble for free-prose dispatches.

A single stdlib lever ported from the `caveman` project under Forge's no-`pip` rule
(REQ-NF-024): a small instruction prepended to a `claude -p` prompt that tells the agent to answer
with maximum brevity, reducing the *output* tokens Forge pays for (recorded to the `_cost_cap`
ledger). Applied at exactly one site — `hooks/_background_agent.py:dispatch` — and **only** to
free-prose dispatches; the schema-constrained ones (verify verdicts, skeptics, gate, structured
miners) are skipped, because they are already minimal and telling them to be terse risks malformed
JSON and degraded reasoning.

Two intensities (REQ-CM-001):
  - ``lite`` — drop pleasantries / preamble / hedging / filler; keep plain sentences.
  - ``full`` — also drop articles where meaning stays clear and prefer fragments.
``ultra`` / ``wenyan`` / dictionary abbreviation are out of scope (accuracy risk; Forge output is
largely machine-read). An unknown level coerces to ``lite``.

Pure stdlib, **never raises** (REQ-NF-041): any internal error degrades to the original prompt, so
a malformed preamble can never break a dispatch. ``apply`` is the identity when disabled or when the
dispatch is schema-constrained, which keeps v0.6.0 byte-identical with the toggle off.
"""

from __future__ import annotations

# The preambles end with a blank line so the instruction never runs into the caller's prompt.
# Kept short — the preamble itself costs input tokens; the win is on the (pricier, larger) output.
_LITE_PREAMBLE = (
    "Answer with maximum brevity. No preamble, no pleasantries, no restating the request, "
    "no hedging, no filler — only the essential content, in plain sentences.\n\n"
)

_FULL_PREAMBLE = (
    "Answer with maximum brevity. No preamble, pleasantries, restating, hedging, or filler. "
    "Drop articles where meaning stays clear; prefer fragments over full sentences. "
    "Essential content only.\n\n"
)

_PREAMBLES = {"lite": _LITE_PREAMBLE, "full": _FULL_PREAMBLE}


def terse_preamble(level: str) -> str:
    """Return the terse-output preamble for ``level`` (``lite``|``full``); unknown ⇒ ``lite``.

    Pure: a stdlib dict lookup with a safe default, no I/O. An unrecognised level (typo,
    unsupported ``ultra``/``wenyan``, ``None``) returns the ``lite`` preamble rather than raising.
    """
    return _PREAMBLES.get(level, _LITE_PREAMBLE)


def apply(prompt: str, *, enabled: bool, has_schema: bool, level: str) -> str:
    """Prepend the terse preamble to ``prompt``, or return it unchanged (REQ-CM-001).

    Identity when ``enabled`` is false OR ``has_schema`` is true — a schema-constrained dispatch is
    never altered (REQ-NF-041). Otherwise returns ``terse_preamble(level) + prompt``. **Never
    raises**: any internal error (e.g. a non-string prompt, a monkeypatched-raising preamble)
    degrades to the original ``prompt``, so caveman can never break a dispatch.
    """
    try:
        if not enabled or has_schema:
            return prompt
        return terse_preamble(level) + prompt
    except Exception:  # noqa: BLE001 — caveman must never break a dispatch (REQ-NF-041)
        return prompt
