# Baseline scores — reading note (numbers only, Phase 9 Task 2C)

Scored with the Task 1 helpers (`evaluate.score_continuation`,
`evaluate.suffix_compliance`) over the frozen 33 val records.
ONNX-free / torch-free path. `v1_greedy` = reference numbers from the
committed `training/eval_report.json` (no re-run).

Methods: `kn` = `baselines.kn_continue(order=4)` (absolute-discounting
backoff over train flat ids, greedy, slot-valid argmax);
`theory` = `baselines.theory_continue` (prefix structure cycled,
Melody/Bass pitches scale-snapped + rub-safe).

## All-val (n=33)

| baseline  | mean_compliance | n_decodable | mean_suffix | n_suffix_scored |
|-----------|----------------:|------------:|------------:|----------------:|
| v1_greedy | 0.9071          | 32          | 0.3333      | 3               |
| kn        | 0.7892          | 33          | 0.6667      | 33              |
| theory    | 0.9431          | 33          | 1.0000      | 33              |

## Composed-only (n=4)

| baseline  | mean_compliance | n_decodable | mean_suffix | n_suffix_scored |
|-----------|----------------:|------------:|------------:|----------------:|
| v1_greedy | 0.5602          | 3           | 0.3333      | 3               |
| kn        | 0.5714          | 4           | 1.0000      | 4               |
| theory    | 0.8000          | 4           | 1.0000      | 4               |

## Procedural-only (n=29, group-split pair mate)

| baseline  | mean_compliance | n_decodable | mean_suffix | n_suffix_scored |
|-----------|----------------:|------------:|------------:|----------------:|
| v1_greedy | 0.9430          | 29          | n/a         | 0               |
| kn        | 0.8193          | 29          | 0.6207      | 29              |
| theory    | 0.9629          | 29          | 1.0000      | 29              |

Note: the GLM forecast that v1 may not beat theory-only on suffix is
recorded here as a forecast; the numbers above are reported as measured,
with no tuning of either baseline for or against it.
