# Claim-to-evidence index

Every claim in this pack, its status, its primary source, and the evidence
file that supports it. Status meanings: **VERIFIED** — checked against the
trace simulator run in this pack *and* the pinned-code rule it models
(simulator-backed claims are VERIFIED only against the simulator +
pinned-code rule, as stated per claim); **SPECIFIED** — defined by the
pinned code but not exercised by the simulator in this pack;
**UNVERIFIED** — no supporting evidence was obtained; **UNTESTABLE** —
the claim cannot be tested with the tooling in this pack.

| ID | Status | Claim | Primary source | Evidence |
|----|--------|-------|----------------|----------|
| C-01 | VERIFIED | Validation quorum is max(ceil(effectiveUNL*0.67), ceil(UNL*0.60)); for a 10-validator UNL the quorum is 7. Simulator + pinned-code rule. | `ValidatorList.cpp` `calculateQuorum`, lines 1845-1935 | `fixtures/source-excerpts/E25.txt`, `outputs/derived/scenario-results.json` (quorum 7 in S-01/02/03/05/06/07/09/10), drill A |
| C-02 | VERIFIED | Transaction-set consensus threshold minCONSENSUS_PCT is 67, not 80. Simulator + pinned-code rule. | `ConsensusParms.h:79` | `fixtures/source-excerpts/E01.txt`, `outputs/derived/scenario-results.json` (`constants.min_consensus_pct` 67), drill H-01 |
| C-03 | VERIFIED | Post-fix amendment threshold is trusted*67/100, strictly greater; S-05 side A records tfGotMajority with 7 yes > 4.69. Simulator + pinned-code rule. | `AmendmentTable.cpp:320-375`; `SystemParameters.h:85` | `fixtures/source-excerpts/E27.txt`, `E29.txt`, `outputs/derived/scenario-results.json` (S-05), drill B-01 |
| C-04 | VERIFIED | A flag ledger occurs every 256 ledgers; S-05 flag ledger is 8283904 and S-09 flag ledger is 8284160 (both seq % 256 == 0). Simulator + pinned-code rule. | `src/xrpld/app/ledger/Ledger.h:426` | `outputs/derived/scenario-results.json` (S-05, S-09 amendment events), drill H-02 |
| C-05 | VERIFIED | The 2-week amendment hold is 1,209,600 s of ledger close time; at the modelled 4 s/ledger it needs 302,400 ledgers and never elapses inside any scenario. Simulator + pinned-code rule. | `SystemParameters.h:88` | `fixtures/source-excerpts/E29.txt`, `outputs/derived/scenario-results.json` (hold_ledgers_needed 302400), drill B-03 |
| C-06 | VERIFIED | Validation currency windows are WALL 5 min, LOCAL 3 min, EARLY 3 min, SET_EXPIRES 10 min, FRESHNESS 20 s. | `Validations.h:47-94` | `fixtures/source-excerpts/E15.txt`, `outputs/derived/scenario-results.json` (`constants`) |
| C-07 | VERIFIED | S-09 expiry crossings match the windows exactly: LOCAL at round 45 (180 s), WALL at round 75 (300 s), SET_EXPIRES at round 150 (600 s); 3 pre-partition sets expired. Simulator + pinned-code rule. | `Validations.h:149-166`, `730-783` | `fixtures/source-excerpts/E16.txt`, `E18.txt`, `outputs/derived/scenario-results.json` (S-09 expiry), drill D-01/D-02 |
| C-08 | VERIFIED | Inbound-ledger acquisition costs at most ~21 s per ledger (initial + 6 retries at 3 s); every simulated rejoin completed with 0 timeouts. Simulator + pinned-code rule. | `InboundLedger.cpp:44-74`, `366-413` | `fixtures/source-excerpts/E32.txt`, `E33.txt`, `outputs/derived/scenario-results.json` (rejoin, all scenarios), drill E-01 |
| C-09 | VERIFIED | Close-time resolution bins are {10,20,30,60,90,120} s, default 30 s; S-06 minority coarsened to 120 s, majority refined to 10 s. Simulator + pinned-code rule. | `LedgerTiming.h:35-53` | `fixtures/source-excerpts/E13.txt`, `outputs/derived/scenario-results.json` (S-06), drill F-01/F-02 |
| C-10 | VERIFIED | There is no explicit split-brain/fork detector in the pinned code; detection is emergent (preferred-ledger comparison, quorum-gated validation advance, operating mode). The simulator's 46 detection signals are modelled definitions, not code events. | grep over consensus/ledger/overlay code; `src/xrpld/overlay/detail/PeerImp.cpp:1865-1870` (only "divergence" hit) | `docs/playbook.md` §1, `outputs/derived/scenario-results.json` (46 signals) |
| C-11 | VERIFIED | A below-quorum side keeps running consensus rounds (stalled/MovedOn/Expired exits) while validation stalls: S-01 minority closed 40 ledgers and validated 0. Simulator + pinned-code rule. | `Consensus.cpp:106-174`, `177-270` | `fixtures/source-excerpts/E05.txt`, `E06.txt`, `outputs/derived/scenario-results.json` (S-01), drill A-S-01 |
| C-12 | VERIFIED | checkAccept advances the last-validated ledger only when trusted validations >= quorum; a minority side's validated sequence stalls within 3 rounds. Simulator + pinned-code rule. | `LedgerMaster.cpp:898-945` | `fixtures/source-excerpts/E31.txt`, `outputs/derived/scenario-results.json` (validated-seq-stalled signals) |
| C-13 | VERIFIED | The UNL does not shrink on partition; each side keeps trusting the whole UNL unless a publisher list expires or is refreshed. Simulator + pinned-code rule. | `ValidatorList.cpp:1938-2131` | `fixtures/source-excerpts/E26.txt`, `outputs/derived/scenario-results.json` (per-side UNL unchanged) |
| C-14 | VERIFIED | Divergent UNLs allow dual validation: S-04 both sides quorum-validated all 40 ledgers (quorums 6 and 5), and the heal discarded 40 validated ledgers. Simulator + pinned-code rule. | `ValidatorList.cpp:1845-1935` (Theorem 8 bound) | `fixtures/source-excerpts/E25.txt`, `outputs/derived/scenario-results.json` (S-04), drill C-03 |
| C-15 | VERIFIED | Preferred-ledger branch support picks the majority chain at heal; 9 of 10 scenarios end with one final hash (S-03 honestly ends unreconciled). Simulator + pinned-code rule. | `LedgerTrie.h:685-778`; `Validations.h:850-899` | `fixtures/source-excerpts/E21.txt`, `E19.txt`, `outputs/derived/scenario-results.json`, drill C-02 |
| C-16 | VERIFIED | Rejoin is hash-chained acquisition + parent-hash invalidation, not transaction replay: 485 ledgers discarded, 515 refetched across the scenarios. Simulator + pinned-code rule. | `LedgerMaster.cpp:826-886`; `Ledger.cpp:54-68` | `fixtures/source-excerpts/E30.txt`, `outputs/derived/scenario-results.json` (rejoin totals), drill E-01 |
| C-17 | VERIFIED | Publisher outage disables quorum (SIZE_MAX): S-08 validated 0 of 30 ledgers with all validators connected. Simulator + pinned-code rule. | `ValidatorList.cpp:1845-1935` | `fixtures/source-excerpts/E25.txt`, `outputs/derived/scenario-results.json` (S-08) |
| C-18 | VERIFIED | listThreshold_ is a majority of publishers (size/2+1); with 3 publishers it is 2. | `ValidatorList.cpp:197-216` | `outputs/derived/scenario-results.json` (S-08 parameters), `fixtures/source-excerpts/E36.txt` |
| C-19 | VERIFIED | A single isolated validator is DISCONNECTED (below minPeerCount), closes nothing, and rejoins cleanly by acquiring the majority chain (S-07: 0 closed, 30 refetched). Simulator + pinned-code rule. | `NetworkOPs.cpp:1049-1078` | `fixtures/source-excerpts/E34.txt`, `outputs/derived/scenario-results.json` (S-07), drill E-03 |
| C-20 | VERIFIED | Asymmetric reachability: the side receiving both sides' validations validates (S-02 side A 40/40 with 10 visible), the other side stalls (40/0 with 4 visible). Simulator + pinned-code rule. | `RCLValidations.cpp:166-277` | `fixtures/source-excerpts/E22.txt`, `outputs/derived/scenario-results.json` (S-02) |
| C-21 | VERIFIED | Flapping 5/5 links cost liveness without forking: S-03 validated 30 of 60 ledgers (up windows only) and no side validated alone. Simulator + pinned-code rule. | `ValidatorList.cpp:1845-1935` (quorum 7 unreachable by 5) | `outputs/derived/scenario-results.json` (S-03), drill A-S-03 |
| C-22 | VERIFIED | Amendment voting is skipped entirely on a below-quorum side (S-05 side B: 3 trusted < quorum 7); its amendment clock freezes. Simulator + pinned-code rule. | `RCLConsensus.cpp:353-380` | `fixtures/source-excerpts/E24.txt`, `outputs/derived/scenario-results.json` (S-05), drill B-02 |
| C-23 | VERIFIED | S-06 minority ledgers all carry the sLCF_NoConsensusTime flag (0x01) once close-time consensus fails. Simulator + pinned-code rule. | `LedgerHeader.h:82`; `RCLConsensus.cpp:494-504` | `outputs/derived/scenario-results.json` (S-06), drill F-02 |
| C-24 | SPECIFIED | A lone validator reaches consensus only after ledgerMAX_CONSENSUS (15 s) has passed (checkConsensusReached total == 0 rule). | `Consensus.cpp:106-174` | `fixtures/source-excerpts/E05.txt` — the simulator models isolation as DISCONNECTED and does not exercise the alone path |
| C-25 | SPECIFIED | Negative-UNL votes can diverge per side: a partitioned side can vote "offline" a validator that is merely unreachable from that side. | `NegativeUNLVote.cpp:33-108`, note at `:301` | No scenario exercises negative-UNL voting (membership empty in all scenarios) |
| C-26 | SPECIFIED | Avalanche required yes-vote % rises 50 -> 65 -> 70 -> 95% with round time; close-time consensus is 75%. | `ConsensusParms.h:146-160` | `fixtures/source-excerpts/E02.txt` — the simulator models the close-time 75% rule only via the S-06 flag, not the full avalanche walk |
| C-27 | SPECIFIED | ValidatorSite refreshes publisher lists on a default 5-minute interval. | `src/xrpld/app/misc/detail/ValidatorSite.cpp:34` | S-08 recovery is modelled, not timed |
| C-28 | SPECIFIED | handleWrongLedger replays stored proposals when switching to the preferred ledger. | `Consensus.h:1063-1115`, `1152-1168` | `fixtures/source-excerpts/E11.txt` — the simulator models the switch, not proposal replay contents |
| C-29 | UNTESTABLE | Real-ledger sha512Half hash recomputation against live postfiatd ledger headers. | `Ledger.cpp:54-68` | No live ledger headers were fetched in this pack; the simulator uses a SHA-256 stand-in hash, recomputed by drill C-01 from the stored fields |
| C-30 | SPECIFIED | A --quorum command-line override replaces the computed quorum (with a warning). | `ValidatorList.cpp:1850-1857` | `fixtures/source-excerpts/E25.txt` — not exercised by any scenario |

## Counts

- VERIFIED: 23
- SPECIFIED: 6
- UNVERIFIED: 0
- UNTESTABLE: 1
- Total: 30
