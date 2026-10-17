# Harmony Forge invariants

Binding granularity is BINARY: each invariant binds to ctest binary
(test-executable) names, not to individual case strings. A binary is
cited only after verifying its `.exe` exists AND its cases register:
build-full/tests/Release holds all 9 cited binaries;
build-off/tests/Debug holds 8 of 9 (test_preview_synth is plugin-ON
gated and has no off build -- stated, not fudged). Suite totals
re-verified via `ctest -N`: 193 tests (build-full/Release), 170 tests
(build-off/Debug). Per invariant, one "Spot-check" line names 1-2 exact
Catch2 case strings personally verified present in BOTH suites'
`ctest -N` (numbers are the observed full/off test numbers).

CI job for all five: `build-test-validate` (`.github/workflows/ci.yml`).
Relevant steps: `Test` (`ctest --test-dir build -C Release
--output-on-failure`), `Determinism proof (render_midi byte-identity)`
(seed-7 double render + `fc /b`), `Validate VST3 (strictness 5)`.

## INV-1: No heavy work on the real-time audio thread

Neural inference, allocation, locks, and file I/O never run in
`PluginProcessor::processBlock`. Audio reads pre-generated MIDI from a
lock-free ring buffer; generation runs on background workers.
Sources: SPEC section 11, THREADING_MODEL.md.

| binary (binding) | suites |
|---|---|
| test_async_generate | full + off |
| test_preview_synth | full only (plugin-ON; no off build) |

Spot-check: "fake-latency runner proves the flow is non-blocking"
(full #88 / off #88). Also covered: "async completion is bit-identical
to the sync path", "preview synth renders audible tone while held",
"preview synth decays after noteOff".

CI: `build-test-validate`, steps `Test` + `Validate VST3 (strictness 5)`.

## INV-2: Deterministic generation (same inputs -> byte-identical outputs)

Fixed seeds and parameters reproduce outputs exactly, end to end.

| binary (binding) | suites |
|---|---|
| test_candidates | full + off |
| test_async_generate | full + off |
| test_memo_filter | full + off |

Spot-check: "same seed gives bit-identical candidates" (full #67 /
off #67). Also covered: "model path threads into generation
deterministically", "memo filter is deterministic".

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

| binary (binding) | suites |
|---|---|
| (entire registered set: all binaries in `ctest -N`) | full + off |
| test_keynorm | full + off |
| test_arrangement | full + off |

Spot-check: "keynorm flag-off generate path is bit-identical to
pre-task output" (full #187 / off #168). Also covered: "arrangement
build is deterministic".

CI: `build-test-validate`, step `Test`.

## INV-4: Memo-filter policy (SPEC section 10)

The shipped C++ path enforces the eval-time memo-ban: first run of >= 4
consecutive memorized 8-windows is cut before the completing token and
repaired to whole notes; drums are excluded and reattached byte-identical;
clean input passes through untouched; empty/missing index is a safe no-op;
same Pattern + same index gives identical results; never throws; file I/O
restricts it to background threads.

| binary (binding) | suites |
|---|---|
| test_memo_filter (all 12 registered cases) | full + off |
| test_sampler (memo cases) | full + off |

Spot-check: "verbatim run is truncated at the offending window"
(full #145 / off #128). Also covered: "clean generation passes through
byte-identical", "missing index file loads nullopt and never throws",
"memo filter is deterministic", "drums are untouched by the memo
filter", "loader round-trips the binary format and rejects garbage",
"committed training index loads (smoke)", "index path resolves to
sibling, bare names to the working dir", "wired path truncates reciting
model output, stays deterministic", "wired path without sibling index
is byte-identical", "override with empty path filters via the working
dir", "bare model filename resolves via the working dir", "sampler memo
block run=2 turns away from recitation", "sampler reuses the shipped
memo index loader".

CI: `build-test-validate`, step `Test`.

## INV-5: Byte-level SMF export fidelity

MIDI file export round-trips exactly and clamps hostile input instead of
emitting corrupt files. (FL_SMOKE.md: with no FL licence on the dev
machine, this ctest layer is the export-path coverage.)

| binary (binding) | suites |
|---|---|
| test_selection (smf1 writer cases) | full + off |
| test_midi_read (read_smf cases) | full + off |

Spot-check: "smf1 round-trips sequential starts and durations"
(full #29 / off #29). Also covered: "smf1 round-trips overlapping chord
notes", "smf1 multitrack export carries channels", "smf1 writer clamps
hostile notes", "read_smf round-trips type-0 writer output",
"read_smf round-trips type-1 multitrack with drums".

CI: `build-test-validate`, step `Test`.
