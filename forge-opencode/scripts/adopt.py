#!/usr/bin/env python3
"""/forge:adopt — brownfield onboarding (T-150, REQ-F-038..043, closes EF-014).

Runs Forge against an EXISTING codebase: detect the project type, sample a bounded
set of files, fan out extractors (via `_orchestrate`) to infer SRS + architecture
drafts, seed `pipeline/state.md`, and hand off to the normal 12-stage flow at Stage 1
so the human confirms the inferred artifacts.

Guarantees:
  - **Read-only to user source** (REQ-F-040): writes ONLY under `pipeline/` and
    `.forge/`. `--dry-run` previews the plan and writes nothing (and does not spend).
  - **Inferred + provenance** (REQ-F-039/041): every draft is banner-marked INFERRED
    and records confidence + the files it was derived from.
  - **Bounded** (REQ-F-043): sampling is capped (`adopt.max_files`, default 40) and
    what was sampled vs skipped is reported — no silent truncation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from typing import Optional

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _orchestrate  # noqa: E402

DEFAULT_MAX_FILES = 40
_EXCLUDE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "pipeline", ".forge", "__pycache__",
    ".venv", "venv", "env", "dist", "build", "target", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "vendor", ".next", ".idea", ".vscode",
}
_PRIORITY_NAMES = {
    "readme.md", "readme", "readme.rst", "package.json", "pyproject.toml",
    "requirements.txt", "setup.py", "cargo.toml", "go.mod", "pom.xml",
    "build.gradle", "pubspec.yaml", "composer.json", "gemfile", "makefile",
}
_SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
                ".rb", ".kt", ".swift", ".c", ".cpp", ".cs", ".php", ".scala"}

_ASPECTS = [
    {"key": "requirements", "subdir": "01-srs", "file": "srs.md", "heading": "Software Requirements"},
    {"key": "architecture", "subdir": "03-architecture", "file": "architecture.md", "heading": "Architecture"},
]


# --- detection (reused) -----------------------------------------------------

def _load_detect(plugin_dir: Path):
    spec = importlib.util.spec_from_file_location(
        "detect_project_type", plugin_dir / "scripts" / "detect-project-type.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["detect_project_type"] = mod
    spec.loader.exec_module(mod)
    return mod


# --- file sampling ----------------------------------------------------------

def _rank(rel: str) -> tuple:
    name = Path(rel).name.lower()
    ext = Path(rel).suffix.lower()
    pri = 0 if name in _PRIORITY_NAMES else (1 if ext in _SOURCE_EXTS else 2)
    return (pri, rel)


def sample_files(cwd: Path, max_files: int) -> tuple[list[str], int]:
    """Return (sampled relpaths, skipped_count). Deterministic; meta dirs excluded;
    manifests/READMEs prioritized; capped at max_files (REQ-F-043)."""
    found: list[str] = []
    cwd = Path(cwd)
    for path in cwd.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(cwd)
        if any(part in _EXCLUDE_DIRS for part in rel.parts):
            continue
        if rel.name.startswith("."):  # skip dotfiles (config noise)
            continue
        found.append(str(rel))
    found.sort(key=_rank)
    sampled = found[:max_files]
    return sampled, len(found) - len(sampled)


def build_digest(cwd: Path, sampled: list[str], max_lines: int = 30) -> str:
    """Structural digest: path + first `max_lines` of each file (OQ-006). Safe on
    binary/oversized files."""
    parts: list[str] = []
    for rel in sampled:
        parts.append(f"### {rel}")
        try:
            text = (Path(cwd) / rel).read_text(errors="replace")
            head = "\n".join(text.splitlines()[:max_lines])
            parts.append(head)
        except OSError:
            parts.append("(unreadable)")
        parts.append("")
    return "\n".join(parts)


# --- inference (fan-out) ----------------------------------------------------

def _build_prompt(digest: str, aspect: dict, project_type: str) -> str:
    return (
        f"You are Forge's brownfield extractor inferring the **{aspect['key']}** of an "
        f"existing `{project_type}` project from a bounded file sample. Reply with one "
        f'JSON object: {{"aspect": "{aspect["key"]}", "confidence": 0.0-1.0, '
        '"content": "<markdown body>", "derived_from": ["<file>", ...]}. Be concrete '
        "but mark uncertainty honestly; this is a draft a human will confirm.\n\n"
        f"--- file sample ---\n{digest}"
    )


def _validate_aspect(parsed: dict) -> dict:
    if not isinstance(parsed, dict):
        raise ValueError("aspect result is not an object")
    aspect = parsed.get("aspect")
    if aspect not in {a["key"] for a in _ASPECTS}:
        raise ValueError(f"unknown aspect: {aspect!r}")
    content = parsed.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("empty content")
    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    derived = parsed.get("derived_from")
    derived = [str(d) for d in derived] if isinstance(derived, list) else []
    return {"aspect": aspect, "confidence": confidence, "content": content, "derived_from": derived}


def infer(digest: str, project_type: str, *, forge_dir: Path, dispatch_fn=None,
          max_parallel: int = 2, claude_bin=None, cwd=None) -> tuple[dict, list, float]:
    """Fan the aspects out. Returns (by_aspect, dropped_aspects, cost). Never raises."""
    fan = _orchestrate.fan_out(
        _ASPECTS,
        lambda a: _build_prompt(digest, a, project_type),
        forge_dir=forge_dir,
        feature="adopt",
        validate=_validate_aspect,
        max_parallel=max_parallel,
        dispatch_fn=dispatch_fn,
        claude_bin=claude_bin,
        cwd=cwd,
    )
    by_aspect = {r["aspect"]: r for r in fan.results if isinstance(r, dict) and r.get("aspect")}
    dropped_aspects = [a["key"] for a in _ASPECTS if a["key"] not in by_aspect]
    return by_aspect, dropped_aspects, fan.total_cost_usd


# --- artifact rendering -----------------------------------------------------

def _seed_state(project_type: str) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"---\nschema_version: 1\nproject_type: {project_type}\ncycle: 1\n"
        f"current_stage: 1\ncurrent_task: null\ncurrent_milestone: null\n"
        f"total_tasks: null\nlast_updated: {now}\nblockers: []\n---\n\n"
        "# Pipeline State\n\n"
        "> Seeded by `/forge:adopt` from an existing codebase. Entered at Stage 1 so "
        "the inferred SRS can be confirmed before proceeding.\n\n"
        "## Stage History\n\n## Last Reflection\n"
    )


def _render_artifact(aspect: dict, data: Optional[dict], project_type: str) -> str:
    heading = f"# {aspect['heading']} — {project_type} (INFERRED DRAFT)"
    if data is None:
        return (
            f"{heading}\n\n> ⚠️ **INFERRED by /forge:adopt — inference unavailable.** The "
            f"extractor for this aspect was dropped (malformed or over the cost cap). "
            f"Re-run `/forge:adopt` or author this stage manually.\n"
        )
    derived = ", ".join(data.get("derived_from") or []) or "(bounded file sample)"
    return (
        f"{heading}\n\n"
        f"> ⚠️ **INFERRED by /forge:adopt — needs human confirmation.** Generated from a "
        f"bounded sample of the existing codebase. **Confidence: {data['confidence']:.2f}**. "
        f"Review and edit before relying on it.\n>\n"
        f"> **Derived from**: {derived}\n\n"
        f"{data['content']}\n"
    )


def write_artifacts(cwd: Path, project_type: str, by_aspect: dict, *, dry_run: bool) -> tuple[list, list]:
    """Write state + inferred drafts under pipeline/ only. Returns (written, would_write)."""
    plan = [Path("pipeline") / "state.md"]
    for a in _ASPECTS:
        plan.append(Path("pipeline") / a["subdir"] / a["file"])
    if dry_run:
        return [], [str(p) for p in plan]

    written: list[str] = []
    state_path = Path(cwd) / "pipeline" / "state.md"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(_seed_state(project_type))
    written.append(str(state_path.relative_to(cwd)))

    for a in _ASPECTS:
        out = Path(cwd) / "pipeline" / a["subdir"] / a["file"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_render_artifact(a, by_aspect.get(a["key"]), project_type))
        written.append(str(out.relative_to(cwd)))
    return written, []


# --- orchestration ----------------------------------------------------------

def adopt(cwd: str, *, dry_run: bool = False, max_files: Optional[int] = None,
          dispatch_fn=None, plugin_dir: Optional[Path] = None) -> dict:
    """Onboard an existing codebase. Never raises; returns a summary dict."""
    cwd_p = Path(cwd)
    plugin_dir = plugin_dir or _PLUGIN_DIR

    if (cwd_p / "pipeline" / "state.md").exists():
        return {"status": "refused",
                "reason": "pipeline/state.md already exists — adopt is for un-initialized projects."}

    detected = _load_detect(plugin_dir).detect(str(cwd_p))
    project_type = detected.get("type", "unknown")
    cap = max_files if max_files is not None else DEFAULT_MAX_FILES
    sampled, skipped = sample_files(cwd_p, cap)

    if dry_run:
        _, would = write_artifacts(cwd_p, project_type, {}, dry_run=True)
        return {"status": "ok", "dry_run": True, "project_type": project_type,
                "sampled": len(sampled), "skipped": skipped, "would_write": would,
                "dropped_aspects": [], "cost_usd": 0.0}

    digest = build_digest(cwd_p, sampled)
    by_aspect, dropped_aspects, cost = infer(
        digest, project_type, forge_dir=cwd_p / ".forge", dispatch_fn=dispatch_fn, cwd=str(cwd_p))
    written, _ = write_artifacts(cwd_p, project_type, by_aspect, dry_run=False)

    return {"status": "ok", "dry_run": False, "project_type": project_type,
            "sampled": len(sampled), "skipped": skipped, "written": written,
            "dropped_aspects": dropped_aspects, "cost_usd": cost}


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="adopt")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument("--plugin-dir", default=str(_PLUGIN_DIR))
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    summary = adopt(args.cwd, dry_run=args.dry_run, max_files=args.max_files,
                    plugin_dir=Path(args.plugin_dir))
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
