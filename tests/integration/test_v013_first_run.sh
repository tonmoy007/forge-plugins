#!/usr/bin/env bash
# First-run round-trip integration test — Forge v0.1.3 (T-108 / REQ-TEST-001)
#
# Simulates a new user's complete first-day experience against the plugin repo:
#   doctor → init --dry-run → init → simulate Stage 1 gate failure →
#   why <gate-id> → force-advance (--reason required) → why <tag> →
#   uninstall --dry-run → uninstall --yes → idempotent re-run
#
# Done-when (AC-TEST-001a): exits 0 on a clean checkout.
# Regression guards (AC-TEST-001b): dry-run preview presence, gate fix-hint
# rendering, force-advance reason requirement, uninstall idempotency.
#
# Usage:  bash tests/integration/test_v013_first_run.sh [--verbose]
#         (run from the forge-plugin repo root)

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPTS="$PLUGIN_DIR/scripts"
VERBOSE="${1:-}"

pass()   { echo "  ✓ $*"; }
fail()   { echo "  ✗ $*" >&2; exit 1; }
header() { echo; echo "==> $*"; }
log()    { [ "$VERBOSE" = "--verbose" ] && echo "    $*" || true; }

# Run a command, capture combined output + exit code WITHOUT a masking pipe.
# Usage: run <outfile> <rcvar> -- cmd args...
run() {
  local out="$1" rcvar="$2"; shift 3  # drop out, rcvar, the literal --
  set +e
  "$@" >"$out" 2>&1
  local _rc=$?           # distinct name so it can't shadow the caller's var
  set -e
  printf -v "$rcvar" '%s' "$_rc"
}

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT
PROJ="$TMPDIR/proj"
mkdir -p "$PROJ"
OUT="$TMPDIR/out.txt"
rc=0

# ── 1. /forge:doctor (healthy environment) ───────────────────────────────────
header "/forge:doctor"
run "$OUT" rc -- python3 "$SCRIPTS/doctor.py" --cwd "$PROJ"
log "$(cat "$OUT")"
# Exit may be 0 (all pass) or 1 (a hard failure such as Claude Code not on PATH
# inside CI); either way it must produce a categorized report and never crash.
grep -qiE 'environment|plugin|project|global' "$OUT" \
  || fail "doctor did not emit a categorized report"
[ "$rc" -eq 0 ] || [ "$rc" -eq 1 ] \
  || fail "doctor crashed (exit $rc, expected 0 or 1)"
pass "doctor produced a categorized report (exit $rc)"

# ── 2. /forge:init --dry-run (REQ-UX-001) ────────────────────────────────────
header "/forge:init --dry-run"
run "$OUT" rc -- bash "$SCRIPTS/init-pipeline.sh" "$PROJ" --dry-run
[ "$rc" -eq 0 ] || fail "init --dry-run exited $rc"
grep -q "Re-run without --dry-run to apply." "$OUT" \
  || fail "dry-run preview missing the re-run hint line"
[ -z "$(ls -A "$PROJ")" ] \
  || fail "dry-run created files (it must not write anything)"
pass "dry-run previewed the plan and wrote nothing"

# ── 3. /forge:init (real, manifest mode — REQ-UX-002) ────────────────────────
header "/forge:init (manifest-only)"
run "$OUT" rc -- bash "$SCRIPTS/init-pipeline.sh" "$PROJ" --manifest-only
[ "$rc" -eq 0 ] || fail "init --manifest-only exited $rc"
python3 - "$OUT" <<'PY' || fail "manifest is not valid JSON / not populated"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["dry_run"] is False, d
assert len(d["created"]) >= 1, d
assert isinstance(d["skipped"], list), d
PY
[ -d "$PROJ/pipeline" ] || fail "pipeline/ not created by real init"
pass "init created the pipeline and emitted a valid manifest"

# ── 4. Simulate a Stage 1 gate failure (REQ-GATE-001/002) ────────────────────
header "Stage 1 gate failure rendering"
run "$OUT" rc -- python3 "$SCRIPTS/format-gate-result.py" --stage 1 --cwd "$PROJ"
log "$(cat "$OUT")"
grep -q "BLOCKERS" "$OUT"  || fail "gate output missing BLOCKERS section"
grep -q "G1-001"  "$OUT"   || fail "gate output missing the G1-001 criterion"
grep -qi "fix:"   "$OUT"   || fail "gate output missing per-criterion fix hint"
pass "gate failure rendered with blockers and fix hints"

# ── 5. /forge:why <gate-id> (REQ-GATE-004) ───────────────────────────────────
header "/forge:why G1-001"
run "$OUT" rc -- python3 "$SCRIPTS/why.py" G1-001 --cwd "$PROJ"
[ "$rc" -eq 0 ] || fail "why G1-001 exited $rc"
grep -q "G1-001" "$OUT" || fail "why G1-001 did not explain the criterion"
pass "why explained the gate criterion"

# Move to a stage that has gate criteria so force-advance has blockers to override.
python3 "$SCRIPTS/state-manager.py" set --field current_stage --value 1 \
  --cwd "$PROJ" >/dev/null

# ── 6. /forge:force-advance — --reason is mandatory (REQ-GATE-003) ───────────
header "/forge:force-advance requires --reason"
run "$OUT" rc -- python3 "$SCRIPTS/force-advance.py" --cwd "$PROJ"
[ "$rc" -ne 0 ] \
  || fail "force-advance succeeded without --reason (must be required)"
pass "force-advance refused to run without --reason (exit $rc)"

header "/forge:force-advance --reason '...'"
run "$OUT" rc -- python3 "$SCRIPTS/force-advance.py" \
  --reason "round-trip test: override the unmet SRS gate intentionally" \
  --cwd "$PROJ" --json
[ "$rc" -eq 0 ] || fail "force-advance with --reason exited $rc"
python3 - "$OUT" <<'PY' || fail "force-advance JSON malformed / lesson not recorded"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["advanced_from"] == 1 and d["advanced_to"] == 2, d
assert d["lesson_recorded"] is True, d
assert d["lesson_tag"] == "force-advance", d
assert d["blockers_overridden"], d
PY
pass "force-advance recorded a lesson and advanced the stage"

# ── 7. /forge:why <lesson-tag> reflects the override (REQ-GATE-004) ──────────
header "/forge:why force-advance"
run "$OUT" rc -- python3 "$SCRIPTS/why.py" force-advance --cwd "$PROJ"
[ "$rc" -eq 0 ] || fail "why force-advance exited $rc"
grep -q "round-trip test" "$OUT" \
  || fail "why did not surface the recorded force-advance reason"
pass "why surfaced the recorded force-advance lesson"

# ── 8. /forge:uninstall --dry-run (REQ-CLEAN-002) ────────────────────────────
header "/forge:uninstall --dry-run"
run "$OUT" rc -- python3 "$SCRIPTS/uninstall.py" --cwd "$PROJ" --dry-run
[ "$rc" -eq 0 ] || fail "uninstall --dry-run exited $rc"
[ -d "$PROJ/pipeline" ] || fail "dry-run removed pipeline/ (must not remove)"
[ -d "$PROJ/.forge" ]   || fail "dry-run removed .forge/ (must not remove)"
pass "uninstall dry-run previewed without removing anything"

# ── 9. /forge:uninstall --yes (REQ-CLEAN-001) ────────────────────────────────
header "/forge:uninstall --yes"
run "$OUT" rc -- python3 "$SCRIPTS/uninstall.py" --cwd "$PROJ" --yes
[ "$rc" -eq 0 ] || fail "uninstall --yes exited $rc"
[ ! -d "$PROJ/pipeline" ] || fail "uninstall did not remove pipeline/"
[ ! -d "$PROJ/.forge" ]   || fail "uninstall did not remove .forge/"
pass "uninstall removed project Forge state"

# ── 10. Idempotent re-run (REQ-CLEAN-003) ────────────────────────────────────
header "/forge:uninstall --yes (idempotent re-run)"
run "$OUT" rc -- python3 "$SCRIPTS/uninstall.py" --cwd "$PROJ" --yes
[ "$rc" -eq 0 ] || fail "second uninstall exited $rc (must be idempotent)"
grep -qi "nothing to remove" "$OUT" \
  || fail "idempotent re-run did not report 'Nothing to remove'"
pass "second uninstall was a clean no-op"

echo
echo "PASS — v0.1.3 first-run round-trip completed successfully"
