# Split-brain playbook

Pinned source throughout: postfiatd commit
`0085a1ff885d6a446369cf73a4430f75af22be55`. Rules marked [CODE] are
traced to pinned code. Rules marked [MODELLED] are recommendations
built on the code; the code does not state them.

## 1. Detection signals

There is no explicit split-brain or fork detector in the pinned code
[CODE]: no function, flag, RPC field, or log line named split-brain or
fork-detection. The only "divergence" hit in the overlay is the
proposal drop in `src/xrpld/overlay/detail/PeerImp.cpp:1865-1870`.
Detection is emergent. The signals below are the observable proxies,
each defined by the simulator and verified against the pinned rules.
All signal counts are SIMULATED (seed 0, 46 signals across 10 scenarios).

| Signal | Meaning | Pinned-code trace | Fires in |
|---|---|---|---|
| `preferred-divergence` | `getPreferred` returns a ledger that is not our local LCL; the network-preferred chain differs from ours | `Validations.h:850-899` (`getPreferred`), `Consensus.h:1119-1148` (`checkLedger`) | Every multi-side scenario, round 0 |
| `validated-seq-stalled` | Validated sequence has not advanced for 3 consecutive rounds while consensus rounds keep closing | `LedgerMaster.cpp:898-945` (`checkAccept` only advances `mLastValidLedger` on quorum); `LedgerMaster.cpp:521-565` (`isValidated`) | Every below-quorum side (S-01, S-02, S-03, S-05, S-06, S-09, S-10) |
| `quorum-not-reached` | Trusted validations visible for a ledger < quorum | `ValidatorList.cpp:1845-1935` (quorum formula); `LedgerMaster.cpp:898-945` | Every below-quorum side, round 0 |
| `operating-mode-disconnected` | Peer count < minPeerCount: DISCONNECTED, consensus not ticked | `NetworkOPs.cpp:1049-1078`; modes `NetworkOPs.h:68-76` | S-07 isolated validator |
| `close-time-no-consensus` | No 75% close-time consensus; resolution coarsening; `sLCF_NoConsensusTime` (0x01) set | `ConsensusParms.h:160`; `LedgerTiming.h:80-140`; `LedgerHeader.h:82`; `RCLConsensus.cpp:494-504` | S-06 minority side |
| `dual-validated-fork` | Both sides quorum-validated their own chains — a true fork, not a stall | `LedgerTrie.h:685-778` (branch support); `ValidatorList.cpp:1898-1929` (Theorem 8 bound) | S-04 only |
| `validation-expired-local` / `-wall` / `validation-set-expired` | Pre-partition validations crossed LOCAL 3 min / WALL 5 min / SET_EXPIRES 10 min | `Validations.h:47-94`, `149-166`, `730-783` | S-09 at rounds 45 / 75 / 150 |
| `publisher-quorum-disabled` | Quorum disabled (SIZE_MAX): too many list publishers unavailable | `ValidatorList.cpp:1845-1935` | S-08 round 0 |
| `amendment-majority-recorded` | `tfGotMajority` recorded at a flag ledger | `AmendmentTable.cpp:847-941`; `SystemParameters.h:85` | S-05 side A, S-09 side A |
| `amendment-vote-skipped-below-quorum` | No vote: trusted validations for the pre-flag ledger < quorum | `RCLConsensus.cpp:353-380` (onClose gate) | S-05 side B, S-09 side B |

### Signal precedence [MODELLED]

1. `dual-validated-fork` outranks all others: it means two canonical
   chains exist, and the rejoin will discard validated ledgers.
2. `publisher-quorum-disabled` outranks partition signals: if quorum
   is disabled, no side can validate, and the fault is in the
   publisher lists, not the links.
3. `validated-seq-stalled` + `preferred-divergence` together mean
   "we are the minority side": act on the minority-side procedure
   below, not on the majority-side one.
4. `close-time-no-consensus` sustained over 3+ rounds means the
   partition is degrading time agreement; treat it as a partition
   signal even if validation has not stalled yet.

## 2. Safe rejoin procedure

[CODE] steps are what the code does; [MODELLED] steps are operator
actions the code does not perform itself.

1. **Do not restart the node first.** [MODELLED] A restart clears the
   stored validations and proposals that `handleWrongLedger` replays
   (`Consensus.h:1152-1168`); the in-memory preferred-ledger state is
   the evidence of which chain the node was on.
2. **Read the preferred ledger.** [CODE] Compare `getPreferred` /
   `getPreferredLCL` (`Validations.h:850-899`, `936-960`) with the
   local last-closed and last-validated ledgers. If they differ, the
   node is on the wrong chain and `checkLedger` /
   `handleWrongLedger` (`Consensus.h:1119-1148`, `1063-1115`) is the
   recovery path.
3. **Confirm quorum is re-established before trusting the rejoin.**
   [MODELLED] Wait until trusted validations for the preferred ledger
   number >= quorum (`ValidatorList.cpp:1845-1935`). Rejoining while
   still below quorum replays the same stall on the new chain.
4. **Let the node acquire; do not force a ledger.** [CODE]
   `handleWrongLedger` calls `acquireLedger`
   (`RCLConsensus.cpp:128-166`); acquisition is per-ledger via
   `InboundLedger` with a 3 s timeout and up to 6 retries, ~21 s worst
   case per ledger (`InboundLedger.cpp:44-74`, `366-413`). In the
   simulator every rejoin completed with 0 timeouts because peers held
   the ledgers; budget 21 s per missing ledger when peers may not.
5. **Expect the minority chain to be discarded, not merged.**
   [CODE] `setFullLedger` invalidates the local SQL entry for a
   sequence whose hash does not match the adopted ledger's parent hash
   (`LedgerMaster.cpp:826-886`). There is no transaction replay on
   rejoin: "replay" means hash-chained acquisition, not re-execution.
6. **Verify the hash chain after rejoin** (see §3). [MODELLED]
   Do not declare the rejoin complete until the checks pass.
7. **Check amendment state after rejoin.** [CODE] Amendment
   majorities are counted per side from that side's trusted
   validations (`AmendmentTable.cpp:847-941`); a majority recorded on
   the losing side never appears in the winning side's `Majorities`
   entry (`AmendmentTable.cpp:955-989` runs only on validated
   ledgers). After rejoin, re-read the amendment majority timestamps
   from the adopted chain; do not carry over the discarded side's
   timestamps.
8. **Check the negative UNL after rejoin.** [CODE] Each side can vote
   a validator "offline" that is merely unreachable from that side
   (`NegativeUNLVote.cpp:33-108`; note at `:301`). After rejoin,
   confirm the negative UNL matches the healed network's view before
   trusting quorum counts.

## 3. Ledger-hash reconciliation checks

[CODE] The ledger hash is `sha512Half` over 10 fields — prefix, seq,
drops, parentHash, txHash, accountHash, parent close time, close time,
close-time resolution, close flags (`Ledger.cpp:54-68`). Any difference
in any field changes the hash; the hash *is* the reconciliation check.
There is no separate reconcile function.

1. **Parent-link check.** For every adopted ledger, `parentHash`
   must equal the hash of the ledger at `seq - 1` on the adopted
   chain. A mismatch means the chain is not the one the hash commits
   to; the ledger must not be adopted (`RCLConsensus.cpp:128-166`
   asserts hash and parent match; `RCLConsensus.cpp:698-701` asserts
   the built ledger's id and parent hash).
2. **Tip check.** After rejoin, the node's last-validated ledger hash
   must equal the preferred ledger's hash (`getPreferredLCL`,
   `Validations.h:936-960`). In the simulator, 9 of 10 scenarios end
   with a single final hash across all sides (S-03 honestly ends
   unreconciled — it ends mid-down-window).
3. **Validated-sequence check.** The validated sequence must advance
   past the pre-partition value. If `mValidLedgerSeq` is unchanged
   after the rejoin, the node acquired ledgers but did not validate
   them — the rejoin is not complete
   (`LedgerMaster.cpp:898-945`, `521-565`).
4. **Close-flag check.** Ledgers closed during the partition on the
   losing side may carry `sLCF_NoConsensusTime` (0x01)
   (`LedgerHeader.h:82`). After rejoin, newly validated ledgers must
   not carry it unless close-time consensus genuinely failed on the
   healed network.
5. **Skip-list spot check.** [MODELLED] Verify `hashOfSeq` for a
   sample of sequences across the rejoin boundary against the adopted
   chain's hashes. A mismatch at the boundary means the local history
   still holds pre-rejoin ledgers under the same sequences.

## 4. Rollback-protection rules

| Rule | Trace |
|---|---|
| Never treat a closed-but-unvalidated ledger as final. Only a quorum-validated ledger (`checkAccept`, `LedgerMaster.cpp:898-945`) is final. | [CODE] |
| Never copy amendment majority timestamps from a discarded chain. Majorities live in the winning chain's `Majorities` entry only. | [CODE] `AmendmentTable.cpp:955-989` |
| Never shrink the UNL by hand to "fix" a partition. The UNL does not shrink on partition; only publisher-list expiry/refresh or negative-UNL votes change it (`ValidatorList.cpp:1938-2131`). A manual shrink changes quorum for every node that trusts the edited list. | [CODE] + [MODELLED] (the prohibition is the recommendation; the mechanism is code) |
| Never use `--quorum` to force validation during a partition. The override (`ValidatorList.cpp:1850-1857`) replaces the computed quorum with a warning and can validate a minority chain that the healed network will discard. | [CODE] + [MODELLED] |
| Never assume a ledger is missing because one lookup failed. Acquisition gives up after ~21 s per ledger, but the caller re-requests the next preferred ledger; rejoin is a loop of attempts, not a single deadline. Retry before concluding. | [CODE] `InboundLedger.cpp:366-413` |
| Never declare a rejoin complete on matching sequence numbers alone. Sequences match across both fork branches; only hashes distinguish them. | [CODE] `Ledger.cpp:54-68` |
| After a partition longer than 10 minutes of simulated ledger time, assume all pre-partition validation sets are expired and budget a full re-acquisition. Do not shortcut from stale sets. | [CODE] `Validations.h:730-783` + [MODELLED] (the budget rule) |
| After any partition, re-verify the publisher lists before the next flag ledger. A stale or missing list can disable quorum at the next vote (`ValidatorList.cpp:1859-1896`). | [CODE] + [MODELLED] |
