#!/bin/bash
# run_all.sh — run the full Validator Partition Recovery Assessment suite
# end to end: excerpt extraction (when a manifest and a pinned checkout
# are available), scenario-schema validation, simulator run, drill checks
# (when a drill script is provided), digest computation, and a full
# SHA-256 listing (all 64 hex chars) of every deterministic output file.
#
# Idempotent: outputs are deterministic (no timestamps, no absolute
# paths, no measured timings in outputs/derived/run-summary.json), so a
# second run produces byte-identical outputs and digests.
#
# Exit codes:
#   0 — every step passed. A not-yet-implemented simulator stub is
#       recorded, not fatal (see below).
#   1 — a step failed.
#   2 — src/partition_sim.py is missing.
#
# Simulator stub: src/partition_sim.py exits 3 with NotImplementedError
# until the harness builder implements it. run_all.sh records that as
# simulator status "not_implemented" in outputs/derived/run-summary.json,
# prints a clear warning, and continues with the remaining steps, so the
# rest of the suite stays verifiable while the simulator is a stub. Once
# implemented, a simulator failure is fatal (exit 1). A missing
# simulator file is always fatal (exit 2).
#
# Excerpt extraction is skipped (recorded, not fatal) when no manifest
# exists yet, or when the pinned checkout is not available in this
# environment (e.g. CI): the shipped excerpts stay covered by
# SHA256SUMS verification instead.
set -u
PACK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PACK_ROOT" || exit 1
PINNED_COMMIT="0085a1ff885d6a446369cf73a4430f75af22be55"
PINNED_CHECKOUT="${PINNED_CHECKOUT:-$HOME/workspace/postfiatd-pin-0085a1f}"
mkdir -p outputs/derived fixtures/source-excerpts
export PINNED_CHECKOUT

OVERALL=0
EXTRACT_STATUS="skipped: no excerpts manifest"
SCENARIOS_STATUS="pass"
SIM_STATUS="not_run"
DRILL_STATUS="skipped: no drill script"

echo "=== run_all.sh ==="
echo "pack: $PACK_ROOT"
echo "pinned commit: $PINNED_COMMIT"

# --- step 1: extract excerpts -------------------------------------------
echo "--- step 1: extract excerpts ---"
if [ -f fixtures/excerpts-manifest.json ]; then
  if [ -d "$PINNED_CHECKOUT" ]; then
    if python3 scripts/extract_excerpts.py; then
      EXTRACT_STATUS="pass"
    else
      echo "extract_excerpts.py FAILED"
      EXTRACT_STATUS="failed"
      OVERALL=1
    fi
  else
    EXTRACT_STATUS="skipped: no pinned checkout at PINNED_CHECKOUT"
    echo "extract skipped: no pinned checkout ($PINNED_CHECKOUT)"
  fi
else
  echo "extract skipped: no fixtures/excerpts-manifest.json yet"
fi

# --- step 2: validate scenario schema -----------------------------------
echo "--- step 2: validate scenarios ---"
if python3 - <<'EOF'
import json, sys
cfg = json.load(open("configs/scenarios.json"))
assert cfg.get("schema_version") == 1, "schema_version != 1"
assert cfg.get("pinned_commit") == "0085a1ff885d6a446369cf73a4430f75af22be55", "pinned_commit mismatch"
sc = cfg["scenarios"]
assert isinstance(sc, list) and len(sc) == 10, f"need 10 scenarios, got {len(sc)}"
ids = [s["id"] for s in sc]
assert ids == [f"S-{i:02d}" for i in range(1, 11)], f"ids must be S-01..S-10, got {ids}"
for s in sc:
    for f in ("id", "name", "topology", "partition", "duration_ledgers", "parameters", "expected_behavior"):
        assert f in s, f"{s['id']}: missing field {f}"
    assert isinstance(s["topology"], dict) and isinstance(s["topology"].get("validator_count"), int), f"{s['id']}: topology.validator_count must be int"
    assert isinstance(s["topology"].get("links"), list), f"{s['id']}: topology.links must be a list"
    assert isinstance(s["partition"], dict) and isinstance(s["partition"].get("sides"), list), f"{s['id']}: partition.sides must be a list"
    assert isinstance(s["duration_ledgers"], int) and s["duration_ledgers"] >= 0, f"{s['id']}: duration_ledgers must be a non-negative int"
    assert isinstance(s["parameters"], dict), f"{s['id']}: parameters must be an object"
    assert isinstance(s["expected_behavior"], str), f"{s['id']}: expected_behavior must be a string"
print("scenarios: 10 entries, ids S-01..S-10, schema OK")
EOF
then
  SCENARIOS_STATUS="pass"
else
  echo "scenario validation FAILED"
  SCENARIOS_STATUS="failed"
  OVERALL=1
fi

# --- step 3: simulator ---------------------------------------------------
echo "--- step 3: simulator ---"
if [ ! -f src/partition_sim.py ]; then
  echo "ERROR: src/partition_sim.py is missing — the harness builder must provide it."
  exit 2
fi
python3 src/partition_sim.py --all --seed 0 --out outputs/derived/scenario-results.json
SIM_RC=$?
if [ "$SIM_RC" -eq 0 ]; then
  SIM_STATUS="pass"
  echo "simulator: PASS"
elif [ "$SIM_RC" -eq 3 ]; then
  SIM_STATUS="not_implemented"
  echo "WARNING: simulator is a stub (NotImplementedError, exit 3) — recorded as not_implemented; harness builder must implement src/partition_sim.py."
else
  SIM_STATUS="failed"
  echo "simulator FAILED (exit $SIM_RC)"
  OVERALL=1
fi

# --- step 4: drill checks -------------------------------------------------
echo "--- step 4: drill checks ---"
if [ -f scripts/drill.py ]; then
  if python3 scripts/drill.py; then
    DRILL_STATUS="pass"
  else
    echo "drill.py FAILED"
    DRILL_STATUS="failed"
    OVERALL=1
  fi
else
  echo "drill skipped: no scripts/drill.py yet"
fi

# --- step 5: run summary (deterministic: no timestamps, no paths) -------
echo "--- step 5: run summary ---"
EXTRACT_STATUS="$EXTRACT_STATUS" SCENARIOS_STATUS="$SCENARIOS_STATUS" \
SIM_STATUS="$SIM_STATUS" DRILL_STATUS="$DRILL_STATUS" python3 - <<'EOF'
import json, os
summary = {
    "pack": "Validator Partition Recovery Assessment",
    "pinned_commit": "0085a1ff885d6a446369cf73a4430f75af22be55",
    "scenario_count": 10,
    "steps": {
        "extract_excerpts": os.environ["EXTRACT_STATUS"],
        "scenarios": os.environ["SCENARIOS_STATUS"],
        "simulator": os.environ["SIM_STATUS"],
        "drills": os.environ["DRILL_STATUS"],
    },
}
with open("outputs/derived/run-summary.json", "w") as fh:
    json.dump(summary, fh, indent=1)
    fh.write("\n")
print("wrote outputs/derived/run-summary.json")
EOF

# --- step 6: full SHA-256 listing of deterministic outputs --------------
echo "--- step 6: SHA-256 of deterministic outputs (full 64 hex chars) ---"
{
  echo "# run.log — deterministic output digests (no timestamps, no absolute paths)"
  echo "# step extract_excerpts: $EXTRACT_STATUS"
  echo "# step scenarios: $SCENARIOS_STATUS"
  echo "# step simulator: $SIM_STATUS"
  echo "# step drills: $DRILL_STATUS"
  find outputs -type f ! -name 'run.log' ! -name 'compare-results.json' \
    ! -name 'fresh-clone-*' | sort | xargs sha256sum
} > outputs/run.log
cat outputs/run.log

# --- step 7: digests -------------------------------------------------------
echo "--- step 7: digests ---"
bash scripts/make_sha256sums.sh || { echo "make_sha256sums.sh FAILED"; OVERALL=1; }
bash scripts/verify_digests.sh || { echo "verify_digests.sh FAILED"; OVERALL=1; }

echo "=== run_all.sh done ==="
echo "extract_excerpts: $EXTRACT_STATUS"
echo "scenarios: $SCENARIOS_STATUS"
echo "simulator: $SIM_STATUS"
echo "drills: $DRILL_STATUS"
if [ "$OVERALL" -ne 0 ]; then
  echo "run_all.sh: FAILED (see steps above)"
  exit 1
fi
if [ "$SIM_STATUS" = "not_implemented" ]; then
  echo "run_all.sh: OK (skeleton state — simulator not yet implemented)"
else
  echo "run_all.sh: ALL STEPS PASSED"
fi
exit 0
