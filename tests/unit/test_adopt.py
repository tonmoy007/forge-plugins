"""Tests for scripts/adopt.py (v0.2 P2 — T-150, REQ-F-038..043, closes EF-014).

`/forge:adopt` onboards an EXISTING codebase: detect the type, sample a bounded set
of files, fan out extractors to infer SRS + architecture drafts (marked INFERRED,
with confidence + provenance), seed state.md, and resume the normal pipeline. It is
read-only to user source (writes only under pipeline/ and .forge/) and supports
--dry-run. A fake dispatch_fn is injected — no real claude.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

_root = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("adopt", _root / "scripts" / "adopt.py")
_ad = importlib.util.module_from_spec(_spec)
sys.modules["adopt"] = _ad
_spec.loader.exec_module(_ad)

PLUGIN_DIR = _root


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def main():\n    return 42\n")
    (tmp_path / "README.md").write_text("# My API\nA small FastAPI service.\n")
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text("x")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main")
    return tmp_path


def _aspect_dispatch(prompt, **kw):
    aspect = "requirements" if "requirements" in prompt else "architecture"
    payload = {"aspect": aspect, "confidence": 0.6,
               "content": f"- inferred {aspect} item", "derived_from": ["README.md"]}
    return SimpleNamespace(status="ok", result=json.dumps(payload), cost_usd=0.01,
                           raw={"is_error": False})


# --- sampling ---------------------------------------------------------------

def test_sample_files_bounded_and_excludes_meta(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    sampled, skipped = _ad.sample_files(tmp_path, max_files=5)
    assert len(sampled) <= 5
    joined = " ".join(str(p) for p in sampled)
    assert "node_modules" not in joined and ".git" not in joined
    # README/manifest are prioritized into the sample
    names = {Path(p).name for p in sampled}
    assert "README.md" in names or "requirements.txt" in names


def test_sample_files_deterministic(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    assert _ad.sample_files(tmp_path, max_files=10)[0] == _ad.sample_files(tmp_path, max_files=10)[0]


# --- adopt e2e --------------------------------------------------------------

def test_adopt_writes_inferred_artifacts(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    summary = _ad.adopt(str(tmp_path), dispatch_fn=_aspect_dispatch, plugin_dir=PLUGIN_DIR)
    srs = (tmp_path / "pipeline" / "01-srs" / "srs.md").read_text()
    arch = (tmp_path / "pipeline" / "03-architecture" / "architecture.md").read_text()
    state = (tmp_path / "pipeline" / "state.md").read_text()
    assert "INFERRED" in srs and "Derived from" in srs
    assert "INFERRED" in arch
    assert "project_type:" in state
    assert summary["project_type"] in ("api", "unknown", "fullstack", "library", "script")


def test_adopt_dry_run_writes_nothing(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    summary = _ad.adopt(str(tmp_path), dry_run=True, dispatch_fn=_aspect_dispatch, plugin_dir=PLUGIN_DIR)
    assert not (tmp_path / "pipeline").exists()
    assert summary["dry_run"] is True
    assert summary["would_write"]  # the plan is reported


def test_adopt_is_read_only_to_user_source(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    _ad.adopt(str(tmp_path), dispatch_fn=_aspect_dispatch, plugin_dir=PLUGIN_DIR)
    # every pre-existing file is byte-identical (no user source touched)
    for p, content in before.items():
        assert p.read_bytes() == content
    # everything newly created lives under pipeline/ or .forge/
    for p in tmp_path.rglob("*"):
        if p.is_file() and p not in before:
            rel = p.relative_to(tmp_path)
            assert rel.parts[0] in ("pipeline", ".forge")


def test_adopt_refuses_existing_pipeline(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    (tmp_path / "pipeline").mkdir()
    (tmp_path / "pipeline" / "state.md").write_text("---\nschema_version: 1\n---\n")
    summary = _ad.adopt(str(tmp_path), dispatch_fn=_aspect_dispatch, plugin_dir=PLUGIN_DIR)
    assert summary["status"] == "refused"


def test_adopt_tolerates_dropped_aspect(tmp_path: Path) -> None:
    _make_repo(tmp_path)

    def disp(prompt, **kw):
        if "architecture" in prompt:
            return SimpleNamespace(status="ok", result="not json", cost_usd=0.0, raw={})
        return _aspect_dispatch(prompt, **kw)

    summary = _ad.adopt(str(tmp_path), dispatch_fn=disp, plugin_dir=PLUGIN_DIR)
    assert (tmp_path / "pipeline" / "01-srs" / "srs.md").exists()  # requirements still written
    assert "architecture" in [a.lower() for a in summary["dropped_aspects"]]
