# Verbatim excerpts

Short verbatim excerpts from the pinned source. Pinned source for
every excerpt: postfiatd commit
`0085a1ff885d6a446369cf73a4430f75af22be55` (2026-10-10, PR #50 merge).
Line numbers were verified with `grep -n` on a local checkout of that
commit. The full ranges live in `fixtures/source-excerpts/` (36 files,
E01–E36); digests and git blob SHAs are in
`fixtures/source-hashes.json`. Only short quotes are reproduced here;
the fixture files are authoritative.

## E01 — Consensus constants (`src/xrpld/consensus/ConsensusParms.h:79-114`)

> `std::size_t const minCONSENSUS_PCT = 67;`

> `std::chrono::milliseconds const ledgerMIN_CLOSE = std::chrono::seconds{2};`

> `std::chrono::milliseconds const ledgerABANDON_CONSENSUS = std::chrono::seconds{120};`

The transaction-set consensus threshold is 67, not the documented
80%. Close timing is bounded (2 s minimum close, 120 s abandon), not
fixed at 3–5 s.

## E02 — Avalanche cutoffs (`src/xrpld/consensus/ConsensusParms.h:146-160`)

The avalanche states require 50%, then 65%, then 70%, then 95%
yes-votes as the round runs long; close-time consensus is 75%
(`avCT_CONSENSUS_PCT`).

## E04 — Close decision (`src/xrpld/consensus/Consensus.cpp:28-103`)

`shouldCloseLedger` closes when more than half the previous round's
proposers have closed, at the end of the idle interval with no
transactions, or once the open time passes `ledgerMIN_CLOSE` and half
the previous round time — never on a fixed 3–5 s timer.

## E13 — Close-time resolution bins (`src/xrpld/consensus/LedgerTiming.h:35-53`)

> `std::chrono::seconds constexpr ledgerPossibleTimeResolutions[] = {`
> `    std::chrono::seconds{10},`
> `    std::chrono::seconds{20},`
> `    std::chrono::seconds{30},`
> `    std::chrono::seconds{60},`
> `    std::chrono::seconds{90},`
> `    std::chrono::seconds{120}};`

Default resolution is 30 s; the resolution coarsens on disagreement
and refines every 8th agreeing ledger (`getNextLedgerTimeResolution`,
`LedgerTiming.h:80-140`).

## E15 — Validation currency (`src/xrpld/consensus/Validations.h:47-94`)

> `std::chrono::seconds validationCURRENT_WALL = std::chrono::minutes{5};`
> `std::chrono::seconds validationCURRENT_LOCAL = std::chrono::minutes{3};`
> `std::chrono::seconds validationCURRENT_EARLY = std::chrono::minutes{3};`
> `std::chrono::seconds validationSET_EXPIRES = std::chrono::minutes{10};`
> `std::chrono::seconds validationFRESHNESS = std::chrono::seconds{20};`

## E16 — Currency test (`src/xrpld/consensus/Validations.h:149-166`)

> `return (signTime > (now - p.validationCURRENT_EARLY)) &&`
> `    (signTime < (now + p.validationCURRENT_WALL)) &&`
> `    ((seenTime == NetClock::time_point{}) ||`
> `     (seenTime < (now + p.validationCURRENT_LOCAL)));`

Three windows, not one deadline.

## E25 — Quorum formula (`src/xrpld/app/misc/detail/ValidatorList.cpp:1845-1935`)

> `// Use a 67% quorum to balance fork safety, liveness, and required UNL`
> `// overlap. Note: Original XRPL uses 80%, but this fork uses 67% for`
> `// devnet/testnet. For mainnet, this should be reverted to 80%.`

> `std::ceil(effectiveUnlSize * 0.67f), std::ceil(unlSize * 0.6f)));`

Effective quorum is `max(ceil(effectiveUNL*0.67), ceil(UNL*0.60))`. If
too many list publishers are unavailable, `calculateQuorum` returns
`SIZE_MAX` — quorum disabled, nothing validates.

## E27 — Amendment threshold (`src/xrpld/app/misc/detail/AmendmentTable.cpp:320-375`)

Pre-`fixAmendmentMajorityCalc` the test is `votes >= threshold` with
threshold `trusted*204/256`; post-fix it is `votes > threshold` with
threshold `trusted*67/100`. The code comment at `:366-371` still
narrates the old 80% story and is stale relative to the 67/100
constant in `SystemParameters.h:85`:

> `constexpr std::ratio<67, 100> postFixAmendmentMajorityCalcThreshold;`
> `constexpr std::chrono::seconds const defaultAmendmentMajorityTime = std::chrono::weeks{2};`

## E29 — Amendment constants (`include/xrpl/protocol/SystemParameters.h:80-88`)

See E27: post-fix ratio `67/100`, pre-fix ratio `204/256`, majority
hold `std::chrono::weeks{2}`.

## E31 — Validation gate (`src/xrpld/app/ledger/detail/LedgerMaster.cpp:898-945`)

> `valCount = validations.size();`
> `if (valCount >= app_.validators().quorum())`
> `    ...`
> `    mLastValidLedger = std::make_pair(hash, seq);`

A ledger becomes fully validated only when trusted validations reach
the validator-list quorum.

## E32 — Inbound-ledger constants (`src/xrpld/app/ledger/detail/InboundLedger.cpp:44-74`)

> `peerCountStart = 5`
> `ledgerTimeoutRetriesMax = 6`
> `auto constexpr ledgerAcquireTimeout = 3000ms;`

Plus `peerCountAdd = 3` per timeout and aggressive mode after 4
timeouts. One missing ledger costs at most ~21 s of fetching before
the node gives up on that hash (`onTimer`, `InboundLedger.cpp:366-413`).

## E21 — Fork choice (`src/xrpld/consensus/LedgerTrie.h:685-778`)

`LedgerTrie::getPreferred` walks spans while branch support exceeds
uncommitted support and picks the child with the largest branch
support at a branch, with the margin over the runner-up deciding
whether to commit. `tipSupport` counts validations for that ledger;
`branchSupport` counts validations for that ledger or any descendant.
