# Decision memo

## Verdict

**A partition in this fork stalls validation on the minority side but
does not halt consensus, does not fork under an identical UNL, and
heals by hash-chained acquisition — except under divergent UNLs, where
both sides validate and a true fork persists until the UNLs
reconverge. The network has no explicit split-brain detector, so
operators must watch the emergent signals (validated-sequence stall,
preferred-ledger divergence, close-time drift, validation expiry) and
gate rejoins on quorum re-establishment, not on link restoration.**

## Reasoning

1. **The 67% quorum is the fork's defining number.** Validation quorum
   is `max(ceil(effectiveUNL*0.67), ceil(UNL*0.60))`
   (`ValidatorList.cpp:1845-1935`), the transaction-set consensus
   threshold is 67 (`ConsensusParms.h:79`), and the post-fix amendment
   threshold is 67/100 strictly greater (`SystemParameters.h:85`).
   Upstream documentation says 80% for all three; the pinned code
   says 67%. Any threshold, runbook, or monitoring rule built on 80%
   misdescribes this network. With 67%, a 7-of-10 side keeps
   validating; the halt band is 33–67% faulty, not the documented
   20–80%.
2. **Identical UNL: at most one side validates.** In 7 of the 10
   simulated scenarios the minority side closed ledgers but validated
   none (S-01: 40 closed / 0 validated; S-09: 200 / 0). Consensus
   keeps running on both sides via the stalled-dispute shortcut,
   MovedOn, and Expired/bow-out exits (`Consensus.cpp:106-270`), so
   "the network stopped" is the wrong mental model — validation
   stopped, consensus did not.
3. **Divergent UNLs: both sides validate.** S-04 is the exception
   that matters: with UNL sizes 8 and 7 and quorums 6 and 5, both
   sides quorum-validated all 40 ledgers, and the heal discarded 40
   validated ledgers. The code permits this (Theorem 8 bound,
   `ValidatorList.cpp:1898-1929`): two UNLs may share all but <33%
   of validators. UNL divergence is therefore the highest-severity
   partition risk in this fork, and it is invisible to link
   monitoring — only validation counts per side reveal it.
4. **Detection is emergent, and the signals work.** There is no
   split-brain detector in the code. The modelled signals fired
   correctly in every scenario: preferred-divergence at round 0,
   quorum-not-reached at round 0, validated-sequence stall within 3
   rounds, close-time drift to 120 s bins with the 0x01 flag (S-06),
   validation expiry at exactly rounds 45 / 75 / 150 (S-09). 46
   signals fired across 10 scenarios; none fired spuriously on a
   healthy side.
5. **Rejoin is cheap when peers hold the ledgers, bounded when they
   do not.** Across all scenarios: 485 ledgers discarded, 515
   refetched, 0 timeouts. The worst-case bound is (6+1) x 3 s = 21 s
   per ledger (`InboundLedger.cpp:44-74`, `366-413`). Budget rejoins
   on that bound, not on the observed 0-timeout runs.
6. **Amendments do not reconcile across a partition.** Each side
   counts only its own trusted validations; a side below quorum does
   not vote at all (S-05 side B: 3 < 7, vote skipped, clock frozen).
   The 2-week hold needs 302,400 ledgers at the modelled 4 s close,
   so no amendment can activate inside any short partition. The
   surviving majority timestamps are always the winning chain's.

## Recommended thresholds

| Threshold / gate | Recommended value | Basis |
|---|---|---|
| Detection: validated-sequence stall | Alert after 3 consecutive rounds with no validation advance | [MODELLED] on `checkAccept` (`LedgerMaster.cpp:898-945`); simulator fires `validated-seq-stalled` at 3 rounds |
| Detection: preferred-ledger divergence | Alert immediately when `getPreferred` != local LCL | [CODE] `Validations.h:850-899`, `Consensus.h:1119-1148`; simulator round 0 |
| Detection: close-time resolution | Alert when resolution >= 60 s sustained over 3+ rounds | [MODELLED] on `LedgerTiming.h:80-140`; S-06 reached 120 s |
| Detection: validation-set age | Warn at 180 s (LOCAL), alert at 300 s (WALL), critical at 600 s (SET_EXPIRES) | [CODE] `Validations.h:47-94`; S-09 crossed at rounds 45 / 75 / 150 |
| Detection: dual validation | Page immediately if two sides both validate at the same sequence | [CODE] `LedgerTrie.h:685-778`; S-04 is the only case and the highest-severity one |
| Rejoin gate 1: quorum re-established | Do not start rejoin procedures until trusted validations for the preferred ledger >= quorum | [MODELLED] on `ValidatorList.cpp:1845-1935` |
| Rejoin gate 2: preferred-ledger stability | Preferred ledger unchanged for 3 consecutive rounds before acquiring | [MODELLED] on `Validations.h:850-899` (prevents acquiring a chain that is itself about to switch) |
| Rejoin gate 3: fetch budget | Budget 21 s per missing ledger; escalate if a single ledger exceeds it | [CODE] `InboundLedger.cpp:366-413` |
| Monitoring cadence: validation counts | Every ledger close (per-round check of trusted validations vs quorum) | [MODELLED] on `LedgerMaster.cpp:898-945` |
| Monitoring cadence: publisher lists | Every refresh interval (default 5 min, `src/xrpld/app/misc/detail/ValidatorSite.cpp:34`); alert if >= `min(listThreshold_, N - listThreshold_ + 1)` publishers unavailable | [CODE] `ValidatorList.cpp:1845-1935` |
| Monitoring cadence: amendment votes | Every flag ledger (every 256 ledgers); alert if any side records a majority the other side does not | [MODELLED] on `AmendmentTable.cpp:847-941` |
| Monitoring cadence: UNL divergence | Every ledger close: compare the trusted validator set across sides; alert on any difference | [MODELLED] on `ValidatorList.cpp:1938-2131`; S-04 shows why |

## Trade-offs

- **67% vs 80% quorum.** Lower quorum buys liveness (a 7-of-10 side
  keeps validating where an 80% rule would stall it) and costs fork
  safety (the dual-validation window under UNL divergence widens, and
  the faulty share that can confirm an invalid ledger drops from 80%
  to 67%). This fork chose liveness; the monitoring above is the price
  of that choice.
- **Alerting on validated-sequence stall after 3 rounds vs 1.**
  1 round would catch stalls faster but fires on every transient
  round where quorum is momentarily missed (e.g. a slow validator);
  3 rounds matches the simulator's stalled-dispute horizon and
  avoids noise. The cost is up to ~12 s of detection delay at the
  modelled close time.
- **Rejoin gate 2 (3 stable rounds) vs immediate acquisition.**
  Immediate acquisition is faster but can chase a preferred ledger
  that switches again mid-fetch, wasting the 21 s per-ledger budget.
  3 rounds of stability costs ~12 s and avoids the chase.
- **Per-ledger monitoring vs sampled monitoring.** Per-ledger checks
  catch every stall but cost a check per close; sampling (e.g. every
  10th ledger) halves the cost and can miss a short partition
  entirely. For a network where a 5-ledger flap (S-03) is realistic,
  sampling is not recommended.

## What is modelled vs pinned-code-derived

- **Pinned-code-derived:** quorum formula, consensus/amendment
  thresholds, validation windows, close-time bins, inbound timeouts,
  flag-ledger interval, 2-week hold, preferred-ledger and
  wrong-ledger mechanisms, publisher-outage disable rule, the absence
  of an explicit detector. Every one of these is cited to file:line in
  `docs/claim-index.md` and excerpted in `fixtures/source-excerpts/`.
- **Modelled:** the detection signals themselves (definitions, not
  code events), the 3-round stall alert, the 3-round stability gate,
  the monitoring cadences, the modelled close time of 4 s/ledger, the
  simulated ledger hash (SHA-256 stand-in for the code's sha512Half),
  and the S-04 tip-hash tie-break (standing in for the LedgerTrie
  span-start-ID rule). The simulator's numbers (560 validated of 1,070
  closed, 46 signals, 485 discarded / 515 refetched) are simulator
  output, not measurements of postfiatd behaviour.

## Counts

- Findings: 12 (HIGH 3, MEDIUM 5, LOW 4), all VERIFIED against the
  simulator + pinned-code rule.
- Claims: 30 (VERIFIED 23, SPECIFIED 6, UNVERIFIED 0, UNTESTABLE 1).
- Risks: 14 (HIGH 3, MEDIUM 6, LOW 5).
- Gaps: 7.
- Drills: 29/29 checks PASS (A 10, B 4, C 3, D 2, E 3, F 2, G 2, H 2,
  T 1), each re-derived from `outputs/derived/scenario-results.json`.
