#!/usr/bin/env python3
"""Library curation — ExpeL voting + TroVE frequency trim + /dream maintenance (T-182).

Keeps the mined-skill library from rotting. Three mechanisms, all offline, `.forge`-only,
never-raise (this runs on the background/maintenance path):

  1. **ExpeL-style voting** (REQ-SM-009). Every reuse outcome is one append-only event in
     `.forge/skill-stats.jsonl`:
       - ADD       — skill admitted; seeds INIT_WEIGHT.
       - UPVOTE    — successful reuse; weight +1, use +1.
       - DOWNVOTE  — failed reuse;     weight -1, use +1 (it was still tried).
       - EDIT      — merged into another skill (bookkeeping; weight unchanged).
     Folding the log yields per-skill weight + use count; skills at weight ≤ 0 are prunable.

  2. **TroVE frequency trim.** Drop skills whose use count falls below a log-scaled
     threshold relative to the busiest skill — rarely-exercised abstractions are noise.

  3. **Scheduled `/dream`-style maintenance** (MiMo Code `/dream`, every 7 days). Merges
     near-duplicate proposal/skill descriptions, prunes never-used / weight-0 skills, and
     flags skills whose referenced files/commands no longer exist on disk. It mutates only
     under `.forge/proposed-skills/` and `<plugin>/skills/` (delete a merged/pruned dir);
     it never writes outside the tree and never raises.

Frontmatter parsing reuses `scripts/_state_lib._split_frontmatter` (no YAML-frontmatter
dependency); PyYAML is imported fail-soft through that helper. The jsonl-append idiom
mirrors `hooks/_error_log.append_jsonl`.

REQ-IDs: REQ-SM-009 (library curation), REQ-NF-016 (never-raises), REQ-NF-018 (.forge-only).
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

INIT_WEIGHT = 1
_STATS_NAME = "skill-stats.jsonl"
_VOTE_ACTIONS = {"ADD", "UPVOTE", "DOWNVOTE", "EDIT"}

# Near-duplicate description threshold (difflib ratio in [0,1]); ≥ this == "the same".
_DUP_RATIO = 0.85
# TroVE trim: drop skills whose use count is below max(1, floor(log2(busiest+1))).
# Single-use skills survive when nothing else is markedly busier.
_TRIM_FLOOR = 2

# Inline references to validate: backtick-quoted paths, and `python3 <path>` invocations.
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_PATHISH_RE = re.compile(r"(?:[\w./-]+/)?[\w-]+\.(?:py|sh|md|yaml|yml|json|txt)$")


# --------------------------------------------------------------------------- #
# Frontmatter (reuse _state_lib; fail-soft if unavailable)
# --------------------------------------------------------------------------- #
def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Delegate to `_state_lib._split_frontmatter`; fail-soft to ({}, text)."""
    try:
        import _state_lib  # noqa: E402 — sibling scripts/ module

        return _state_lib._split_frontmatter(text)
    except Exception:  # noqa: BLE001 — missing PyYAML / import glitch must not crash
        return {}, text


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
@dataclass
class SkillStat:
    """Folded curation state for one skill."""

    name: str
    weight: int = 0
    uses: int = 0
    merged_away: bool = False


@dataclass
class Flag:
    """A skill that references a file/command no longer present on disk."""

    skill: str
    missing: str


@dataclass
class MaintenanceReport:
    """Outcome of a `/dream`-style maintenance pass."""

    merged: list[tuple[str, str]] = field(default_factory=list)  # (kept, removed)
    pruned: list[str] = field(default_factory=list)
    flagged: list[Flag] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Voting + persistence
# --------------------------------------------------------------------------- #
def _append_stat(forge_dir: Path, record: dict) -> bool:
    """Append one stats event as a JSON line. Never raises (advisory log)."""
    try:
        forge_dir.mkdir(parents=True, exist_ok=True)
        with (forge_dir / _STATS_NAME).open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return True
    except (OSError, TypeError, ValueError):
        return False


def vote(forge_dir: Path, skill: str, action: str) -> bool:
    """Record one ExpeL vote for `skill`. Unknown actions are ignored. Never raises.

    Returns True iff an event was written.
    """
    act = str(action).upper()
    if act not in _VOTE_ACTIONS or not skill:
        return False
    return _append_stat(forge_dir, {"skill": str(skill), "action": act})


def _read_stats_rows(forge_dir: Path) -> list[dict]:
    """Read `skill-stats.jsonl`, skipping unreadable/malformed lines. Never raises."""
    path = forge_dir / _STATS_NAME
    rows: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def aggregate_stats(forge_dir: Path) -> dict[str, SkillStat]:
    """Fold the vote log into per-skill `SkillStat`. Never raises.

    ADD seeds INIT_WEIGHT; UPVOTE is +1 weight / +1 use; DOWNVOTE is -1 weight / +1 use;
    EDIT marks the skill merged-away (weight unchanged).
    """
    stats: dict[str, SkillStat] = {}
    for row in _read_stats_rows(forge_dir):
        name = row.get("skill")
        action = row.get("action")
        if not isinstance(name, str) or not name or not isinstance(action, str):
            continue
        st = stats.get(name)
        if st is None:
            st = SkillStat(name=name)
            stats[name] = st
        act = action.upper()
        if act == "ADD":
            st.weight += INIT_WEIGHT
        elif act == "UPVOTE":
            st.weight += 1
            st.uses += 1
        elif act == "DOWNVOTE":
            st.weight -= 1
            st.uses += 1
        elif act == "EDIT":
            st.merged_away = True
    return stats


def prunable_by_weight(stats: dict[str, SkillStat]) -> set[str]:
    """Skills whose ExpeL weight has fallen to 0 or below (prune-at-zero)."""
    return {name for name, st in stats.items() if st.weight <= 0}


def trim_by_frequency(stats: dict[str, SkillStat]) -> set[str]:
    """TroVE frequency trim: skills used below a log-scaled threshold. Never raises.

    Threshold = max(_TRIM_FLOOR, floor(log2(busiest_uses + 1))). With a flat library
    (everyone used about the same) nothing is trimmed; one runaway-popular skill raises
    the bar and sweeps out the long tail of single-use abstractions.
    """
    if not stats:
        return set()
    busiest = max((st.uses for st in stats.values()), default=0)
    if busiest <= _TRIM_FLOOR:
        return set()
    threshold = max(_TRIM_FLOOR, int(math.log2(busiest + 1)))
    return {name for name, st in stats.items() if st.uses < threshold}


# --------------------------------------------------------------------------- #
# Maintenance: SKILL.md scanning
# --------------------------------------------------------------------------- #
@dataclass
class _SkillDoc:
    slug: str
    skill_md: Path
    name: str
    description: str
    body: str


def _load_skill_doc(skill_md: Path) -> Optional[_SkillDoc]:
    """Parse a SKILL.md into a _SkillDoc; None if unreadable."""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None
    meta, body = _split_frontmatter(text)
    name = str(meta.get("name", "")).strip() or skill_md.parent.name
    desc = str(meta.get("description", "")).strip()
    return _SkillDoc(
        slug=skill_md.parent.name, skill_md=skill_md, name=name, description=desc, body=body
    )


def _scan_skill_dir(root: Path) -> list[_SkillDoc]:
    """Load every <root>/*/SKILL.md. Returns [] if the root is absent. Never raises."""
    docs: list[_SkillDoc] = []
    try:
        if not root.exists():
            return docs
        for skill_md in sorted(root.glob("*/SKILL.md")):
            doc = _load_skill_doc(skill_md)
            if doc is not None:
                docs.append(doc)
    except OSError:
        return docs
    return docs


def _norm_desc(desc: str) -> str:
    """Whitespace-collapsed, lowercased description for similarity comparison."""
    return re.sub(r"\s+", " ", desc).strip().lower()


def _merge_near_duplicates(docs: list[_SkillDoc]) -> list[tuple[str, str]]:
    """Remove proposal dirs whose descriptions are near-identical to an earlier one.

    Keeps the first (lexicographically by slug, via sorted scan) of each duplicate set
    and deletes the rest from disk. Returns (kept_slug, removed_slug) pairs. Never raises.
    """
    merged: list[tuple[str, str]] = []
    kept: list[_SkillDoc] = []
    for doc in docs:
        norm = _norm_desc(doc.description)
        if not norm:
            kept.append(doc)
            continue
        match = next(
            (
                k
                for k in kept
                if _norm_desc(k.description)
                and difflib.SequenceMatcher(None, _norm_desc(k.description), norm).ratio()
                >= _DUP_RATIO
            ),
            None,
        )
        if match is None:
            kept.append(doc)
            continue
        if _safe_rmtree(doc.skill_md.parent):
            merged.append((match.slug, doc.slug))
    return merged


def _referenced_paths(body: str) -> list[str]:
    """Extract file-path-looking references from a SKILL.md body."""
    refs: list[str] = []
    for chunk in _BACKTICK_RE.findall(body):
        for token in chunk.split():
            token = token.strip("`'\"(),;")
            if _PATHISH_RE.search(token):
                refs.append(token)
    return refs


def _flag_missing_refs(doc: _SkillDoc, plugin_dir: Path) -> list[Flag]:
    """Flag any referenced path that exists neither under plugin_dir nor as an absolute path."""
    flags: list[Flag] = []
    for ref in _referenced_paths(doc.body):
        candidate = Path(ref)
        exists = False
        try:
            exists = (plugin_dir / ref).exists() or (candidate.is_absolute() and candidate.exists())
        except OSError:
            exists = False
        if not exists:
            flags.append(Flag(skill=doc.name, missing=ref))
    return flags


def _safe_rmtree(path: Path) -> bool:
    """rmtree that never raises. Returns True iff the dir is gone afterwards."""
    try:
        shutil.rmtree(path, ignore_errors=True)
        return not path.exists()
    except OSError:
        return False


def run_maintenance(forge_dir: Path, *, plugin_dir: Path) -> MaintenanceReport:
    """`/dream`-style pass: merge near-duplicate proposals, prune never-used / weight-0
    installed skills, flag installed skills referencing missing files. Never raises.

    `.forge`-only and `<plugin>/skills`-only mutations (it only deletes merged/pruned
    skill directories). Pruning/flagging applies to *installed* skills (those under
    `<plugin>/skills`); merging applies to pending proposals under `.forge/proposed-skills`.
    """
    report = MaintenanceReport()
    try:
        proposed_root = forge_dir / "proposed-skills"
        skills_root = plugin_dir / "skills"

        # 1. Merge near-duplicate *proposals* (cheap to dedup before they install).
        report.merged = _merge_near_duplicates(_scan_skill_dir(proposed_root))

        # 2. Prune + flag *installed* skills against the vote log.
        stats = aggregate_stats(forge_dir)
        weight_pruned = prunable_by_weight(stats)
        for doc in _scan_skill_dir(skills_root):
            st = stats.get(doc.name)
            never_used = st is None or st.uses == 0
            zero_weight = doc.name in weight_pruned
            if never_used or zero_weight:
                if _safe_rmtree(doc.skill_md.parent):
                    report.pruned.append(doc.name)
                continue  # don't bother flagging a skill we just removed
            report.flagged.extend(_flag_missing_refs(doc, plugin_dir))
    except Exception:  # noqa: BLE001 — maintenance is best-effort; never crash the caller
        return report
    return report


# --------------------------------------------------------------------------- #
# CLI (capability/cost-gated maintenance entry point)
# --------------------------------------------------------------------------- #
def _gate_allows(forge_dir: Path) -> tuple[bool, str]:
    """Cost-gate the maintenance pass via `_cost_cap.precheck`; fail-soft to allow.

    Maintenance is cheap (offline, no LLM) but we still honor the shared spend gate so a
    blown budget halts every background activity uniformly. If the gate can't load, allow.
    """
    try:
        sys.path.insert(0, str(_HERE.parent / "hooks"))
        import _cost_cap  # noqa: E402 — sibling hooks/ module

        decision = _cost_cap.precheck(forge_dir, 0.0)
        return bool(decision.allowed), str(decision.reason)
    except Exception:  # noqa: BLE001 — gate absence must not block offline maintenance
        return True, "cost gate unavailable — allowing offline maintenance"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--cwd", default=".", help="project root (default: current dir)")
    p.add_argument(
        "--plugin-dir",
        default=None,
        help="plugin root containing skills/; default: parent of this script",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("vote", help="record an ExpeL vote for a skill")
    pv.add_argument("--skill", required=True, help="skill name")
    pv.add_argument(
        "--action", required=True, choices=sorted(_VOTE_ACTIONS), help="vote action"
    )

    sub.add_parser("stats", help="emit JSON of folded per-skill curation stats")
    sub.add_parser(
        "maintain", help="run the /dream-style merge/prune/flag maintenance pass"
    )

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    cwd = Path(args.cwd).resolve()
    forge_dir = cwd / ".forge"
    plugin_dir = (
        Path(args.plugin_dir).resolve() if args.plugin_dir else _HERE.parent
    )

    if args.cmd == "vote":
        ok = vote(forge_dir, args.skill, args.action)
        print(json.dumps({"recorded": ok, "skill": args.skill, "action": args.action}))
        return 0

    if args.cmd == "stats":
        stats = aggregate_stats(forge_dir)
        out = {
            name: {"weight": st.weight, "uses": st.uses, "merged_away": st.merged_away}
            for name, st in sorted(stats.items())
        }
        print(json.dumps(out, indent=2))
        return 0

    if args.cmd == "maintain":
        allowed, reason = _gate_allows(forge_dir)
        if not allowed:
            print(json.dumps({"skipped": True, "reason": reason}))
            return 0
        report = run_maintenance(forge_dir, plugin_dir=plugin_dir)
        print(
            json.dumps(
                {
                    "merged": [{"kept": k, "removed": r} for k, r in report.merged],
                    "pruned": report.pruned,
                    "flagged": [{"skill": f.skill, "missing": f.missing} for f in report.flagged],
                },
                indent=2,
            )
        )
        return 0

    return 0  # unreachable; argparse enforces required subcommand


if __name__ == "__main__":
    sys.exit(main())
