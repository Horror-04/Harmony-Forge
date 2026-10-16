# S0 test matrix: "21 tests only in Release" disentangled

Baseline tag: `refactor/s0-baseline` (commit a813afc). Full name lists:
`s0-tests-release.txt` (build-full) and `s0-tests-debug.txt` (build-off).

## Configurations (three axes, not one)

| build dir | HARMONY_FORGE_BUILD_PLUGIN | HARMONY_FORGE_WITH_ONNX | ctest config run | tests in `ctest -N` | result |
|---|---|---|---|---|---|
| build-full | ON | ON (ORT C++ 1.22.0) | Release | 193 | 193/193 pass, wall 22.3 s |
| build-off | OFF | OFF (offline stub) | Debug | 170 | 170/170 pass, wall 7.0 s |

The 23-test delta is FULLY explained by the two CMake options. The
Release-vs-Debug axis contributes **zero**: no test source contains
`NDEBUG`/`_DEBUG`/config conditionals (grepped `tests/*.cpp`), and both
suites are green.

## Delta attribution (24 full-only, 1 off-only, net 23)

24 tests exist only in build-full (`ctest -N` diff, `=>` side):

| group | tests | gate | binaries |
|---|---|---|---|
| plugin-ON only | 21 | `if(HARMONY_FORGE_BUILD_PLUGIN)` in tests/CMakeLists.txt | test_chordtrack_pin (2), test_keyboard_moves (9), test_focus_resize (4), test_preview_synth (2), test_plugin_state (4) |
| ONNX-ON only | 3 | `#ifdef HARMONY_FORGE_WITH_ONNX` in tests/test_ort_logits.cpp:141 | test_ort_logits: argmax-matches-greedy, loads-once, fill-failure-per-call |

1 test exists only in build-off (`<=` side): `ort logits unavailable
without ORT (offline stub)` — the `#else` branch of the same `#ifdef`
(tests/test_ort_logits.cpp:191).

So "21 tests only in Release" = the 21 plugin-gated tests. They are not
Release-gated; they would run identically in a Debug+plugin-ON build
(not configured in this repo). The remaining net-2 delta is the ONNX
option (+3 with / -1 without in test_ort_logits: 6 vs 4 cases).

## Per-binary counts (from `*-b12d07c_tests.cmake` discovery files)

| binary | full | off | note |
|---|---|---|---|
| test_analysis | 16 | 16 | |
| test_arrangement | 7 | 7 | |
| test_async_generate | 6 | 6 | |
| test_candidates | 6 | 6 | |
| test_chordtrack_pin | 2 | 0 | plugin-ON only |
| test_constraints | 8 | 8 | |
| test_explain | 9 | 9 | |
| test_focus_resize | 4 | 0 | plugin-ON only |
| test_inference | 5 | 5 | |
| test_keyboard_moves | 9 | 0 | plugin-ON only |
| test_keynorm | 11 | 11 | |
| test_memo_filter | 12 | 12 | |
| test_midi_read | 12 | 12 | |
| test_model_preview | 6 | 6 | |
| test_note_cues | (5 built, 0 registered) | — | plugin-ON only; deliberately NOT in `ctest -N` (headless drawText teardown crash, see tests/CMakeLists.txt) |
| test_ort_logits | 6 | 4 | ONNX option switches 3 real vs 1 stub case |
| test_plugin_state | 4 | 0 | plugin-ON only |
| test_preview_synth | 2 | 0 | plugin-ON only |
| test_reference_analyze | 4 | 4 | |
| test_sampler | 16 | 16 | |
| test_selection | 16 | 16 | |
| test_theory | 18 | 18 | |
| test_tokenizer | 14 | 14 | |
| test_visual_polish | (3 built, 0 registered) | — | plugin-ON only; deliberately NOT in `ctest -N` (same headless cause) |
| test_memo_e2e | 0 registered | 0 registered | real-model nightly material; `[.]` tag, never in `ctest -N` |
| ctest total | 193 | 170 | built-but-unregistered binaries excluded |

## Open questions for plan refinement (not resolved in S0)

- No Debug+plugin-ON or Release+plugin-OFF build dir exists, so
  plugin-ON/OFF vs Release/Debug separation is by code reading + discovery
  files, not by a 2x2 build matrix. If a later stage needs the
  interaction term measured, add the two missing configure presets.
- TSan/RTSan need Linux/clang runners: document as CI-later, do not
  attempt on Windows/MSVC (per controller decision).
- Runtime allocation counters inside processBlock need code hooks
  (explicitly OUT for S0; S5+ item).
