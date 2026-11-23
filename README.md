# Validator Partition Recovery Assessment

## Verdict

**A partition in this fork stalls validation on the minority side but
does not halt consensus, does not fork under an identical UNL, and
heals by hash-chained acquisition — except under divergent UNLs, where
both sides validate and a true fork persists until the UNLs
reconverge. The network has no explicit split-brain detector, so
operators must watch the emergent signals and gate rejoins on quorum
re-establishment, not on link restoration.**

## Key numbers (SIMULATED, seed 0 — not measured postfiatd behaviour)

- Pinned source: postfiatd `0085a1ff885d6a446369cf73a4430f75af22be55`
  (2026-10-10, PR #50 merge).
- Validation quorum is 67%, not 80%:
  `max(ceil(effectiveUNL*0.67), ceil(UNL*0.60))` — 7 of 10.
  Consensus threshold 67; amendment threshold 67/100 strictly greater.
- 10 scenarios, 580 ledger-rounds, 1,070 ledger objects stored.
  560 ledgers validated, 6,010 validations counted, 46 detection
  signals fired.
- Rejoin totals: 485 ledgers discarded (40 of them validated, all in
  S-04), 515 refetched, 0 timeouts. Worst case 21 s per ledger.
- 9 of 10 scenarios end reconciled; S-03 honestly ends unreconciled
  (scenario ends mid-down-window).
- Amendment-vote split (S-05): majority side records `tfGotMajority`
  (7 yes > 4.69) at flag ledger 8283904; minority side does not vote
  at all (3 trusted < quorum 7); the 2-week hold needs 302,400
  ledgers at the modelled 4 s close and never elapses.
- Validation-expiry cascade (S-09): LOCAL crossed round 45, WALL
  round 75, SET_EXPIRES round 150; 3 pre-partition sets swept.
- Drills: 29/29 checks PASS (A 10, B 4, C 3, D 2, E 3, F 2, G 2, H 2,
  T 1), each re-derived from `outputs/derived/scenario-results.json`.
- Excerpts: 36 verbatim pinned-source excerpts, 16 source files,
  blob SHAs cross-checked against the GitHub API.

## Counts

- Findings: 12 (HIGH 3, MEDIUM 5, LOW 4), all VERIFIED against the
  simulator + pinned-code rule.
- Claims: 30 (VERIFIED 23, SPECIFIED 6, UNVERIFIED 0, UNTESTABLE 1).
- Risks: 14 (HIGH 3, MEDIUM 6, LOW 5).
- Gaps: 7.

## Reproduce

```bash
python3 src/partition_sim.py --all --seed 0   # trace simulator -> outputs/derived/scenario-results.json
python3 scripts/drill.py                       # 29 drill cases, exit 0 only if all pass
python3 scripts/extract_excerpts.py            # verbatim pinned-source excerpts + hashes
bash scripts/run_all.sh                        # full suite end to end
bash scripts/clean_reproduce.sh                # full fresh-environment check
bash scripts/verify_digests.sh                 # sha256sum -c SHA256SUMS
```

Only deterministic simulation runs. No live node, no RPC calls, no
transactions, no votes, no live key material, no credentials anywhere
in the pack.

## File map

- `README.md` — this file.
- `findings.json` — 12 findings with severity, status, evidence.
- `run-manifest.json` — pinned commit, counts recomputed from the tables.
- `docs/` — decision memo, scenario matrix, playbook, methodology,
  claim-to-evidence index, excerpts, citations, evidence index, risk
  register, gap register.
- `src/partition_sim.py` — stdlib-only trace simulator (deterministic,
  seed 0).
- `scripts/` — simulator runner, drill, excerpts, reproduce, compare,
  digests.
- `configs/scenarios.json` — the 10 scenarios with topology, partition,
  parameters, expected behaviour, and per-scenario pinned-code sources.
- `fixtures/source-excerpts/` — 36 verbatim pinned-source excerpts
  with file paths and grep-verified line numbers.
- `fixtures/source-hashes.json` — SHA-256 digests and git blob SHAs
  for every cited source file.
- `outputs/` — unedited simulator log, drill log, derived JSONs,
  fresh-clone reproduction evidence.
- `SHA256SUMS` — digests of every pack file except itself and the
  internal-only `PACK-READY.md`.
