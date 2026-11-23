# Citations

Pinned source for all code citations: postfiatd commit
`0085a1ff885d6a446369cf73a4430f75af22be55` (2026-10-10, PR #50 merge).
Line numbers were verified with `grep -n` on a local checkout of that
commit. Excerpt files live in `fixtures/source-excerpts/` (E01–E36);
digests and blob SHAs are in `fixtures/source-hashes.json`.

## Pinned-source excerpts

| Excerpt file | Source file and lines | Subject |
|--------------|----------------------|---------|
| `E01.txt` | `src/xrpld/consensus/ConsensusParms.h` 79-114 | minCONSENSUS_PCT 67, close timing, abandon 120 s |
| `E02.txt` | `src/xrpld/consensus/ConsensusParms.h` 146-169 | Avalanche cutoffs, avCT 75%, avMIN/STALLED rounds |
| `E03.txt` | `src/xrpld/consensus/ConsensusParms.h` 175-201 | getNeededWeight avalanche state machine |
| `E04.txt` | `src/xrpld/consensus/Consensus.cpp` 28-103 | shouldCloseLedger |
| `E05.txt` | `src/xrpld/consensus/Consensus.cpp` 106-174 | checkConsensusReached |
| `E06.txt` | `src/xrpld/consensus/Consensus.cpp` 177-270 | checkConsensus: No / Yes / MovedOn / Expired |
| `E07.txt` | `src/xrpld/consensus/Consensus.h` 1169-1240 | phaseOpen |
| `E08.txt` | `src/xrpld/consensus/Consensus.h` 1367-1431 | phaseEstablish |
| `E09.txt` | `src/xrpld/consensus/Consensus.h` 1689-1805 | haveConsensus |
| `E10.txt` | `src/xrpld/consensus/Consensus.h` 1493-1685 | updateOurPositions (close-time avalanche) |
| `E11.txt` | `src/xrpld/consensus/Consensus.h` 1063-1115 | handleWrongLedger |
| `E12.txt` | `src/xrpld/consensus/Consensus.h` 1119-1148 | checkLedger |
| `E13.txt` | `src/xrpld/consensus/LedgerTiming.h` 35-53 | Close-time resolution bins |
| `E14.txt` | `src/xrpld/consensus/LedgerTiming.h` 80-128 | getNextLedgerTimeResolution |
| `E15.txt` | `src/xrpld/consensus/Validations.h` 47-94 | ValidationParms (WALL/LOCAL/EARLY/SET/FRESHNESS) |
| `E16.txt` | `src/xrpld/consensus/Validations.h` 149-166 | isCurrent three-window test |
| `E17.txt` | `src/xrpld/consensus/Validations.h` 624-707 | Validations::add (Byzantine checks) |
| `E18.txt` | `src/xrpld/consensus/Validations.h` 730-783 | Validations::expire |
| `E19.txt` | `src/xrpld/consensus/Validations.h` 850-899 | Validations::getPreferred |
| `E20.txt` | `src/xrpld/consensus/Validations.h` 936-960 | Validations::getPreferredLCL |
| `E21.txt` | `src/xrpld/consensus/LedgerTrie.h` 685-778 | LedgerTrie::getPreferred (branch support) |
| `E22.txt` | `src/xrpld/app/consensus/RCLValidations.cpp` 166-277 | handleNewValidation |
| `E23.txt` | `src/xrpld/app/consensus/RCLConsensus.cpp` 814-932 | Adaptor::validate |
| `E24.txt` | `src/xrpld/app/consensus/RCLConsensus.cpp` 353-380 | onClose flag-ledger gate |
| `E25.txt` | `src/xrpld/app/misc/detail/ValidatorList.cpp` 1845-1935 | calculateQuorum (67% formula) |
| `E26.txt` | `src/xrpld/app/misc/detail/ValidatorList.cpp` 1938-2131 | updateTrusted |
| `E27.txt` | `src/xrpld/app/misc/detail/AmendmentTable.cpp` 320-380 | computeThreshold + passes |
| `E28.txt` | `src/xrpld/app/misc/detail/AmendmentTable.cpp` 847-941 | doVoting (tfGotMajority / tfLostMajority) |
| `E29.txt` | `include/xrpl/protocol/SystemParameters.h` 80-88 | Amendment thresholds, 2-week hold |
| `E30.txt` | `src/xrpld/app/ledger/Ledger.cpp` 54-68 | calculateLedgerHash |
| `E31.txt` | `src/xrpld/app/ledger/detail/LedgerMaster.cpp` 898-945 | checkAccept (hash, seq) |
| `E32.txt` | `src/xrpld/app/ledger/detail/InboundLedger.cpp` 44-74 | Inbound-ledger constants |
| `E33.txt` | `src/xrpld/app/ledger/detail/InboundLedger.cpp` 366-413 | InboundLedger::onTimer |
| `E34.txt` | `src/xrpld/app/misc/NetworkOPs.cpp` 1049-1078 | processHeartbeatTimer peer-count gate |
| `E35.txt` | `src/xrpld/consensus/DisputedTx.h` 85-148 | DisputedTx::stalled |

## Docs (secondary sources — code wins on conflict)

Fetched 2026-11-23. The xrpl.org docs describe upstream rippled at
80% thresholds; this fork uses 67%. Any doc claim cited here is paired
with the pinned-code figure.

- Consensus protocol: https://xrpl.org/docs/concepts/consensus-protocol
  (fetched 2026-11-23; "Last updated 5 months ago" on the page).
  Claims 80% consensus, <20% faulty for progress, 20–80% halt band.
  Pinned code diverges: 67% (`ConsensusParms.h:79`), halt band 33–67%.
- Amendments: https://xrpl.org/docs/concepts/networks-and-servers/amendments
  (found via search 2026-11-23; "Last updated 1 month ago" on the page).
  Claims >80% support for 2 weeks, flag ledger every 256 ledgers.
  Pinned code diverges on % (67/100 post-fix, 204/256 pre-fix) and
  agrees on the 2-week window and the 256-ledger interval.
- Consensus percentages (secondary corroboration):
  https://medium.com/@cody.topp11/two-payments-one-balance-how-xrp-ledger-consensus-settles-the-argument-37cf71f54a9e,
  https://chainstack.com/what-is-xrp-ledger/,
  https://www.okx.com/learn/what-is-xrp-consensus-mechanism,
  https://academy.xrpl-commons.org/journeys/2026-july-university-of-zurich-uzh/modules/introduction-to-the-xrp-ledger
  — all state 80% consensus and 3–5 s closes; both figures diverge
  from / are not constants in the pinned code.
- Amendment voting, live status (upstream corroboration):
  https://dev.to/xrplto/xrpl-amendment-voting-check-the-live-status-of-every-amendment-3ihi,
  https://financefeeds.com/six-xrp-ledger-amendments-reach-end-of-two-week-validator-vote/,
  https://www.weex.com/learn/articles/xrp-upgrade-update-xrpl-batch-slips-to-oct-9-and-what-changes-x7xq9m7krr0ptjur8conz454
  — upstream 80% rule with a live 35-validator / 28-quorum anchor.
  These describe upstream rippled, not this fork.
- Theorem 8 (UNL overlap bound, cited in the pinned code's own
  comment at `ValidatorList.cpp:1898-1929`): Chase–MacBrough,
  arXiv:1802.07242.

## Absence checks

- "split-brain" / "fork detection" as a named concept: no function,
  flag, RPC field, or log line in the consensus or ledger code. The
  only "divergence" hit in the overlay is the untrusted-proposal drop
  at `src/xrpld/overlay/detail/PeerImp.cpp:1865-1870`.
- No `Validations.cpp` and no `InboundLedger.cpp` at the paths a
  reader might expect (`app/misc/`, `app/ledger/`); the real paths are
  `consensus/Validations.h` (header-only), `app/misc/detail/*`, and
  `app/ledger/detail/*`. No `LedgerConsensus` class exists.
