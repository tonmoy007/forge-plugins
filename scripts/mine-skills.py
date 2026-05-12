#!/usr/bin/env python3
"""Aggregate .forge/patterns.jsonl by signature and emit SKILL.md drafts.

Input:
    .forge/patterns.jsonl         — sliding 3-tool windows from T-026
    .forge/skill-blacklist.txt    — signatures the user rejected (one per line)
    skills/*/SKILL.md             — existing skills (name collisions excluded)

Output:
    .forge/proposed-skills/<slug>/SKILL.md  — one draft per qualifying pattern
    stdout                                   — one written-path per line

Exit code:
    0 when no proposals were written
    N when N proposals were written (cap at 100 for shell-exit sanity)

The draft is deterministic and rule-based. The skill-miner agent (T-016)
is the LLM-driven upgrade path; T-027 ships the rule-based fallback so
mining works with no model call.

REQ-IDs: REQ-071 (frequency threshold ≥3), REQ-072 (skill draft generation),
REQ-074 (rejected pattern blacklist).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = 3
_EXIT_CAP = 100  # cap stdlib exit code to a sane range

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PatternRecord:
    ts: str
    session: str
    tools: list[str]
    signature: str


@dataclass
class Candidate:
    signature: str
    tools: list[str]
    count: int
    first_seen: str
    last_seen: str
    sessions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_patterns(path: Path, session: Optional[str] = None) -> list[PatternRecord]:
    """Read patterns.jsonl. Silently skip malformed lines. Returns [] if missing."""
    if not path.exists():
        return []
    records: list[PatternRecord] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("line %d: skipping malformed JSON", lineno)
            continue
        sig = obj.get("signature")
        tools = obj.get("tools")
        ts = obj.get("ts", "")
        sess = obj.get("session", "")
        if not sig or not isinstance(tools, list) or not tools:
            logger.warning("line %d: missing signature or tools — skipped", lineno)
            continue
        if session is not None and sess != session:
            continue
        records.append(
            PatternRecord(ts=ts, session=sess, tools=[str(t) for t in tools], signature=sig)
        )
    return records


def load_blacklist(path: Path) -> set[str]:
    """Read .forge/skill-blacklist.txt. Lines starting with `#` are comments."""
    if not path.exists():
        return set()
    out: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line)
    return out


def load_existing_skill_names(plugin_dir: Path) -> set[str]:
    """Inspect all skills/*/SKILL.md frontmatter for `name:` and return the set."""
    skills_dir = plugin_dir / "skills"
    names: set[str] = set()
    if not skills_dir.exists():
        return names
    for skill_md in skills_dir.glob("*/SKILL.md"):
        try:
            text = skill_md.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines()[:30]:
            m = re.match(r"^name:\s*(\S+)", line)
            if m:
                names.add(m.group(1).strip())
                break
    return names


# ---------------------------------------------------------------------------
# Aggregation + slug generation
# ---------------------------------------------------------------------------


def aggregate(records: Iterable[PatternRecord]) -> dict[str, Candidate]:
    """Group records by signature; track count, first/last ts, sessions."""
    groups: dict[str, Candidate] = {}
    for r in records:
        c = groups.get(r.signature)
        if c is None:
            groups[r.signature] = Candidate(
                signature=r.signature,
                tools=list(r.tools),
                count=1,
                first_seen=r.ts,
                last_seen=r.ts,
                sessions=[r.session] if r.session else [],
            )
        else:
            c.count += 1
            if r.ts and (not c.first_seen or r.ts < c.first_seen):
                c.first_seen = r.ts
            if r.ts and (not c.last_seen or r.ts > c.last_seen):
                c.last_seen = r.ts
            if r.session and r.session not in c.sessions:
                c.sessions.append(r.session)
    return groups


def _short_tool_name(tool: str) -> str:
    """Strip MCP prefixes and return a lowercase, hyphen-friendly chunk.

    >>> _short_tool_name("Read")
    'read'
    >>> _short_tool_name("mcp__plugin_foo__do_thing")
    'do-thing'
    """
    last = tool.rsplit("__", 1)[-1] if "__" in tool else tool
    last = re.sub(r"[^A-Za-z0-9]+", "-", last).strip("-").lower()
    return last or "tool"


def slug_from_tools(tools: list[str]) -> str:
    parts = [_short_tool_name(t) for t in tools]
    return "forge-" + "-".join(parts)


# ---------------------------------------------------------------------------
# SKILL.md draft generation
# ---------------------------------------------------------------------------


def render_skill_md(slug: str, candidate: Candidate) -> str:
    """Render a SKILL.md draft. Deterministic for a given Candidate."""
    tool_arrow = " → ".join(candidate.tools)
    description = (
        f"PROPOSED (auto-mined). Repeated tool sequence detected: {tool_arrow}. "
        f"Observed {candidate.count} times. Review and refine before approving."
    )
    steps_lines = [f"{i}. Invoke `{tool}`" for i, tool in enumerate(candidate.tools, 1)]
    steps_block = "\n".join(steps_lines)
    sessions_block = ", ".join(candidate.sessions) if candidate.sessions else "(unknown)"

    return (
        f"---\n"
        f"name: {slug}\n"
        f"description: {description}\n"
        f"status: proposed\n"
        f"---\n"
        f"\n"
        f"# {slug} (proposed)\n"
        f"\n"
        f"## When to Use\n"
        f"\n"
        f"After observing the workflow `{tool_arrow}` repeated {candidate.count} "
        f"times across sessions, automate it as a single skill invocation.\n"
        f"\n"
        f"## Steps\n"
        f"\n"
        f"{steps_block}\n"
        f"\n"
        f"## Verification\n"
        f"\n"
        f"Replay the recorded tool sequence and confirm it produces the same "
        f"end state. Adjust the steps to add inputs, branching, or guards "
        f"before approving this proposal.\n"
        f"\n"
        f"## Provenance\n"
        f"\n"
        f"- Pattern signature: `{candidate.signature}`\n"
        f"- Occurrences: {candidate.count}\n"
        f"- First seen: {candidate.first_seen or '(unknown)'}\n"
        f"- Last seen: {candidate.last_seen or '(unknown)'}\n"
        f"- Sessions: {sessions_block}\n"
    )


# ---------------------------------------------------------------------------
# Write planning
# ---------------------------------------------------------------------------


@dataclass
class Proposal:
    slug: str
    signature: str
    path: Path
    content: str


def plan_proposals(
    candidates: dict[str, Candidate],
    threshold: int,
    blacklist: set[str],
    existing_names: set[str],
    proposed_root: Path,
) -> list[Proposal]:
    """Apply threshold + blacklist + name-collision filters; return ordered list."""
    plans: list[Proposal] = []
    used_slugs: set[str] = set()
    # Stable order: by signature lexicographic so re-runs match
    for sig in sorted(candidates):
        c = candidates[sig]
        if c.count < threshold:
            continue
        if sig in blacklist:
            continue
        slug = slug_from_tools(c.tools)
        if slug in existing_names or slug in used_slugs:
            continue
        used_slugs.add(slug)
        plans.append(
            Proposal(
                slug=slug,
                signature=sig,
                path=proposed_root / slug / "SKILL.md",
                content=render_skill_md(slug, c),
            )
        )
    return plans


def write_proposals(proposals: list[Proposal]) -> list[Path]:
    """Write each proposal's SKILL.md. Skip if the file already exists.

    Skipping preserves any user edits made between mining runs — the T-028
    approval flow lets users modify proposals in place, and a subsequent
    mine-skills.py run must not clobber those edits.
    """
    written: list[Path] = []
    for p in proposals:
        if p.path.exists():
            continue
        p.path.parent.mkdir(parents=True, exist_ok=True)
        p.path.write_text(p.content, encoding="utf-8")
        written.append(p.path)
    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--cwd", default=".", help="project root (default: current dir)")
    p.add_argument(
        "--session",
        default=None,
        help="only count patterns recorded under this session id",
    )
    p.add_argument(
        "--threshold",
        type=int,
        default=_DEFAULT_THRESHOLD,
        help=f"minimum occurrences to propose (default: {_DEFAULT_THRESHOLD})",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print planned proposal paths without writing",
    )
    p.add_argument(
        "--plugin-dir",
        default=None,
        help="plugin root (for skills/ collision check); default: parent of this script",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    cwd = Path(args.cwd).resolve()
    plugin_dir = (
        Path(args.plugin_dir).resolve()
        if args.plugin_dir
        else Path(__file__).resolve().parent.parent
    )

    forge_dir = cwd / ".forge"
    patterns_path = forge_dir / "patterns.jsonl"
    blacklist_path = forge_dir / "skill-blacklist.txt"
    proposed_root = forge_dir / "proposed-skills"

    records = parse_patterns(patterns_path, session=args.session)
    candidates = aggregate(records)
    blacklist = load_blacklist(blacklist_path)
    existing_names = load_existing_skill_names(plugin_dir)

    plans = plan_proposals(
        candidates,
        threshold=args.threshold,
        blacklist=blacklist,
        existing_names=existing_names,
        proposed_root=proposed_root,
    )

    if args.dry_run:
        for p in plans:
            print(str(p.path))
        return min(len(plans), _EXIT_CAP)

    written = write_proposals(plans)
    for path in written:
        print(str(path))
    return min(len(written), _EXIT_CAP)


if __name__ == "__main__":
    sys.exit(main())
