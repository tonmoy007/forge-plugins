#!/usr/bin/env python3
"""Dreamer daemon (T-143, REQ-F-015..021) — nightly lesson consolidation.

`/forge:dreamer-run` triggers the Dreamer to consolidate `.forge/lessons.yaml`:
  - Confidence decay: lessons below threshold are marked dormant (F-017).
  - Duplicate detection: Jaccard similarity on trigger+rule word-sets (F-018).
  - Contradiction detection: opposing-polarity similar-trigger pairs (F-019).
  - Optional consolidation summary via a cheap-model, session-reused dispatch (F-020).
  - Daily digest written to `pipeline/log/daily-<date>.md` (idempotent per day).

Boundaries (hard):
  - Duplicate/contradiction detection is FLAG ONLY — the Dreamer never merges,
    deletes, or auto-resolves lessons. Human decides.
  - Cost rule: pins a cheap model (`DREAMER_MODEL`) and reuses one session.
  - Capability-false → deterministic digest still written, no dispatch.
  - Never raises (it runs on-demand from a skill).

Mirrors the structure of `scripts/observer.py`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

import yaml

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))
import _background_agent  # noqa: E402  (the single background adapter)

try:
    import _event_log  # noqa: E402  (HMAC-chained audit log)
except Exception:  # noqa: BLE001 — audit logging is best-effort, never load-blocking
    _event_log = None  # type: ignore[assignment]

# Cost rule (spike O-2): daemons pin a cheap model + reuse one session.
DREAMER_MODEL = "haiku"

_SESSION_NAME = "dreamer-session.json"
_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"
_DREAMER_STAGE = 9

_NEGATION_TOKENS = frozenset({"never", "don't", "do not", "avoid", "no"})

_CONSOLIDATION_PROMPT = (
    "You are Forge's Dreamer. You have just completed a lesson consolidation run. "
    "Provide a single short paragraph (3-5 sentences) summarising what the consolidation "
    "found and any patterns worth noting. Be terse and concrete. No bullet lists."
)


# --- capability -----------------------------------------------------------------

def _capability_available(forge_dir: Path) -> bool:
    caps = _background_agent.read_capabilities(forge_dir)
    return bool(caps and caps.get("forge_background_available"))


# --- session reuse --------------------------------------------------------------

def _load_session(forge_dir: Path) -> Optional[dict]:
    try:
        data = json.loads((forge_dir / _SESSION_NAME).read_text())
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _save_session(forge_dir: Path, record: dict) -> None:
    try:
        forge_dir.mkdir(parents=True, exist_ok=True)
        (forge_dir / _SESSION_NAME).write_text(json.dumps(record))
    except OSError:
        return


# --- deterministic helpers (pure, testable) -------------------------------------

def _word_set(text: str) -> frozenset:
    return frozenset(text.lower().split())


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _has_negation(text: str) -> bool:
    lower = text.lower()
    return any(tok in lower for tok in _NEGATION_TOKENS)


def apply_confidence_decay(
    lessons: list[dict],
    threshold: float = 0.3,
) -> tuple[list[dict], int]:
    """Mark lessons with numeric confidence < threshold as dormant (F-017).

    Returns (updated_lessons, n_dormant) where n_dormant is the total count of
    lessons at or moved to dormant status (lessons below threshold). Lessons
    without a numeric confidence field are untouched. Idempotent: re-running
    produces the same result and the same count (already-dormant lessons below
    threshold are still counted, ensuring digest content is stable across runs).
    Never mutates the input list — returns shallow copies of changed items.
    """
    updated: list[dict] = []
    n_dormant = 0
    for lesson in lessons:
        raw_conf = lesson.get("confidence")
        if raw_conf is None or not isinstance(raw_conf, (int, float)):
            updated.append(lesson)
            continue
        if float(raw_conf) < threshold:
            n_dormant += 1
            if lesson.get("status") != "dormant":
                updated.append({**lesson, "status": "dormant"})
            else:
                updated.append(lesson)
        else:
            updated.append(lesson)
    return updated, n_dormant


def find_duplicates(
    lessons: list[dict],
    threshold: float = 0.8,
) -> list[tuple[int, int, float]]:
    """Find pairs of lessons with Jaccard similarity >= threshold (F-018).

    Similarity is computed on the combined word-set of (trigger + " " + rule),
    lowercased. Returns index pairs (i, j) with i < j, and the jaccard score.
    FLAG ONLY — this function never mutates lessons.
    """
    combined: list[frozenset] = []
    for lesson in lessons:
        text = f"{lesson.get('trigger', '')} {lesson.get('rule', '')}"
        combined.append(_word_set(text))

    pairs: list[tuple[int, int, float]] = []
    n = len(combined)
    for i in range(n):
        for j in range(i + 1, n):
            score = _jaccard(combined[i], combined[j])
            if score >= threshold:
                pairs.append((i, j, score))
    return pairs


def find_contradictions(lessons: list[dict]) -> list[tuple[int, int]]:
    """Find pairs of lessons with similar triggers but opposing rule polarities (F-019).

    A pair is a contradiction when:
      - Trigger word-sets have Jaccard >= 0.5 (similar context)
      - Exactly one of the two rules contains a negation token
        {never, don't, do not, avoid, no}

    FLAG ONLY — this function never mutates lessons.
    """
    triggers: list[frozenset] = [_word_set(l.get("trigger", "")) for l in lessons]
    rule_has_negation: list[bool] = [_has_negation(l.get("rule", "")) for l in lessons]

    pairs: list[tuple[int, int]] = []
    n = len(lessons)
    for i in range(n):
        for j in range(i + 1, n):
            if _jaccard(triggers[i], triggers[j]) >= 0.5:
                # XOR: exactly one has a negation → opposing polarity
                if rule_has_negation[i] != rule_has_negation[j]:
                    pairs.append((i, j))
    return pairs


def build_digest(
    date: str,
    *,
    decayed: int,
    duplicates: list,
    contradictions: list,
    total: int,
    consolidation: str = "",
) -> str:
    """Build a markdown daily digest summarising the Dreamer's run."""
    lines = [
        f"# Dreamer Daily Digest — {date}",
        "",
        f"**Total lessons:** {total}  ",
        f"**Decayed to dormant:** {decayed}  ",
        f"**Duplicate pairs flagged:** {len(duplicates)}  ",
        f"**Contradiction pairs flagged:** {len(contradictions)}  ",
        "",
    ]
    if duplicates:
        lines.append("## Duplicate Pairs (flag only — human decides)")
        for pair in duplicates:
            i, j, score = pair
            lines.append(f"- Lessons {i} & {j} — Jaccard {score:.2f}")
        lines.append("")
    if contradictions:
        lines.append("## Contradiction Pairs (flag only — human decides)")
        for i, j in contradictions:
            lines.append(f"- Lessons {i} & {j}")
        lines.append("")
    if consolidation:
        lines.append("## Consolidation")
        lines.append(consolidation)
        lines.append("")
    return "\n".join(lines)


def daily_digest_path(cwd: object, date: str) -> Path:
    """Return the path for the daily digest: <cwd>/pipeline/log/daily-<date>.md."""
    return Path(str(cwd)) / "pipeline" / "log" / f"daily-{date}.md"


def write_lessons_atomic(path: Path, data: dict) -> bool:
    """Atomically write lessons YAML via tmp + os.replace (F-021). Never raises."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            suffix=".tmp",
            delete=False,
            encoding="utf-8",
        ) as fh:
            yaml.dump(data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)
            fh.flush()
            os.fsync(fh.fileno())
            tmp = fh.name
        os.replace(tmp, path)
        return True
    except Exception:  # noqa: BLE001 — never raises
        return False


# --- audit event (best-effort) -------------------------------------------------

def _log_event(forge_dir: Path, session_id: str, payload: dict) -> None:
    if _event_log is None:
        return
    try:
        _event_log.append(
            forge_dir, "dreamer_run", session_id, _DREAMER_STAGE,
            payload, "dreamer",
        )
    except Exception:  # noqa: BLE001 — audit is best-effort
        return


# --- consolidation dispatch ----------------------------------------------------

def _dispatch_consolidation(
    forge_dir: Path,
    *,
    resume: Optional[str],
    cwd: Optional[str],
    claude_bin: Optional[str],
    model: str,
    dispatch_fn: Optional[object],
) -> object:
    if dispatch_fn is not None:
        return dispatch_fn(
            _CONSOLIDATION_PROMPT,
            forge_dir=forge_dir,
            feature="dreamer",
            resume=resume,
            model=model,
            cwd=cwd,
            claude_bin=claude_bin,
        )
    return _background_agent.dispatch(
        _CONSOLIDATION_PROMPT,
        forge_dir=forge_dir,
        feature="dreamer",
        resume=resume,
        model=model,
        cwd=cwd,
        claude_bin=claude_bin,
    )


# --- orchestrator --------------------------------------------------------------

def run(
    cwd: str,
    *,
    now: Optional[dt.datetime] = None,
    claude_bin: Optional[str] = None,
    model: str = DREAMER_MODEL,
    dispatch_fn: Optional[object] = None,
) -> dict:
    """Orchestrate F-015..021. Never raises.

    Returns {decayed, duplicates, contradictions, digest_path, consolidation_used}.
    """
    try:
        when = now if now is not None else dt.datetime.now(dt.timezone.utc)
        date_str = when.strftime("%Y-%m-%d")
        forge_dir = Path(cwd) / ".forge"
        lessons_path = forge_dir / "lessons.yaml"

        # F-015: load lessons.yaml — missing → graceful no-op
        if not lessons_path.exists():
            return {
                "decayed": 0,
                "duplicates": [],
                "contradictions": [],
                "digest_path": str(daily_digest_path(cwd, date_str)),
                "consolidation_used": False,
            }

        try:
            raw = yaml.safe_load(lessons_path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            raw = {}

        lessons: list[dict] = raw.get("lessons", []) or []
        schema_version = raw.get("schema_version", 1)

        # F-017: confidence decay
        lessons, n_decayed = apply_confidence_decay(lessons)

        # F-021: atomic write back
        write_lessons_atomic(lessons_path, {"schema_version": schema_version, "lessons": lessons})

        # F-018: duplicate detection (flag only)
        dups = find_duplicates(lessons)

        # F-019: contradiction detection (flag only)
        contras = find_contradictions(lessons)

        # F-020: optional consolidation (capability-gated)
        consolidation_text = ""
        consolidation_used = False
        sess = _load_session(forge_dir)
        prior_session_id = (sess or {}).get("session_id") or None

        if _capability_available(forge_dir):
            try:
                res = _dispatch_consolidation(
                    forge_dir,
                    resume=prior_session_id,
                    cwd=cwd,
                    claude_bin=claude_bin,
                    model=model,
                    dispatch_fn=dispatch_fn,
                )
                if res.status == "ok" and not (res.raw or {}).get("is_error"):
                    consolidation_text = res.result or ""
                    new_session_id = res.session_id or prior_session_id or ""
                    _save_session(forge_dir, {"session_id": new_session_id})
                    consolidation_used = True
            except Exception:  # noqa: BLE001
                pass

        # Build digest (idempotent — overwrite with deterministic content)
        digest = build_digest(
            date_str,
            decayed=n_decayed,
            duplicates=dups,
            contradictions=contras,
            total=len(lessons),
            consolidation=consolidation_text,
        )
        dpath = daily_digest_path(cwd, date_str)
        try:
            dpath.parent.mkdir(parents=True, exist_ok=True)
            dpath.write_text(digest, encoding="utf-8")
        except OSError:
            pass

        # Best-effort audit event
        _log_event(forge_dir, prior_session_id or "", {
            "decayed": n_decayed,
            "duplicates": len(dups),
            "contradictions": len(contras),
        })

        return {
            "decayed": n_decayed,
            "duplicates": dups,
            "contradictions": contras,
            "digest_path": str(dpath),
            "consolidation_used": consolidation_used,
        }
    except Exception:  # noqa: BLE001 — daemon entry must never raise
        return {
            "decayed": 0,
            "duplicates": [],
            "contradictions": [],
            "digest_path": "",
            "consolidation_used": False,
        }


# --- CLI -----------------------------------------------------------------------

def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="dreamer")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--claude-bin", default=None)
    parser.add_argument("--model", default=DREAMER_MODEL)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", action="store_true", help="run a dreamer consolidation pass")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.run:
        result = run(args.cwd, claude_bin=args.claude_bin, model=args.model)
        print("Dreamer run complete.")
        print(f"  Decayed: {result['decayed']}")
        print(f"  Duplicate pairs: {len(result['duplicates'])}")
        print(f"  Contradiction pairs: {len(result['contradictions'])}")
        print(f"  Digest: {result['digest_path']}")
        print(f"  Consolidation used: {result['consolidation_used']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
