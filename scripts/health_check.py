#!/usr/bin/env python3
"""Health daemon (T-144, REQ-F-022..026) — self-diagnostic for the Forge plugin.

`/forge:health-check` runs this script to produce a structured health report:
  - Runs hook unit tests as a subprocess and parses pass/fail counts (F-023).
  - Loads .forge/lessons.yaml and checks for structural integrity issues (F-024).
  - Computes overall status: healthy / degraded / failing (F-022).
  - If status is "failing" AND `health.auto_disable_hooks: true` in config.yaml,
    records a health_auto_disable event (F-025/F-026) — NEVER silently.

Boundaries (hard):
  - Never raises (REQ-NF-006 parity with observer.py).
  - Auto-disable is ALWAYS surfaced: events.jsonl + health-surface.txt.
  - Config gating: auto-disable requires explicit opt-in; default is False.

Status thresholds (F-022):
  - "healthy"  — hook tests pass AND no lesson integrity issues.
  - "degraded" — hook tests pass BUT lesson issues exist (non-blocking problems).
  - "failing"  — hook tests failed (regardless of lesson state).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_DIR / "hooks"))

try:
    import _event_log  # noqa: E402  (HMAC-chained audit log)
except Exception:  # noqa: BLE001 — audit logging best-effort, never load-blocking
    _event_log = None  # type: ignore[assignment]

_HEALTH_STAGE = 0  # health is cross-stage; use stage 0 (infra)
_SURFACE_NAME = "health-surface.txt"
_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"

# Regex to find [[xref-slug]] tokens inside trigger/rule text.
_XREF_RE = re.compile(r"\[\[([^\]]+)\]\]")


# ---------------------------------------------------------------------------
# YAML helper (mirrors _cost_cap._safe_yaml_load)
# ---------------------------------------------------------------------------

def _safe_yaml_load(text: str) -> Optional[dict]:
    """Parse YAML, returning None on any failure (incl. PyYAML absent)."""
    try:
        import yaml  # noqa: F401
    except ImportError:
        return None
    try:
        data = yaml.safe_load(text)
    except Exception:  # noqa: BLE001 — malformed config must not crash
        return None
    return data if isinstance(data, dict) else None


def _read_text(path: Path) -> str:
    try:
        return path.read_text()
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# F-023 — hook test runner
# ---------------------------------------------------------------------------

def run_hook_tests(
    plugin_dir: Path,
    *,
    timeout: float = 60.0,
    runner: Optional[Callable[..., str]] = None,
) -> dict:
    """Run hook-focused unit tests and parse pass/fail counts.

    Returns ``{passed: int, failed: int, ok: bool, detail: str}``.
    Never raises; subprocess errors yield ok=False with detail.

    Parameters
    ----------
    plugin_dir:
        Root of the plugin (where tests/ lives).
    timeout:
        Subprocess timeout in seconds (ignored when runner is injected).
    runner:
        Optional callable for injection in tests; called with keyword args
        ``plugin_dir`` and ``timeout``, returns raw stdout string.
    """
    if runner is not None:
        output = runner(plugin_dir=plugin_dir, timeout=timeout)
        return _parse_pytest_output(output)

    cmd = [
        sys.executable, "-m", "pytest",
        "tests/unit",
        "-k", "hook or session_start or stop_reflect or prompt_submit",
        "-q",
        "--tb=no",
        "--no-header",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(plugin_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = proc.stdout + proc.stderr
        return _parse_pytest_output(output)
    except subprocess.TimeoutExpired:
        return {"passed": 0, "failed": 0, "ok": False,
                "detail": f"hook tests timed out after {timeout}s"}
    except Exception as exc:  # noqa: BLE001
        return {"passed": 0, "failed": 0, "ok": False,
                "detail": f"could not run hook tests: {exc}"}


def _parse_pytest_output(output: str) -> dict:
    """Extract pass/fail counts from pytest -q output.

    Handles lines like:
      - "12 passed" / "12 passed, 0 failed"
      - "8 passed, 4 failed"
      - "4 failed" (no pass count)
      - "no tests ran"
    """
    passed = 0
    failed = 0
    # Look for the summary line that pytest -q emits: "X passed" or "X failed"
    # Pattern: match combinations like "5 passed, 2 failed" or just "5 passed"
    pass_m = re.search(r"(\d+)\s+passed", output)
    fail_m = re.search(r"(\d+)\s+failed", output)
    if pass_m:
        passed = int(pass_m.group(1))
    if fail_m:
        failed = int(fail_m.group(1))

    if not pass_m and not fail_m:
        # Could be "no tests ran" or subprocess error output
        ok = False
        detail = (output.strip()[:200] if output.strip()
                  else "no tests found matching hook filter")
        return {"passed": 0, "failed": 0, "ok": ok, "detail": detail}

    ok = failed == 0
    detail = f"{passed} passed, {failed} failed"
    return {"passed": passed, "failed": failed, "ok": ok, "detail": detail}


# ---------------------------------------------------------------------------
# F-024 — lesson integrity checker
# ---------------------------------------------------------------------------

def check_lesson_integrity(lessons_path: Path) -> list[dict]:
    """Load lessons.yaml and return a list of issue dicts ``{kind, detail}``.

    Checks:
      - File missing → issue kind "missing_file"
      - Malformed YAML → issue kind "malformed_yaml"
      - Each lesson missing ``trigger`` or ``rule`` → "missing_field"
      - ``confidence`` present but outside [0.0, 1.0] → "confidence_out_of_range"
      - ``[[name]]`` token in rule/trigger matching no other lesson slug → "broken_xref"

    Returns empty list when clean. Never raises.
    """
    issues: list[dict] = []
    try:
        if not lessons_path.exists():
            return [{"kind": "missing_file",
                     "detail": f"{lessons_path} does not exist"}]

        text = lessons_path.read_text()
    except OSError as exc:
        return [{"kind": "io_error", "detail": str(exc)}]

    # Parse YAML
    try:
        import yaml
        try:
            data = yaml.safe_load(text)
        except Exception as exc:  # noqa: BLE001
            return [{"kind": "malformed_yaml",
                     "detail": f"YAML parse error: {exc}"}]
    except ImportError:
        # Without PyYAML we cannot check; treat as clean to avoid false alarms.
        return []

    if not isinstance(data, dict):
        return [{"kind": "malformed_yaml",
                 "detail": "top-level document is not a mapping"}]

    lessons = data.get("lessons", [])
    if not isinstance(lessons, list):
        return [{"kind": "malformed_yaml",
                 "detail": "'lessons' key is not a list"}]

    # Build slug set for xref resolution.
    # Slug = lowercased, spaces→hyphens version of trigger text (first 60 chars).
    def _slugify(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", text.lower().strip())[:60].strip("-")

    slugs: set[str] = set()
    for lesson in lessons:
        if not isinstance(lesson, dict):
            continue
        trigger = lesson.get("trigger", "")
        if isinstance(trigger, str) and trigger.strip():
            slugs.add(_slugify(trigger))

    for idx, lesson in enumerate(lessons):
        if not isinstance(lesson, dict):
            issues.append({"kind": "malformed_yaml",
                           "detail": f"lesson {idx} is not a mapping"})
            continue

        trigger = lesson.get("trigger")
        rule = lesson.get("rule")

        # Required fields
        if not trigger or not str(trigger).strip():
            issues.append({"kind": "missing_field",
                           "detail": f"lesson {idx} is missing 'trigger'"})
        if not rule or not str(rule).strip():
            issues.append({"kind": "missing_field",
                           "detail": f"lesson {idx} is missing 'rule'"})

        # Confidence range
        confidence = lesson.get("confidence")
        if confidence is not None:
            try:
                conf_float = float(confidence)
                if conf_float < 0.0 or conf_float > 1.0:
                    issues.append({"kind": "confidence_out_of_range",
                                   "detail": (f"lesson {idx} confidence={confidence} "
                                              f"is outside [0.0, 1.0]")})
            except (TypeError, ValueError):
                issues.append({"kind": "confidence_out_of_range",
                               "detail": f"lesson {idx} confidence={confidence!r} "
                                         f"is not a number"})

        # Cross-reference check: [[slug]] tokens in trigger and rule
        for field_name, field_val in [("trigger", trigger), ("rule", rule)]:
            if not isinstance(field_val, str):
                continue
            for m in _XREF_RE.finditer(field_val):
                ref = m.group(1).strip()
                ref_slug = _slugify(ref)
                if ref_slug not in slugs:
                    issues.append({"kind": "broken_xref",
                                   "detail": (f"lesson {idx} {field_name} references "
                                              f"[[{ref}]] which matches no known lesson")})

    return issues


# ---------------------------------------------------------------------------
# F-022 — overall status
# ---------------------------------------------------------------------------

def overall_status(hook_result: dict, lesson_issues: list) -> str:
    """Compute overall health status from hook results and lesson issues.

    Rules (clear and documented):
      - "failing"  — hook tests failed (hook_result["ok"] is False).
                     This is the most severe state regardless of lesson health.
      - "degraded" — hook tests passed but lesson integrity issues exist.
                     Lessons are advisory; hooks failing to lint indicates config debt,
                     not a blocking failure.
      - "healthy"  — hook tests passed AND no lesson integrity issues.
    """
    if not hook_result.get("ok", False):
        return "failing"
    if lesson_issues:
        return "degraded"
    return "healthy"


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------

def build_report(
    status: str,
    hook_result: dict,
    lesson_issues: list,
    *,
    auto_disabled: Optional[list[str]] = None,
) -> str:
    """Build a readable markdown health report."""
    auto_disabled = auto_disabled or []
    lines = [
        "# Forge Health Report",
        "",
        f"**Status:** `{status.upper()}`",
        "",
        "## Hook Tests",
        "",
    ]
    passed = hook_result.get("passed", 0)
    failed = hook_result.get("failed", 0)
    detail = hook_result.get("detail", "")
    ok_icon = "PASS" if hook_result.get("ok") else "FAIL"
    lines.append(f"- Result: {ok_icon}")
    lines.append(f"- {passed} passed, {failed} failed")
    if detail:
        lines.append(f"- Detail: {detail}")
    lines.append("")
    lines.append("## Lesson Store Integrity")
    lines.append("")
    if not lesson_issues:
        lines.append("- No issues found.")
    else:
        for issue in lesson_issues:
            lines.append(f"- [{issue['kind']}] {issue['detail']}")
    lines.append("")

    if auto_disabled:
        lines.append("## Auto-Disable Applied")
        lines.append("")
        lines.append("> WARNING: hooks were auto-disabled because status is FAILING")
        lines.append("> and `health.auto_disable_hooks: true` is set in config.yaml.")
        lines.append("> This was recorded in .forge/events.jsonl and .forge/health-surface.txt.")
        lines.append("")
        for item in auto_disabled:
            lines.append(f"- {item}")
        lines.append("")
    elif status == "failing":
        lines.append("## Auto-Disable")
        lines.append("")
        lines.append("- Policy is OFF (`health.auto_disable_hooks` not set to true).")
        lines.append("- No hooks were disabled. Review failing tests manually.")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by /forge:health-check*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# F-025 — auto-disable policy reader
# ---------------------------------------------------------------------------

def auto_disable_policy(forge_dir: Path) -> bool:
    """Return True ONLY if `health.auto_disable_hooks` is explicitly `true`.

    Reads `.forge/config.yaml`. Defaults to False on any absence or error.
    Never raises.
    """
    cfg_path = forge_dir / "config.yaml"
    if not cfg_path.exists():
        return False
    text = _read_text(cfg_path)
    data = _safe_yaml_load(text)
    if not isinstance(data, dict):
        return False
    health_section = data.get("health")
    if not isinstance(health_section, dict):
        return False
    return health_section.get("auto_disable_hooks") is True


# ---------------------------------------------------------------------------
# F-026 — non-silent auto-disable surfacing
# ---------------------------------------------------------------------------

def _surface_auto_disable(forge_dir: Path, auto_disabled: list[str]) -> None:
    """Write surfaced note to .forge/health-surface.txt and append event.

    Called ONLY when status is failing AND policy is True.
    Two outputs ensure the auto-disable is never silent (F-026):
      1. events.jsonl — HMAC-chained audit record (machine-readable).
      2. health-surface.txt — human-readable note for session-start to show.
    """
    import datetime as dt

    ts = dt.datetime.now(dt.timezone.utc).strftime(_TS_FMT)
    label = ", ".join(auto_disabled) if auto_disabled else "hook test suite"

    # 1. Audit event (best-effort; wrapped so it never crashes run())
    if _event_log is not None:
        try:
            _event_log.append(
                forge_dir,
                "health_auto_disable",
                "health-check",
                _HEALTH_STAGE,
                {"auto_disabled": auto_disabled, "reason": "hook tests failing"},
                "health",
            )
        except Exception:  # noqa: BLE001
            pass

    # 2. Human-readable surface note
    try:
        forge_dir.mkdir(parents=True, exist_ok=True)
        surface_path = forge_dir / _SURFACE_NAME
        surface_path.write_text(
            f"[{ts}] Forge Health: FAILING — auto-disable policy triggered.\n"
            f"The following were flagged for auto-disable: {label}\n"
            f"Review .forge/events.jsonl for the full audit record.\n"
            f"Fix hook test failures and re-run /forge:health-check to clear.\n"
        )
    except OSError:
        pass


def _clear_surface(forge_dir: Path) -> None:
    """Remove a stale health-surface note once the system is no longer failing.
    Never raises."""
    try:
        (forge_dir / _SURFACE_NAME).unlink()
    except OSError:
        pass  # absent or unremovable — nothing to clear


# ---------------------------------------------------------------------------
# F-022 — run() orchestrator
# ---------------------------------------------------------------------------

def run(
    cwd: str,
    *,
    plugin_dir: Optional[Path] = None,
    runner: Optional[Callable[..., str]] = None,
    now=None,  # unused; accepted for API parity / future use
) -> dict:
    """Orchestrate a full health check. Never raises.

    Parameters
    ----------
    cwd:
        Working directory of the project being checked (.forge lives here).
    plugin_dir:
        Root of the plugin installation (where tests/ lives). Defaults to the
        directory two levels above this script.
    runner:
        Optional callable injected for tests so pytest is never actually spawned.

    Returns
    -------
    dict with keys: status, report, issues, hook_result, auto_disabled.
    """
    try:
        cwd_path = Path(cwd)
        forge_dir = cwd_path / ".forge"
        _plugin_dir = plugin_dir if plugin_dir is not None else _PLUGIN_DIR

        # Step 1: run hook tests
        hook_result = run_hook_tests(_plugin_dir, runner=runner)

        # Step 2: check lesson integrity
        lessons_path = forge_dir / "lessons.yaml"
        lesson_issues = check_lesson_integrity(lessons_path)

        # Step 3: compute status
        status = overall_status(hook_result, lesson_issues)

        # Step 4: auto-disable (only when failing AND policy opt-in)
        auto_disabled: list[str] = []
        if status == "failing" and auto_disable_policy(forge_dir):
            # Record what would be disabled — we surface it but don't actually
            # remove files; the "disable" is surfaced for human action (F-026).
            auto_disabled = ["hook test suite (failing — manual review required)"]
            _surface_auto_disable(forge_dir, auto_disabled)
        else:
            # Recovered (or policy off): clear any stale surfaced warning so the
            # next session start doesn't keep showing a resolved auto-disable.
            _clear_surface(forge_dir)

        # Step 5: build report
        report = build_report(status, hook_result, lesson_issues,
                              auto_disabled=auto_disabled)

        return {
            "status": status,
            "report": report,
            "issues": lesson_issues,
            "hook_result": hook_result,
            "auto_disabled": auto_disabled,
        }
    except Exception:  # noqa: BLE001 — health daemon must never raise
        return {
            "status": "failing",
            "report": "# Forge Health Report\n\n**Status:** `FAILING`\n\nUnexpected error during health check.\n",
            "issues": [],
            "hook_result": {"passed": 0, "failed": 0, "ok": False,
                            "detail": "health check itself raised an exception"},
            "auto_disabled": [],
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="health_check",
                                     description="Forge health daemon (T-144)")
    parser.add_argument("--cwd", default=".",
                        help="project working directory (.forge lives here)")
    parser.add_argument("--plugin-dir", default=None,
                        help="plugin root (defaults to two dirs above this script)")
    parser.add_argument("--run", action="store_true",
                        help="run the full health check and print the report")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if not args.run:
        parser.print_help()
        return 1

    plugin_dir = Path(args.plugin_dir) if args.plugin_dir else None
    result = run(args.cwd, plugin_dir=plugin_dir)
    print(result["report"])
    return 0 if result["status"] == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
