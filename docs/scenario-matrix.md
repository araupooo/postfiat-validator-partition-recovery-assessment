# Scenario matrix

All values labelled SIMULATED are trace-simulator output
(`outputs/derived/scenario-results.json`, seed 0). They model the
pinned-code rules; they are not measurements of postfiatd behaviour.
Pinned source throughout: postfiatd commit
`0085a1ff885d6a446369cf73a4430f75af22be55`.

Quorum rule (identical UNL of 10): `max(ceil(10*0.67), ceil(10*0.60)) = 7`
— `src/xrpld/app/misc/detail/ValidatorList.cpp:1845-1935`.
Modelled close time is 4 s/ledger in every scenario (an assumption:
close time is emergent in the code, there is no fixed 3–5 s constant —
`src/xrpld/consensus/Consensus.cpp:28-103`).

## S-01 — Minority/majority split 7/3 (40 ledgers)

| | Expected (pinned-code rule) | SIMULATED observed |
|---|---|---|
| Majority side A (7) | Collects 7 trusted validations, reaches quorum 7, validates every ledger (`LedgerMaster.cpp:898-945` checkAccept) | 40 closed, 40 validated |
| Minority side B (3) | Collects 3 < 7, never validates; consensus rounds keep running via stalled/MovedOn/Expired exits (`Consensus.cpp:177-270`) | 40 closed, 0 validated |
| Rejoin | Preferred-ledger divergence detected; B discards its chain, re-acquires A's (`Consensus.h:1063-1115`, `LedgerMaster.cpp:826-886`) | 40 discarded, 40 refetched, 0 timeouts, hashes reconciled |

## S-02 — Asymmetric reachability, one-way link (40 ledgers)

| | Expected (pinned-code rule) | SIMULATED observed |
|---|---|---|
| Side A (6), receives B's validations | 6 own + 4 from B = 10 visible >= quorum 7, validates (`RCLValidations.cpp:166-277`) | 40 closed, 40 validated |
| Side B (4), receives only its own | 4 < 7, stalls validation while consensus runs | 40 closed, 0 validated |
| Rejoin | B adopts A's chain | 40 discarded, 40 refetched, hashes reconciled |

## S-03 — Flapping links 5/5 (60 ledgers, 5 up / 5 down)

| | Expected (pinned-code rule) | SIMULATED observed |
|---|---|---|
| Link up (5-ledger windows) | Full 10-validator set, quorum 7, validates | 30 ledgers validated (6 up windows x 5) |
| Link down (5-ledger windows) | 5/5 split, neither side reaches quorum 7 | 0 validated in down windows; both sides closed 5 ledgers per window |
| Fork | No side ever validates alone, so no persistent fork | 0 dual-validated ledgers; 25 discarded / 25 refetched across 5 reconvergences |
| End state | Scenario ends mid-down-window | Sides still diverge at round 59; last validated ledger is round 54 (honestly unreconciled) |

## S-04 — UNL subset isolation, divergent UNLs (40 ledgers, 12 validators)

| | Expected (pinned-code rule) | SIMULATED observed |
|---|---|---|
| Side A trusts 8 (7 own + 1) | Quorum `max(ceil(8*0.67)=6, ceil(8*0.60)=5) = 6`; collects 7, validates (`ValidatorList.cpp:1845-1935`) | 40 closed, 40 validated |
| Side B trusts 7 (5 own + 2) | Quorum `max(ceil(7*0.67)=5, ceil(7*0.60)=5) = 5`; collects 5, validates | 40 closed, 40 validated |
| Fork | Both sides quorum-validate: a true dual-validated fork persists until UNLs reconverge (Theorem 8 bound, `ValidatorList.cpp:1898-1929`) | 80 validated total; at heal 40 validated ledgers discarded, 40 refetched, winner side A by tip-hash tie-break (modelled) |

## S-05 — Amendment-vote split across a flag ledger (60 ledgers)

| | Expected (pinned-code rule) | SIMULATED observed |
|---|---|---|
| Flag ledger 8283904 (`seq % 256 == 0`, `src/xrpld/app/ledger/Ledger.h:426`) | Voting on the pre-flag ledger; side A counts 7 trusted validations >= quorum 7, so it votes (`RCLConsensus.cpp:353-380`) | Flag ledger at round 4; side A trusted 7, yes 7 |
| Majority test (post-fix) | `votes > trusted*67/100`, strictly greater (`AmendmentTable.cpp:320-375`; `SystemParameters.h:85`) | 7 > 4.69: majority recorded, `tfGotMajority` |
| Minority side B | 3 trusted < quorum 7, so no vote at all; amendment clock freezes | Vote skipped; yes 1 recorded but not counted |
| Hold | 2 weeks = 1,209,600 s; at 4 s/ledger needs 302,400 ledgers (`SystemParameters.h:88`) | Hold not elapsed; amendment NOT enabled in either side |
| Rejoin | Surviving majority timestamps are side A's (only its chain is validated) | 60 discarded, 60 refetched, hashes reconciled |

## S-06 — Ledger-close stall with close-time drift (40 ledgers)

| | Expected (pinned-code rule) | SIMULATED observed |
|---|---|---|
| Majority side A (7) | Validates normally; close-time resolution refines every 8th agreeing ledger (`LedgerTiming.h:80-140`) | 40 closed, 40 validated, resolution 30 -> 10 s |
| Minority side B (3) | Close-time votes disagree internally (modelled clock drift); no 75% close-time consensus (`ConsensusParms.h:160`); resolution coarsens one bin per ledger; `sLCF_NoConsensusTime` (0x01) set (`LedgerHeader.h:82`; `RCLConsensus.cpp:494-504`) | 40 closed, 0 validated, resolution 30 -> 120 s, flag 0x01 on all 40 ledgers |
| Consensus | Rounds end via stalled-dispute shortcut / MovedOn / Expired, never via quorum (`Consensus.cpp:106-174`, `177-270`) | No deadlock: 40 rounds closed on both sides |

## S-07 — Single-validator isolation (30 ledgers)

| | Expected (pinned-code rule) | SIMULATED observed |
|---|---|---|
| Isolated validator 9 | 0 peers < minPeerCount: DISCONNECTED, consensus not ticked (`NetworkOPs.cpp:1049-1078`) | 0 ledgers closed, 0 validated |
| Remaining 9 | 9 >= quorum 7, validate every ledger | 30 closed, 30 validated |
| Rejoin | `handleWrongLedger` + InboundLedger acquisition, at most ~21 s per ledger (`InboundLedger.cpp:44-74`, `366-413`) | 0 discarded, 30 refetched, 0 timeouts, hashes reconciled |

## S-08 — Publisher outage disables quorum (30 ledgers, no partition)

| | Expected (pinned-code rule) | SIMULATED observed |
|---|---|---|
| Publishers | 2 of 3 unavailable >= `min(listThreshold_=2, 3-2+1=2)` (`ValidatorList.cpp:1845-1935`) | Quorum disabled (SIZE_MAX) from round 0 |
| Validation | Nothing validates anywhere, although all 10 validators are connected and agree | 30 closed, 0 validated |
| Recovery | `updateTrusted` recomputes quorum 7 when lists refresh (`ValidatorList.cpp:1938-2131`; refresh default 5 min, `src/xrpld/app/misc/detail/ValidatorSite.cpp:34`) | MODELLED recovery: quorum recomputed 7, validation resumes next close |

## S-09 — Validation-expiry cascade, long partition (200 ledgers, 800 s)

| | Expected (pinned-code rule) | SIMULATED observed |
|---|---|---|
| Majority side A (7) | Fresh validations inside every window, validates | 200 closed, 200 validated |
| Minority side B (3) | Pre-partition validations go stale: LOCAL 3 min (`Validations.h:149-166`), WALL 5 min, SET_EXPIRES 10 min sweep (`Validations.h:730-783`) | 200 closed, 0 validated |
| Expiry crossings | LOCAL at 180 s, WALL at 300 s, SET at 600 s; at 4 s/ledger rounds 45 / 75 / 150 | LOCAL round 45, WALL round 75, SET round 150; 3 pre-partition sets expired |
| Amendment | Flag ledger 8284160 inside the window: side A records majority, side B skips (below quorum) | Side A `tfGotMajority` (7 > 4.69); side B skipped |
| Rejoin | No usable pre-partition validation to shortcut from; full re-acquisition | 200 discarded, 200 refetched, hashes reconciled |

## S-10 — Rejoin hash-reconciliation race (40 ledgers)

| | Expected (pinned-code rule) | SIMULATED observed |
|---|---|---|
| Split | 7/3: majority validates, minority stalls | A 40/40, B 40/0 |
| Fork choice | Branch support picks the majority chain (`LedgerTrie.h:685-778`); loser stops proposing, replays proposals, acquires (`Consensus.h:1063-1115`) | Winner side A (7 vs 3 branch support) |
| Acquisition | One InboundLedger acquisition per ledger; 3 s timeout, 6 retries max, ~21 s worst case per ledger (`InboundLedger.cpp:44-74`, `366-413`) | 40 refetched, 0 timeouts; worst-case bound 40 x 21 s = 840 s if peers lacked the ledgers |
| Reconciliation | Parent-hash mismatch invalidates local ledgers (`LedgerMaster.cpp:826-886`); hash is the check, there is no separate reconcile function (`Ledger.cpp:54-68`) | 40 discarded, 0 minority ledgers survive as canonical, final hashes match |

## Totals (SIMULATED, seed 0)

- 10 scenarios, 580 ledger-rounds, 1,070 ledger objects stored.
- 560 ledgers validated, 6,010 validations counted, 46 detection signals fired.
- Rejoin totals: 485 ledgers discarded (40 of them validated, all in S-04), 515 refetched, 0 timeouts.
- 9 of 10 scenarios end reconciled; S-03 honestly ends unreconciled (scenario ends mid-down-window).
