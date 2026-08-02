#!/usr/bin/env python3
"""Sprint view over the task DAG (REQ-F-044..048, v0.3.4 / M4).

`/forge:sprint` is deterministic (no LLM): it groups the next *ready* DAG tasks into a
sprint and, at sprint end, reports done-vs-carried. It is a **view over the DAG**, not a
parallel tracker — the task DAG (`pipeline/05-plan/task-dag.md`) and the implementation
progress (`pipeline/06-implementation/progress.md`) remain the single source of truth, and
**T-IDs are the identity** so carry-over preserves a task across sprints (F-047).

Commands (cwd = project root):
    sprint.py plan   [--size K] [--milestone N] [--cwd PATH]
    sprint.py review [--sprint NN] [--cwd PATH]
    sprint.py list   [--cwd PATH]

`plan` writes `pipeline/05-plan/sprint-NN.md` (carry-over tasks first, then new ready ones
up to the target size). `review` writes `pipeline/12-release/sprint-NN-review.md` (done /
carried / blockers). Fully **opt-in** (F-048): a project that never runs `/forge:sprint`
sees no sprint files and zero behavior change.

Stdlib only. Errors are reported on stderr with a non-zero exit; the helpers never raise
into a caller that imports this module.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DAG_RELPATH = "pipeline/05-plan/task-dag.md"
PROGRESS_RELPATH = "pipeline/06-implementation/progress.md"
PLAN_DIR = "pipeline/05-plan"
REVIEW_DIR = "pipeline/12-release"
STATE_RELPATH = "pipeline/state.md"

_DEFAULT_SIZE = 5

TASK_HEADING = re.compile(r"^#{2,4}\s+.*?\b(T-\d+)\b(.*)$", re.MULTILINE)
TASK_ID = re.compile(r"\bT-\d+\b")
SIZE_RE = re.compile(r"\[([SML])\]")
DONE_MARK = re.compile(r"🟢|✅|\bdone\b|\[x\]", re.IGNORECASE)
MILESTONE_RE = re.compile(r"^##\s+Milestone\s+(\d+)\b", re.MULTILINE)
SPRINT_FILE_RE = re.compile(r"sprint-(\d+)\.md$")


@dataclass
class Task:
    id: str
    title: str = ""
    deps: set = field(default_factory=set)
    size: Optional[str] = None  # S | M | L
    milestone: Optional[int] = None


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def _milestone_at(text: str, pos: int) -> Optional[int]:
    """The milestone number of the `## Milestone N` section containing `pos`, or None."""
    last = None
    for m in MILESTONE_RE.finditer(text):
        if m.start() <= pos:
            last = int(m.group(1))
        else:
            break
    return last


def _arrow_deps(text: str) -> dict:
    """Parse `A → B → C` edges from fenced blocks: each `X → Y` means Y depends on X."""
    deps: dict = {}
    for block in re.findall(r"```.*?```", text, re.DOTALL):
        for line in block.splitlines():
            ids = TASK_ID.findall(line)
            if "→" not in line and "->" not in line:
                continue
            for prev, nxt in zip(ids, ids[1:]):
                deps.setdefault(nxt, set()).add(prev)
    return deps


def parse_tasks(dag_text: str) -> list:
    """Return [Task] for every `### T-NNN` heading, in declared order. Never raises.

    Dependencies come from an inline `Depends on: T-x, T-y` line in the task block and/or
    from a `→`/`->` arrow graph in a fenced block. Size is an optional `[S|M|L]` tag.
    """
    if not isinstance(dag_text, str):
        return []
    matches = list(TASK_HEADING.finditer(dag_text))
    arrow = _arrow_deps(dag_text)
    tasks: list = []
    for i, mt in enumerate(matches):
        tid = mt.group(1)
        heading = mt.group(2) or ""
        start = mt.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(dag_text)
        block = dag_text[start:end]

        deps: set = set(arrow.get(tid, set()))
        dm = re.search(r"Depends on\*?\*?:\s*(.+)", block, re.IGNORECASE)
        if dm:
            deps |= {d for d in TASK_ID.findall(dm.group(1))}
        deps.discard(tid)

        size_m = SIZE_RE.search(heading)
        title = heading
        title = SIZE_RE.sub("", title)
        title = re.sub(r"\([^)]*REQ[^)]*\)", "", title)  # drop trailing (REQ-…) refs
        title = title.strip(" —-:\t")

        tasks.append(Task(
            id=tid,
            title=title,
            deps=deps,
            size=size_m.group(1) if size_m else None,
            milestone=_milestone_at(dag_text, start),
        ))
    return tasks


def done_tasks(cwd) -> set:
    """T-IDs marked done in progress.md (🟢/✅/done/[x]). {} when absent. Never raises."""
    progress = Path(cwd) / PROGRESS_RELPATH
    done: set = set()
    try:
        text = progress.read_text()
    except OSError:
        return done
    for line in text.splitlines():
        if DONE_MARK.search(line):
            done.update(TASK_ID.findall(line))
    return done


# --------------------------------------------------------------------------- #
# Ordering + selection
# --------------------------------------------------------------------------- #
def topo_order(tasks: list) -> list:
    """Dependency-first order; ties broken by declared order. Cycle-safe. Never raises."""
    order_index = {t.id: i for i, t in enumerate(tasks)}
    in_set = set(order_index)
    deps = {t.id: {d for d in t.deps if d in in_set} for t in tasks}
    by_id = {t.id: t for t in tasks}
    placed: set = set()
    resolved: list = []
    remaining = [t.id for t in tasks]
    while remaining:
        ready = [t for t in remaining if deps[t] <= placed]
        if not ready:  # dependency cycle — fall back to declared order
            ready = [min(remaining, key=lambda t: order_index[t])]
        nxt = min(ready, key=lambda t: order_index[t])
        resolved.append(by_id[nxt])
        placed.add(nxt)
        remaining.remove(nxt)
    return resolved


def select_sprint(tasks: list, done: set, *, size: int = _DEFAULT_SIZE,
                  milestone: Optional[int] = None, exclude: Optional[set] = None) -> list:
    """The next `size` not-done tasks in dependency order (optionally one milestone).

    `exclude` drops already-accounted-for tasks (e.g. carry-over handled separately).
    Never raises.
    """
    exclude = exclude or set()
    pool = [t for t in tasks
            if t.id not in done and t.id not in exclude
            and (milestone is None or t.milestone == milestone)]
    ordered = topo_order(pool)
    if size is not None and size >= 0:
        ordered = ordered[:size]
    return ordered


# --------------------------------------------------------------------------- #
# Sprint files
# --------------------------------------------------------------------------- #
def existing_sprints(cwd) -> list:
    """Sorted sprint numbers with a `sprint-NN.md` file. Never raises."""
    d = Path(cwd) / PLAN_DIR
    nums: list = []
    try:
        paths = list(d.glob("sprint-*.md"))
    except OSError:
        return []
    for p in paths:
        m = SPRINT_FILE_RE.search(p.name)
        if m:
            nums.append(int(m.group(1)))
    return sorted(nums)


def next_sprint_number(cwd) -> int:
    nums = existing_sprints(cwd)
    return (nums[-1] + 1) if nums else 1


def sprint_path(cwd, n: int) -> Path:
    return Path(cwd) / PLAN_DIR / f"sprint-{n:02d}.md"


def review_path(cwd, n: int) -> Path:
    return Path(cwd) / REVIEW_DIR / f"sprint-{n:02d}-review.md"


def sprint_task_ids(cwd, n: int) -> list:
    """Ordered T-IDs recorded in sprint-NN.md (one per checklist line). Never raises."""
    path = sprint_path(cwd, n)
    ids: list = []
    try:
        text = path.read_text()
    except OSError:
        return ids
    for line in text.splitlines():
        if re.match(r"\s*-\s*\[", line):  # a checklist row "- [ ] T-xxx — …"
            found = TASK_ID.findall(line)
            if found:
                ids.append(found[0])
    return ids


def _project_name(cwd) -> str:
    dag = Path(cwd) / DAG_RELPATH
    try:
        first = dag.read_text().splitlines()[0]
        m = re.search(r"#\s*Task DAG\s*[—-]\s*(.+)", first)
        if m:
            return m.group(1).strip()
    except (OSError, IndexError):
        pass
    return Path(cwd).resolve().name


def render_sprint(n: int, project: str, planned: list, carried_ids: set) -> str:
    lines = [
        f"# Sprint {n:02d} — {project}",
        "",
        "> Generated by `/forge:sprint plan` — a **view over the task DAG** (T-IDs are the",
        "> identity). The DAG and `pipeline/06-implementation/progress.md` remain the source",
        f"> of truth. At sprint end run `/forge:sprint review --sprint {n}`.",
        "",
        "## Committed tasks",
        "",
    ]
    for t in planned:
        suffix = "  _(carried over)_" if t.id in carried_ids else ""
        size = f" [{t.size}]" if t.size else ""
        title = f" — {t.title}" if t.title else ""
        lines.append(f"- [ ] {t.id}{size}{title}{suffix}")
    lines.append("")
    return "\n".join(lines)


def _read_blockers(cwd) -> list:
    """Best-effort: blockers listed in pipeline/state.md frontmatter. [] on any issue."""
    path = Path(cwd) / STATE_RELPATH
    try:
        text = path.read_text()
    except OSError:
        return []
    m = re.search(r"^blockers:\s*\[(.*?)\]", text, re.MULTILINE)
    if not m or not m.group(1).strip():
        return []
    return [b.strip().strip("'\"") for b in m.group(1).split(",") if b.strip()]


def review_sprint(cwd, n: int) -> Optional[dict]:
    """Compute {planned, done, carried, blockers} for sprint n, or None if it has no file."""
    planned = sprint_task_ids(cwd, n)
    if not planned:
        return None
    done = done_tasks(cwd)
    done_ids = [tid for tid in planned if tid in done]
    carried = [tid for tid in planned if tid not in done]
    return {
        "planned": planned,
        "done": done_ids,
        "carried": carried,
        "blockers": _read_blockers(cwd),
    }


def render_review(n: int, project: str, review: dict, titles: dict) -> str:
    def _line(tid: str) -> str:
        t = titles.get(tid)
        return f"- {tid} — {t}" if t else f"- {tid}"

    planned, done, carried = review["planned"], review["done"], review["carried"]
    lines = [
        f"# Sprint {n:02d} Review — {project}",
        "",
        f"Planned: {len(planned)} · Done: {len(done)} · Carried: {len(carried)}",
        "",
        "## Done",
        "",
        *([_line(t) for t in done] or ["(none)"]),
        "",
        "## Carried (not done — roll into the next sprint)",
        "",
        *([_line(t) for t in carried] or ["(none)"]),
        "",
        "## Blockers",
        "",
        *([f"- {b}" for b in review["blockers"]] or ["(none recorded in pipeline/state.md)"]),
        "",
        "## Lessons",
        "",
        "See `tasks/lessons.md` for lessons captured during this sprint.",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _load_dag(cwd) -> Optional[str]:
    dag = Path(cwd) / DAG_RELPATH
    if not dag.exists():
        print(f"task DAG not found: {dag} — run /forge:plan (Stage 5) first.",
              file=sys.stderr)
        return None
    try:
        return dag.read_text()
    except OSError as exc:
        print(f"could not read {dag}: {exc}", file=sys.stderr)
        return None


def _cmd_plan(args) -> int:
    cwd = Path(args.cwd)
    dag_text = _load_dag(cwd)
    if dag_text is None:
        return 1
    tasks = parse_tasks(dag_text)
    if not tasks:
        print(f"no tasks found in {DAG_RELPATH}", file=sys.stderr)
        return 1

    by_id = {t.id: t for t in tasks}
    done = done_tasks(cwd)
    n = next_sprint_number(cwd)

    # Carry-over: not-done tasks from the previous sprint keep their identity and lead the
    # new sprint (F-047). Then fill to size with new ready tasks.
    carried_ids: list = []
    if n > 1:
        carried_ids = [tid for tid in sprint_task_ids(cwd, n - 1)
                       if tid not in done and tid in by_id]
    carried_tasks = [by_id[tid] for tid in carried_ids]
    remaining = max(0, args.size - len(carried_tasks))
    fresh = select_sprint(tasks, done, size=remaining, milestone=args.milestone,
                          exclude=set(carried_ids))
    planned = carried_tasks + fresh
    if not planned:
        print("[Forge] nothing to plan — all tasks are done (or already in flight).",
              file=sys.stderr)
        return 0

    project = _project_name(cwd)
    path = sprint_path(cwd, n)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_sprint(n, project, planned, set(carried_ids)))
    except OSError as exc:
        print(f"could not write {path}: {exc}", file=sys.stderr)
        return 1
    print(f"[Forge] sprint {n:02d}: {len(planned)} task(s) "
          f"({len(carried_ids)} carried) → {path}", file=sys.stderr)
    for t in planned:
        print(t.id)
    return 0


def _cmd_review(args) -> int:
    cwd = Path(args.cwd)
    n = args.sprint if args.sprint is not None else (existing_sprints(cwd)[-1]
                                                     if existing_sprints(cwd) else None)
    if n is None:
        print("no sprints to review — run `/forge:sprint plan` first.", file=sys.stderr)
        return 1
    review = review_sprint(cwd, n)
    if review is None:
        print(f"sprint {n:02d} not found ({sprint_path(cwd, n)})", file=sys.stderr)
        return 1

    titles = {t.id: t.title for t in parse_tasks(_load_dag(cwd) or "")}
    project = _project_name(cwd)
    path = review_path(cwd, n)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_review(n, project, review, titles))
    except OSError as exc:
        print(f"could not write {path}: {exc}", file=sys.stderr)
        return 1
    print(f"[Forge] sprint {n:02d} review: {len(review['done'])} done, "
          f"{len(review['carried'])} carried → {path}", file=sys.stderr)
    return 0


def _cmd_list(args) -> int:
    cwd = Path(args.cwd)
    nums = existing_sprints(cwd)
    if not nums:
        print("No sprints yet. Run `/forge:sprint plan` to start one.")
        return 0
    done = done_tasks(cwd)
    for n in nums:
        ids = sprint_task_ids(cwd, n)
        done_n = sum(1 for t in ids if t in done)
        reviewed = " (reviewed)" if review_path(cwd, n).exists() else ""
        print(f"sprint-{n:02d}: {done_n}/{len(ids)} done{reviewed}")
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="sprint.py",
                                     description="Sprint view over the Forge task DAG")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="group the next ready tasks into a sprint")
    p_plan.add_argument("--cwd", default=".")
    p_plan.add_argument("--size", type=int, default=_DEFAULT_SIZE, metavar="K",
                        help=f"target task count (default {_DEFAULT_SIZE})")
    p_plan.add_argument("--milestone", type=int, default=None, metavar="N")
    p_plan.set_defaults(func=_cmd_plan)

    p_review = sub.add_parser("review", help="report done vs carried for a sprint")
    p_review.add_argument("--cwd", default=".")
    p_review.add_argument("--sprint", type=int, default=None, metavar="NN")
    p_review.set_defaults(func=_cmd_review)

    p_list = sub.add_parser("list", help="list sprints and their progress")
    p_list.add_argument("--cwd", default=".")
    p_list.set_defaults(func=_cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
