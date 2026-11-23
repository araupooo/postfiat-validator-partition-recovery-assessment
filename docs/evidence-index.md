# Evidence index

## Documents

| File | Contents |
|------|----------|
| `README.md` | Verdict, reproduction steps, file map, counts |
| `docs/decision-memo.md` | Verdict, reasoning, recommended thresholds, trade-offs, modelled-vs-derived split |
| `docs/scenario-matrix.md` | All 10 scenarios: expected vs SIMULATED-observed behaviour, traced to pinned source file:line |
| `docs/playbook.md` | Split-brain detection signals, safe rejoin procedure, ledger-hash reconciliation checks, rollback-protection rules |
| `docs/methodology.md` | Pinned source, simulator model + assumptions, measured-vs-simulated separation, reproduction steps |
| `docs/claim-index.md` | 30 claims with status and primary source |
| `docs/risk-register.md` | 14 risks with severity and mitigation |
| `docs/gap-register.md` | 7 gaps with what would close each |
| `docs/excerpts.md` | Short verbatim excerpts from primary sources with exact commit SHA + repo paths |
| `docs/citations.md` | Primary sources per claim (pinned files + docs URLs with fetch dates) |
| `docs/evidence-index.md` | This file |

## Code

| File | Contents |
|------|----------|
| `src/partition_sim.py` | Stdlib-only trace simulator: validator voting + ledger close under partition scenarios (deterministic, seed 0) |
| `scripts/drill.py` | 29 drill cases re-verifying simulator invariants from scenario-results.json |
| `scripts/extract_excerpts.py` | Verbatim pinned-source excerpts + `fixtures/source-hashes.json` |
| `scripts/run_all.sh` | Full suite: excerpts -> scenarios -> simulator -> drills -> digests |
| `scripts/clean_reproduce.sh` | Full fresh-environment reproduction check |
| `scripts/compare_reproduce.py` | Comparison checks between a fresh run and the shipped outputs |
| `scripts/verify_digests.sh` | `sha256sum -c SHA256SUMS` |
| `scripts/make_sha256sums.sh` | Regenerate `SHA256SUMS` |

## Simulator outputs (`outputs/`, unedited)

Simulator log: `outputs/sim-run.log`. Drill log: `outputs/drill-run.log`.
Reproduction evidence: `outputs/fresh-clone-*` and
`outputs/fresh-clone-compare.log`.

Derived: `outputs/derived/scenario-results.json` (10 scenarios, 1,070
ledger objects, full SHA-256 in `outputs/sim-run.log`),
`outputs/derived/drill-results.json` (29/29 PASS),
`outputs/derived/run-summary.json`, `outputs/derived/compare-results.json`
(fresh-clone comparison).

## Fixtures

`fixtures/source-excerpts/` holds 36 verbatim pinned-source excerpts
(E01–E36, see `docs/citations.md` for the list).
`fixtures/source-hashes.json` holds SHA-256 digests and git blob SHAs
for every cited source file (16 files). `fixtures/excerpts-manifest.json`
is the excerpt list the extractor runs from.

## Machine-readable summaries

| File | Contents |
|------|----------|
| `findings.json` | 12 findings with severity, status, evidence |
| `run-manifest.json` | Pinned commit, counts recomputed from the tables |
| `configs/scenarios.json` | The 10 scenarios with topology, partition, parameters, expected behaviour, and per-scenario pinned-code sources |
| `configs/scenarios.README.md` | Schema for `configs/scenarios.json` |
| `SHA256SUMS` | SHA-256 digests of every pack file except itself and `PACK-READY.md` |
