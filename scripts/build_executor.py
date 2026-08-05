#!/usr/bin/env python3
"""Deterministic Stage 6 Pro execution engine (T-248, REQ-BUILDEXEC-001).

Owns everything mechanical in Builder Pro's per-task pipeline so the agent
(`agents/builder-pro.md`) only ever generates code and tests: context resolve
(`read-doc.py` against the real canonical task-dag/spec base paths, `spec_plan`
depth only — REQ-BUILDCTX-002's `spec_arch_plan`/`full_chain` widening is T-253),
gate execution (four checks + profile `additional_criteria`, per-check report,
never one aggregate boolean), commit + progress write (only after every gate
check passes), traceability update (extends `pipeline/05-plan/traceability.md`'s
`CODE` leaf), one `build-log.jsonl` line per attempt, `DEFECT-###` escalation on a
second consecutive failure, resume (skip tasks already marked done), and batch
delegation to `parallel_build.run_parallel_build` (never reimplemented).

See references/build/01..05.md for the full design this implements.

Usage (cwd = project root):
    build_executor.py context --task T-XXX [--cwd PATH]
    build_executor.py gate [--cwd PATH] [--criteria-json PATH]
    build_executor.py finish --task T-XXX --files F [F ...] [--cwd PATH] [--message MSG] [--criteria-json PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "scripts"))
import parallel_build as _pb  # noqa: E402  (batch path delegates here — AC-BUILDEXEC-001c)

DAG_BASE = "pipeline/05-plan/task-dag"
SPEC_BASE = "pipeline/04-spec/technical-spec"
ARCH_BASE = "pipeline/03-architecture/architecture"  # only at spec_arch_plan/full_chain (T-253)
SRS_BASE = "pipeline/01-srs/srs"
PROGRESS_RELPATH = "pipeline/06-implementation/progress.md"
TRACE_RELPATH = "pipeline/05-plan/traceability.md"
BUILD_LOG_RELPATH = "pipeline/06-implementation/build-log.jsonl"

TASK_HEADING = re.compile(r"^#{2,4}\s+.*?\b(T-\d+)\b.*$", re.MULTILINE)
TASK_ID = re.compile(r"\bT-\d+\b")
REQ_ID = re.compile(r"\b(?:REQ|NFR)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
FILE_TOKEN = re.compile(r"`([^`]+)`")
DONE_MARK = re.compile(r"🟢|✅|\bdone\b|\[x\]", re.IGNORECASE)
SECTION_HEADING = re.compile(r"^##\s+.+$", re.MULTILINE)
MILESTONE_HEADING = re.compile(r"^##\s+Milestone\s+{n}\b.*?$", re.MULTILINE)
DEFECT_ID = re.compile(r"\bDEFECT-(\d+)\b")


class ContextResolutionError(Exception):
    """Context cannot be resolved deterministically: missing task, missing
    requirement, or missing canonical document. Fails closed — no bundle, no
    generation."""


# --------------------------------------------------------------------------- #
# Data shapes
# --------------------------------------------------------------------------- #


@dataclass
class TaskEntry:
    id: str
    description: str
    files: list
    depends_on: list
    req_ids: list
    done_when: str


@dataclass
class ContextBundle:
    task_id: str
    files: list
    req_ids: list
    description: str
    spec_excerpts: list
    architecture_excerpts: Optional[list]  # None => "(not resolved at this depth)"
    additional_criteria: list


@dataclass
class DetectedCommand:
    argv: Optional[list]
    skip_reason: str = ""


@dataclass
class GateCheck:
    name: str
    status: str  # "pass" | "fail" | "skipped"
    detail: str = ""


@dataclass
class GateReport:
    checks: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.status != "fail" for c in self.checks)

    def to_lines(self) -> list:
        return [
            f"{c.name}: {c.status}" + (f" ({c.detail})" if c.detail else "")
            for c in self.checks
        ]


@dataclass
class RecordResult:
    committed: bool
    commit_sha: Optional[str]
    defect_id: Optional[str]
    build_log_entry: dict


# --------------------------------------------------------------------------- #
# read-doc.py resolution (never a hardcoded flat-file assumption)
# --------------------------------------------------------------------------- #


def read_doc(cwd: Path, base: str, *, plugin_dir: Path = _PLUGIN_DIR) -> Optional[str]:
    """Resolve a canonical document (single-file or split layout) via read-doc.py.
    None if neither layout is present."""
    script = plugin_dir / "scripts" / "read-doc.py"
    result = subprocess.run(
        [sys.executable, str(script), base],
        cwd=str(cwd), capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


# --------------------------------------------------------------------------- #
# Task-dag parsing
# --------------------------------------------------------------------------- #


def _task_block_span(text: str, task_id: str) -> Optional[tuple]:
    matches = list(TASK_HEADING.finditer(text))
    for i, m in enumerate(matches):
        if m.group(1) != task_id:
            continue
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        return start, end
    return None


def _task_block(text: str, task_id: str) -> Optional[str]:
    span = _task_block_span(text, task_id)
    return text[span[0]:span[1]] if span else None


def _field_value(block: str, field_name: str) -> Optional[str]:
    pattern = re.compile(
        rf"-\s+\*\*{re.escape(field_name)}\*\*:\s*(.*?)(?=\n-\s+\*\*[A-Za-z]|\Z)",
        re.DOTALL,
    )
    m = pattern.search(block)
    return m.group(1).strip() if m else None


def resolve_task_entry(dag_text: str, task_id: str) -> Optional[TaskEntry]:
    block = _task_block(dag_text, task_id)
    if block is None:
        return None
    files_val = _field_value(block, "Files") or ""
    files = FILE_TOKEN.findall(files_val)
    deps_val = _field_value(block, "Depends on") or ""
    depends_on = [] if re.search(r"\bnone\b", deps_val, re.IGNORECASE) else TASK_ID.findall(deps_val)
    req_val = _field_value(block, "REQ-IDs") or ""
    req_ids = REQ_ID.findall(req_val)
    description = (_field_value(block, "Description") or "").strip()
    done_when = (_field_value(block, "Done when") or "").strip()
    return TaskEntry(
        id=task_id, description=description, files=files,
        depends_on=depends_on, req_ids=req_ids, done_when=done_when,
    )


# --------------------------------------------------------------------------- #
# Spec/section matching
# --------------------------------------------------------------------------- #


def _sections(doc_text: str) -> list:
    matches = list(SECTION_HEADING.finditer(doc_text))
    if not matches:
        return [doc_text] if doc_text.strip() else []
    out = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(doc_text)
        out.append(doc_text[start:end])
    return out


def matching_sections(doc_text: str, needles: list) -> list:
    if not doc_text:
        return []
    needles = [n for n in needles if n]
    if not needles:
        return []
    return [s for s in _sections(doc_text) if any(n in s for n in needles)]


def defined_req_ids(srs_text: str) -> set:
    return set(REQ_ID.findall(srs_text or ""))


# --------------------------------------------------------------------------- #
# Context resolution — REQ-BUILDEXEC-001, AC-BUILDEXEC-001a
# --------------------------------------------------------------------------- #


def _stage6_additional_criteria(cwd: Path, *, plugin_dir: Path = _PLUGIN_DIR) -> list:
    script = plugin_dir / "scripts" / "load-profile.py"
    result = subprocess.run(
        [sys.executable, str(script), "--cwd", str(cwd), "--stage", "6", "--format", "json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    overrides = data.get("stage_overrides") or {}
    criteria = overrides.get("additional_criteria") if isinstance(overrides, dict) else None
    return criteria or []


def resolve_context(
    cwd: Path, task_id: str, *, plugin_dir: Path = _PLUGIN_DIR,
) -> ContextBundle:
    """Resolve one task's context bundle. Fails closed (raises
    ContextResolutionError) rather than producing a bundle for an unresolvable
    task or a task with no traceable requirement."""
    dag_text = read_doc(cwd, DAG_BASE, plugin_dir=plugin_dir)
    if dag_text is None:
        raise ContextResolutionError(f"task-dag not found: {DAG_BASE}")

    task = resolve_task_entry(dag_text, task_id)
    if task is None:
        raise ContextResolutionError(f"task not found in task-dag: {task_id}")

    srs_text = read_doc(cwd, SRS_BASE, plugin_dir=plugin_dir) or ""
    known_reqs = defined_req_ids(srs_text)
    if not any(r in known_reqs for r in task.req_ids):
        raise ContextResolutionError(
            f"{task_id}: no REQ-ID resolves against {SRS_BASE}.md — "
            "nothing builds without a traceable requirement or specification"
        )

    spec_text = read_doc(cwd, SPEC_BASE, plugin_dir=plugin_dir) or ""
    needles = list(task.req_ids) + [Path(f).name for f in task.files]
    spec_excerpts = matching_sections(spec_text, needles)

    additional_criteria = _stage6_additional_criteria(cwd, plugin_dir=plugin_dir)

    description = task.description
    if task.done_when:
        description = f"{description}\nDone when: {task.done_when}"

    return ContextBundle(
        task_id=task.id,
        files=task.files,
        req_ids=task.req_ids,
        description=description,
        spec_excerpts=spec_excerpts,
        architecture_excerpts=None,  # spec_plan depth only this phase — T-253 widens
        additional_criteria=additional_criteria,
    )


# --------------------------------------------------------------------------- #
# Gate detection and execution — REQ-BUILDEXEC-001, AC-BUILDEXEC-001b
# --------------------------------------------------------------------------- #


def _pyproject_has_section(cwd: Path, section: str) -> bool:
    pp = cwd / "pyproject.toml"
    if pp.is_file():
        try:
            return f"[tool.{section}]" in pp.read_text(errors="ignore")
        except OSError:
            return False
    return False


def _has_ruff_config(cwd: Path) -> bool:
    return (
        _pyproject_has_section(cwd, "ruff")
        or (cwd / "ruff.toml").exists()
        or (cwd / ".ruff.toml").exists()
    )


def _has_mypy_config(cwd: Path) -> bool:
    if _pyproject_has_section(cwd, "mypy") or (cwd / "mypy.ini").exists():
        return True
    setup_cfg = cwd / "setup.cfg"
    if setup_cfg.is_file():
        try:
            return "[mypy]" in setup_cfg.read_text(errors="ignore")
        except OSError:
            return False
    return False


def detect_gate_commands(cwd: Path) -> dict:
    """Detect what the project already uses — never invent a build system.
    Returns a DetectedCommand per check name; None argv means skip-with-reason."""
    if (cwd / "package.json").is_file():
        try:
            pkg = json.loads((cwd / "package.json").read_text())
        except (OSError, json.JSONDecodeError):
            pkg = {}
        scripts = pkg.get("scripts", {}) if isinstance(pkg, dict) else {}
        return {
            "compile": (
                DetectedCommand(["npm", "run", "build"]) if "build" in scripts
                else DetectedCommand(None, "no npm build script configured")
            ),
            "lint": (
                DetectedCommand(["npm", "run", "lint"]) if "lint" in scripts
                else DetectedCommand(None, "no npm lint script configured")
            ),
            "test": (
                DetectedCommand(["npm", "test"]) if "test" in scripts
                else DetectedCommand(None, "no npm test script configured")
            ),
            "static_analysis": (
                DetectedCommand(["npx", "tsc", "--noEmit"]) if (cwd / "tsconfig.json").exists()
                else DetectedCommand(None, "no tsconfig.json — no type-checker configured")
            ),
        }

    is_python = any(
        (cwd / name).exists() for name in ("pyproject.toml", "setup.py", "requirements.txt")
    )
    if is_python:
        return {
            "compile": DetectedCommand(None, "Python has no compile step"),
            "lint": (
                DetectedCommand([sys.executable, "-m", "ruff", "check", "."]) if _has_ruff_config(cwd)
                else DetectedCommand(None, "no ruff config found")
            ),
            "test": DetectedCommand([sys.executable, "-m", "pytest", "-q"]),
            "static_analysis": (
                DetectedCommand([sys.executable, "-m", "mypy", "."]) if _has_mypy_config(cwd)
                else DetectedCommand(None, "no mypy config found")
            ),
        }

    reason = "no recognized project stack (no package.json or Python project markers)"
    return {name: DetectedCommand(None, reason) for name in ("compile", "lint", "test", "static_analysis")}


def run_check(
    cwd: Path, name: str, detected: DetectedCommand, *,
    timeout: int = 300, run: Callable = subprocess.run,
) -> GateCheck:
    if detected.argv is None:
        return GateCheck(name=name, status="skipped", detail=detected.skip_reason)
    try:
        result = run(detected.argv, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return GateCheck(name=name, status="fail", detail=str(exc)[:300])
    if result.returncode == 0:
        return GateCheck(name=name, status="pass")
    detail = (result.stderr.strip() or result.stdout.strip() or "exited non-zero")[-300:]
    return GateCheck(name=name, status="fail", detail=detail)


def run_criterion(
    cwd: Path, criterion: dict, *, plugin_dir: Path = _PLUGIN_DIR, run: Callable = subprocess.run,
) -> GateCheck:
    cid = criterion.get("id", "criterion")
    check = criterion.get("check")
    if check != "script_returns_zero":
        return GateCheck(
            name=cid, status="skipped",
            detail="no automated check defined — manual/agent verification required",
        )
    args = criterion.get("args", {}) or {}
    script_rel = args.get("script", "")
    script = plugin_dir / script_rel
    if not script.exists():
        return GateCheck(name=cid, status="fail", detail=f"check script not implemented: {script_rel}")
    argv = [sys.executable, str(script)] + [str(a) for a in args.get("argv", [])]
    try:
        result = run(argv, cwd=str(cwd), capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return GateCheck(name=cid, status="fail", detail=str(exc)[:300])
    if result.returncode == 0:
        return GateCheck(name=cid, status="pass")
    detail = (result.stderr.strip() or result.stdout.strip() or "exited non-zero")[:300]
    return GateCheck(name=cid, status="fail", detail=detail)


def run_gate(
    cwd: Path, *, additional_criteria: Optional[list] = None,
    run: Callable = subprocess.run, plugin_dir: Path = _PLUGIN_DIR,
) -> GateReport:
    detected = detect_gate_commands(cwd)
    checks = [
        run_check(cwd, name, detected[name], run=run)
        for name in ("compile", "lint", "test", "static_analysis")
    ]
    checks += [
        run_criterion(cwd, c, plugin_dir=plugin_dir, run=run)
        for c in (additional_criteria or [])
    ]
    return GateReport(checks=checks)


# --------------------------------------------------------------------------- #
# build-log.jsonl
# --------------------------------------------------------------------------- #


def append_build_log(cwd: Path, entry: dict) -> None:
    path = cwd / BUILD_LOG_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True))
        fh.write("\n")


def consecutive_failures(cwd: Path, task_id: str) -> int:
    """Count consecutive failed attempts for a task from the end of build-log.jsonl,
    stopping at the most recent pass. A malformed line is state we cannot verify --
    fail closed: count it as a failure (biases toward opening a DEFECT-### sooner)
    rather than silently skipping it (which would undercount and could suppress the
    escalation gate on a corrupted log)."""
    path = cwd / BUILD_LOG_RELPATH
    if not path.exists():
        return 0
    count = 0
    for line in reversed(path.read_text().splitlines()):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            print(
                f"build_executor: malformed build-log.jsonl line for {task_id} "
                "-- counted as a failure (fail closed, not open)",
                file=sys.stderr,
            )
            count += 1
            continue
        if entry.get("task_id") != task_id:
            continue
        if entry.get("passed"):
            break
        count += 1
    return count


def next_defect_id(cwd: Path) -> str:
    path = cwd / BUILD_LOG_RELPATH
    highest = 0
    if path.exists():
        for m in DEFECT_ID.finditer(path.read_text()):
            highest = max(highest, int(m.group(1)))
    return f"DEFECT-{highest + 1:03d}"


# --------------------------------------------------------------------------- #
# Progress + traceability writes — commit/progress-write only on pass
# --------------------------------------------------------------------------- #


def done_tasks(cwd: Path) -> set:
    path = cwd / PROGRESS_RELPATH
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text().splitlines():
        if DONE_MARK.search(line):
            done.update(TASK_ID.findall(line))
    return done


def update_progress(cwd: Path, task_id: str, *, done: bool, note: str) -> None:
    path = cwd / PROGRESS_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text() if path.exists() else "# Implementation Progress\n\n## Tasks\n\n"
    mark = "[x]" if done else "[ ]"
    line = f"- {mark} {task_id} — {note}"
    lines = text.splitlines()
    for i, existing in enumerate(lines):
        if task_id in existing and existing.lstrip().startswith("- ["):
            lines[i] = line
            break
    else:
        lines.append(line)
    path.write_text("\n".join(lines) + "\n")


def extend_traceability(cwd: Path, task_id: str, files: list) -> None:
    """Extend pipeline/05-plan/traceability.md's CODE leaf for this task
    (REQ-BUILDCTX per references/build/04-traceability-validation.md) — appends to
    Stage 5's own artifact, never a parallel file."""
    path = cwd / TRACE_RELPATH
    text = path.read_text() if path.exists() else ""
    code_line = "- **Code:** " + ", ".join(f"`{f}`" for f in files)
    span = _task_block_span(text, task_id) if text else None
    if span is not None:
        start, end = span
        block = text[start:end].rstrip("\n")
        text = text[:start] + block + "\n" + code_line + "\n" + text[end:].lstrip("\n")
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += f"\n### {task_id}\n\n{code_line}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def record_attempt(
    cwd: Path,
    task_id: str,
    files: list,
    gate_report: GateReport,
    *,
    commit_message: Optional[str] = None,
    duration_s: Optional[float] = None,
    run: Callable = subprocess.run,
    now: Optional[float] = None,
) -> RecordResult:
    """Commit + progress write + traceability extension, only after every gate
    check passes (AC-BUILDEXEC-001d for the traceability part). Always appends one
    build-log.jsonl line, pass or fail. Opens a DEFECT-### on a second consecutive
    failure of the same task, never the first."""
    ts = now if now is not None else time.time()
    passed = gate_report.passed
    entry = {
        "task_id": task_id,
        "ts": ts,
        "files": list(files),
        "gate": [{"name": c.name, "status": c.status, "detail": c.detail} for c in gate_report.checks],
        "passed": passed,
        "commit_sha": None,
        "defect_id": None,
        "duration_s": duration_s,
    }

    defect_id: Optional[str] = None
    commit_sha: Optional[str] = None

    if passed:
        message = commit_message or f"feat({task_id}): implement task"
        # "--" stops git from treating a file path that happens to start with "-"
        # as an option (argument injection via an attacker- or agent-chosen path).
        run(["git", "add", "--", *files], cwd=str(cwd), capture_output=True, text=True)
        commit = run(["git", "commit", "-m", message], cwd=str(cwd), capture_output=True, text=True)
        if commit.returncode == 0:
            sha_result = run(["git", "rev-parse", "HEAD"], cwd=str(cwd), capture_output=True, text=True)
            commit_sha = sha_result.stdout.strip() if sha_result.returncode == 0 else None
        entry["commit_sha"] = commit_sha
        update_progress(cwd, task_id, done=True, note=f"done (commit {commit_sha or '?'})")
        extend_traceability(cwd, task_id, files)
    else:
        failures = consecutive_failures(cwd, task_id) + 1
        if failures >= 2:
            defect_id = next_defect_id(cwd)
            failing = ", ".join(c.name for c in gate_report.checks if c.status == "fail")
            update_progress(cwd, task_id, done=False, note=f"{defect_id} open ({failing} failing)")
        entry["defect_id"] = defect_id

    append_build_log(cwd, entry)
    return RecordResult(
        committed=passed and commit_sha is not None,
        commit_sha=commit_sha, defect_id=defect_id, build_log_entry=entry,
    )


# --------------------------------------------------------------------------- #
# Batch path — AC-BUILDEXEC-001c: delegate to parallel_build, never duplicate it
# --------------------------------------------------------------------------- #


def milestone_nodes(dag_text: str, milestone: int) -> list:
    pat = re.compile(rf"^##\s+Milestone\s+{milestone}\b.*?$", re.MULTILINE)
    m = pat.search(dag_text)
    if not m:
        return []
    start = m.end()
    nxt = re.search(r"^##\s+", dag_text[start:], re.MULTILINE)
    end = start + nxt.start() if nxt else len(dag_text)

    ids_in_section = []
    seen = set()
    for tm in TASK_HEADING.finditer(dag_text):
        if start <= tm.start() < end and tm.group(1) not in seen:
            seen.add(tm.group(1))
            ids_in_section.append(tm.group(1))

    nodes = []
    for tid in ids_in_section:
        entry = resolve_task_entry(dag_text, tid)
        nodes.append(_pb.TaskNode(id=tid, depends_on=(entry.depends_on if entry else [])))
    return nodes


def run_batch(
    cwd: Path,
    milestone: int,
    *,
    config,
    forge_dir: Path,
    feature: str,
    resume: bool = False,
    plugin_dir: Path = _PLUGIN_DIR,
    **kwargs,
):
    """Fan the milestone's ready tasks out through parallel_build.run_parallel_build
    — never reimplement worktree isolation or bounded dispatch here."""
    dag_text = read_doc(cwd, DAG_BASE, plugin_dir=plugin_dir) or ""
    nodes = milestone_nodes(dag_text, milestone)
    done = done_tasks(cwd) if resume else set()
    return _pb.run_parallel_build(
        nodes, done, config=config, forge_dir=forge_dir, feature=feature, repo=cwd, **kwargs,
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _bundle_to_json(bundle: ContextBundle) -> str:
    return json.dumps({
        "task_id": bundle.task_id,
        "files": bundle.files,
        "req_ids": bundle.req_ids,
        "description": bundle.description,
        "spec_excerpts": bundle.spec_excerpts,
        "architecture_excerpts": bundle.architecture_excerpts,
        "additional_criteria": bundle.additional_criteria,
    }, indent=2)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="build_executor.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ctx = sub.add_parser("context", help="resolve and print a task's context bundle")
    p_ctx.add_argument("--task", required=True)
    p_ctx.add_argument("--cwd", default=".")

    p_gate = sub.add_parser("gate", help="run the four checks (dry run, no commit)")
    p_gate.add_argument("--cwd", default=".")
    p_gate.add_argument("--criteria-json", default=None)

    p_fin = sub.add_parser("finish", help="run the gate, then commit + record only on pass")
    p_fin.add_argument("--task", required=True)
    p_fin.add_argument("--files", nargs="+", required=True)
    p_fin.add_argument("--cwd", default=".")
    p_fin.add_argument("--message", default=None)
    p_fin.add_argument("--criteria-json", default=None)

    args = parser.parse_args(argv)
    cwd = Path(args.cwd)

    if args.command == "context":
        try:
            bundle = resolve_context(cwd, args.task)
        except ContextResolutionError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(_bundle_to_json(bundle))
        return 0

    if args.command in ("gate", "finish"):
        criteria = json.loads(Path(args.criteria_json).read_text()) if args.criteria_json else []
        report = run_gate(cwd, additional_criteria=criteria)
        for line in report.to_lines():
            print(line, file=sys.stderr)
        if args.command == "gate":
            return 0 if report.passed else 1
        result = record_attempt(cwd, args.task, args.files, report, commit_message=args.message)
        print(json.dumps({
            "committed": result.committed, "commit_sha": result.commit_sha,
            "defect_id": result.defect_id, "gate_passed": report.passed,
        }))
        return 0 if result.committed else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
