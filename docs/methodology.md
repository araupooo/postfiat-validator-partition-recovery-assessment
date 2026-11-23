# Methodology

## Pinned source

postfiatd commit `0085a1ff885d6a446369cf73a4430f75af22be55`
(2026-10-10, PR #50 merge). A local checkout at
`~/workspace/postfiatd-pin-0085a1f` was verified with
`git rev-parse HEAD` before any excerpt was taken. Every line number
in this pack was verified with `grep -n` on that checkout; no line
number was taken from a web fetch. `scripts/extract_excerpts.py`
re-derives all 36 excerpts from the checkout and records SHA-256
digests plus git blob SHAs in `fixtures/source-hashes.json` (16 source
files). Every cited file's blob SHA + size was cross-checked against
the GitHub API (repo `postfiatorg/postfiatd`, ref = pinned commit);
all 30 files in the research set matched (API size == local byte
count).

Real paths are used throughout. There is no
`src/xrpld/app/misc/Validations.cpp` and no
`src/xrpld/app/ledger/InboundLedger.cpp` in this tree: validations
live header-only in `src/xrpld/consensus/Validations.h`;
`AmendmentTable.cpp` / `ValidatorList.cpp` / `ValidatorSite.cpp` live
under `src/xrpld/app/misc/detail/`; `InboundLedger.cpp` /
`LedgerMaster.cpp` live under `src/xrpld/app/ledger/detail/`. There is
no `LedgerConsensus` class — the engine is the generic
`Consensus<Adaptor>` template plus the `RCLConsensus` adaptor.

## Simulator model

`src/partition_sim.py` (stdlib only, deterministic, seed 0) is a
trace simulator of validator voting + ledger close under 10 partition
scenarios (`configs/scenarios.json`, S-01..S-10). Per ledger round and
per side it models:

- **Validation counting.** Each validator validates its side's ledger
  each round; a side counts only the validations visible to it
  (partition, asymmetry, and flap visibility rules per scenario).
  A ledger is validated iff visible trusted validations >= quorum
  (`LedgerMaster.cpp:898-945` checkAccept).
- **Quorum.** `max(ceil(effectiveUNL*0.67), ceil(UNL*0.60))`
  (`ValidatorList.cpp:1845-1935`); disabled (SIZE_MAX) when
  unavailable publishers >= `min(listThreshold_, N - listThreshold_ + 1)`.
- **Consensus.** Within a side all members propose the same set, so
  agreement is 100% >= `minCONSENSUS_PCT` 67
  (`ConsensusParms.h:79`). A side below `minPeerCount_` peers is
  DISCONNECTED and closes nothing (`NetworkOPs.cpp:1049-1078`).
  Below-quorum sides keep closing ledgers via the stalled/MovedOn/
  Expired exits (`Consensus.cpp:106-270`); they never deadlock.
- **Close time.** Modelled close time is 4 s/ledger (an assumption;
  the code has no fixed close constant — `Consensus.cpp:28-103`).
  Close-time resolution starts at 30 s, refines one bin every 8th
  agreeing ledger, coarsens one bin per disagreeing ledger, over bins
  {10,20,30,60,90,120} (`LedgerTiming.h:35-53`, `80-140`). S-06 models
  internal close-time disagreement on the minority side; other
  scenarios model internal agreement. Close-time consensus is 75%
  (`ConsensusParms.h:160`); without it the `sLCF_NoConsensusTime`
  flag (0x01) is set (`LedgerHeader.h:82`).
- **Amendment voting.** At flag ledgers (`seq % 256 == 0`,
  `src/xrpld/app/ledger/Ledger.h:426`), voting runs only when trusted validations for the
  pre-flag ledger >= quorum (`RCLConsensus.cpp:353-380`). Majority is
  `votes > trusted*67/100`, strictly greater, post-fix
  (`AmendmentTable.cpp:320-375`; `SystemParameters.h:85`). Note: the
  code truncates the threshold to an integer (`(trusted*67)/100` by
  integer division, so trusted 7 gives threshold 4 and majority needs
  > 4); the simulator uses the float value (4.69) and the same
  strictly-greater comparison. Both give the same verdict for every
  trusted count in these scenarios (trusted 7 needs >= 5 yes votes
  either way). The 2-week
  hold is 1,209,600 s of ledger close time; at 4 s/ledger it needs
  302,400 ledgers and never elapses inside any scenario.
- **Validation expiry.** Pre-partition validation sets age in
  simulated seconds; LOCAL 3 min / WALL 5 min / EARLY 3 min
  (`Validations.h:47-94`, `149-166`) and the 10-minute set sweep
  (`Validations.h:730-783`) are evaluated per round (S-09).
- **Fork choice and rejoin.** Branch support (validated-ledger count,
  ties broken by larger tip hash — a modelled stand-in for the
  LedgerTrie span-start-ID rule, `LedgerTrie.h:685-778`) picks the
  winner; the loser discards its diverged ledgers and re-fetches the
  winner's, one InboundLedger acquisition per ledger, first attempt,
  0 timeouts, worst-case bound (6+1) x 3 s = 21 s per ledger
  (`InboundLedger.cpp:44-74`, `366-413`). Parent-hash mismatch
  invalidates local ledgers (`LedgerMaster.cpp:826-886`). There is no
  transaction replay on rejoin.
- **Detection signals.** The code has no explicit split-brain
  detector, so the simulator defines its own signals
  (preferred-divergence, validated-sequence stall, quorum-not-reached,
  operating-mode-disconnected, close-time-no-consensus,
  dual-validated-fork, validation expiry, publisher-quorum-disabled,
  amendment-majority-recorded, amendment-vote-skipped-below-quorum).
  These are modelled definitions, not code events.
- **Simulated ledger hash.** SHA-256 over (parent_hash, seq,
  close_time, resolution, close_flags, tx_count). The pinned code
  uses sha512Half over 10 fields (`Ledger.cpp:54-68`); the simulator
  hash is a stand-in chain link, and the drill recomputes it from the
  stored fields (C-01) rather than claiming it equals a real ledger
  hash.

## Assumptions

- Modelled close time 4 s/ledger for every scenario (within the
  emergent range implied by `ledgerMIN_CLOSE` 2 s and
  `ledgerIDLE_INTERVAL` 15 s; not a code constant).
- Validators inside a side always agree on the transaction set and
  (except S-06 minority) on close time; no Byzantine validators are
  modelled (no conflicting/multiple validations, no badSeq).
- The `fixAmendmentMajorityCalc` post-fix branch is modelled (67/100,
  strictly greater). Whether it is enabled depends on the feature-flag
  state of the ledger being voted on; the pre-fix branch (204/256,
  `>=`) is recorded in the drill (B-04) but not simulated.
- Negative-UNL membership is empty in every scenario; publisher lists
  are static except S-08.
- Rejoin assumes peers hold the winner's ledgers (first-attempt
  acquisition). The 21 s per-ledger worst case is a bound, not an
  observation.

## Measured vs simulated separation

Nothing in this pack was measured against a live postfiatd node. Every
"observed" value is SIMULATED output of the trace simulator, labelled
as such in `outputs/derived/scenario-results.json`, in
`outputs/sim-run.log`, and in every doc table. The only measured facts
are the pinned-code facts (verified by `grep -n` on the pinned
checkout and by blob-SHA cross-check against the GitHub API) and the
simulator's own determinism (same seed => byte-identical output,
verified by drill G-01 with full SHA-256 digests). Claims backed by
the simulator + a pinned-code rule are marked VERIFIED in
`docs/claim-index.md` with that qualification stated; code-only claims
are SPECIFIED; the one claim this pack cannot test is UNTESTABLE.

## Drills

`scripts/drill.py` runs 29 cases in 8 groups (A quorum arithmetic
per scenario, B amendment arithmetic, C hash-chain integrity, D
expiry-window arithmetic, E rejoin/fetch model, F close-time bins, G
determinism, H constants, T timing sanity). Every case re-derives its
invariant from `outputs/derived/scenario-results.json` instead of
trusting the stored values. The total drill elapsed time is measured
with `time.monotonic()` and only sanity-checked as non-negative; the
value is NOT recorded in any output file or log line, so drill outputs
stay byte-identical across runs and the reproduction comparison passes.
No timing value is ever compared exactly. Exit code is 0 only if every case
passes. Drill log: `outputs/drill-run.log`. Drill results:
`outputs/derived/drill-results.json`.

## Reproduction

```bash
bash scripts/run_all.sh         # excerpts -> scenarios -> simulator -> drills -> digests
bash scripts/clean_reproduce.sh # fresh-copy run + comparison (see outputs/fresh-clone-compare.log)
bash scripts/verify_digests.sh  # sha256sum -c SHA256SUMS
```

`scripts/clean_reproduce.sh` copies the pack to a throwaway
directory, drops all generated outputs, re-runs everything from
scratch via `scripts/run_all.sh`, and compares the fresh numbers with
the shipped ones via `scripts/compare_reproduce.py` (exit 0 only if
every comparison check passes). The fresh outputs are copied back as
`outputs/fresh-clone-*` and the comparison is recorded in
`outputs/fresh-clone-compare.log`. The simulator is deterministic
(no timestamps, no absolute paths, no measured timings in derived
outputs), so a second run produces byte-identical outputs and digests.

## Digests

`scripts/make_sha256sums.sh` writes `SHA256SUMS` over every pack file
except `SHA256SUMS` itself and the internal-only `PACK-READY.md`.
`scripts/verify_digests.sh` verifies them (`sha256sum -c`). All log
digests printed by the simulator and the drill are full 64-char
SHA-256 values.

## Boundaries

- No live node was run; no RPC calls were made; no transactions, no
  votes, no key material, no credentials anywhere in the pack.
- No upstream rippled checkout was available; upstream line numbers
  are not cited and no per-version diff against rippled 3.4.1 is
  claimed.
- The simulator does not model Byzantine validators, proposal replay
  contents, the full avalanche walk, negative-UNL voting, or the
  `--quorum` CLI override (see `docs/gap-register.md`).
- Docs describe upstream rippled at 80% thresholds; this fork uses
  67%. Where a doc claim conflicts with the pinned code, the code
  wins and the divergence is flagged (see `docs/citations.md`).
