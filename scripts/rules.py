#!/usr/bin/env python3
"""User-authored rules surface — loader + selector (REQ-RULES-001..004, v0.3.0).

Parses `.forge/rules/*.md`: user-authored constraint files with YAML frontmatter
(`{description, scope, stages?, globs?, priority?}`) plus a Markdown body (the rule
text the agent should follow). Consumed by:

  - `hooks/session-start.py`  — injects `always` + `stage` rules into context.
  - `hooks/pre-tool-write.py` — injects `glob` rules matching the written file.
  - `skills/forge-rules`      — `list` / `validate` via the CLI here.

Scope model (mirrors Cursor project rules):
  - `always` — every session.
  - `stage`  — only when `current_stage ∈ stages`.
  - `glob`   — only on writes to files matching `globs`.
  - `manual` — never auto-selected (referenced explicitly by name).

Design rules:
  - **Never raises** — imported by hooks. Any unreadable/malformed file is skipped;
    an absent directory yields `[]`.
  - **Stdlib + PyYAML, fail-soft** — PyYAML is read defensively (absent → that file is
    skipped). No third-party `frontmatter` dependency (lesson 2026-05-24): frontmatter
    is split with a stdlib fence parser + PyYAML for the YAML block only.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_FENCE = "---"
RULES_DIRNAME = "rules"
VALID_SCOPES = ("always", "stage", "glob", "manual")
_DEFAULT_RENDER_BUDGET = 1200


# --------------------------------------------------------------------------- #
# Parsing helpers (self-contained; never raise)
# --------------------------------------------------------------------------- #
def _safe_yaml_load(text: str) -> Optional[dict]:
    """Parse a YAML block, returning None on any failure (incl. PyYAML absent)."""
    try:
        import yaml  # noqa: F401
    except ImportError:
        return None
    try:
        data = yaml.safe_load(text)
    except Exception:  # noqa: BLE001 — malformed YAML must not crash the loader
        return None
    return data if isinstance(data, dict) else None


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (metadata, body); ({}, text) when no leading `---` fence. Never raises.

    Mirrors `scripts/_state_lib._split_frontmatter` but with a fail-soft YAML load so
    this module stays importable even when PyYAML is missing.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != _FENCE:
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == _FENCE:
            yaml_block = "".join(lines[1:i])
            body = "".join(lines[i + 1:])
            if body.startswith("\n"):
                body = body[1:]
            return (_safe_yaml_load(yaml_block) or {}), body
    return {}, text


def _coerce_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _coerce_int_list(value: object) -> list[int]:
    items = value if isinstance(value, list) else ([] if value is None else [value])
    out: list[int] = []
    for v in items:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            continue
    return out


def _coerce_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if value is None:
        return []
    return [str(value)]


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
@dataclass
class Rule:
    name: str
    scope: str
    description: str = ""
    stages: list = field(default_factory=list)
    globs: list = field(default_factory=list)
    priority: int = 0
    body: str = ""

    def matches_stage(self, stage: Optional[int]) -> bool:
        return self.scope == "stage" and stage is not None and stage in self.stages

    def matches_glob(self, file_path: Optional[str]) -> bool:
        if self.scope != "glob" or not file_path:
            return False
        return any(_glob_match(file_path, g) for g in self.globs)


def _glob_match(file_path: str, pattern: str) -> bool:
    """fnmatch-based glob with sensible `**` handling. Never raises."""
    try:
        fp = str(file_path).replace(os.sep, "/")
        pat = str(pattern).replace(os.sep, "/")
        base = fp.rsplit("/", 1)[-1]
        if fnmatch.fnmatch(fp, pat):
            return True
        # `**/x` should also match a root-level `x`.
        if pat.startswith("**/") and fnmatch.fnmatch(base, pat[3:]):
            return True
        # a bare pattern (no slash) matches by basename.
        if "/" not in pat and fnmatch.fnmatch(base, pat):
            return True
        return False
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------- #
# Load + select + render
# --------------------------------------------------------------------------- #
def rules_dir(forge_dir) -> Path:
    return Path(forge_dir) / RULES_DIRNAME


def load_rules(forge_dir) -> list[Rule]:
    """Load all valid rules from `<forge_dir>/rules/*.md`, priority-desc then name.

    Files without valid frontmatter / an unknown scope (e.g. a README) are skipped.
    Never raises; an absent or unreadable directory yields [].
    """
    d = rules_dir(forge_dir)
    try:
        if not d.is_dir():
            return []
        paths = sorted(d.glob("*.md"))
    except OSError:
        return []

    rules: list[Rule] = []
    for p in paths:
        try:
            text = p.read_text()
        except OSError:
            continue
        meta, body = _split_frontmatter(text)
        scope = str(meta.get("scope", "")).strip().lower()
        if scope not in VALID_SCOPES:
            continue  # not a rule (README, missing/invalid scope) — fail-soft skip
        rules.append(
            Rule(
                name=p.stem,
                scope=scope,
                description=str(meta.get("description", "")).strip(),
                stages=_coerce_int_list(meta.get("stages")),
                globs=_coerce_str_list(meta.get("globs")),
                priority=_coerce_int(meta.get("priority"), 0),
                body=body.strip(),
            )
        )
    rules.sort(key=lambda r: (-r.priority, r.name))
    return rules


def select(
    rules: list[Rule],
    *,
    stage: Optional[int] = None,
    file_path: Optional[str] = None,
    scope: Optional[str] = None,
) -> list[Rule]:
    """Return the rules whose activation condition is met given the context.

    - `always` rules are always included.
    - `stage` rules require a matching `stage`.
    - `glob` rules require a matching `file_path`.
    - `manual` rules are never auto-selected.
    Pass `scope=` to narrow to a single scope (its condition still applies).
    """
    out: list[Rule] = []
    for r in rules:
        if scope is not None and r.scope != scope:
            continue
        if r.scope == "always":
            out.append(r)
        elif r.scope == "stage" and r.matches_stage(stage):
            out.append(r)
        elif r.scope == "glob" and r.matches_glob(file_path):
            out.append(r)
        # manual → never auto-selected
    return out


def render(rules: list[Rule], max_chars: int = _DEFAULT_RENDER_BUDGET) -> str:
    """Render selected rules as a compact, budget-bounded block ('' when empty).

    One line per rule: `• <name>: <description-or-body-excerpt>`. Stops adding lines
    once the budget would be exceeded, so callers can inject within a token budget.
    """
    if not rules:
        return ""
    lines: list[str] = []
    used = 0
    for r in rules:
        summary = r.description or r.body.splitlines()[0] if r.body else r.description
        summary = (summary or r.scope).strip()
        line = f"• {r.name}: {summary}"
        if len(line) > 160:
            line = line[:157] + "…"
        if used + len(line) + 1 > max_chars:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI (for the /forge:rules skill)
# --------------------------------------------------------------------------- #
def _forge_dir(cwd: str) -> Path:
    return Path(cwd) / ".forge"


_README_TEMPLATE = """# Forge Rules

User-authored rules that steer Forge's agents. Each `*.md` file here has YAML
frontmatter + a markdown body (the rule text the agent should follow).

Frontmatter:
    description: short summary
    scope: always | stage | glob | manual
    stages: [6, 7]        # for scope: stage
    globs: ["**/*.tsx"]   # for scope: glob
    priority: 0           # higher shows first

Scopes:
    always  - injected every session (within the context budget)
    stage   - injected when the pipeline is on a listed stage
    glob    - surfaced when writing a file matching globs (advisory, never blocks)
    manual  - never auto-injected; reference it by name

See `references/rules-format.md` for the full schema. Manage with `/forge:rules`.
"""

_EXAMPLE_RULE = """---
description: House style for generated prose and code
scope: always
priority: 10
---
- Prefer clarity over cleverness; keep sentences short.
- Match the surrounding file's conventions before introducing new ones.
- No commented-out code or TODOs without an owner.
"""


def _rule_template(scope: str, description: str) -> str:
    extra = ""
    if scope == "stage":
        extra = "stages: [6]\n"
    elif scope == "glob":
        extra = "globs: ['**/*']\n"
    return (
        "---\n"
        f"description: {description or 'TODO: describe this rule'}\n"
        f"scope: {scope}\n"
        f"{extra}"
        "---\n"
        "TODO: write the rule the agent should follow.\n"
    )


def _cmd_init(args) -> int:
    """Scaffold `.forge/rules/` with a README + example rule. Idempotent."""
    d = rules_dir(_forge_dir(args.cwd))
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"ERROR: could not create {d}: {exc}", file=sys.stderr)
        return 1
    created, skipped = [], []
    for name, body in (("README.md", _README_TEMPLATE), ("00-style.md", _EXAMPLE_RULE)):
        path = d / name
        if path.exists():
            skipped.append(name)
            continue
        try:
            path.write_text(body)
            created.append(name)
        except OSError as exc:
            print(f"WARN: could not write {name}: {exc}", file=sys.stderr)
    print(f"Rules dir: {d}")
    if created:
        print(f"  created: {', '.join(created)}")
    if skipped:
        print(f"  kept (already present): {', '.join(skipped)}")
    print("Edit .forge/rules/*.md or run `/forge:rules add <name>`. See "
          "references/rules-format.md.")
    return 0


def _cmd_add(args) -> int:
    """Create a new rule file from a template. Refuses to clobber an existing file."""
    scope = str(args.scope).strip().lower()
    if scope not in VALID_SCOPES:
        print(f"ERROR: invalid scope {args.scope!r}; choose one of {', '.join(VALID_SCOPES)}",
              file=sys.stderr)
        return 2
    stem = args.name[:-3] if args.name.endswith(".md") else args.name
    d = rules_dir(_forge_dir(args.cwd))
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"ERROR: could not create {d}: {exc}", file=sys.stderr)
        return 1
    path = d / f"{stem}.md"
    if path.exists():
        print(f"Rule {path.name} already exists — not overwritten. Edit it directly.")
        return 0
    try:
        path.write_text(_rule_template(scope, args.description or ""))
    except OSError as exc:
        print(f"ERROR: could not write {path}: {exc}", file=sys.stderr)
        return 1
    print(f"Created {path} (scope: {scope}). Fill in the body, then `/forge:rules validate`.")
    return 0


def _cmd_list(args) -> int:
    rules = load_rules(_forge_dir(args.cwd))
    if not rules:
        print("No rules found in .forge/rules/. Run `/forge:rules init` to scaffold.")
        return 0
    for r in rules:
        scope_detail = ""
        if r.scope == "stage":
            scope_detail = f" stages={r.stages}"
        elif r.scope == "glob":
            scope_detail = f" globs={r.globs}"
        print(f"[{r.scope}{scope_detail}] {r.name} — {r.description or '(no description)'}")
    return 0


def _cmd_validate(args) -> int:
    """Report malformed rule files. Exit 0 unless a usage error (REQ-RULES-007)."""
    d = rules_dir(_forge_dir(args.cwd))
    if not d.is_dir():
        print("No .forge/rules/ directory. Run `/forge:rules init` to scaffold.")
        return 0
    issues = 0
    valid = 0
    for p in sorted(d.glob("*.md")):
        try:
            meta, body = _split_frontmatter(p.read_text())
        except OSError as exc:
            print(f"WARN {p.name}: unreadable ({exc})")
            issues += 1
            continue
        scope = str(meta.get("scope", "")).strip().lower()
        if scope not in VALID_SCOPES:
            if p.name.lower() != "readme.md":
                print(f"WARN {p.name}: missing/invalid scope (got {meta.get('scope')!r}); skipped")
                issues += 1
            continue
        if scope == "stage" and not _coerce_int_list(meta.get("stages")):
            print(f"WARN {p.name}: scope=stage but no valid `stages` list")
            issues += 1
        if scope == "glob" and not _coerce_str_list(meta.get("globs")):
            print(f"WARN {p.name}: scope=glob but no `globs` list")
            issues += 1
        if not body.strip():
            print(f"WARN {p.name}: empty rule body")
            issues += 1
        valid += 1
    print(f"Validated {valid} rule(s); {issues} issue(s).")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="rules.py", description="Forge user-rules loader")
    parser.add_argument("--cwd", default=os.getcwd(), help="project root (default: cwd)")
    # Shared --cwd on subparsers via SUPPRESS so a value before the subcommand survives
    # (lesson 2026-05-14: argparse subparser defaults overwrite parent values).
    sub_common = argparse.ArgumentParser(add_help=False)
    sub_common.add_argument("--cwd", default=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", parents=[sub_common]).set_defaults(func=_cmd_init)
    p_add = sub.add_parser("add", parents=[sub_common])
    p_add.add_argument("name", help="rule file name (without .md)")
    p_add.add_argument("--scope", default="always",
                       help=f"one of {', '.join(VALID_SCOPES)} (default: always)")
    p_add.add_argument("--description", default="", help="short rule description")
    p_add.set_defaults(func=_cmd_add)
    sub.add_parser("list", parents=[sub_common]).set_defaults(func=_cmd_list)
    sub.add_parser("validate", parents=[sub_common]).set_defaults(func=_cmd_validate)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
