#!/usr/bin/env python3
"""partition_sim.py — validator partition recovery simulator.

SIMULATED, not measured: this is a trace simulator of validator voting
+ ledger close under partition scenarios, built from the pinned-code
rules in postfiatd commit 0085a1ff885d6a446369cf73a4430f75af22be55.
Every "observed" value in the output is labelled SIMULATED; it models
the pinned code, it is not a measurement of postfiatd behaviour.

Pinned-code rules modelled (see configs/scenarios.json "source" fields
and docs/methodology.md for the full list):
- Validation quorum: max(ceil(effectiveUNL*0.67), ceil(UNL*0.60))
  (ValidatorList.cpp:1845-1935). Publisher outage disables quorum
  (SIZE_MAX) when unavailable publishers >= min(listThreshold_,
  N - listThreshold_ + 1).
- Transaction-set consensus threshold minCONSENSUS_PCT = 67
  (ConsensusParms.h:79); close-time consensus 75%; avalanche
  50 -> 65 -> 70 -> 95%.
- Amendment threshold post-fix: trusted*67/100, strictly greater
  (AmendmentTable.cpp:320-375; SystemParameters.h:85); 2-week hold
  (1,209,600 s) measured in ledger close time; flag ledger every 256
  (Ledger.h:426); voting only when trusted validations for the
  pre-flag ledger >= quorum() (RCLConsensus.cpp:353-380).
- Validation currency: WALL 5 min / LOCAL 3 min / EARLY 3 min;
  set expiry 10 min (Validations.h:47-94); isCurrent three-window test
  (Validations.h:149-166); expire sweep (Validations.h:730-783).
- Close timing: ledgerMIN_CLOSE 2 s, ledgerIDLE_INTERVAL 15 s,
  ledgerMIN_CONSENSUS 1950 ms, ledgerMAX_CONSENSUS 15 s, abandon 120 s
  (ConsensusParms.h); close-time bins {10,20,30,60,90,120} s, default
  30 s (LedgerTiming.h:35-53); coarsen on disagreement, refine every
  8th ledger on agreement (LedgerTiming.h:80-140).
- Inbound ledger: 3 s timeout, 5 start peers +3/timeout, give up after
  >6 timeouts (~21 s per ledger) (InboundLedger.cpp:44-74, 366-413).
- Preferred-ledger branch support (LedgerTrie.h:685-778); wrong-ledger
  recovery (Consensus.h:1063-1115); hash-chain invalidation on rejoin
  via setFullLedger (LedgerMaster.cpp:826-886).
- No explicit split-brain detector exists in the pinned code; detection
  signals in this simulator are MODELLED definitions (preferred-ledger
  divergence, validated-sequence stall, quorum failure, operating mode,
  close-time flag, validation expiry), not code events.

Simulated ledger hashes use SHA-256 over (parent_hash, seq, close_time,
resolution, close_flags, tx_count). The pinned code uses sha512Half
(Ledger.cpp:54-68); the simulator hash is a stand-in chain link, and is
labelled as such wherever it appears.

Usage:
    python3 src/partition_sim.py --all [--seed N] [--out PATH]
    python3 src/partition_sim.py --scenario S-01 [--seed N] [--out PATH]

Exit codes:
    0 — simulation ran.
    2 — argument error (argparse) or unknown scenario id.
    3 — simulator not implemented (retained for interface compat;
        this implementation never returns 3).

Determinism: identical (scenario, seed) inputs produce byte-identical
outputs. No wall-clock time, no timestamps, no absolute paths in any
output. The only randomness is a seeded Random used for deterministic
per-ledger transaction counts.
"""
import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent
PINNED_COMMIT = "0085a1ff885d6a446369cf73a4430f75af22be55"

# Pinned-code constants (see module docstring for sources).
QUORUM_PCT_NUM = 67
QUORUM_PCT_DEN = 100
QUORUM_FLOOR_NUM = 60
QUORUM_FLOOR_DEN = 100
MIN_CONSENSUS_PCT = 67
CLOSE_TIME_CONSENSUS_PCT = 75
AVALANCHE_CUTOFFS = [50, 65, 70, 95]
TIME_RESOLUTIONS = [10, 20, 30, 60, 90, 120]
DEFAULT_RESOLUTION = 30
FLAG_LEDGER_INTERVAL = 256
MAJORITY_HOLD_SECONDS = 1209600  # 2 weeks
VALIDATION_WALL_S = 300
VALIDATION_LOCAL_S = 180
VALIDATION_EARLY_S = 180
VALIDATION_SET_EXPIRES_S = 600
VALIDATION_FRESHNESS_S = 20
LEDGER_MIN_CLOSE_S = 2
LEDGER_IDLE_INTERVAL_S = 15
LEDGER_MIN_CONSENSUS_MS = 1950
LEDGER_MAX_CONSENSUS_S = 15
LEDGER_ABANDON_CONSENSUS_S = 120
ACQUIRE_TIMEOUT_S = 3
ACQUIRE_RETRIES_MAX = 6
ACQUIRE_PEER_START = 5
ACQUIRE_PEER_ADD = 3
ACQUIRE_AGGRESSIVE_AFTER = 4
CLOSE_FLAG_NO_CONSENSUS_TIME = 0x01


def ceil_div(a, b):
    return -(-a // b)


def quorum_for(unl_size, effective_unl_size):
    """max(ceil(eff*0.67), ceil(unl*0.60)) — ValidatorList.cpp:1934."""
    return max(
        ceil_div(effective_unl_size * QUORUM_PCT_NUM, QUORUM_PCT_DEN),
        ceil_div(unl_size * QUORUM_FLOOR_NUM, QUORUM_FLOOR_DEN),
    )


def amendment_threshold(trusted_count):
    """Post-fix threshold value: trusted*67/100; majority needs votes
    STRICTLY GREATER than this (AmendmentTable.cpp:320-375)."""
    return trusted_count * QUORUM_PCT_NUM / QUORUM_PCT_DEN


def ledger_hash(parent_hash, seq, close_time, resolution, close_flags,
                tx_count):
    """SIMULATED hash-chain link (SHA-256 stand-in; the pinned code uses
    sha512Half over 10 fields, Ledger.cpp:54-68)."""
    payload = "|".join([parent_hash, str(seq), str(close_time),
                        str(resolution), str(close_flags), str(tx_count)])
    return hashlib.sha256(payload.encode()).hexdigest()


def load_scenarios():
    cfg = PACK_ROOT / "configs" / "scenarios.json"
    with open(cfg, encoding="utf-8") as fh:
        data = json.load(fh)
    return data["scenarios"]


def load_scenario_ids():
    try:
        return [s["id"] for s in load_scenarios()]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def build_parser():
    p = argparse.ArgumentParser(
        description="Validator partition recovery simulator.")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--scenario", metavar="ID",
                       help="run a single scenario, e.g. S-01")
    group.add_argument("--all", action="store_true",
                       help="run all scenarios in configs/scenarios.json")
    p.add_argument("--seed", type=int, default=0,
                   help="deterministic RNG seed (default 0)")
    p.add_argument("--out", metavar="PATH", default=None,
                   help="write scenario results JSON to PATH "
                        "(default: outputs/derived/scenario-results.json)")
    return p


class SideState:
    """Per-side simulated chain + counters."""

    def __init__(self, name, members, unl, quorum, genesis_parent):
        self.name = name
        self.members = list(members)
        self.unl = list(unl)
        self.quorum = quorum  # None means disabled (SIZE_MAX)
        self.chain = []  # ledger dicts
        self.parent_hash = genesis_parent
        self.validated = 0
        self.closed = 0
        self.validations_counted = 0
        self.resolution = DEFAULT_RESOLUTION
        self.resolution_idx = TIME_RESOLUTIONS.index(DEFAULT_RESOLUTION)
        self.agree_rounds = 0  # consecutive rounds with close-time agreement
        self.stalled_rounds = 0  # consecutive rounds without validation
        self.split_closed_since_reconcile = 0  # ledgers closed while split
        self.split_validated_since_reconcile = 0  # validated while split
        self.signals = []  # (round, signal, detail)
        self.signal_seen = set()
        self.amendment_events = []
        self.disconnected = False

    def tip_hash(self):
        return self.chain[-1]["hash"] if self.chain else self.parent_hash

    def fire(self, rnd, signal, detail):
        if signal not in self.signal_seen:
            self.signal_seen.add(signal)
            self.signals.append({"round": rnd, "signal": signal,
                                 "detail": detail})

    def close_ledger(self, rnd, seq, close_time, close_flags, tx_count,
                     validations_visible, consensus_reached):
        """Close one ledger for this side; returns the ledger dict."""
        h = ledger_hash(self.parent_hash, seq, close_time,
                        self.resolution, close_flags, tx_count)
        ledger = {"seq": seq, "parent_hash": self.parent_hash, "hash": h,
                  "close_time": close_time,
                  "close_time_resolution": self.resolution,
                  "close_flags": close_flags, "tx_count": tx_count,
                  "validations_visible": validations_visible,
                  "quorum": self.quorum,
                  "validated": False,
                  "consensus_reached": consensus_reached}
        self.chain.append(ledger)
        self.parent_hash = h
        self.closed += 1
        self.validations_counted += validations_visible
        if self.quorum is not None and validations_visible >= self.quorum:
            ledger["validated"] = True
            self.validated += 1
            self.stalled_rounds = 0
        else:
            self.stalled_rounds += 1
        return ledger


def run_scenario(sc, seed):
    rng = random.Random(seed * 1000 + int(sc["id"][2:]))
    params = sc.get("parameters", {})
    sides_idx = sc["partition"]["sides"]
    n_validators = sc["topology"]["validator_count"]
    start_seq = params.get("start_seq", 8284000)
    close_s = int(params.get("modelled_close_time_s", 4))
    duration = sc["duration_ledgers"]
    min_peers = params.get("min_peer_count", 2)
    negative_unl = set(params.get("negative_unl", []))
    support_yes = set(params.get("amendment_support_yes",
                                 list(range(n_validators))))
    genesis_parent = hashlib.sha256(
        ("partition-sim-genesis:%d" % (start_seq - 1)).encode()).hexdigest()

    # Per-side UNLs (S-04 diverges; default is the full validator set).
    unl_by_side = []
    for i, side in enumerate(sides_idx):
        if i == 0 and "unl_a" in params:
            unl_by_side.append(list(params["unl_a"]))
        elif i == 1 and "unl_b" in params:
            unl_by_side.append(list(params["unl_b"]))
        else:
            unl_by_side.append(list(range(n_validators)))

    # Publisher outage (S-08): quorum disabled, SIZE_MAX.
    publishers_down = params.get("publishers_unavailable", 0)
    publishers_total = params.get("publishers_total", 0)
    list_threshold = params.get("list_threshold", 0)
    quorum_disabled = False
    if publishers_total:
        limit = min(list_threshold, publishers_total - list_threshold + 1)
        quorum_disabled = publishers_down >= limit

    sides = []
    for i, side in enumerate(sides_idx):
        unl = unl_by_side[i]
        eff = [v for v in unl if v not in negative_unl]
        q = None if quorum_disabled else quorum_for(len(unl), len(eff))
        sides.append(SideState("side-%s" % chr(ord("A") + i), side, unl, q,
                               genesis_parent))
        if quorum_disabled:
            sides[-1].fire(0, "publisher-quorum-disabled",
                            "2 of 3 publishers unavailable >= min(listThreshold_=2, 3-2+1=2); "
                            "calculateQuorum returns SIZE_MAX, quorum disabled")

    flap_up = params.get("flap_up_ledgers")
    flap_down = params.get("flap_down_ledgers")
    asym = "asymmetry" in params
    disagree_side = params.get("minority_close_time_disagreement", False)

    # Expiry tracking (S-09): pre-partition validation sets, one per
    # minority-side validator for the last common ledger.
    expiry = None
    if sc["id"] == "S-09":
        expiry = {"pre_partition_sets": len(sides[1].members),
                  "wall_crossed_round": None,
                  "local_crossed_round": None,
                  "set_expires_crossed_round": None,
                  "sets_expired": 0}

    rejoin = {"ledgers_refetched": 0, "ledgers_discarded": 0,
              "ledgers_discarded_validated": 0, "timeouts": 0,
              "acquire_attempts": 0,
              "worst_case_seconds_per_ledger": (ACQUIRE_RETRIES_MAX + 1) * ACQUIRE_TIMEOUT_S,
              "events": []}
    close_time_base = 1000000000  # arbitrary simulated epoch (seconds)

    def groups_for_round(rnd):
        """Return the list of validator groups active this round."""
        if flap_up is not None:
            cycle = flap_up + flap_down
            if rnd % cycle < flap_up:
                return [list(range(n_validators))]  # unified
            return [list(s) for s in sides_idx]
        return [list(s) for s in sides_idx]

    def visible_validations(group_members, rnd):
        """Validations visible to a group this round (visibility rules)."""
        if flap_up is not None:
            cycle = flap_up + flap_down
            if rnd % cycle < flap_up:
                return len(group_members)  # unified: all see all
        if asym:
            # Side A (index 0) also receives side B's validations.
            if group_members == sides_idx[0]:
                return len(sides_idx[0]) + len(sides_idx[1])
            return len(group_members)
        return len(group_members)

    # Map group membership -> SideState (unified group maps to side A
    # as the continuing chain; the other side is reconciled at merge).
    side_by_frozenset = {frozenset(s.members): s for s in sides}

    for rnd in range(duration):
        seq = start_seq + rnd
        close_time = close_time_base + rnd * close_s
        groups = groups_for_round(rnd)
        unified = len(groups) == 1 and len(groups[0]) == n_validators

        for group in groups:
            key = frozenset(group)
            if unified:
                # One shared chain: side A carries it; other sides are
                # reconciled to it at the end of the round.
                state = sides[0]
                peers = len(group) - 1
            else:
                state = side_by_frozenset[key]
                peers = len(group) - 1

            # Peer-count gate: below minPeerCount_ the node is
            # DISCONNECTED and consensus is not ticked
            # (NetworkOPs.cpp:1049-1078).
            if peers < min_peers:
                state.disconnected = True
                state.fire(rnd, "operating-mode-disconnected",
                           "%s has %d peer(s) < minPeerCount %d; consensus not ticked"
                           % (state.name, peers, min_peers))
                continue

            # Consensus: within a group all members propose the same set,
            # so agree% = 100 >= minCONSENSUS_PCT 67.
            consensus_reached = True

            # Close-time agreement: within a side the validators agree,
            # except the S-06 minority side, whose votes disagree.
            side_index = sides.index(state) if not unified else 0
            internal_disagreement = (
                disagree_side and not unified and side_index == 1)
            if internal_disagreement:
                close_flags = CLOSE_FLAG_NO_CONSENSUS_TIME
                state.fire(rnd, "close-time-no-consensus",
                           "no 75%% close-time consensus inside %s; sLCF_NoConsensusTime set, "
                           "close time = prev close time + 1 s" % state.name)
                # Coarsen one bin per ledger of disagreement.
                if state.resolution_idx < len(TIME_RESOLUTIONS) - 1:
                    state.resolution_idx += 1
                    state.resolution = TIME_RESOLUTIONS[state.resolution_idx]
                state.agree_rounds = 0
            else:
                close_flags = 0
                state.agree_rounds += 1
                # Refine one bin every 8th agreeing ledger.
                if state.agree_rounds % 8 == 0 and state.resolution_idx > 0:
                    state.resolution_idx -= 1
                    state.resolution = TIME_RESOLUTIONS[state.resolution_idx]

            tx_count = rng.randint(0, 4)
            vis = visible_validations(group, rnd)
            # Quorum counts trusted validations visible to this side;
            # in the divergent-UNL case (S-04) only validations from
            # validators in this side's UNL count.
            if "unl_a" in params:
                unl_set = set(state.unl)
                vis = len([v for v in group if v in unl_set])
                if asym:
                    pass
            ledger = state.close_ledger(rnd, seq, close_time, close_flags,
                                        tx_count, vis, consensus_reached)
            if not unified:
                state.split_closed_since_reconcile += 1
                if ledger["validated"]:
                    state.split_validated_since_reconcile += 1

            # Detection signals.
            if not unified and len(sides) > 1:
                state.fire(rnd, "preferred-divergence",
                           "getPreferred returns this side's chain, not the local LCL "
                           "of the other side (modelled detector; the code has no explicit "
                           "split-brain flag)")
            if state.quorum is None:
                pass
            elif vis < state.quorum:
                state.fire(rnd, "quorum-not-reached",
                           "%d trusted validations visible < quorum %d for seq %d"
                           % (vis, state.quorum, seq))
            if state.stalled_rounds == 3:
                state.fire(rnd, "validated-seq-stalled",
                           "validated sequence has not advanced for 3 consecutive rounds")

            # Amendment voting at flag ledgers.
            if seq % FLAG_LEDGER_INTERVAL == 0:
                trusted = vis
                if state.quorum is not None and trusted >= state.quorum:
                    yes = len([v for v in group if v in support_yes])
                    thr = amendment_threshold(trusted)
                    majority = yes > thr
                    hold_needed = int(math.ceil(
                        MAJORITY_HOLD_SECONDS / close_s))
                    ev = {"flag_ledger_seq": seq,
                          "trusted_validations": trusted,
                          "yes_votes": yes,
                          "threshold_value": thr,
                          "threshold_rule": "votes > trusted*67/100 (post-fix, strictly greater)",
                          "majority_recorded": majority,
                          "pseudo_tx": "tfGotMajority" if majority else "none (no majority)",
                          "hold_seconds": MAJORITY_HOLD_SECONDS,
                          "hold_ledgers_needed_at_modelled_close": hold_needed,
                          "hold_elapsed_in_scenario": False,
                          "enabled_in_scenario": False}
                    state.amendment_events.append(ev)
                    if majority:
                        state.fire(rnd, "amendment-majority-recorded",
                                   "tfGotMajority for seq %d: %d yes > %.2f threshold"
                                   % (seq, yes, thr))
                else:
                    ev = {"flag_ledger_seq": seq,
                          "trusted_validations": trusted,
                          "yes_votes": len([v for v in group if v in support_yes]),
                          "threshold_value": None,
                          "threshold_rule": "no vote: trusted validations < quorum() "
                                            "(RCLConsensus.cpp:353-380 gate)",
                          "majority_recorded": False,
                          "pseudo_tx": "none (vote skipped, below quorum)",
                          "hold_seconds": MAJORITY_HOLD_SECONDS,
                          "hold_ledgers_needed_at_modelled_close": int(math.ceil(
                              MAJORITY_HOLD_SECONDS / close_s)),
                          "hold_elapsed_in_scenario": False,
                          "enabled_in_scenario": False}
                    state.amendment_events.append(ev)
                    state.fire(rnd, "amendment-vote-skipped-below-quorum",
                               "flag ledger %d: %d trusted validations < quorum %s; "
                               "amendment clock frozen on this side" % (seq, trusted, state.quorum))

        # Flap-up reconvergence: when the link comes back up, the side
        # with less branch support discards its down-window ledgers and
        # re-fetches the winner's chain (modelled LedgerTrie getPreferred
        # + handleWrongLedger + InboundLedger acquisition).
        if flap_up is not None:
            cycle = flap_up + flap_down
            if rnd % cycle == flap_up - 1 or rnd == duration - 1:
                # End of an up window (or end of scenario): reconcile.
                pass
            if rnd % cycle == 0 and rnd > 0:
                # Link just came back up: reconcile the two sides.
                _reconcile(sides, rnd, rejoin)

        # Expiry windows (S-09): age of the pre-partition validation sets.
        if expiry is not None:
            age = rnd * close_s
            if expiry["local_crossed_round"] is None and age >= VALIDATION_LOCAL_S:
                expiry["local_crossed_round"] = rnd
                sides[1].fire(rnd, "validation-expired-local",
                              "pre-partition validations older than LOCAL 3 min (%d s)" % age)
            if expiry["wall_crossed_round"] is None and age >= VALIDATION_WALL_S:
                expiry["wall_crossed_round"] = rnd
                sides[1].fire(rnd, "validation-expired-wall",
                              "pre-partition validations older than WALL 5 min (%d s)" % age)
            if expiry["set_expires_crossed_round"] is None and age >= VALIDATION_SET_EXPIRES_S:
                expiry["set_expires_crossed_round"] = rnd
                expiry["sets_expired"] = expiry["pre_partition_sets"]
                sides[1].fire(rnd, "validation-set-expired",
                              "pre-partition validation sets swept after SET_EXPIRES 10 min (%d s); "
                              "%d set(s) expired" % (age, expiry["sets_expired"]))

    # Final heal / rejoin for non-flap scenarios with >1 side.
    healed_winner = None
    if flap_up is None and len(sides) > 1:
        healed_winner = _reconcile(sides, duration, rejoin, final=True)

    # Dual-validated fork signal (S-04): both sides validated ledgers.
    if len(sides) > 1 and all(s.validated > 0 for s in sides):
        for s in sides:
            s.fire(duration - 1, "dual-validated-fork",
                   "both sides quorum-validated their own chains (%d vs %d ledgers); "
                   "fork persists until UNLs reconverge" % (sides[0].validated, sides[1].validated))

    # Publisher-outage recovery note (S-08): publishers return at the end.
    publisher_recovery = None
    if quorum_disabled:
        eff_q = quorum_for(params.get("unl_size", n_validators),
                           params.get("unl_size", n_validators))
        publisher_recovery = {
            "publishers_restored": True,
            "quorum_recomputed": eff_q,
            "note": "MODELLED recovery: after the publisher lists refresh "
                    "(ValidatorSite default 5 min), updateTrusted recomputes quorum; "
                    "validation resumes from the next close. No ledgers were validated "
                    "during the outage.",
        }

    side_results = []
    for s in sides:
        side_results.append({
            "side": s.name,
            "validators": s.members,
            "unl": s.unl,
            "unl_size": len(s.unl),
            "effective_unl_size": len([v for v in s.unl if v not in negative_unl]),
            "quorum": s.quorum,
            "quorum_disabled": s.quorum is None,
            "ledgers_closed": s.closed,
            "ledgers_validated": s.validated,
            "validations_counted": s.validations_counted,
            "validated_sequence_stalled": s.stalled_rounds > 0,
            "stalled_rounds_at_end": s.stalled_rounds,
            "disconnected": s.disconnected,
            "close_time_resolution_final_s": s.resolution,
            "close_time_resolution_bins": TIME_RESOLUTIONS,
            "tip_hash": s.tip_hash(),
            "ledger_hashes": [l["hash"] for l in s.chain],
            "ledgers": s.chain,
            "detection_signals": s.signals,
            "amendment_events": s.amendment_events,
        })

    if healed_winner is not None:
        # Post-heal every side's tip is the winner's tip (hash-chained
        # acquisition); per-side chains above still record what each side
        # closed during the partition.
        final_hashes = [healed_winner.tip_hash() for _ in sides]
        reconciled = True
    elif len(sides) == 1:
        final_hashes = [sides[0].tip_hash()]
        reconciled = True
        rejoin["final_ledger_hash"] = sides[0].tip_hash()
        rejoin["winner"] = sides[0].name
    else:
        # Flapping scenario ends mid-down-window: sides still diverge.
        final_hashes = [s.tip_hash() for s in sides]
        reconciled = len(set(final_hashes)) == 1
    result = {
        "id": sc["id"],
        "name": sc["name"],
        "seed": seed,
        "status": "SIMULATED",
        "duration_ledgers": duration,
        "start_seq": start_seq,
        "modelled_close_time_s": close_s,
        "sides": side_results,
        "ledgers_closed_total": sum(s.closed for s in sides),
        "ledgers_validated_total": sum(s.validated for s in sides),
        "validations_counted_total": sum(s.validations_counted for s in sides),
        "detection_signals_total": sum(len(s.signals) for s in sides),
        "rejoin": rejoin,
        "final_ledger_hash": final_hashes[0] if reconciled else None,
        "final_ledger_hashes_by_side": final_hashes,
        "final_hashes_reconciled": reconciled,
        "expiry": expiry,
        "publisher_recovery": publisher_recovery,
        "expected_behavior": sc.get("expected_behavior", ""),
        "source": sc.get("source", ""),
    }
    if flap_up is not None:
        result["counting_note"] = (
            "ledgers_closed_total is a per-side sum: down-window ledgers were closed "
            "independently by both sides, up-window ledgers once on the shared chain. "
            "Distinct ledger rounds = duration_ledgers.")
    return result


def _reconcile(sides, rnd, rejoin, final=False):
    """Preferred-ledger reconciliation (modelled LedgerTrie getPreferred
    + handleWrongLedger + InboundLedger acquisition).

    Per-side chains and observed counters are NOT overwritten: they record
    what each side actually closed during the partition. Reconciliation is
    pure accounting here: the side with more validated ledgers (branch
    support) wins; ties break on the larger tip hash (modelled tie-break
    standing in for the LedgerTrie span-start-ID rule). The loser discards
    the ledgers it closed since the last reconcile and re-fetches the
    winner's ledgers closed since then, one InboundLedger acquisition per
    ledger, first attempt (peers hold them), 0 timeouts. Worst case if
    peers lacked them: (retries_max + 1) * 3 s per ledger."""
    if len(sides) < 2:
        return None
    ranked = sorted(sides, key=lambda s: (s.validated, s.tip_hash()),
                    reverse=True)
    winner, loser = ranked[0], ranked[1]
    div_loser = loser.split_closed_since_reconcile
    div_winner = winner.split_closed_since_reconcile
    div_loser_validated = loser.split_validated_since_reconcile
    rejoin["ledgers_discarded"] += div_loser
    rejoin["ledgers_discarded_validated"] += div_loser_validated
    rejoin["ledgers_refetched"] += div_winner
    rejoin["acquire_attempts"] += div_winner
    rejoin["events"].append({
        "round": rnd, "winner": winner.name, "loser": loser.name,
        "winner_validated": winner.validated,
        "loser_validated": loser.validated,
        "ledgers_discarded": div_loser,
        "ledgers_discarded_validated": div_loser_validated,
        "ledgers_refetched": div_winner, "timeouts": 0,
        "worst_case_seconds_if_peers_lacked_ledgers":
            div_winner * (ACQUIRE_RETRIES_MAX + 1) * ACQUIRE_TIMEOUT_S,
        "note": "branch support picked %s; %s discarded its diverged ledgers "
                "(parent-hash mismatch invalidates local ledgers, "
                "setFullLedger) and re-acquired the winner chain ledger by ledger" % (
                    winner.name, loser.name)})
    for s in sides:
        s.split_closed_since_reconcile = 0
        s.split_validated_since_reconcile = 0
    if final:
        rejoin["final_ledger_hash"] = winner.tip_hash()
        rejoin["winner"] = winner.name
    return winner


def run_all(seed):
    scenarios = load_scenarios()
    results = [run_scenario(sc, seed) for sc in scenarios]
    doc = {
        "pack": "Validator Partition Recovery Assessment",
        "pinned_commit": PINNED_COMMIT,
        "seed": seed,
        "status": "SIMULATED",
        "model_note": "SIMULATED trace output. Values model the pinned-code rules listed in "
                      "docs/methodology.md; they are not measurements of postfiatd behaviour. "
                      "Simulated ledger hashes are SHA-256 stand-ins, not sha512Half recomputations.",
        "constants": {
            "validation_quorum_rule": "max(ceil(effectiveUNL*0.67), ceil(UNL*0.60))",
            "min_consensus_pct": MIN_CONSENSUS_PCT,
            "close_time_consensus_pct": CLOSE_TIME_CONSENSUS_PCT,
            "avalanche_cutoffs_pct": AVALANCHE_CUTOFFS,
            "close_time_resolution_bins_s": TIME_RESOLUTIONS,
            "default_close_time_resolution_s": DEFAULT_RESOLUTION,
            "flag_ledger_interval": FLAG_LEDGER_INTERVAL,
            "amendment_majority_hold_seconds": MAJORITY_HOLD_SECONDS,
            "amendment_threshold_rule": "votes > trusted*67/100 (post-fix, strictly greater)",
            "validation_current_wall_s": VALIDATION_WALL_S,
            "validation_current_local_s": VALIDATION_LOCAL_S,
            "validation_current_early_s": VALIDATION_EARLY_S,
            "validation_set_expires_s": VALIDATION_SET_EXPIRES_S,
            "validation_freshness_s": VALIDATION_FRESHNESS_S,
            "ledger_min_close_s": LEDGER_MIN_CLOSE_S,
            "ledger_idle_interval_s": LEDGER_IDLE_INTERVAL_S,
            "ledger_min_consensus_ms": LEDGER_MIN_CONSENSUS_MS,
            "ledger_max_consensus_s": LEDGER_MAX_CONSENSUS_S,
            "ledger_abandon_consensus_s": LEDGER_ABANDON_CONSENSUS_S,
            "inbound_acquire_timeout_s": ACQUIRE_TIMEOUT_S,
            "inbound_acquire_retries_max": ACQUIRE_RETRIES_MAX,
            "inbound_acquire_peer_start": ACQUIRE_PEER_START,
            "inbound_acquire_peer_add": ACQUIRE_PEER_ADD,
            "inbound_acquire_aggressive_after_timeouts": ACQUIRE_AGGRESSIVE_AFTER,
        },
        "scenarios": results,
    }
    return doc


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.scenario:
        known = load_scenario_ids()
        if known is not None and args.scenario not in known:
            print(f"partition_sim: unknown scenario {args.scenario!r}; "
                  f"known ids: {', '.join(known)}", file=sys.stderr)
            return 2
        scenarios = load_scenarios()
        sc = next(s for s in scenarios if s["id"] == args.scenario)
        doc = run_all(args.seed)
        doc["scenarios"] = [r for r in doc["scenarios"]
                            if r["id"] == args.scenario]
    else:
        doc = run_all(args.seed)

    out = Path(args.out) if args.out else (
        PACK_ROOT / "outputs" / "derived" / "scenario-results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
        fh.write("\n")

    results_digest = hashlib.sha256(out.read_bytes()).hexdigest()
    lines = []
    lines.append("partition_sim: SIMULATED run (seed %d)" % args.seed)
    lines.append("partition_sim: pinned commit %s" % PINNED_COMMIT)
    for r in doc["scenarios"]:
        lines.append(
            "partition_sim: %s %s — closed=%d validated=%d validations=%d "
            "signals=%d reconciled=%s tip=%s"
            % (r["id"], r["name"], r["ledgers_closed_total"],
               r["ledgers_validated_total"], r["validations_counted_total"],
               r["detection_signals_total"], r["final_hashes_reconciled"],
               (r["final_ledger_hash"] or r["final_ledger_hashes_by_side"][0])))
    lines.append("partition_sim: scenarios=%d" % len(doc["scenarios"]))
    lines.append("partition_sim: scenario-results.json sha256: %s"
                 % results_digest)
    lines.append("partition_sim: SIMULATED — values model pinned-code rules; "
                 "not measured postfiatd behaviour.")
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)

    # Unedited log: same content, next to the results file when the
    # caller writes outside the pack, else outputs/sim-run.log.
    default_out = PACK_ROOT / "outputs" / "derived" / "scenario-results.json"
    if Path(out).resolve() == default_out.resolve():
        log_path = PACK_ROOT / "outputs" / "sim-run.log"
    else:
        log_path = out.parent / "sim-run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
