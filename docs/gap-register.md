# Gap register

Gaps are things this pack could not establish. They are recorded here
rather than papered over; each one names what would close it.

| ID | Gap | What would close it |
|----|-----|---------------------|
| G-01 | No live postfiatd node was run. Every "observed" value in this pack is simulator output, not a measurement of postfiatd behaviour. | Run the 10 scenarios against a live multi-validator testnet (or a local multi-node devnet) and compare validated counts, close times, and rejoin timings with the simulated values. |
| G-02 | No live ledger headers were fetched, so real sha512Half ledger-hash recomputation was not demonstrated (C-29 UNTESTABLE). | Fetch ledger headers from a live node and recompute hashes with the `Ledger.cpp:54-68` formula; compare with the simulator's SHA-256 stand-in chain. |
| G-03 | The full avalanche walk (50 -> 65 -> 70 -> 95%) is not simulated; only the 75% close-time rule is exercised (S-06 flag). | Extend the simulator with per-dispute vote tracking and avalanche state transitions per `ConsensusParms.h:146-201`. |
| G-04 | Negative-UNL voting is not exercised (membership empty in all scenarios), so per-side negative-UNL divergence is unmodelled. | Add a scenario with a validator voted onto the negative UNL on one side only and measure the effective-quorum split. |
| G-05 | Proposal replay contents on wrong-ledger recovery are not modelled; the simulator models the switch, not what is replayed. | Instrument `playbackProposals` (`Consensus.h:1152-1168`) on a live node during a rejoin and record which proposals survive. |
| G-06 | The alone-validator consensus path (consensus only after ledgerMAX_CONSENSUS 15 s) is not exercised; S-07 models isolation as DISCONNECTED instead. | Add a scenario with a single validator above minPeerCount (e.g. peered only to non-validators) and measure its close cadence. |
| G-07 | No per-version diff against upstream rippled 3.4.1 was done; no upstream checkout was available in this environment. | Check out rippled 3.4.1 and diff the consensus/validation/amendment files against the pinned tree line by line. |

## Counts

- Total: 7
