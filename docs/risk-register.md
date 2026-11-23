# Risk register

| ID | Severity | Risk | Evidence | Mitigation / note |
|----|----------|------|----------|-------------------|
| R-01 | HIGH | Divergent UNLs let both sides of a partition quorum-validate, creating a true dual-validated fork whose heal discards validated ledgers. | F-02, S-04 (40 validated ledgers discarded) | Monitor the trusted validator set per side every ledger close; alert on any difference. Never let two sides' UNLs diverge (see decision memo thresholds). |
| R-02 | HIGH | No explicit split-brain detector: a partition can persist undetected if nobody watches the emergent signals. | F-03, C-10 | Watch validated-sequence stall (3 rounds), preferred-ledger divergence (immediate), and close-time drift (>= 60 s); see playbook §1. |
| R-03 | HIGH | An amendment majority recorded on the losing side vanishes at heal; an operator acting on it (e.g. scheduling an upgrade) acts on a majority that never existed on the canonical chain. | F-05, S-05 | After any partition, re-read amendment majority timestamps from the adopted chain only; never carry over the discarded side's timestamps (playbook §2 step 7). |
| R-04 | MEDIUM | Closed-but-unvalidated ledgers can be mistaken for final by tooling that counts closes instead of validations. | F-04, S-01 (40 closed / 0 validated) | Treat only quorum-validated ledgers as final; check `checkAccept` advancement, not close counts. |
| R-05 | MEDIUM | The 67% quorum lowers the faulty share that can confirm an invalid ledger (67% vs upstream 80%) and shifts the halt band to 33–67% faulty. | F-01, C-01/C-02 | Do not quote upstream 80% safety figures for this fork; use 67% in every threshold and runbook. |
| R-06 | MEDIUM | Publisher outage freezes validation network-wide with no partition at all; the fault is invisible to link monitoring. | F-08, S-08 (0 of 30 validated) | Monitor publisher availability against `min(listThreshold_, N - listThreshold_ + 1)`; alert before quorum disables. |
| R-07 | MEDIUM | A partition longer than 10 minutes expires all pre-partition validation sets, forcing a full re-acquisition with no shortcut. | F-07, S-09 (sets swept at round 150) | After a >10-minute partition, budget a full re-acquisition; do not shortcut from stale sets (playbook §4). |
| R-08 | MEDIUM | Flapping links halve validation liveness (S-03: 30 of 60 ledgers validated) while producing no fork — the failure looks like slowness, not a split. | F-09, S-03 | Alert on validated-ledger rate, not just on peer/link state; a 50% validation rate with all peers up means flapping, not load. |
| R-09 | MEDIUM | Close-time drift desynchronises the two sides' ledger times (S-06: 30 s -> 120 s bins); downstream systems reading close times see inconsistent timestamps. | F-10, S-06 | Alert on close-time resolution >= 60 s sustained; check the `sLCF_NoConsensusTime` flag on healed ledgers. |
| R-10 | LOW | The modelled 4 s/ledger close time is an assumption; real close times are emergent and a slower network stretches every time-based threshold (expiry, hold) in ledger units. | Methodology assumptions | Re-derive round counts from measured close times before applying the S-09 expiry rounds (45/75/150) to a live network. |
| R-11 | LOW | The simulator hash is a SHA-256 stand-in, not the code's sha512Half; a hash mismatch in the simulator proves a model bug, not a code bug. | C-29 (UNTESTABLE) | Do not cite simulator hashes as ledger hashes; verify real ledgers with the sha512Half formula in `Ledger.cpp:54-68`. |
| R-12 | LOW | The fork-choice tie-break is modelled (larger tip hash) rather than the code's span-start-ID rule; a tied branch-support case could resolve differently in the code. | S-04, `LedgerTrie.h:685-778` | In a real dual-validated fork, read the trie decision from the node rather than trusting the simulator's tie-break. |
| R-13 | LOW | Negative-UNL divergence is unmodelled: the two sides can disagree about which validators are unreliable, changing effective quorum per side after heal. | C-25 (SPECIFIED) | After rejoin, confirm the negative UNL matches the healed network's view (playbook §2 step 8). |
| R-14 | LOW | A `--quorum` CLI override silently replaces the computed quorum and can validate a minority chain the healed network will discard. | C-30 (SPECIFIED) | Audit startup flags for `--quorum` on every validator; never use it to force validation during a partition. |

## Counts

- HIGH: 3
- MEDIUM: 6
- LOW: 5
- Total: 14
