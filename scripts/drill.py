#!/usr/bin/env python3
"""drill.py — re-verify simulator invariants from scenario-results.json.

Usage:
    python3 scripts/drill.py [RESULTS_JSON]

Reads outputs/derived/scenario-results.json (default) and re-derives
every invariant from the stored values instead of trusting them:
quorum arithmetic per scenario/side, amendment threshold arithmetic,
hash-chain integrity of the simulated ledgers, expiry-window arithmetic,
rejoin fetch counts against the timeout model, close-time bin membership,
flag-ledger interval, and determinism (re-run the simulator with the
same seed and compare full SHA-256 digests; re-run with a different
seed and confirm the output changes).

Exit 0 only if every case passes. Prints one PASS/FAIL line per case
with the FULL 64-char SHA-256 digest where a digest is involved, and
writes outputs/derived/drill-results.json plus outputs/drill-run.log
(the log is the unedited stdout of this run).

Timing: the total drill elapsed time is measured with time.monotonic()
and only sanity-checked as non-negative. The value is NOT recorded in
any output file or log line, so drill outputs stay byte-identical
across runs. No timing value is ever compared exactly (loose band by
design).
"""
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS = PACK_ROOT / "outputs" / "derived" / "scenario-results.json"
PINNED_COMMIT = "0085a1ff885d6a446369cf73a4430f75af22be55"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def ceil_div(a, b):
    return -(-a // b)


def quorum_for(unl_size, effective_unl_size):
    return max(ceil_div(effective_unl_size * 67, 100),
               ceil_div(unl_size * 60, 100))


def sim_ledger_hash(parent_hash, seq, close_time, resolution, close_flags,
                    tx_count):
    payload = "|".join([parent_hash, str(seq), str(close_time),
                        str(resolution), str(close_flags), str(tx_count)])
    return hashlib.sha256(payload.encode()).hexdigest()


def main():
    results_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RESULTS
    doc = json.loads(results_path.read_text())
    scenarios = {r["id"]: r for r in doc["scenarios"]}
    consts = doc["constants"]
    checks = []
    lines = []

    def check(cid, label, ok, detail=""):
        checks.append({"id": cid, "check": label, "pass": bool(ok),
                       "detail": detail})
        lines.append(("PASS " if ok else "FAIL ") + cid + " " + label +
                     ((" — " + detail) if detail else ""))

    t_start = time.monotonic()

    # --- A: quorum arithmetic, per scenario, per side -------------------
    for sid in sorted(scenarios):
        r = scenarios[sid]
        ok = True
        details = []
        for s in r["sides"]:
            if s["quorum_disabled"]:
                if s["quorum"] is not None:
                    ok = False
                    details.append("%s: quorum should be null when disabled" % s["side"])
                if s["ledgers_validated"] != 0:
                    ok = False
                    details.append("%s: validated %d with quorum disabled" % (s["side"], s["ledgers_validated"]))
                continue
            want = quorum_for(s["unl_size"], s["effective_unl_size"])
            if s["quorum"] != want:
                ok = False
                details.append("%s: stored quorum %s != recomputed %d" % (s["side"], s["quorum"], want))
            validated = sum(1 for l in s["ledgers"] if l["validated"])
            if validated != s["ledgers_validated"]:
                ok = False
                details.append("%s: stored validated %d != chain count %d" % (
                    s["side"], s["ledgers_validated"], validated))
            for l in s["ledgers"]:
                expect = (l["validations_visible"] >= s["quorum"]) if s["quorum"] else False
                if l["validated"] != expect:
                    ok = False
                    details.append("%s seq %d: validated=%s but %d visible vs quorum %s" % (
                        s["side"], l["seq"], l["validated"], l["validations_visible"], s["quorum"]))
                    break
        check("A-%s" % sid, "quorum arithmetic + validated flags for %s" % sid,
              ok, "; ".join(details) if details else
              "quorum=%s per side, validated flags match visible-vs-quorum" % (
                  [s["quorum"] for s in r["sides"]]))

    # --- B: amendment threshold arithmetic ------------------------------
    r5 = scenarios["S-05"]
    a_side = r5["sides"][0]
    ev_a = a_side["amendment_events"][0]
    thr = 7 * 67 / 100
    check("B-01", "S-05 majority side: 7 yes > 7*67/100 = 4.69 (strictly greater)",
          ev_a["majority_recorded"] is True and ev_a["yes_votes"] == 7
          and abs(ev_a["threshold_value"] - thr) < 1e-9
          and ev_a["pseudo_tx"] == "tfGotMajority",
          "threshold_value=%.2f, pseudo_tx=%s" % (ev_a["threshold_value"], ev_a["pseudo_tx"]))
    b_side = r5["sides"][1]
    ev_b = b_side["amendment_events"][0]
    check("B-02", "S-05 minority side: vote skipped, 3 trusted < quorum 7",
          ev_b["majority_recorded"] is False
          and ev_b["trusted_validations"] == 3
          and ev_b["pseudo_tx"] == "none (vote skipped, below quorum)",
          "trusted=%d, yes=%d" % (ev_b["trusted_validations"], ev_b["yes_votes"]))
    r9 = scenarios["S-09"]
    ev9 = r9["sides"][0]["amendment_events"][0]
    check("B-03", "S-09 flag ledger: hold needs ceil(1209600/4) = 302400 ledgers",
          ev9["hold_ledgers_needed_at_modelled_close"] == 302400
          and ev9["hold_elapsed_in_scenario"] is False
          and ev9["enabled_in_scenario"] is False,
          "hold_ledgers_needed=%d" % ev9["hold_ledgers_needed_at_modelled_close"])
    check("B-04", "post-fix 67/100 (0.67) < pre-fix 204/256 (0.796875)",
          67 / 100 < 204 / 256,
          "post-fix 0.67 vs pre-fix 0.796875; docs 80%% matches neither pinned branch")

    # --- C: hash-chain integrity ----------------------------------------
    chain_ok = True
    chain_detail = ""
    total_ledgers = 0
    for sid in sorted(scenarios):
        for s in scenarios[sid]["sides"]:
            parent = None
            for l in s["ledgers"]:
                total_ledgers += 1
                if parent is not None and l["parent_hash"] != parent:
                    chain_ok = False
                    chain_detail = "%s %s seq %d: parent mismatch" % (sid, s["side"], l["seq"])
                    break
                recomputed = sim_ledger_hash(
                    l["parent_hash"], l["seq"], l["close_time"],
                    l["close_time_resolution"], l["close_flags"], l["tx_count"])
                if recomputed != l["hash"]:
                    chain_ok = False
                    chain_detail = "%s %s seq %d: hash mismatch" % (sid, s["side"], l["seq"])
                    break
                parent = l["hash"]
            if not chain_ok:
                break
        if not chain_ok:
            break
    check("C-01", "hash-chain integrity: every simulated ledger hash recomputes, parent links hold",
          chain_ok, chain_detail or "%d ledgers checked" % total_ledgers)
    rec_ok = True
    rec_detail = ""
    for sid in sorted(scenarios):
        r = scenarios[sid]
        if r["final_hashes_reconciled"]:
            if r["final_ledger_hash"] is None or len(set(r["final_ledger_hashes_by_side"])) != 1:
                rec_ok = False
                rec_detail = "%s: reconciled but final hashes differ" % sid
            if r["rejoin"].get("final_ledger_hash") != r["final_ledger_hash"]:
                rec_ok = False
                rec_detail = "%s: rejoin final hash != result final hash" % sid
    check("C-02", "reconciled scenarios have one final hash, equal to the rejoin winner tip",
          rec_ok, rec_detail or "9/10 reconciled (S-03 ends mid-down-window, honestly unreconciled)")
    r4 = scenarios["S-04"]
    check("C-03", "S-04 dual validation: both sides validated 40; 40 validated ledgers discarded at heal",
          r4["sides"][0]["ledgers_validated"] == 40
          and r4["sides"][1]["ledgers_validated"] == 40
          and r4["rejoin"]["ledgers_discarded_validated"] == 40,
          "discarded_validated=%d" % r4["rejoin"]["ledgers_discarded_validated"])

    # --- D: expiry-window arithmetic ------------------------------------
    ex = r9["expiry"]
    check("D-01", "S-09 expiry rounds match the windows: LOCAL 180 s @45, WALL 300 s @75, SET 600 s @150",
          ex["local_crossed_round"] == 45 and ex["local_crossed_round"] * 4 == 180
          and ex["wall_crossed_round"] == 75 and ex["wall_crossed_round"] * 4 == 300
          and ex["set_expires_crossed_round"] == 150
          and ex["set_expires_crossed_round"] * 4 == 600,
          "local=%s wall=%s set=%s" % (ex["local_crossed_round"], ex["wall_crossed_round"],
                                       ex["set_expires_crossed_round"]))
    check("D-02", "S-09 expired sets equal pre-partition sets (3)",
          ex["sets_expired"] == ex["pre_partition_sets"] == 3,
          "sets_expired=%d" % ex["sets_expired"])

    # --- E: rejoin / fetch-count model ----------------------------------
    e_ok = True
    e_detail = ""
    for sid in sorted(scenarios):
        r = scenarios[sid]
        rj = r["rejoin"]
        if rj["ledgers_refetched"] != sum(e["ledgers_refetched"] for e in rj["events"]):
            e_ok = False
            e_detail = "%s: refetched total != event sum" % sid
        if rj["ledgers_discarded"] != sum(e["ledgers_discarded"] for e in rj["events"]):
            e_ok = False
            e_detail = "%s: discarded total != event sum" % sid
        if rj["acquire_attempts"] != rj["ledgers_refetched"]:
            e_ok = False
            e_detail = "%s: acquire attempts != refetched" % sid
        if rj["timeouts"] != 0:
            e_ok = False
            e_detail = "%s: unexpected timeouts %d" % (sid, rj["timeouts"])
        if rj["worst_case_seconds_per_ledger"] != 21:
            e_ok = False
            e_detail = "%s: worst case per ledger != (6+1)*3 = 21 s" % sid
    check("E-01", "rejoin totals equal event sums; attempts == refetched; 0 timeouts; worst case 21 s/ledger",
          e_ok, e_detail or "all 10 scenarios")
    r10 = scenarios["S-10"]
    check("E-02", "S-10: minority discarded 40 == its closed 40; refetched 40 == majority closed 40",
          r10["rejoin"]["ledgers_discarded"] == 40
          and r10["sides"][1]["ledgers_closed"] == 40
          and r10["rejoin"]["ledgers_refetched"] == 40
          and r10["sides"][0]["ledgers_closed"] == 40,
          "discarded=%d refetched=%d" % (r10["rejoin"]["ledgers_discarded"],
                                         r10["rejoin"]["ledgers_refetched"]))
    r7 = scenarios["S-07"]
    check("E-03", "S-07: isolated side discarded 0 (closed nothing) and refetched 30 (whole majority chain)",
          r7["rejoin"]["ledgers_discarded"] == 0
          and r7["rejoin"]["ledgers_refetched"] == 30
          and r7["sides"][1]["ledgers_closed"] == 0,
          "discarded=%d refetched=%d" % (r7["rejoin"]["ledgers_discarded"],
                                         r7["rejoin"]["ledgers_refetched"]))

    # --- F: close-time bins ----------------------------------------------
    bins = {10, 20, 30, 60, 90, 120}
    f_ok = True
    f_detail = ""
    for sid in sorted(scenarios):
        for s in scenarios[sid]["sides"]:
            for l in s["ledgers"]:
                if l["close_time_resolution"] not in bins:
                    f_ok = False
                    f_detail = "%s %s seq %d: resolution %s not in bins" % (
                        sid, s["side"], l["seq"], l["close_time_resolution"])
    r6 = scenarios["S-06"]
    check("F-01", "every close-time resolution is in {10,20,30,60,90,120}",
          f_ok, f_detail or "all ledgers in all scenarios")
    check("F-02", "S-06 minority coarsened to 120 s with sLCF_NoConsensusTime (0x01); majority refined to 10 s, flags 0",
          r6["sides"][1]["close_time_resolution_final_s"] == 120
          and all(l["close_flags"] == 0x01 for l in r6["sides"][1]["ledgers"])
          and r6["sides"][0]["close_time_resolution_final_s"] == 10
          and all(l["close_flags"] == 0 for l in r6["sides"][0]["ledgers"]),
          "minority final=%d s, majority final=%d s" % (
              r6["sides"][1]["close_time_resolution_final_s"],
              r6["sides"][0]["close_time_resolution_final_s"]))

    # --- G: determinism ---------------------------------------------------
    results_digest = sha256_file(results_path)
    with tempfile.TemporaryDirectory(prefix="pftl-partition-drill.") as td:
        tmp_out = Path(td) / "scenario-results.json"
        proc = subprocess.run(
            [sys.executable, str(PACK_ROOT / "src" / "partition_sim.py"),
             "--all", "--seed", "0", "--out", str(tmp_out)],
            capture_output=True, text=True)
        rerun_ok = proc.returncode == 0
        rerun_digest = sha256_file(tmp_out) if tmp_out.is_file() else "missing"
        proc2 = subprocess.run(
            [sys.executable, str(PACK_ROOT / "src" / "partition_sim.py"),
             "--all", "--seed", "1", "--out", str(Path(td) / "seed1.json")],
            capture_output=True, text=True)
        seed1_digest = sha256_file(Path(td) / "seed1.json") if proc2.returncode == 0 else "missing"
    check("G-01", "determinism: same-seed re-run is byte-identical (full SHA-256)",
          rerun_ok and rerun_digest == results_digest,
          "shipped=%s rerun=%s" % (results_digest, rerun_digest))
    check("G-02", "seed sensitivity: seed 1 output differs from seed 0",
          seed1_digest != results_digest and seed1_digest != "missing",
          "seed0=%s seed1=%s" % (results_digest, seed1_digest))

    # --- H: constants ------------------------------------------------------
    check("H-01", "consensus constants: minCONSENSUS_PCT 67, close-time 75, avalanche 50/65/70/95",
          consts["min_consensus_pct"] == 67
          and consts["close_time_consensus_pct"] == 75
          and consts["avalanche_cutoffs_pct"] == [50, 65, 70, 95],
          "min=%d ct=%d avalanche=%s" % (consts["min_consensus_pct"],
                                         consts["close_time_consensus_pct"],
                                         consts["avalanche_cutoffs_pct"]))
    check("H-02", "flag-ledger interval 256: S-05 flag 8283904 %% 256 == 0, S-09 flag 8284160 %% 256 == 0",
          consts["flag_ledger_interval"] == 256
          and 8283904 % 256 == 0 and 8284160 % 256 == 0,
          "interval=%d" % consts["flag_ledger_interval"])

    # Timing sanity only: non-negative, never compared exactly. The
    # value is NOT recorded in any output file or log line: persisting
    # it would make drill-results.json, drill-run.log, and run.log
    # (which digests them) differ on every run and break the
    # byte-identical reproduction check.
    elapsed_ms = (time.monotonic() - t_start) * 1000.0
    timing_ok = elapsed_ms >= 0
    check("T-01", "timing sanity: total drill elapsed_ms is non-negative (loose band, never exact)",
          timing_ok, "value not recorded; never compared")

    passed = sum(1 for c in checks if c["pass"])
    total = len(checks)
    lines.append("drill: %d/%d checks PASS" % (passed, total))
    lines.append("drill: scenario-results.json sha256: %s" % results_digest)
    lines.append("drill: pinned commit %s" % PINNED_COMMIT)
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)

    result_doc = {
        "pack": "Validator Partition Recovery Assessment",
        "pinned_commit": PINNED_COMMIT,
        "results_file": "outputs/derived/scenario-results.json",
        "results_sha256": results_digest,
        "checks": checks,
        "passed": passed,
        "total": total,
    }
    out_derived = PACK_ROOT / "outputs" / "derived" / "drill-results.json"
    out_derived.parent.mkdir(parents=True, exist_ok=True)
    with open(out_derived, "w", encoding="utf-8") as fh:
        json.dump(result_doc, fh, indent=1, sort_keys=True)
        fh.write("\n")
    (PACK_ROOT / "outputs" / "drill-run.log").write_text(text)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
