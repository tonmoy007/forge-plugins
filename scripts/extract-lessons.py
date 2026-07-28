#!/usr/bin/env python3
"""Extract structured lessons from .forge/correction-flags.jsonl.

Parses correction flags written by prompt-submit.py and appends
Trigger/Rule/Why entries to tasks/lessons.md.

Rule-based extraction is always available. Pass --llm to route through
the lesson-extractor agent (falls back to rule-based on any failure).

Pass --propose to skip the direct file write and instead print the
extracted lessons as YAML to stdout — the caller (hooks/stop-reflect.py)
then validates each proposal and writes it via the Proposal->Validator->
Executor rails, which also mirrors it into .forge/lessons.yaml.
"""

from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import logging
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_LESSONS_HEADER = "## Lessons"
_TAG_KEYWORDS = ["test", "hook", "script", "yaml", "git", "python"]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CorrectionFlag:
    ts: str
    session: str
    prompt: str


@dataclass
class Lesson:
    date: str
    title: str
    trigger: str
    rule: str
    why: str
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_flags(path: Path, since: Optional[str] = None) -> list[CorrectionFlag]:
    """Parse correction-flags.jsonl. Returns [] silently if file is missing."""
    if not path.exists():
        return []
    flags: list[CorrectionFlag] = []
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                ts: str = obj["ts"]
                session: str = obj["session"]
                prompt: str = obj["prompt"]
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("line %d: skipping malformed record: %s", lineno, exc)
                continue
            if since and ts[:10] < since:
                continue
            flags.append(CorrectionFlag(ts=ts, session=session, prompt=prompt))
    return flags


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _load_existing_titles(output_path: Path) -> list[str]:
    if not output_path.exists():
        return []
    titles: list[str] = []
    for line in output_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^###\s+\d{4}-\d{2}-\d{2}\s+[—-]\s+(.+)$", line)
        if m:
            titles.append(m.group(1).strip())
    return titles


def _is_duplicate(title: str, existing: list[str]) -> bool:
    t = title.lower().strip()
    for e in existing:
        ratio = difflib.SequenceMatcher(None, t, e.lower().strip()).ratio()
        if ratio >= 0.8:
            return True
    return False


# ---------------------------------------------------------------------------
# Rule-based extraction helpers
# ---------------------------------------------------------------------------


def _split_why(text: str) -> tuple[str, str]:
    """Return (rule_text, why_text) split on 'because' or 'otherwise'."""
    for marker in ["because", "otherwise"]:
        m = re.search(r"\b" + marker + r"\b", text, re.IGNORECASE)
        if m:
            why = text[m.end():].strip().rstrip(".,;")
            if why:
                why = why[0].upper() + why[1:]
            rule_text = text[: m.start()].strip().rstrip(",;")
            return rule_text, why
    return text.strip(), "Prevents repeating this mistake"


def _extract_tags(prompt: str) -> list[str]:
    tags: list[str] = []
    for m in re.finditer(r"\S+\.(?:py|md|json|sh)\b", prompt):
        fname = m.group().rstrip(".,;)")
        if fname not in tags:
            tags.append(fname)
    for kw in _TAG_KEYWORDS:
        if re.search(r"\b" + kw + r"\b", prompt, re.IGNORECASE):
            if kw not in tags:
                tags.append(kw)
    return tags


def _rule_based_extract(flag: CorrectionFlag) -> Optional[Lesson]:
    prompt = flag.prompt
    date = flag.ts[:10]
    tags = _extract_tags(prompt)
    rule_text, why = _split_why(prompt)

    rule: Optional[str] = None

    # "don't X" / "never X" / "stop X" — strip trailing filler (here/there/now)
    neg_m = re.search(
        r"\b(don'?t|never|stop)\s+(.+?)(?=\s+(?:here|there|now)\b|[,;]|$)",
        rule_text,
        re.IGNORECASE,
    )
    if neg_m:
        x_part = neg_m.group(2).strip()
        rest = rule_text[neg_m.end():].lstrip(" \t,;")
        # Strip leading filler word if it ended the match
        rest = re.sub(r"^(?:here|there|now)\b\s*[,;]?\s*", "", rest, flags=re.IGNORECASE)

        use_m = re.search(r"\buse\s+(.+?)\s+instead\b", rest, re.IGNORECASE)
        if use_m:
            rule = f"Don't {x_part}; use {use_m.group(1).strip()} instead"
        else:
            rule = f"Don't {x_part}"

    # "use X instead of Y" / "use X not Y"
    if rule is None:
        m = re.search(
            r"\buse\s+(.+?)\s+instead\s+of\s+(.+?)(?:[,;.]|$)", rule_text, re.IGNORECASE
        )
        if m:
            rule = f"Use {m.group(1).strip()}, not {m.group(2).strip()}"
        else:
            m = re.search(
                r"\buse\s+(.+?)\s+not\s+(.+?)(?:[,;.]|$)", rule_text, re.IGNORECASE
            )
            if m:
                rule = f"Use {m.group(1).strip()}, not {m.group(2).strip()}"

    # "always X" / "prefer X"
    if rule is None:
        m = re.search(
            r"\b(always|prefer)\s+(.+?)(?:[,;.]|$)", rule_text, re.IGNORECASE
        )
        if m:
            rule = f"Always {m.group(2).strip()}"

    # "use X instead" (without of/not Y)
    if rule is None:
        m = re.search(r"\buse\s+(.+?)\s+instead\b", rule_text, re.IGNORECASE)
        if m:
            rule = f"Use {m.group(1).strip()} instead"

    if rule is None:
        return None

    title = rule[:60]
    return Lesson(
        date=date,
        title=title,
        trigger="When this pattern occurs",
        rule=rule,
        why=why,
        tags=tags,
    )


# ---------------------------------------------------------------------------
# LLM path
# ---------------------------------------------------------------------------


def _llm_extract(flag: CorrectionFlag) -> Optional[Lesson]:
    """Attempt LLM-backed extraction; silently fall back to None on any failure."""
    try:
        hooks_dir = Path(__file__).parent.parent / "hooks"
        spec = importlib.util.spec_from_file_location(
            "_invoke_agent", hooks_dir / "_invoke_agent.py"
        )
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        response: str = mod.invoke_agent(
            "lesson-extractor",
            {"prompt": flag.prompt, "ts": flag.ts, "session": flag.session},
        )
        if not response:
            return None
        data = json.loads(response)
        return Lesson(
            date=flag.ts[:10],
            title=str(data.get("title", ""))[:60],
            trigger=str(data.get("trigger", "When this pattern occurs")),
            rule=str(data.get("rule", "")),
            why=str(data.get("why", "Prevents repeating this mistake")),
            tags=list(data.get("tags", [])),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("LLM extraction failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_lesson(flag: CorrectionFlag, use_llm: bool = False) -> Optional[Lesson]:
    """Extract a Lesson from a CorrectionFlag. Returns None if no pattern matches."""
    if use_llm:
        lesson = _llm_extract(flag)
        if lesson:
            return lesson
    return _rule_based_extract(flag)


def emit_proposals(lessons: list[Lesson]) -> None:
    """Print extracted lessons as YAML to stdout — propose only, no file write.

    Keys match what hooks/stop-reflect.py's _parse_lesson_output reads
    (trigger/rule/why); stage_tags is intentionally omitted since Lesson
    carries keyword tags, not stage numbers — the caller defaults it to
    the current stage.
    """
    payload = [
        {"trigger": l.trigger, "rule": l.rule, "why": l.why}
        for l in lessons
    ]
    print(yaml.safe_dump(payload, sort_keys=False))


def format_lesson(lesson: Lesson) -> str:
    """Render a Lesson as the tasks/lessons.md markdown format."""
    tags_str = ", ".join(lesson.tags)
    return (
        f"### {lesson.date} — {lesson.title}\n"
        f"- **Trigger**: {lesson.trigger}\n"
        f"- **Rule**: {lesson.rule}\n"
        f"- **Why**: {lesson.why}\n"
        f"- **Tags**: [{tags_str}]\n"
    )


def append_lessons(
    output_path: Path,
    lessons: list[Lesson],
    *,
    dry_run: bool = False,
) -> None:
    """Append formatted lessons into the '## Lessons' section, atomically."""
    if not lessons:
        return

    if dry_run:
        for lesson in lessons:
            print(format_lesson(lesson))
        return

    if output_path.exists():
        content = output_path.read_text(encoding="utf-8")
    else:
        content = f"# Lessons Learned\n\n{_LESSONS_HEADER}\n"

    formatted = "\n".join(format_lesson(l) for l in lessons)

    if _LESSONS_HEADER in content:
        header_idx = content.index(_LESSONS_HEADER)
        after_header_nl = content.find("\n", header_idx)
        if after_header_nl == -1:
            new_content = content + "\n\n" + formatted + "\n"
        else:
            insert_pos = after_header_nl + 1
            new_content = content[:insert_pos] + "\n" + formatted + "\n" + content[insert_pos:]
    else:
        new_content = content.rstrip() + f"\n\n{_LESSONS_HEADER}\n\n" + formatted + "\n"

    fd, tmp_path = tempfile.mkstemp(dir=output_path.parent, suffix=".tmp")
    tmp = Path(tmp_path)
    try:
        os.close(fd)
        tmp.write_text(new_content, encoding="utf-8")
        tmp.replace(output_path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract structured lessons from correction-flags.jsonl"
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        default=Path("."),
        metavar="PATH",
        help="project root; --input/--output default relative to it (matches other forge scripts)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        metavar="PATH",
        help="default: <cwd>/.forge/correction-flags.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help="default: <cwd>/tasks/lessons.md",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print without writing")
    parser.add_argument("--since", metavar="YYYY-MM-DD", help="Skip flags older than date")
    parser.add_argument("--llm", action="store_true", help="Use lesson-extractor agent")
    parser.add_argument(
        "--propose",
        action="store_true",
        help="Print extracted lessons as YAML to stdout instead of writing "
        "tasks/lessons.md directly — for callers that validate before persisting",
    )
    args = parser.parse_args(argv)

    # REQ-EXTRACT-CWD-001: derive default paths from --cwd; explicit flags override.
    if args.input is None:
        args.input = args.cwd / ".forge" / "correction-flags.jsonl"
    if args.output is None:
        args.output = args.cwd / "tasks" / "lessons.md"

    flags = parse_flags(args.input, since=args.since)
    if not flags:
        logger.debug("No flags found in %s", args.input)
        return 0

    existing_titles = _load_existing_titles(args.output)

    lessons: list[Lesson] = []
    for flag in flags:
        lesson = extract_lesson(flag, use_llm=args.llm)
        if lesson is None:
            logger.debug("No pattern matched for flag at %s", flag.ts)
            continue
        if _is_duplicate(lesson.title, existing_titles):
            logger.debug("Skipping duplicate: %s", lesson.title)
            continue
        lessons.append(lesson)
        existing_titles.append(lesson.title)

    if args.propose:
        emit_proposals(lessons)
        return 0

    append_lessons(args.output, lessons, dry_run=args.dry_run)
    if not args.dry_run:
        logger.info("Appended %d lesson(s) to %s", len(lessons), args.output)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.exit(main())
