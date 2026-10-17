# S3 remainder inventory (before slice 3; `candidates.cpp` post-slices-1-2)

Method: `py -3 -m lizard -l cpp` (1.24.1) + consumer grep this task.
NLOC/CCN per function; consumers decide the TU, not size.

## Per-function table (current lines)

| function | lines | NLOC/CCN | consumers (grep) | TU verdict |
|---|---|---|---|---|
| `fnv1a` | 47-54 | 8/2 | `stream_seed` only | facade (seed family) |
| `mix64` | 56-59 | 4/1 | `stream_seed` only | facade (seed family) |
| `stream_seed` | 61-69 | 9/1 | impl `:533`-area (mode-in-seed `:66` stays) | facade |
| `snap_to_pcs` | 73-87 | 12/9 | `apply_mode` only (`:171`) | modes TU-local (slice 3) |
| `scale_or_major` | 89-93 | 5/2 | impl (`:378`) + modes | `detail` inline (SPLIT consumer) |
| `is_minor_family` | 95-99 | 5/5 | `apply_mode` only (`:163`,`:174`) | modes TU-local (slice 3) |
| `material_from_runner` | 111-122 | 12/3 | impl (`:416`) | model (stage 4g) |
| `material_with_runner` | 125-133 | 9/3 | `material_from_runner_with` | model |
| `material_from_runner_with` | 140-150 | 11/2 | impl (`:414`) + tests (seam) | model |
| `apply_mode` | 160-213 | 51/30 | impl (`:423`-area) | modes (slice 3, exception) |
| `enforce_caps` | 216-235 | 20/7 | impl (`:423`) + arrangement comment (`:427`, no call) | facade (stage 8) |
| `sampler_provider_cache` | 253-256 | 4/1 | `sampler_provider_for` | model (ONNX-gated area) |
| `sampler_provider_for` | 258-266 | 9/3 | `material_via_sampler_or_greedy` | model |
| `sampling_unavailable_once` | 272-286 | 15/3 | same | model |
| `production_sampler_cfg` | 295-305 | 11/1 | same | model |
| `material_via_sampler_or_greedy` | 311-364 | 49/13 | impl (`:410`); holds `:497` | model (call-site TU) |
| `generate_candidates_impl` | 371-440 | 37/9 | public via `generate*` (70 lines) | FACADE (order lives here) |
| `progression_for_params` | 448-472 | 25/7 | impl + `arrangement.cpp:89` + `async_generate.cpp:45,54` + `ranking.cpp:98`; PUBLIC API (`candidates.h:29`) | facade TU, stays public |
| `generate_candidates_with_runner` | 474-477 | 4/1 | tests/seams; PUBLIC API | facade TU, stays public |
| `generate_candidates` | 479-481 | 3/1 | everyone; PUBLIC API | facade TU, stays public |

## Group sums (NLOC)

- Seed family (facade): 21. Mode helpers to modes: 17 (`snap` 12 + `is_minor` 5);
  `scale_or_major` 5 to `detail`. Material trio (model): 32.
- `apply_mode` (slice 3): 51. `enforce_caps` (facade): 20.
- Sampler/model group (model): 88 (4+9+15+11+49, incl. `:497`).
- Generate (facade): 37 + 25 + 4 + 3 = 69 (`impl` itself 70 lines).

## Facade-size verdict (answers the ≤150 question)

- `generate_candidates_impl` alone is 70 lines — the ORDER fits.
- Projected facade TU: impl 70 + enforce ~20 + seed family ~23 +
  `scale_or_major` via `detail` + progression/thins ~32 + includes/comments
  ≈ 150-170 lines. TIGHT against ≤150; measured call belongs pre-slice-4.
- Projected model TU: 32 + 88 ≈ 120 NLOC ≈ 160-190 lines ≤ 250. Holds
  `:497` + ONNX-gating, decided pre-slice-4 as its own commit (per plan).
- Nothing unplanned remains: every line is stage 0-9, a public API, or a
  named helper above. The ≤150 miss is composition (model group rides
  along), not hidden code.
