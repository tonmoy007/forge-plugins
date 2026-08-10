"""T-228 / REQ-DK-001: scripts/check_docker_readiness.py, the advisory Docker
hygiene check.

Covers AC-DK-001: unpinned/no-healthcheck/no-user/no-dockerignore fixture -> WARN:
lines, exit 0; clean Dockerfile -> pass line, exit 0; no-Docker dir -> no-op, exit
0; unreadable files don't crash.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

import check_docker_readiness as cdr  # noqa: E402


UNPINNED_DOCKERFILE = """\
FROM python:latest
COPY . /app
CMD ["python", "app.py"]
"""

CLEAN_DOCKERFILE = """\
FROM python:3.12.4-slim@sha256:abc123 AS builder
COPY . /app

FROM builder AS final
HEALTHCHECK CMD curl -f http://localhost/ || exit 1
USER appuser
CMD ["python", "app.py"]
"""


def test_no_docker_artifacts_no_op(tmp_path: Path) -> None:
    findings = cdr.check_docker_readiness(tmp_path)
    assert findings.has_artifacts is False
    assert findings.warnings == []


def test_unpinned_no_healthcheck_no_user_no_dockerignore_all_flagged(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text(UNPINNED_DOCKERFILE)
    findings = cdr.check_docker_readiness(tmp_path)
    assert findings.has_artifacts is True
    joined = " ".join(findings.warnings).lower()
    assert "latest" in joined or "pin" in joined
    assert "healthcheck" in joined
    assert "user" in joined
    assert "dockerignore" in joined


def test_clean_dockerfile_no_warnings(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text(CLEAN_DOCKERFILE)
    (tmp_path / ".dockerignore").write_text(".git\n__pycache__\n")
    findings = cdr.check_docker_readiness(tmp_path)
    assert findings.has_artifacts is True
    assert findings.warnings == []


def test_multi_stage_from_referencing_earlier_stage_not_flagged(tmp_path: Path) -> None:
    """`FROM builder AS final` refers to an earlier build stage, not a registry
    image -- must not be flagged as unpinned."""
    (tmp_path / "Dockerfile").write_text(CLEAN_DOCKERFILE)
    (tmp_path / ".dockerignore").write_text("x\n")
    findings = cdr.check_docker_readiness(tmp_path)
    assert not any("builder" in w.lower() and "pin" in w.lower() for w in findings.warnings)


def test_digest_pinned_from_not_flagged(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text(
        "FROM python@sha256:abc123def456\nHEALTHCHECK CMD true\nUSER appuser\n"
    )
    (tmp_path / ".dockerignore").write_text("x\n")
    findings = cdr.check_docker_readiness(tmp_path)
    assert findings.warnings == []


def test_root_user_directive_flagged(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text(
        "FROM python:3.12.4\nHEALTHCHECK CMD true\nUSER root\n"
    )
    (tmp_path / ".dockerignore").write_text("x\n")
    findings = cdr.check_docker_readiness(tmp_path)
    assert any("user" in w.lower() for w in findings.warnings)


def test_compose_parses_and_has_services(tmp_path: Path) -> None:
    (tmp_path / "docker-compose.yml").write_text("services:\n  web:\n    image: nginx\n")
    findings = cdr.check_docker_readiness(tmp_path)
    assert findings.has_artifacts is True
    assert not any("compose" in w.lower() for w in findings.warnings)


def test_compose_missing_services_key_flagged(tmp_path: Path) -> None:
    (tmp_path / "docker-compose.yml").write_text("version: '3'\n")
    findings = cdr.check_docker_readiness(tmp_path)
    assert any("services" in w.lower() or "compose" in w.lower() for w in findings.warnings)


def test_compose_unparseable_flagged_not_crash(tmp_path: Path) -> None:
    (tmp_path / "docker-compose.yml").write_text("not: valid: yaml: at: all: [\n")
    findings = cdr.check_docker_readiness(tmp_path)  # must not raise
    assert findings.has_artifacts is True


def test_unreadable_dockerfile_does_not_crash(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "Dockerfile").write_text(UNPINNED_DOCKERFILE)
    real_open = open

    def _boom(path, *a, **k):
        if "Dockerfile" in str(path):
            raise OSError("permission denied")
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", _boom)
    findings = cdr.check_docker_readiness(tmp_path)  # must not raise
    assert findings.has_artifacts is True


def test_main_always_exits_zero_even_with_findings(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text(UNPINNED_DOCKERFILE)
    rc = cdr.main(["--cwd", str(tmp_path)])
    assert rc == 0


def test_main_exits_zero_no_docker(tmp_path: Path) -> None:
    rc = cdr.main(["--cwd", str(tmp_path)])
    assert rc == 0


def test_main_exits_zero_clean(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text(CLEAN_DOCKERFILE)
    (tmp_path / ".dockerignore").write_text("x\n")
    rc = cdr.main(["--cwd", str(tmp_path)])
    assert rc == 0
