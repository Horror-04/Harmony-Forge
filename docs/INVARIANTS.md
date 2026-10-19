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

## Case-level binding (S4b-main T7, Catch2 tags [inv1]–[inv5])

The binary rows above remain authoritative for CI. Since S4b-main T7 each
bound case ALSO carries a named `[invN]` tag (appended to its suite tag,
never replacing it), so coverage is pinned to test names instead of binary
granularity alone. Tag discipline: the tagged set is EXACTLY the
spot-check + "Also covered" case strings named in this doc — no extras.
Enforcement: `tools/lint_inv_tags.py` (in-script expected map, same
blocking shape as `tools/lint_golden_pin.py`; missing tag FAILS) wired as
a blocking step in the `gates` and `build-test-validate` CI jobs.

| inv | TEST_CASE (why it pins the invariant) |
|---|---|
| inv1 | "fake-latency runner proves the flow is non-blocking" — 50 ms worker sleep is invisible to the submitter (submit returns without running inference on the caller thread) |
| inv1 | "async completion is bit-identical to the sync path" — background-queue handoff preserves bytes (audio reads pre-generated MIDI, generation runs off-thread) |
| inv1 | "preview synth renders audible tone while held" — preview voice lifecycle (prepare/noteOn/render) produces output without blocking (plugin-ON only; source-level tag, no off build by design) |
| inv1 | "preview synth decays after noteOff" — note-off teardown releases cleanly (plugin-ON only; same portability note) |
| inv2 | "same seed gives bit-identical candidates" — spot-check; fixed seed reproduces candidates exactly |
| inv2 | "model path threads into generation deterministically" — configured model path still yields identical outputs incl. async == sync |
| inv2 | "memo filter is deterministic" — same Pattern + same index gives identical results (shared with inv4) |
| inv3 | "keynorm flag-off generate path is bit-identical to pre-task output" — spot-check; refactor left default-path bytes unchanged |
| inv3 | "arrangement build is deterministic" — arrangement output stable across the refactor (the full registered set itself is the rest of this gate: `ctest` 251/251 full + 221/221 off) |
| inv4 | "verbatim run is truncated at the offending window" — spot-check; first >= 4-window run is cut before the completing token |
| inv4 | "clean generation passes through byte-identical" — clean input untouched |
| inv4 | "missing index file loads nullopt and never throws" — empty/missing index is a safe no-op, never throws |
| inv4 | "drums are untouched by the memo filter" — drums excluded and reattached byte-identical |
| inv4 | "loader round-trips the binary format and rejects garbage" — index loader totality |
| inv4 | "committed training index loads (smoke)" — shipped index loads |
| inv4 | "index path resolves to sibling, bare names to the working dir" — path resolution rule |
| inv4 | "wired path truncates reciting model output, stays deterministic" — end-to-end SPEC section 10 guarantee on final candidates |
| inv4 | "wired path without sibling index is byte-identical" — missing sibling index is a safe no-op |
| inv4 | "override with empty path filters via the working dir" — override-path rule + byte-identical fallback |
| inv4 | "bare model filename resolves via the working dir" — bare-name resolution rule |
| inv4 | "sampler memo block run=2 turns away from recitation" — sampler-level memo-ban enforcement |
| inv4 | "sampler reuses the shipped memo index loader" — sampler consumes the shipped loader (policy wiring) |
| inv5 | "smf1 round-trips sequential starts and durations" — spot-check; writer output parses back exactly |
| inv5 | "smf1 round-trips overlapping chord notes" — on/off interleave round-trips exactly |
| inv5 | "smf1 multitrack export carries channels" — multitrack export carries per-track channels incl. drums |
| inv5 | "smf1 writer clamps hostile notes" — hostile input clamped, never corrupt |
| inv5 | "read_smf round-trips type-0 writer output" — type-0 writer output reads back exactly |
| inv5 | "read_smf round-trips type-1 multitrack with drums" — type-1 multitrack with drums reads back exactly |

Considered and NOT tagged (binding stays 1:1 with the case strings named
above): "all modes are deterministic and capped" / "rank is deterministic"
(inv2-flavoured but unnamed in INV-2); "rapid regenerates supersede" /
"shutdown waits for the in-flight job" (inv1-flavoured but unnamed);
"sampler runs only via the background worker" (inv1-flavoured, lives in
test_sampler, unnamed in INV-1); extra read_smf edge cases (unnamed in
INV-5); "arrangement build is deterministic" carries [inv3] only (its
determinism is cited as the INV-3 behavior gate, not INV-2 generation
determinism). Portability: test_preview_synth is plugin-ON gated (no off
build, tests/CMakeLists.txt); tags are inert Catch2 metadata that travel
with the case wherever it builds, and the lint is source-level, so no
per-suite presence is required of full-only cases.
