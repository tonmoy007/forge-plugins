#!/usr/bin/env python3
"""User-driven approval flow for mined skill proposals.

Operates on `.forge/proposed-skills/<slug>/SKILL.md` (produced by T-027
mine-skills.py). Three subcommands:

  list      — JSON catalog of pending proposals
  approve   — install <slug> into <plugin-dir>/skills/<slug>/SKILL.md
  reject    — append the proposal's signature to .forge/skill-blacklist.txt
              and delete the proposal directory

The user *modifies* a proposal by editing the SKILL.md in place before
running `approve`. mine-skills.py skips paths that already exist, so user
edits survive re-mining (see T-027 write_proposals).

Stdlib only.

REQ-IDs: REQ-073 (user approval required), REQ-074 (rejected pattern blacklist).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_SIGNATURE_LINE_RE = re.compile(r"Pattern signature:\s*`([^`]+)`")
_FRONTMATTER_NAME_RE = re.compile(r"^name:\s*(\S+)")
_STATUS_LINE_RE = re.compile(r"^status:\s*proposed\s*$", re.MULTILINE)
_BLACKLIST_HEADER = (
    "# .forge/skill-blacklist.txt — one pattern signature per line.\n"
    "# Signatures listed here will not be re-proposed by mine-skills.py.\n"
)


@dataclass
class Proposal:
    slug: str
    path: Path
    name: str
    signature: str
    description: str = ""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _parse_proposal(skill_md: Path) -> Optional[Proposal]:
    """Return a Proposal from a SKILL.md file, or None if unparseable."""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None
    name = ""
    desc = ""
    for line in text.splitlines()[:30]:
        m = _FRONTMATTER_NAME_RE.match(line)
        if m:
            name = m.group(1).strip()
        if line.startswith("description:"):
            desc = line.split(":", 1)[1].strip()
    sig_match = _SIGNATURE_LINE_RE.search(text)
    if not name or not sig_match:
        return None
    return Proposal(
        slug=skill_md.parent.name,
        path=skill_md,
        name=name,
        signature=sig_match.group(1),
        description=desc,
    )


def list_pending(cwd: Path) -> list[Proposal]:
    proposed_root = cwd / ".forge" / "proposed-skills"
    if not proposed_root.exists():
        return []
    out: list[Proposal] = []
    for skill_md in sorted(proposed_root.glob("*/SKILL.md")):
        p = _parse_proposal(skill_md)
        if p is not None:
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------


def _strip_status_proposed(text: str) -> str:
    """Remove a `status: proposed` line from the YAML frontmatter block."""
    if not text.startswith("---"):
        return text
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return text
    _, frontmatter, body = parts
    frontmatter = _STATUS_LINE_RE.sub("", frontmatter)
    frontmatter = re.sub(r"\n{2,}", "\n", frontmatter)
    return f"---\n{frontmatter}---\n{body}"


def approve(cwd: Path, slug: str, plugin_dir: Path) -> Path:
    """Install proposal at <plugin_dir>/skills/<slug>/SKILL.md. Returns dest path."""
    src = cwd / ".forge" / "proposed-skills" / slug / "SKILL.md"
    if not src.exists():
        raise FileNotFoundError(f"no pending proposal for slug: {slug}")
    dest_dir = plugin_dir / "skills" / slug
    dest = dest_dir / "SKILL.md"
    if dest.exists():
        raise FileExistsError(f"skill already installed: {dest}")
    text = src.read_text(encoding="utf-8")
    text = _strip_status_proposed(text)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    shutil.rmtree(src.parent)
    return dest


# ---------------------------------------------------------------------------
# Reject
# ---------------------------------------------------------------------------


def _append_blacklist(blacklist_path: Path, signature: str) -> None:
    """Append a signature line; create with header if file doesn't exist."""
    existing = blacklist_path.read_text(encoding="utf-8") if blacklist_path.exists() else ""
    if any(line.strip() == signature for line in existing.splitlines()):
        return  # already blacklisted; idempotent
    blacklist_path.parent.mkdir(parents=True, exist_ok=True)
    if not existing:
        existing = _BLACKLIST_HEADER
    if existing and not existing.endswith("\n"):
        existing += "\n"
    blacklist_path.write_text(existing + signature + "\n", encoding="utf-8")


def reject(cwd: Path, slug: str) -> str:
    """Blacklist the proposal's signature, delete the proposal dir. Returns the signature."""
    skill_md = cwd / ".forge" / "proposed-skills" / slug / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"no pending proposal for slug: {slug}")
    proposal = _parse_proposal(skill_md)
    if proposal is None:
        raise ValueError(f"proposal at {skill_md} has no parseable signature")
    _append_blacklist(cwd / ".forge" / "skill-blacklist.txt", proposal.signature)
    shutil.rmtree(skill_md.parent)
    return proposal.signature


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--cwd", default=".", help="project root (default: current dir)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="emit JSON catalog of pending proposals")

    pa = sub.add_parser("approve", help="install a proposal into skills/")
    pa.add_argument("--slug", required=True, help="proposal slug (directory name)")
    pa.add_argument(
        "--plugin-dir",
        default=None,
        help="plugin root containing skills/; default: parent of this script",
    )

    pr = sub.add_parser("reject", help="blacklist a proposal and remove it")
    pr.add_argument("--slug", required=True)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    cwd = Path(args.cwd).resolve()

    if args.cmd == "list":
        out = [
            {
                "slug": p.slug,
                "name": p.name,
                "signature": p.signature,
                "description": p.description,
                "path": str(p.path),
            }
            for p in list_pending(cwd)
        ]
        print(json.dumps(out, indent=2))
        return 0

    if args.cmd == "approve":
        plugin_dir = (
            Path(args.plugin_dir).resolve()
            if args.plugin_dir
            else Path(__file__).resolve().parent.parent
        )
        try:
            dest = approve(cwd, args.slug, plugin_dir)
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        except FileExistsError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"approved: {dest}")
        return 0

    if args.cmd == "reject":
        try:
            sig = reject(cwd, args.slug)
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"rejected: {args.slug} (signature {sig} blacklisted)")
        return 0

    return 0  # unreachable; argparse enforces required subcommand


if __name__ == "__main__":
    sys.exit(main())
