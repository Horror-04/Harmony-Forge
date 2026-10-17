# S3.0 Phase 1 (d): per-function CCN for `src/inference/candidates.cpp`

Method: `py -3 -m lizard -l cpp` (lizard 1.24.1) — same method as
`docs/measurements/s0-lizard.csv` (header
`file,functions,nloc_total,ccn_max,ccn_mean,ccn_gt10,ccn_gt15`, where
`nloc_total` is the sum of per-function NLOC). Reproduced, not assumed:
(1) current lizard on `src/inference/constraints.cpp` gives 5 fns /
NLOC-sum 70 / max 19 / mean 7.0 / gt10 1 / gt15 1 — exactly the S0 row;
(2) lizard on `git show acef4de:src/inference/candidates.cpp` vs the
working tree differs only by the one intervening commit (6d0e7e3,
gen.h switch: +1 file NLOC, line numbers +1, all function CCNs
unchanged).

## Per-function table (current tree)

| function | lines | NLOC | CCN | note |
|---|---|---|---|---|
| `hf::infer::mod12` | 44 | 1 | 1 | |
| `hf::infer::fnv1a` | 47-54 | 8 | 2 | |
| `hf::infer::mix64` | 56-59 | 4 | 1 | |
| `hf::infer::stream_seed` | 61-69 | 9 | 1 | |
| `hf::infer::octave_pull` | 71-75 | 5 | 3 | |
| `hf::infer::snap_to_pcs` | 79-93 | 12 | 9 | |
| `hf::infer::scale_or_major` | 95-99 | 5 | 2 | |
| `hf::infer::is_minor_family` | 101-105 | 5 | 5 | |
| `hf::infer::tone_pcs` | 108-114 | 7 | 2 | |
| `hf::infer::compose_base` | 118-174 | 51 | **16** | EXCEPTION (>15) |
| `hf::infer::material_from_runner` | 186-197 | 12 | 3 | |
| `hf::infer::material_with_runner` | 200-208 | 9 | 3 | |
| `hf::infer::material_from_runner_with` | 215-225 | 11 | 2 | |
| `hf::infer::apply_candidate_transform` | 228-306 | 74 | **30** | EXCEPTION (>15) |
| `hf::infer::apply_mode` | 311-364 | 51 | **30** | EXCEPTION (>15) |
| `hf::infer::enforce_caps` | 367-386 | 20 | 7 | |
| `hf::infer::sampler_provider_cache` | 404-407 | 4 | 1 | |
| `hf::infer::sampler_provider_for` | 409-417 | 9 | 3 | |
| `hf::infer::sampling_unavailable_once` | 423-437 | 15 | 3 | |
| `hf::infer::production_sampler_cfg` | 446-456 | 11 | 1 | |
| `hf::infer::material_via_sampler_or_greedy` | 462-515 | 49 | 13 | |
| `hf::infer::generate_candidates_impl` | 522-591 | 37 | 9 | |
| `hf::infer::progression_for_params` | 595-619 | 25 | 7 | |
| `hf::infer::generate_candidates_with_runner` | 621-624 | 4 | 1 | |
| `hf::infer::generate_candidates` | 626-628 | 3 | 1 | |

Aggregate (s0-lizard.csv format):
`src/inference/candidates.cpp,25,441,30,6.24,4,3`
(25 functions, NLOC-sum 441, max 30, mean 156/25 = 6.24, gt10 4, gt15 3
— unchanged since S0 at the function level.)

## S3 ratchet-exceptions (CCN > 15 — move unchanged, CCN must not grow)

1. `compose_base` (`candidates.cpp:118-174`) — CCN 16.
2. `apply_candidate_transform` (`candidates.cpp:228-306`) — CCN 30.
3. `apply_mode` (`candidates.cpp:311-364`) — CCN 30.
