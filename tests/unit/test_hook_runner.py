"""Tests for scripts/_hook_runner.py.

Run with: python -m pytest tests/unit/test_hook_runner.py -q

POSIX-only (the wrapper uses SIGALRM). Skipped on Windows.
"""
from __future__ import annotations

import json
import os
import signal
import sys
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("hook_runner is POSIX-only", allow_module_level=True)

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _hook_runner as hook_runner  # noqa: E402


# ---------- timeout resolution ----------

class TestResolveTimeout:
    def test_default_for_known_hook(self):
        assert hook_runner._resolve_timeout("session-start") == 30.0
        assert hook_runner._resolve_timeout("prompt-submit") == 1.0
        assert hook_runner._resolve_timeout("stop-reflect") == 10.0

    def test_fallback_for_unknown_hook(self):
        assert hook_runner._resolve_timeout("custom-hook") == 5.0

    def test_global_env_override(self, monkeypatch):
        monkeypatch.setenv("FORGE_HOOK_TIMEOUT", "0.5")
        assert hook_runner._resolve_timeout("session-start") == 0.5

    def test_per_hook_env_override(self, monkeypatch):
        monkeypatch.setenv("FORGE_HOOK_TIMEOUT_SESSION_START", "60")
        assert hook_runner._resolve_timeout("session-start") == 60.0

    def test_per_hook_wins_over_global(self, monkeypatch):
        monkeypatch.setenv("FORGE_HOOK_TIMEOUT", "0.5")
        monkeypatch.setenv("FORGE_HOOK_TIMEOUT_SESSION_START", "60")
        assert hook_runner._resolve_timeout("session-start") == 60.0

    def test_invalid_env_value_falls_through(self, monkeypatch):
        monkeypatch.setenv("FORGE_HOOK_TIMEOUT", "not-a-number")
        assert hook_runner._resolve_timeout("session-start") == 30.0


# ---------- log location ----------

class TestResolveLogDir:
    def test_explicit_cwd_arg(self, tmp_path):
        assert hook_runner._resolve_log_dir(tmp_path) == tmp_path / ".forge"

    def test_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
        assert hook_runner._resolve_log_dir() == tmp_path / ".forge"

    def test_fallback_to_cwd(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        monkeypatch.chdir(tmp_path)
        assert hook_runner._resolve_log_dir() == tmp_path / ".forge"


# ---------- error emission ----------

class TestEmitError:
    def test_creates_log_dir_and_file(self, tmp_path):
        hook_runner._emit_error("test-hook", "TestError", "detail", tmp_path)
        log = tmp_path / ".forge" / "hook-errors.log"
        assert log.exists()
        record = json.loads(log.read_text())
        assert record["hook"] == "test-hook"
        assert record["kind"] == "TestError"
        assert record["detail"] == "detail"
        assert "ts" in record

    def test_appends_multiple_records(self, tmp_path):
        hook_runner._emit_error("h", "K1", "d1", tmp_path)
        hook_runner._emit_error("h", "K2", "d2", tmp_path)
        log = tmp_path / ".forge" / "hook-errors.log"
        lines = log.read_text().strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["kind"] == "K1"
        assert json.loads(lines[1])["kind"] == "K2"

    def test_detail_capped(self, tmp_path):
        long = "x" * 5000
        hook_runner._emit_error("h", "K", long, tmp_path)
        log = tmp_path / ".forge" / "hook-errors.log"
        record = json.loads(log.read_text())
        assert len(record["detail"]) == hook_runner._DETAIL_CAP

    def test_never_raises_on_unwritable_dir(self, tmp_path):
        # Point log dir at a path that can't be created (parent is a file)
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory")
        bad_cwd = blocker / "subdir"  # would need to create through a file
        # Should not raise:
        hook_runner._emit_error("h", "K", "d", bad_cwd)

    def test_rotates_when_log_exceeds_cap(self, tmp_path, monkeypatch):
        # T-146: hook-errors.log must stay bounded. With a tiny ceiling, the next
        # emit rolls the existing log to .1 and starts fresh — no unbounded growth.
        monkeypatch.setenv("FORGE_LOG_MAX_BYTES", "200")
        for i in range(60):  # well past 200 bytes of JSONL records
            hook_runner._emit_error("h", "K", f"d{i}", tmp_path)
        log = tmp_path / ".forge" / "hook-errors.log"
        backup = tmp_path / ".forge" / "hook-errors.log.1"
        assert log.exists()
        assert log.stat().st_size < 5000  # bounded, not the full 60-record history
        assert backup.exists()  # rotated history preserved, not deleted

    def test_no_rotation_when_disabled(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FORGE_LOG_MAX_BYTES", "0")  # disable rotation
        for i in range(30):
            hook_runner._emit_error("h", "K", f"d{i}", tmp_path)
        log = tmp_path / ".forge" / "hook-errors.log"
        assert len(log.read_text().strip().splitlines()) == 30  # all kept, no rotation
        assert not (tmp_path / ".forge" / "hook-errors.log.1").exists()


# ---------- run_hook behavior (subprocess) ----------

def _run_in_subprocess(
    script_body: str,
    *,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> tuple[int, str, str]:
    """Run a script via subprocess so SystemExit propagates as the process exit code.

    Builds the script by concatenating strings directly (no textwrap.dedent) so
    that ``script_body`` — which may contain its own embedded newlines starting
    at column 0 — never introduces inconsistent indentation in the assembled file.
    """
    import subprocess
    import tempfile

    preamble = (
        "import sys\n"
        f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
        "from _hook_runner import run_hook\n"
    )
    full = preamble + script_body + "\n"

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(full)
        path = f.name
    try:
        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            env=proc_env,
            cwd=str(cwd) if cwd is not None else None,
            timeout=60,
        )
        return result.returncode, result.stdout, result.stderr
    finally:
        os.unlink(path)


class TestCleanReturn:
    def test_returns_zero_when_fn_returns(self, tmp_path):
        rc, out, _ = _run_in_subprocess(
            "def main(): print('hello')\n"
            "run_hook(main, hook_name='session-start')",
            env={"CLAUDE_PROJECT_DIR": str(tmp_path)},
        )
        assert rc == 0
        assert "hello" in out

    def test_propagates_explicit_exit_zero(self, tmp_path):
        rc, _, _ = _run_in_subprocess(
            "def main():\n"
            "    import sys\n"
            "    sys.exit(0)\n"
            "run_hook(main, hook_name='session-start')",
            env={"CLAUDE_PROJECT_DIR": str(tmp_path)},
        )
        assert rc == 0


class TestExceptionIsolation:
    def test_uncaught_exception_exits_zero(self, tmp_path):
        rc, _, _ = _run_in_subprocess(
            "def main(): raise RuntimeError('boom')\n"
            "run_hook(main, hook_name='session-start')",
            env={"CLAUDE_PROJECT_DIR": str(tmp_path)},
        )
        assert rc == 0
        log = tmp_path / ".forge" / "hook-errors.log"
        assert log.exists()
        record = json.loads(log.read_text().strip().splitlines()[-1])
        assert record["kind"] == "RuntimeError"
        assert "boom" in record["detail"]

    def test_keyboard_interrupt_isolated(self, tmp_path):
        rc, _, _ = _run_in_subprocess(
            "def main(): raise KeyboardInterrupt()\n"
            "run_hook(main, hook_name='session-start')",
            env={"CLAUDE_PROJECT_DIR": str(tmp_path)},
        )
        assert rc == 0


class TestTimeout:
    def test_timeout_kills_hook(self, tmp_path):
        rc, _, _ = _run_in_subprocess(
            "import time\n"
            "def main(): time.sleep(5)\n"
            "run_hook(main, hook_name='prompt-submit')",  # 1s default timeout
            env={"CLAUDE_PROJECT_DIR": str(tmp_path)},
        )
        assert rc == 0
        log = tmp_path / ".forge" / "hook-errors.log"
        record = json.loads(log.read_text().strip().splitlines()[-1])
        assert record["kind"] == "timeout"
        assert "1.0s" in record["detail"] or "1s" in record["detail"]

    def test_env_override_can_extend_timeout(self, tmp_path):
        # Hook sleeps 0.1s; timeout extended to 0.3s; should finish cleanly.
        rc, _, _ = _run_in_subprocess(
            "import time\n"
            "def main():\n"
            "    time.sleep(0.1)\n"
            "    print('ok')\n"
            "run_hook(main, hook_name='prompt-submit')",
            env={
                "CLAUDE_PROJECT_DIR": str(tmp_path),
                "FORGE_HOOK_TIMEOUT_PROMPT_SUBMIT": "0.3",
            },
        )
        assert rc == 0


class TestBlockingSemantics:
    def test_blocking_hook_propagates_exit_2(self, tmp_path):
        rc, _, _ = _run_in_subprocess(
            "def main():\n"
            "    import sys\n"
            "    sys.exit(2)\n"
            "run_hook(main, hook_name='pre-tool-write')",
            env={"CLAUDE_PROJECT_DIR": str(tmp_path)},
        )
        assert rc == 2

    def test_nonblocking_hook_suppresses_exit_2(self, tmp_path):
        rc, _, _ = _run_in_subprocess(
            "def main():\n"
            "    import sys\n"
            "    sys.exit(2)\n"
            "run_hook(main, hook_name='post-tool-use')",
            env={"CLAUDE_PROJECT_DIR": str(tmp_path)},
        )
        assert rc == 0
        log = tmp_path / ".forge" / "hook-errors.log"
        record = json.loads(log.read_text().strip().splitlines()[-1])
        assert record["kind"] == "unexpected-exit-2"

    def test_blocking_hook_with_exception_does_not_block(self, tmp_path):
        # Critical: a blocking hook that CRASHES must not propagate exit 2.
        # Only an explicit sys.exit(2) blocks.
        rc, _, _ = _run_in_subprocess(
            "def main(): raise RuntimeError('boom')\n"
            "run_hook(main, hook_name='pre-tool-write')",
            env={"CLAUDE_PROJECT_DIR": str(tmp_path)},
        )
        assert rc == 0

    def test_blocking_hook_with_timeout_does_not_block(self, tmp_path):
        # Same rule for timeouts: a blocking hook timing out should NOT
        # propagate exit 2. Slow hook != deliberate block.
        rc, _, _ = _run_in_subprocess(
            "import time\n"
            "def main(): time.sleep(3)\n"
            "run_hook(main, hook_name='pre-tool-write')",
            env={"CLAUDE_PROJECT_DIR": str(tmp_path)},
        )
        assert rc == 0

    def test_explicit_blocking_override(self, tmp_path):
        rc, _, _ = _run_in_subprocess(
            "def main():\n"
            "    import sys\n"
            "    sys.exit(2)\n"
            "run_hook(main, hook_name='session-start', blocking=True)",
            env={"CLAUDE_PROJECT_DIR": str(tmp_path)},
        )
        assert rc == 2


class TestSignalCleanup:
    def test_setitimer_disarmed_after_run(self, tmp_path, monkeypatch):
        # In-process test: run_hook should clear the timer in its finally block.
        # If it doesn't, a subsequent SIGALRM would fire later.
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

        def quick_hook():
            sys.exit(0)

        try:
            hook_runner.run_hook(quick_hook, hook_name="session-start", timeout=0.5)
        except SystemExit:
            pass

        # itimer should be disarmed (returns (0.0, 0.0) when not active)
        remaining, _ = signal.setitimer(signal.ITIMER_REAL, 0)
        assert remaining == 0


class TestNoSigalrmPlatform:
    """T-155 / REQ-F-054 — Windows: `signal.setitimer`/`SIGALRM` do not exist there, so
    run_hook must degrade to *no wall-clock timeout* rather than crash. Simulated on POSIX
    by removing those attrs at runtime before the call."""

    def test_runs_without_setitimer(self, tmp_path):
        rc, out, _ = _run_in_subprocess(
            "import signal\n"
            "for a in ('setitimer', 'getitimer', 'SIGALRM', 'ITIMER_REAL'):\n"
            "    if hasattr(signal, a):\n"
            "        delattr(signal, a)\n"
            "def main(): print('ran')\n"
            "run_hook(main, hook_name='session-start')",
            env={"CLAUDE_PROJECT_DIR": str(tmp_path)},
        )
        assert rc == 0
        assert "ran" in out

    def test_blocking_exit2_without_setitimer(self, tmp_path):
        rc, _, _ = _run_in_subprocess(
            "import signal, sys\n"
            "for a in ('setitimer', 'getitimer', 'SIGALRM', 'ITIMER_REAL'):\n"
            "    if hasattr(signal, a):\n"
            "        delattr(signal, a)\n"
            "def main(): sys.exit(2)\n"
            "run_hook(main, hook_name='pre-tool-write')",
            env={"CLAUDE_PROJECT_DIR": str(tmp_path)},
        )
        assert rc == 2  # blocking semantics intact without the timer

    def test_exception_isolated_without_setitimer(self, tmp_path):
        rc, _, _ = _run_in_subprocess(
            "import signal\n"
            "for a in ('setitimer', 'getitimer', 'SIGALRM', 'ITIMER_REAL'):\n"
            "    if hasattr(signal, a):\n"
            "        delattr(signal, a)\n"
            "def main(): raise RuntimeError('boom')\n"
            "run_hook(main, hook_name='session-start')",
            env={"CLAUDE_PROJECT_DIR": str(tmp_path)},
        )
        assert rc == 0  # uncaught exception still isolated (exit 0)