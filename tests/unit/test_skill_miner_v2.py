"""Tests for scripts/skill_miner_v2.py (T-178 — REQ-SM-003, REQ-SM-004).

The v2 miner replaces the n-gram tool-name miner (mine-skills.py). It operates
over the SEMANTIC episodes produced by _trace_semantics (verb sequences), finds
ordered verb fragments recurring across >=k DISTINCT episodes, anti-unifies
their instances, and promotes a fragment to a candidate ONLY IF:
  (a) anti-unification yields a coherent parameterized skeleton (REQ-SM-003),
  (b) the source episodes are >=k distinct, AND
  (c) those episodes ended in SUCCESS (REQ-SM-004).

Acceptance (AC-SM-001/003/004):
  - a parameterized candidate from 3 distinct SUCCESSFUL episodes w/ differing
    names,
  - NOTHING from a control stream where Bash/Read/Write merely co-occur with no
    coherent shape,
  - a motif recurring 3x but in all-FAILED episodes is NOT promoted.

Stdlib only; deterministic; never raises.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_scripts = Path(__file__).resolve().parent.parent.parent / "scripts"

_ts_path = _scripts / "_trace_semantics.py"
_ts_spec = importlib.util.spec_from_file_location("_trace_semantics", _ts_path)
assert _ts_spec and _ts_spec.loader
ts_mod = importlib.util.module_from_spec(_ts_spec)
sys.modules["_trace_semantics"] = ts_mod
_ts_spec.loader.exec_module(ts_mod)

_au_path = _scripts / "_antiunify.py"
_au_spec = importlib.util.spec_from_file_location("_antiunify", _au_path)
assert _au_spec and _au_spec.loader
au_mod = importlib.util.module_from_spec(_au_spec)
sys.modules["_antiunify"] = au_mod
_au_spec.loader.exec_module(au_mod)

_sm_path = _scripts / "skill_miner_v2.py"
_sm_spec = importlib.util.spec_from_file_location("skill_miner_v2", _sm_path)
assert _sm_spec and _sm_spec.loader
sm_mod = importlib.util.module_from_spec(_sm_spec)
sys.modules["skill_miner_v2"] = sm_mod
_sm_spec.loader.exec_module(sm_mod)


# ---------------------------------------------------------------------------
# Helpers — build raw session-log records, run them through the real pipeline.
# ---------------------------------------------------------------------------


def _call(
    tool: str,
    file: str = "",
    success: bool = True,
    session: str = "s1",
    command: str = "",
) -> dict:
    rec: dict = {
        "ts": "2026-06-16T12:00:00Z",
        "session": session,
        "tool": tool,
        "file": file,
        "success": success,
        "stage": 6,
    }
    if command:
        rec["command"] = command
    return rec


def _fix_episode(src: str, test_cmd: str, test_file: str, session: str) -> list[dict]:
    """A successful failure->fix->regression episode (ends green)."""
    return [
        _call("Bash", success=False, session=session, command=test_cmd),
        _call("Read", file=src, session=session),
        _call("Edit", file=src, session=session),
        _call("Bash", success=True, session=session, command=test_cmd),
        _call("Write", file=test_file, session=session),
    ]


def _failed_episode(src: str, test_cmd: str, session: str) -> list[dict]:
    """A failure->patch episode that never goes green (incomplete / failed)."""
    return [
        _call("Bash", success=False, session=session, command=test_cmd),
        _call("Read", file=src, session=session),
        _call("Edit", file=src, session=session),
        _call("Bash", success=False, session=session, command=test_cmd),
    ]


def _episodes(records: list[dict]):
    return ts_mod.segment(ts_mod.enrich(records))


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_no_episodes_yields_no_candidates() -> None:
    assert sm_mod.mine_candidates([]) == []


def test_garbage_never_raises() -> None:
    assert sm_mod.mine_candidates(None) == []  # type: ignore[arg-type]


def test_single_episode_below_k_not_promoted() -> None:
    eps = _episodes(_fix_episode("src/a.py", "pytest a", "tests/test_a.py", "s1"))
    assert sm_mod.mine_candidates(eps) == []


# ---------------------------------------------------------------------------
# AC-SM-001/003 — a parameterized candidate from 3 distinct SUCCESS episodes
# ---------------------------------------------------------------------------


def test_three_distinct_successful_episodes_promote_one_candidate() -> None:
    records = (
        _fix_episode("src/a.py", "pytest a", "tests/test_a.py", "s1")
        + _fix_episode("src/b.py", "pytest b", "tests/test_b.py", "s2")
        + _fix_episode("src/c.py", "pytest c", "tests/test_c.py", "s3")
    )
    candidates = sm_mod.mine_candidates(_episodes(records))
    assert len(candidates) == 1
    cand = candidates[0]
    # the recurring failure->fix->regression shape
    assert [s.verb for s in cand.skeleton.steps] == [
        "run-tests",
        "inspect",
        "patch",
        "run-tests",
        "add-regression-test",
    ]
    # parameterized over the differing names
    assert len(cand.skeleton.parameters) >= 1
    assert cand.support >= sm_mod.MIN_DISTINCT_EPISODES


def test_candidate_records_distinct_episode_support() -> None:
    records = (
        _fix_episode("src/a.py", "pytest a", "tests/test_a.py", "s1")
        + _fix_episode("src/b.py", "pytest b", "tests/test_b.py", "s2")
        + _fix_episode("src/c.py", "pytest c", "tests/test_c.py", "s3")
    )
    candidates = sm_mod.mine_candidates(_episodes(records))
    assert candidates[0].support == 3


# ---------------------------------------------------------------------------
# AC-SM-001 — NOTHING from a control stream with no coherent shape
# ---------------------------------------------------------------------------


def test_control_stream_no_coherent_shape_yields_nothing() -> None:
    """Bash/Read/Write merely co-occur, in shuffled orders, no failure->fix
    shape, never reaching a coherent repeated procedure. Must emit nothing."""
    records = (
        [
            _call("Bash", command="ls", session="c1"),
            _call("Read", file="notes.txt", session="c1"),
            _call("Write", file="out.txt", session="c1"),
        ]
        + [
            _call("Read", file="a.txt", session="c2"),
            _call("Write", file="b.txt", session="c2"),
            _call("Bash", command="echo hi", session="c2"),
        ]
        + [
            _call("Write", file="z.txt", session="c3"),
            _call("Bash", command="pwd", session="c3"),
            _call("Read", file="y.txt", session="c3"),
        ]
    )
    candidates = sm_mod.mine_candidates(_episodes(records))
    assert candidates == []


# ---------------------------------------------------------------------------
# AC-SM-004 — a motif recurring 3x but in all-FAILED episodes is NOT promoted
# ---------------------------------------------------------------------------


def test_failed_episodes_are_not_promoted() -> None:
    records = (
        _failed_episode("src/a.py", "pytest a", "s1")
        + _failed_episode("src/b.py", "pytest b", "s2")
        + _failed_episode("src/c.py", "pytest c", "s3")
    )
    eps = _episodes(records)
    # sanity: the motif really does recur 3x (same verb shape, distinct episodes)
    assert len(eps) >= 3
    candidates = sm_mod.mine_candidates(eps)
    assert candidates == []


def test_mixed_two_success_one_fail_below_k_not_promoted() -> None:
    """Only 2 successful episodes share the shape (3rd failed) -> below k=3
    distinct SUCCESSFUL episodes -> not promoted."""
    records = (
        _fix_episode("src/a.py", "pytest a", "tests/test_a.py", "s1")
        + _fix_episode("src/b.py", "pytest b", "tests/test_b.py", "s2")
        + _failed_episode("src/c.py", "pytest c", "s3")
    )
    candidates = sm_mod.mine_candidates(_episodes(records))
    assert candidates == []


def test_default_k_is_three() -> None:
    assert sm_mod.MIN_DISTINCT_EPISODES == 3


# ---------------------------------------------------------------------------
# T-179 (REQ-SM-005, REQ-NF-017, AC-SM-005) — LLM induction with graceful
# degradation. The induction step turns each deterministic Candidate into an
# InducedSkill: a NAMED, parameterized procedure with a one-line third-person
# description and citations to the source trace lines. ONE cheap-model (haiku)
# background dispatch via the structured-output (--json-schema) path, cost- and
# capability-gated. When background/LLM is unavailable OR FORGE_NO_BACKGROUND=1
# OR the dispatch fails, the deterministic anti-unified skeleton (REQ-SM-003) is
# the proposal — never a hard failure, never raises.
#
# Tests MUST NOT touch the network: the dispatch boundary is injected
# (dispatch_fn) and the capability/kill-switch gate is parameterised so neither
# path shells out to `claude`.
# ---------------------------------------------------------------------------


def _three_episode_candidates():
    """A single coherent candidate from 3 distinct successful fix episodes."""
    records = (
        _fix_episode("src/a.py", "pytest a", "tests/test_a.py", "s1")
        + _fix_episode("src/b.py", "pytest b", "tests/test_b.py", "s2")
        + _fix_episode("src/c.py", "pytest c", "tests/test_c.py", "s3")
    )
    cands = sm_mod.mine_candidates(_episodes(records))
    assert len(cands) == 1
    return cands


class _Dispatched:
    """A stand-in DispatchResult — duck-typed like _background_agent.DispatchResult."""

    def __init__(self, status: str, result: str = "", reason: str = "", cost_usd=None):
        self.status = status
        self.result = result
        self.reason = reason
        self.cost_usd = cost_usd
        self.session_id = "sess-x"
        self.raw = None


def test_induce_empty_candidates_is_empty() -> None:
    assert sm_mod.induce([], forge_dir=Path("/nonexistent"), available=True) == []


def test_induce_garbage_never_raises() -> None:
    # None / wrong types degrade to [] rather than raising (REQ-NF-017).
    assert sm_mod.induce(None, forge_dir=None, available=True) == []  # type: ignore[arg-type]


def test_induce_uses_llm_procedure_when_dispatch_available(tmp_path) -> None:
    cands = _three_episode_candidates()
    captured: dict = {}

    def fake_dispatch(prompt, **kwargs):
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        import json as _json

        payload = {
            "name": "red-green-regression-fix",
            "description": (
                "Drives a failing test to green by inspecting, patching the source, "
                "and adding a regression test."
            ),
            "procedure": [
                "Run the failing test to confirm red",
                "Inspect the implicated source file",
                "Patch the source file",
                "Re-run the test to confirm green",
                "Add a regression test",
            ],
            "citations": ["src/a.py:run-tests", "src/b.py:patch"],
        }
        return _Dispatched("ok", result=_json.dumps(payload))

    induced = sm_mod.induce(
        cands,
        forge_dir=tmp_path,
        available=True,
        dispatch_fn=fake_dispatch,
    )
    assert len(induced) == 1
    skill = induced[0]
    assert skill.source == "llm"
    assert skill.name == "red-green-regression-fix"
    assert "regression" in skill.description.lower()
    assert len(skill.procedure) == 5
    assert skill.citations  # non-empty provenance
    # the candidate's skeleton/motif is preserved as provenance
    assert skill.candidate is cands[0]

    # The dispatch went through the structured-output, cheap-model, gated path.
    kw = captured["kwargs"]
    assert kw.get("output_schema")  # --json-schema path
    assert kw.get("model") == sm_mod.INDUCTION_MODEL
    assert kw.get("feature") == "skill_induction"
    assert kw.get("max_budget_usd") is not None
    assert kw.get("forge_dir") == tmp_path


def test_induce_falls_back_to_skeleton_when_background_off() -> None:
    cands = _three_episode_candidates()

    def boom(*_a, **_k):  # must NEVER be called when capability is absent
        raise AssertionError("dispatch must not be called when background is off")

    induced = sm_mod.induce(
        cands,
        forge_dir=Path("/nonexistent"),
        available=False,
        dispatch_fn=boom,
    )
    assert len(induced) == 1
    skill = induced[0]
    assert skill.source == "deterministic"
    # the deterministic proposal still carries a name, third-person description,
    # a procedure derived from the skeleton verbs, and citations — never empty.
    assert skill.name
    assert skill.description
    assert skill.procedure == [s.verb for s in cands[0].skeleton.steps]
    assert skill.citations
    assert skill.candidate is cands[0]


def test_induce_falls_back_when_dispatch_returns_non_ok(tmp_path) -> None:
    cands = _three_episode_candidates()

    def skipped(*_a, **_k):
        return _Dispatched("skipped", reason="daily cap reached")

    induced = sm_mod.induce(
        cands, forge_dir=tmp_path, available=True, dispatch_fn=skipped
    )
    assert len(induced) == 1
    assert induced[0].source == "deterministic"


def test_induce_falls_back_when_dispatch_returns_garbage_json(tmp_path) -> None:
    cands = _three_episode_candidates()

    def garbage(*_a, **_k):
        return _Dispatched("ok", result="not json at all {")

    induced = sm_mod.induce(
        cands, forge_dir=tmp_path, available=True, dispatch_fn=garbage
    )
    assert len(induced) == 1
    assert induced[0].source == "deterministic"


def test_induce_falls_back_when_dispatch_raises(tmp_path) -> None:
    cands = _three_episode_candidates()

    def raiser(*_a, **_k):
        raise RuntimeError("network exploded")

    # induce must absorb a raising dispatch and degrade — never propagate.
    induced = sm_mod.induce(
        cands, forge_dir=tmp_path, available=True, dispatch_fn=raiser
    )
    assert len(induced) == 1
    assert induced[0].source == "deterministic"


def test_induction_model_is_cheap() -> None:
    assert sm_mod.INDUCTION_MODEL == "haiku"


# ---------------------------------------------------------------------------
# T-180 (REQ-SM-006, AC-SM-005/006) — agentskills.io SKILL.md emission. Each
# promoted+induced candidate is rendered as .forge/proposed-skills/<slug>/SKILL.md
# in the standard format: YAML frontmatter (name + non-empty third-person
# description) + body sections When to Use / Procedure / Pitfalls / Verification
# / Provenance (with source-trace-line citations). Never emit an unnamed proposal.
# The render is deterministic and never raises; it reuses _state_lib._split_frontmatter
# for parse round-trips. Output is consumable by the EXISTING skill-approval flow
# (carries a `Pattern signature:` line), preserving approve/reject/blacklist.
# ---------------------------------------------------------------------------


def _one_induced_deterministic():
    """A single deterministic (background-off) InducedSkill from a real candidate."""
    cands = _three_episode_candidates()
    induced = sm_mod.induce(cands, forge_dir=Path("/nonexistent"), available=False)
    assert len(induced) == 1
    return induced[0]


def _one_induced_llm():
    """A single LLM-sourced InducedSkill with a clean name + description."""
    cands = _three_episode_candidates()

    def fake_dispatch(prompt, **kwargs):
        import json as _json

        payload = {
            "name": "red-green-regression-fix",
            "description": (
                "Drives a failing test to green by inspecting the implicated source, "
                "patching it, and adding a regression test. Use when a test is red."
            ),
            "procedure": [
                "Run the failing test to confirm red",
                "Inspect the implicated source file",
                "Patch the source file",
                "Re-run the test to confirm green",
                "Add a regression test",
            ],
            "citations": ["src/a.py:run-tests", "src/b.py:patch"],
        }
        return _Dispatched("ok", result=_json.dumps(payload))

    return sm_mod.induce(
        cands, forge_dir=Path("/tmp"), available=True, dispatch_fn=fake_dispatch
    )[0]


def _frontmatter_of(text: str) -> dict:
    """Parse the SKILL.md frontmatter the same way the repo does (_state_lib)."""
    sl_path = _scripts / "_state_lib.py"
    sl_spec = importlib.util.spec_from_file_location("_state_lib", sl_path)
    assert sl_spec and sl_spec.loader
    sl_mod = importlib.util.module_from_spec(sl_spec)
    sys.modules["_state_lib"] = sl_mod
    sl_spec.loader.exec_module(sl_mod)
    meta, _body = sl_mod._split_frontmatter(text)
    return meta


def test_render_skill_md_is_valid_agentskills_format() -> None:
    md = sm_mod.render_skill_md(_one_induced_llm())
    meta = _frontmatter_of(md)
    # Frontmatter: name + non-empty third-person description (AC-SM-005/006).
    assert meta.get("name") == "red-green-regression-fix"
    assert isinstance(meta.get("description"), str) and meta["description"].strip()
    # status: proposed is carried so the approval flow can strip it on install.
    assert meta.get("status") == "proposed"
    # Body sections per the agentskills.io standard.
    for section in (
        "## When to Use",
        "## Procedure",
        "## Pitfalls",
        "## Verification",
        "## Provenance",
    ):
        assert section in md, f"missing section: {section}"


def test_render_skill_md_carries_provenance_citations() -> None:
    md = sm_mod.render_skill_md(_one_induced_llm())
    # Source-trace-line citations appear under Provenance (REQ-SM-006).
    assert "src/a.py:run-tests" in md
    assert "src/b.py:patch" in md
    # A Pattern signature line keeps the existing approval/blacklist flow working.
    assert "Pattern signature:" in md


def test_render_skill_md_never_emits_unnamed_proposal() -> None:
    # A deterministic skeleton proposal still carries a real, non-empty name.
    md = sm_mod.render_skill_md(_one_induced_deterministic())
    meta = _frontmatter_of(md)
    assert isinstance(meta.get("name"), str) and meta["name"].strip()
    assert isinstance(meta.get("description"), str) and meta["description"].strip()


def test_render_skill_md_is_parseable_by_skill_approval(tmp_path) -> None:
    """The emitted SKILL.md must be consumable by the EXISTING skill-approval
    flow (REQ-NF-019: approval/blacklist preserved, not duplicated)."""
    sa_path = _scripts / "skill-approval.py"
    sa_spec = importlib.util.spec_from_file_location("skill_approval", sa_path)
    assert sa_spec and sa_spec.loader
    sa_mod = importlib.util.module_from_spec(sa_spec)
    sys.modules["skill_approval"] = sa_mod
    sa_spec.loader.exec_module(sa_mod)

    md = sm_mod.render_skill_md(_one_induced_llm())
    d = tmp_path / ".forge" / "proposed-skills" / "red-green-regression-fix"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(md, encoding="utf-8")

    proposal = sa_mod._parse_proposal(d / "SKILL.md")
    assert proposal is not None
    assert proposal.name == "red-green-regression-fix"
    assert proposal.signature  # non-empty signature for blacklist
    assert proposal.description.strip()


def test_render_skill_md_never_raises_on_garbage() -> None:
    # A malformed/None induced object degrades to a minimal valid proposal,
    # never raises (REQ-NF-016 hot-path discipline).
    md = sm_mod.render_skill_md(None)  # type: ignore[arg-type]
    assert isinstance(md, str)
    meta = _frontmatter_of(md)
    assert meta.get("name")


def test_render_skill_md_is_deterministic() -> None:
    skill = _one_induced_llm()
    assert sm_mod.render_skill_md(skill) == sm_mod.render_skill_md(skill)


# ---------------------------------------------------------------------------
# T-180 — write_proposals: persist induced skills to .forge/proposed-skills/<slug>/.
# Skips slugs that already exist (so user edits survive re-mining, like the v1
# path) and honors the blacklist + already-installed names. Never raises.
# ---------------------------------------------------------------------------


def test_write_proposals_writes_skill_md(tmp_path) -> None:
    induced = sm_mod.induce(
        _three_episode_candidates(), forge_dir=Path("/nonexistent"), available=False
    )
    written = sm_mod.write_proposals(induced, forge_dir=tmp_path / ".forge")
    assert len(written) == 1
    path = written[0]
    assert path.exists()
    assert path.name == "SKILL.md"
    assert path.parent.parent.name == "proposed-skills"
    assert "## Provenance" in path.read_text(encoding="utf-8")


def test_write_proposals_skips_existing_slug(tmp_path) -> None:
    induced = _one_induced_llm()
    forge_dir = tmp_path / ".forge"
    slug_dir = forge_dir / "proposed-skills" / "red-green-regression-fix"
    slug_dir.mkdir(parents=True)
    user_edited = slug_dir / "SKILL.md"
    user_edited.write_text("USER EDITED — do not clobber", encoding="utf-8")

    written = sm_mod.write_proposals([induced], forge_dir=forge_dir)
    assert written == []  # nothing written; user edit preserved
    assert user_edited.read_text(encoding="utf-8") == "USER EDITED — do not clobber"


def test_write_proposals_honors_blacklist(tmp_path) -> None:
    induced = _one_induced_llm()
    forge_dir = tmp_path / ".forge"
    forge_dir.mkdir(parents=True)
    # signature for this candidate == its motif signature
    sig = sm_mod._motif_signature(induced.candidate)
    (forge_dir / "skill-blacklist.txt").write_text(sig + "\n", encoding="utf-8")

    written = sm_mod.write_proposals([induced], forge_dir=forge_dir)
    assert written == []


def test_write_proposals_never_raises_on_garbage(tmp_path) -> None:
    assert sm_mod.write_proposals(None, forge_dir=tmp_path) == []  # type: ignore[arg-type]
    assert sm_mod.write_proposals([], forge_dir=tmp_path) == []
