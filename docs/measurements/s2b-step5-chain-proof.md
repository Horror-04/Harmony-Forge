# Step 5: spec→consumer chain proof (two-phase track-slot 5→4 scratch)

Throwaway branch `refactor/s2b-step5` (base `refactor/s2b-4b` = eb16110), deleted
after. `update_goldens.py` never ran (both phases); `lint_golden_pin` green in
both phases (frozen bitmap untouched throughout).

Shift: `training/vocab_spec.py` slot 2 (track) `hi: 6 → 5` — same boundary as
E2 (`s2entry_gate.json` check2_sensitivity). E2 reference values replicated
below: `python_shift_reddened_total` 37 = 34 (OFF,ON) seeds + 3 v2b seeds;
seed-1 (OFF,ON) scratch sha `d9232d43` vs banked `43d28496`.

## 0. Pre/post-shift state (all four re-verified after revert)

| value | pre-shift | post-scratch |
|---|---|---|
| `training/vocab_spec.py` sha256 | `ee59ab64…56b613a` | identical |
| `src/core/serialization/vocab_layout.gen.h` sha256 | `f1533f04…370d343` | identical |
| `tests/golden/manifest.json` sha256 | `fb1d56d5…30f49ca67` | identical |
| `git status` | 3 untracked dirs only (`.opencode/`, `external/pluginval/`, `training/ab_task6/`) | identical |
| `lint_golden_pin` | PASS (`d66faabd…`) | PASS |

## 1. Phase A (shift in spec only, `gen.h` banked, C++ binaries pre-shift)

| link | how it reddened | verdict |
|---|---|---|
| `--check` | RED: `STOP - spec-derived bitmap a3e5f025… != frozen pin d66faabd…` | ✅ expected |
| Python bitmap (`tools/tests/test_slot_bitmap.py`) | RED (3 failures) | ✅ expected |
| Python spec-read (`training/tests/test_tokenizer_spec_read.py`) | RED 2/6: `test_spec_read_matches_frozen_bitmap`, `test_spec_read_golden_sha` | ✅ expected (absolute pins) |
| Python 37-row spot (`test_matrix_spot_37_named_rows`) | GREEN | ⚠️ S3.0-list item 1 (blind by construction: probes + expectations both derived from live spec — coherence pin, not absolute pin) |
| Python aliases + count-head (`test_unchanged_aliases…`, `test_empty_prefix…`) | GREEN | ✅ correct (coherence preserved) |
| `test_gen_vocab_layout.py` | RED 2/5 (`test_check_passes_on_repo_files`, `test_two_writes_are_byte_identical` — both gated behind the pin refusal); stdlib/AST/file-path legs GREEN | ✅ expected |
| `test_update_goldens_refusal.py` / `test_golden_pin_lint.py` | GREEN / PASS | ✅ expected (frozen untouched) |
| C++ suite (`build-off` Debug, pre-shift binaries) | 176/176 GREEN | ✅ expected |
| `lint_golden_pin` | PASS | ✅ expected |

## 2. Phase B (gen.h regenerated + rebuilt; surgical diff: track-hi line 6→5 + comment lines only, caps 1024/6/170 untouched)

Compile: GREEN in `build-off` (Debug, full) and `build-full` (Release,
`dump_worker_ids` target) — no `static_assert` trap (asserts pin caps, shift
moves a slot bound). Runtime-test sensitivity therefore proven directly; no
second shift variant needed (refinement 1 not triggered).

| link | how it reddened | verdict |
|---|---|---|
| C++ bitmap (`#68 vocab layout header tables match the frozen bitmap`) | RED | ✅ expected |
| C++ tokenizer (`#66 decode_tokens matches the frozen slot bitmap exhaustively`) | RED | ✅ expected |
| sampler range pin (`#152`, contains `:459` `CHECK(hi == want[s][1])`) | RED (`4 == 5`) | ✅ expected |
| sampler fuzz (`#153 FSM fuzz: >=50 prefixes all decodable`) | RED | ✅ expected |
| golden multi-track (`#60`, fixture contains `tt=5` → `nullopt`) | RED | ✅ expected (downstream consumer; same as E2) |
| full Debug suite | 171/176, other 171 GREEN incl `#65` frozen-bitmap file, `#67` caps, `#69` count-head `-1→0..170`, `#161` OOB, `#154` empty-prefix, `#160` wiring | ✅ (greens analyzed below) |
| `-1→0..170` (`#69`), OOB (`#161`), empty-prefix (`#154`) | GREEN | ✅ verified-blind (shift outside their domain: `-1` head + invalid slots — Sonnet `[проверить]` closed, not gaps) |
| wiring (`#160`, contains `:752`) | GREEN | ⚠️ S3.0-list item 2 (pins determinism/fallback, not absolute bounds; reddens only on sampler↔codec incoherence per Task-2 G3 — coherent shift keeps sampler+codec in agreement) |
| sampler output-sha (128/128 via shifted Release `dump_worker_ids`; `sampler.obj` 23:46 > `gen.h` 23:33 proves shifted bounds linked in) | GREEN (128/128 identical) | ⚠️ S3.0-list item 3 — mechanism PROVEN, not inferred: all 128 outputs scanned, 1152 track-slot draws contain ZERO id-5 (`track5_scan.py` procedure). The Gate-4 fixture trajectories (fixed prefix `[1,0,0,1,60,4,4]`, mock model) never propose track 5, so the boundary is unexercised. The set still pins sampler↔codec coherence (G3) but not this bound. |
| build-full ONNX `ort_logits` tests (3, build-full-only) | NOT RUN | ⚠️ recorded with construction proof (`src/inference/ort_logits.cpp:38` consumes only `kVocabMaxTokens`; `tests/test_ort_logits.cpp` has zero slot references) — blind by construction to slot-bound shifts; S3.0 stage-sensitivity covers logits separately |
| `test_expected_errors.py` (2/2, tap-refusal live probe incl `linear_16` cause) | GREEN | ✅ expected (refusal precedes decode) |
| `lint_golden_pin` | PASS | ✅ expected |

## 3. Cube rows (Python legs via venv python torch 2.14.1 / ORT 1.31.0; C++ legs via both binaries)

| cells | live vs banked | verdict |
|---|---|---|
| `render_model` (OFF,ON) × E2's 34 seeds | 30 sha-diffs + 4 M1 ERROR→ok flips (17,27,36,52); seed-1 live `d9232d43…` == E2 recorded scratch sha | ✅ 34/34 E2 set replicated — **Phase A** (Python reads the spec; `gen.h`-independent: the C++ legs below are identical in both binary states, so these Python diffs belong to A) |
| `render_model` v2b (ON,ON) × seeds 0–31 (`training/v2b_s11.onnx`) | diffs exactly {6, 9, 22}; other 29 identical | ✅ E2 set replicated — **Phase A** (same reason) |
| `render_model` (OFF,OFF)+(ON,OFF) × seeds 1,3,5 (controls) | 6/6 identical | ✅ E2-consistent (greedy corners don't draw track 5) |
| S0 (ON,ON) ERROR × seeds 1,2,3 | identical tap refusal (modulo scratch-run interpreter path in argv; cause text proven by green `test_expected_errors`) | ✅ negative control |
| `render_midi` Release/old × seeds 0,1,5 × multi × Strict/Creative (OFF/OFF cells) | 12/12 identical | ✅ Phase-A C++ green |
| `render_midi` Debug/shifted × same 12 cells | 12/12 identical | ✅ Phase-B C++ zero-drift (E2 mechanism extended to the sampler-inclusive shift: composer emits tracks 0/1/2 only) |
| **total** | 30 + 4 + 3 = **37 vs E2's 37** | ✅ "37 строк с 37" matches (E2: `python_shift_reddened_total` 37) |

Cube-cell procedure: `cube_driver.py` (throwaway, deleted with branch) re-ran
banked cells via `tools/sha_matrix.py::run_render_{model,midi}` and compared
(bytes, sha256, status with temp-path normalization). NOTE: system python
lacks torch — a first driver pass ran under it and produced vacuous
(ERROR-status) diffs on torch-needing cells; valid results above are all from
the `training/.venv` python pass. `render_midi` cells are valid from both
passes (C++ only).

## 4. Revert proof

After `git checkout` of both files: 4/4 state values identical (§0),
`build-off` rebuilt → ctest 176/176 GREEN, `build-full dump_worker_ids`
rebuilt → ctest 199/199 GREEN, Python bitmap/spec-read/`--check` all GREEN.
The 5 Phase-B reds appear/disappear exactly with the shift — no other
contamination. `git status` clean (3 pre-existing untracked dirs only).

## 5. "Expected-red-but-green" list for S3.0 (no chain holes; absolute pins on both languages all reddened)

1. `test_matrix_spot_37_named_rows` — coherence pin, blind to coherent shifts by construction (§1). GUARD RULE: this spot is NOT spec-drift protection; drift is guarded by the frozen bitmap + `d66faabf` lint pin + the absolute red tests (Python bitmap/sha, C++ #66/#68, `--check`). Never cite the spot as drift defense.
2. wiring `#160`/`:752` — determinism/fallback pin; coherent-shift-blind, incoherence-sensitive (§2). CORRECTION (controller): the Phase-B red expectation for `:752` was erroneous — the test checks determinism and fallback, so a coherent shift correctly leaves it green; the test is right, the expectation was wrong.
3. output-sha 128-cell set — boundary-blind for track 5 (proven: 1152 draws, 0 hits); needs a boundary-hitting cell or stage-sensitivity coverage (§2). S4b BACKLOG: add a cell where the mock model puts mass on slot id 5 (non-blocking for S3: ranges frozen there; 4b's boundary cover stands on the sampler-copy bitmap-MATCH + #152).
4. build-full ONNX `ort_logits` trio — NOT RUN, basis: grep (`src/inference/ort_logits.cpp:38` consumes only `kVocabMaxTokens`; zero slot references in `tests/test_ort_logits.cpp`); construction-blind to slot-bound shifts (§2).
5. (Verified-blind, NOT gaps: `#69`/`#161`/`#154`, S0 ERROR rows, greedy corners, all `render_midi` rows.)
