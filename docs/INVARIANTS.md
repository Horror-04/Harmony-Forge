# Harmony Forge invariants

Every invariant below binds to test names verified present in `ctest -N`
(build-full/Release, 193 tests; build-off/Debug, 170 tests) and to the CI
job `build-test-validate` (`.github/workflows/ci.yml`). No aspirational
references: a binding names only tests and jobs confirmed to exist.

CI job for all five: `build-test-validate` (runs-on windows-2022).
Relevant steps: `Test` (`ctest --test-dir build -C Release
--output-on-failure`), `Determinism proof (render_midi byte-identity)`
(seed-7 double render + `fc /b`), `Validate VST3 (strictness 5)`.

## INV-1: No heavy work on the real-time audio thread

Neural inference, allocation, locks, and file I/O never run in
`PluginProcessor::processBlock`. Audio reads pre-generated MIDI from a
lock-free ring buffer; generation runs on background workers.
Sources: SPEC section 11, THREADING_MODEL.md.

| bound test | binary | suites |
|---|---|---|
| fake-latency runner proves the flow is non-blocking | test_async_generate | full + off |
| async completion is bit-identical to the sync path | test_async_generate | full + off |
| preview synth renders audible tone while held | test_preview_synth | full only (plugin-ON) |
| preview synth decays after noteOff | test_preview_synth | full only (plugin-ON) |

CI: `build-test-validate`, steps `Test` + `Validate VST3 (strictness 5)`.

## INV-2: Deterministic generation (same inputs -> byte-identical outputs)

Fixed seeds and parameters reproduce outputs exactly, end to end.

| bound test | binary | suites |
|---|---|---|
| same seed gives bit-identical candidates | test_candidates | full + off |
| all modes are deterministic and capped | test_candidates | full + off |
| model path threads into generation deterministically | test_async_generate | full + off |
| memo filter is deterministic | test_memo_filter | full + off |

CI: `build-test-validate`, step `Determinism proof (render_midi
byte-identity)` (render_midi seed-7 twice + binary compare).

## INV-3: Both suites stay fully green (refactor behavior gate)

`ctest` passes 193/193 in build-full/Release and 170/170 in
build-off/Debug. The 23-test delta is option-gated only (plugin-ON adds
21, ONNX-ON adds a net 2 in test_ort_logits); Release-vs-Debug
contributes zero. Evidence: docs/measurements/s0-test-matrix.md.
Deliberately unregistered binaries are NOT part of this gate:
test_note_cues and test_visual_polish (headless drawText teardown crash,
see tests/CMakeLists.txt) and test_memo_e2e (nightly-only `[.]` tag).

| bound test | binary | suites |
|---|---|---|
| (entire registered set: all 193 / 170 names in `ctest -N`) | all | full + off |
| keynorm flag-off generate path is bit-identical to pre-task output | test_keynorm | full + off |
| arrangement build is deterministic | test_arrangement | full + off |

CI: `build-test-validate`, step `Test`.

## INV-4: Memo-filter policy (SPEC section 10)

The shipped C++ path enforces the eval-time memo-ban: first run of >= 4
consecutive memorized 8-windows is cut before the completing token and
repaired to whole notes; drums are excluded and reattached byte-identical;
clean input passes through untouched; empty/missing index is a safe no-op;
same Pattern + same index gives identical results; never throws; file I/O
restricts it to background threads.

| bound test | binary | suites |
|---|---|---|
| verbatim run is truncated at the offending window | test_memo_filter | full + off |
| clean generation passes through byte-identical | test_memo_filter | full + off |
| missing index file loads nullopt and never throws | test_memo_filter | full + off |
| memo filter is deterministic | test_memo_filter | full + off |
| drums are untouched by the memo filter | test_memo_filter | full + off |
| loader round-trips the binary format and rejects garbage | test_memo_filter | full + off |
| committed training index loads (smoke) | test_memo_filter | full + off |
| index path resolves to sibling, bare names to the working dir | test_memo_filter | full + off |
| wired path truncates reciting model output, stays deterministic | test_memo_filter | full + off |
| wired path without sibling index is byte-identical | test_memo_filter | full + off |
| override with empty path filters via the working dir | test_memo_filter | full + off |
| bare model filename resolves via the working dir | test_memo_filter | full + off |
| sampler memo block run=2 turns away from recitation | test_sampler | full + off |
| sampler reuses the shipped memo index loader | test_sampler | full + off |

CI: `build-test-validate`, step `Test`.

## INV-5: Byte-level SMF export fidelity

MIDI file export round-trips exactly and clamps hostile input instead of
emitting corrupt files. (FL_SMOKE.md: with no FL licence on the dev
machine, this ctest layer is the export-path coverage.)

| bound test | binary | suites |
|---|---|---|
| smf1 round-trips sequential starts and durations | test_selection | full + off |
| smf1 round-trips overlapping chord notes | test_selection | full + off |
| smf1 multitrack export carries channels | test_selection | full + off |
| smf1 writer clamps hostile notes | test_selection | full + off |
| read_smf round-trips type-0 writer output | test_midi_read | full + off |
| read_smf round-trips type-1 multitrack with drums | test_midi_read | full + off |

CI: `build-test-validate`, step `Test`.
