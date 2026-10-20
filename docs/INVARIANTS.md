# Harmony Forge invariants

Binding granularity is BINARY: each invariant binds to ctest binary
(test-executable) names, not to individual case strings. A binary is
cited only after verifying its `.exe` exists AND its cases register:
build-full/tests/Release holds all 9 cited binaries;
build-off/tests/Debug holds 8 of 9 (test_preview_synth is plugin-ON
gated and has no off build -- stated, not fudged). Suite totals
re-verified via `ctest -N` at **phase-B B10 (2026-10-20): 254 tests
(build-full/Release), 221 tests (build-off/Debug)**
(docs/measurements/ratchet.md, the G10 row + the §7 counter table --
the growth over the S10 close (2026-10-19: 251/221) is the 3 new B10
ORT-only cases in tests/test_ort_logits.cpp, which live in an
`#ifdef HARMONY_FORGE_WITH_ONNX` block and therefore move the full
configuration only). The **S0 baseline** for the same two
configurations was **193 tests (build-full/Release), 170 tests
(build-off/Debug)** (docs/measurements/s0-test-matrix.md:10-11) -- the
S0 numbers are the baseline, the current numbers are the gate. Per
invariant, one "Spot-check" line names 1-2 exact Catch2 case strings
personally verified present in BOTH suites' `ctest -N` (numbers are the
observed full/off test numbers, re-derived at the S10 close).

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
(full #100 / off #100). Also covered: "async completion is bit-identical
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

Spot-check: "same seed gives bit-identical candidates" (full #77 /
off #77). Also covered: "model path threads into generation
deterministically", "memo filter is deterministic".

CI: `build-test-validate`, step `Determinism proof (render_midi
byte-identity)` (render_midi seed-7 twice + binary compare).

## INV-3: Both suites stay fully green (refactor behavior gate)

`ctest` passes **254/254 in build-full/Release** and **221/221 in
build-off/Debug** (measured 2026-10-20 at phase-B B10 --
docs/measurements/ratchet.md, the G10 row + the §7 counter table; the
growth over the S10 close's 251/221 is the 3 new B10 ORT-only cases in
tests/test_ort_logits.cpp, which are compiled out of the off
configuration by their `#ifdef HARMONY_FORGE_WITH_ONNX` block). The
33-test delta is option-gated only: the plugin-ON families contribute 28
(test_chordtrack_pin 2, test_keyboard_moves 9, test_focus_resize 4,
test_preview_synth 2, test_plugin_state 4, test_params_from_state 2,
test_vertical_slice 1, test_rt_violation_counter 3, test_rt_soak 1) and
the ONNX option a net 5 (6 real cases in test_ort_logits vs the 1
offline-stub case). Release-vs-Debug contributes zero: the only
`#ifndef NDEBUG` blocks in the test tree (4 sites, in
tests/test_rt_violation_counter.cpp and tests/test_rt_soak.cpp) sit in
plugin-ON-only binaries whose `#else` branches assert the same things,
so no case is registered or unregistered by the configuration.
The **S0 baseline** for the same pair was 193/193 in build-full/Release
and 170/170 in build-off/Debug, with a 23-test delta (plugin-ON adds
21, ONNX-ON adds a net 2 in test_ort_logits) -- Evidence:
docs/measurements/s0-test-matrix.md:10-11,18-34.
Deliberately unregistered binaries are NOT part of this gate:
test_note_cues and test_visual_polish (headless drawText teardown crash,
see tests/CMakeLists.txt) and test_memo_e2e (nightly-only `[.]` tag)
-- re-verified at the S10 close: 3 / 5 / 1 cases in source, 0 registered.

| binary (binding) | suites |
|---|---|
| (entire registered set: all binaries in `ctest -N`) | full + off |
| test_keynorm | full + off |
| test_arrangement | full + off |

Spot-check: "keynorm flag-off generate path is bit-identical to
pre-task output" (full #217 / off #194 -- re-derived from `ctest -N` on
2026-10-20, after the 3 new B10 ORT-only cases moved the full
configuration's indices by 3; the off configuration is unchanged). Also
covered: "arrangement build is deterministic".

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
(full #161 / off #143). Also covered: "clean generation passes through
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
| inv3 | "arrangement build is deterministic" — arrangement output stable across the refactor (the full registered set itself is the rest of this gate: `ctest` 254/254 full + 221/221 off) |
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

## DECLARED GAPS (NOT invariants — open, owned, tracked in the phase-B record)

**What this section is, and what it is not.** The five sections above
(INV-1..INV-5) are the repo's invariants: each binds to named ctest binaries
and to named Catch2 cases, and breaking one is a failure. **The entries below
are NOT invariants.** They are **declared GAPS** — properties the code does
*not* have today, recorded here so that each gap is visible, named and owned
instead of being silently assumed. Nothing in this section is bound to a test
or to a gate: the `[inv1]`-`[inv5]` tag set above is unchanged (29 bindings
over 5 invariants, `tools/lint_inv_tags.py`) and no CI step enforces a gap.
A gap is closed by the work item named in its entry, and the entry is deleted
when that work lands.

### GAP-1 — the ORT logits provider has NO slot-range guard

**The gap.** The slot-range guard for the ORT logits provider is **ABSENT**.
`src/inference/ort_logits.cpp:42` sets
`constexpr size_t kMaxIds = hf::ser::kVocabMaxTokens;` and
`OrtLogitsProvider::get_logits` (`src/inference/ort_logits.cpp:150-193`)
validates **only** against that token count (`n == 0 || n > kMaxIds`,
`src/inference/ort_logits.cpp:154`), plus the output element type, the output
shape `{1, n, kSamplerVocab}` and the finiteness of every produced float. It
**never** consults the slot ranges `kVocabSlotLo` / `kVocabSlotHi`
(`src/core/serialization/vocab_layout.gen.h:30-31`), so a prefix id outside
the slot-legal range is not rejected at the ORT boundary: the provider
reports success and returns logits for the full 256-wide vocabulary
(`src/inference/sampler.h:41`, `kSamplerVocab = 256`).

**Why it is a gap and not a broken invariant.** The slot ranges exist and are
enforced elsewhere: decode-side
(`src/core/serialization/tokenizer.cpp:80-85`), the sampler's FSM mask
(`src/inference/sampler.cpp:140-155`, applied at
`src/inference/sampler.cpp:227-229`) and the model-manifest compatibility
check (`src/inference/model_manifest.cpp:268-272`). An out-of-range prefix id
is therefore rejected further downstream (or only masked) — the ORT boundary
is the one place that does not check it. No invariant above promised a
boundary guard, so nothing above is broken; the missing check is simply
recorded here as an open gap.

**Owner, work and acceptance criteria.** `docs/BACKLOG-phase-B.md` item
**B10** — the deferred-work record: where the guard would go, why it was
deferred, the owner decision it needs (reject vs. mask), and its observable
acceptance criteria (a test in `tests/test_ort_logits.cpp` that names the
slot range it violates, with no false rejection on the frozen prefixes at
`tests/test_ort_logits.cpp:48-60`). The separate, larger item in B10 — a
product-level pin on the logits the committed `training/model.logits.onnx`
produces — is also still open: the sidecar's output is pinned by no artifact
in this repository.

**Status at the S10 close (2026-10-19).** OPEN, knowingly. No test binds it,
no gate covers it, and the invariant binding set above is unchanged. The
numbers behind this statement are in `docs/measurements/s10-final.md` §4.
