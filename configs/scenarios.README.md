# configs/scenarios.json — schema

`configs/scenarios.json` lists the 10 partition scenarios (S-01..S-10)
run by `src/partition_sim.py --all`. The file is a placeholder scaffold:
every scenario entry is structurally valid but its values are TODOs for
the harness builder to fill. `scripts/run_all.sh` validates the schema
on every run (10 entries, ids S-01..S-10 unique, all fields present
with the types below); it does not check that the values are filled in.

## Top level

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer | Schema version, currently 1. |
| `pinned_commit` | string | postfiatd commit the scenarios were derived from: `0085a1ff885d6a446369cf73a4430f75af22be55`. |
| `default_seed` | integer | Default `--seed` for deterministic runs. |
| `_note` | string | Human note; ignored by tooling. |
| `scenarios` | array of 10 objects | The scenarios, ids S-01..S-10. |

## Scenario object

| Field | Type | Meaning |
|---|---|---|
| `id` | string | `S-01` .. `S-10`, unique. |
| `name` | string | Short scenario name. Placeholder: `TODO: scenario S-NN name`. |
| `topology` | object | Validator set and links. `validator_count` (integer, placeholder 0), `links` (array of `[a, b]` validator-index pairs, placeholder `[]`), `note` (string, TODO). |
| `partition` | object | How the network is split. `sides` (array of arrays of validator indices, placeholder `[]`), `note` (string, TODO). |
| `duration_ledgers` | integer | Partition duration in ledgers. Placeholder 0. |
| `parameters` | object | Simulator parameters for this scenario (timeouts, thresholds, flags). Placeholder `{}`. |
| `expected_behavior` | string | The pass criterion for this scenario, in words. Empty string until the harness builder fills it; an empty `expected_behavior` means the scenario has no pass criterion yet and the simulator must not claim a pass for it. |

## Filling in a scenario

Replace each TODO value with the real value; keep the field types.
Do not rename fields and do not drop `expected_behavior` — leave it as
`""` rather than deleting it if the criterion is not yet known. After
filling in, run `bash scripts/run_all.sh` to re-validate.
