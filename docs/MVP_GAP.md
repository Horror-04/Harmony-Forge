# MVP Gap Audit (Task 0, read-only)

Document status: **RECORD** — a dated audit, true as of 2026-10-18; what has changed since is annotated at the end of this file. Date: 2026-10-18. Scope: SPEC §14 (9 MVP items) × §16 (7 acceptance criteria).
Verdicts: `OK` / `PARTIAL` / `MISSING` + proof (`ctest` binary + case, or `file:line`, or `MISSING`).
No code was changed for this audit.

## ctest counts (NOT re-verified here)

- `build-full` / `build-off` directories do **not** exist in this worktree, so
  `ctest --test-dir build-full -N` / `ctest --test-dir build-off -N` could not run.
- Reference numbers (unverified, from `docs/INVARIANTS.md:6-12` + `docs/measurements/s0-test-matrix.md`):
  **193 tests (build-full/Release), 170 tests (build-off/Debug)**,
  23-test delta fully option-gated (plugin-ON 21 + ONNX-ON net 2).
- Downstream tasks MUST re-verify with `ctest -N` on both suites before claiming counts.
- Task 4 re-verified 2026-10-18 (this worktree, Release): **218 tests
  (build-full) / 193 tests (build-off)**, `ctest` 100% pass both suites
  (21.5 s / 21.2 s). Delta vs Task-3 record (213/188): +5 Task-4 pins.
- Fix round 1 (same day): **221 tests (build-full) / 195 tests
  (build-off)**, 100% pass (21.4 s / 20.9 s). Delta: +3 pins (2
  `test_selection` [task4] + 1 `test_vertical_slice` [slice][task4]).
  All binary/case proofs below cite source that exists in-tree (read-verified), not test runs.

## SPEC §14 — MVP composition (9 items)

| # | Item | Verdict | Proof |
|---|------|---------|-------|
| 1 | VST3 + Standalone | OK | `src/plugin/CMakeLists.txt:11` — `FORMATS VST3 AU Standalone`; pluginval strictness-5 `SUCCESS` logged in `docs/measurements/s0-pluginval.log` (tail line `SUCCESS`) |
| 2 | Chord, Melody, Bass generators | OK | `src/inference/candidates.cpp:113-181` (impl) + `:252-254` (facade) — `generate_candidates[_impl]` returns 4 `Pattern`s (Safe/Catchy/Complex/Unexpected); `src/inference/candidate_base.cpp:38` — compose base `{melody, bass, chords}` (the melody-first track order is also noted at `src/plugin/ui/PatternDocument.h:178`); pins in `test_candidates` (`tests/test_candidates.cpp:50,62,81,105,126`) |
| 3 | Piano Roll + Chord Track | OK | `src/plugin/ui/PianoRoll.cpp`, `src/plugin/ui/ChordTrack.cpp` exist; `test_chordtrack_pin` (`tests/test_chordtrack_pin.cpp:153,162`), `test_keyboard_moves` (9 cases, plugin-ON). Note: `test_note_cues` / `test_visual_polish` deliberately unregistered (headless teardown, see `tests/CMakeLists.txt:160-186`) — paint evidence only |
| 4 | Key auto-detection | OK | `src/core/music/key_detect.cpp:25` — `detect_key()`; consumed by `src/plugin/ui/ExplainView.cpp:71` and `src/core/music/reference_analyze.cpp:25`; pins `test_analysis` (`tests/test_analysis.cpp:50,57,64`) |
| 5 | Freeze by tracks and bars | OK | `src/core/model/selection.h:77-84` + `src/core/model/selection.cpp:162-257` (track/bar/note freeze, rhythm-vs-pitch axis); `src/plugin/ui/PatternDocument.h:74-80` + `src/plugin/ui/PatternDocument.cpp:150-162`; pins `test_selection` (`tests/test_selection.cpp:147,184,213,367`) |
| 6 | Regenerate selected region (4 candidates) | OK | Task 4 DONE 2026-10-18: selection-scoped regenerate via `PatternDocument::regenerateSelection` (`src/plugin/ui/PatternDocument.h:126-133`, `src/plugin/ui/PatternDocument.cpp:456-470`) = whole-pattern regenerate merged under (user freeze UNION `freeze_complement_of_selection`) (`src/core/model/selection.h:93-111`, `src/core/model/selection.cpp:301-346`); UI: CandidateBar "Regen sel" (`src/plugin/ui/CandidateBar.h:25,58`) + `doRegenerateSelection` (`src/plugin/audio/PluginEditor.cpp:473`). Pins: `test_selection.cpp` [task4] complement/track/note/union + merge byte-identity; `test_candidates.cpp` [task4] frozen-track byte-identical. Fix round 1: doc-level scoping + determinism in `test_vertical_slice.cpp` [slice][task4]; union merged-effect byte-identity + empty-selection==legacy pins in `test_selection.cpp`. |
| 7 | Drag-and-drop MIDI to FL + multitrack export | PARTIAL | Code path exists: `src/plugin/audio/PluginEditor.cpp:519-546` (`startMidiDrag` → `finishDrag` → `hf::app::export_pattern_bytes` = `assign_default_channels` + `write_smf1(copy, 480)`, `src/app/midi_exporter.cpp:9-13` → temp `HarmonyForge-drag.mid` → `performExternalDragDropOfFiles`); multitrack channels via `assign_default_channels`; `src/companion/fl_dispatcher.py` (dry-run capable, API-verified list `:16-28`); byte-level pins `test_selection` (`tests/test_selection.cpp:324,344,387,422`). GAP: manual in-FL smoke NOT-RUN — `docs/FL_SMOKE.md:81-83` all 3 cases `NOT-RUN` (no FL licence on dev machine). → Task 5 |
| 8 | Local ONNX model + Music Theory Validator | PARTIAL | `training/model.onnx` + `model.logits.onnx` + `memo_index.bin` shipped; `OnnxRunner` pins `test_inference` (`tests/test_inference.cpp:43,52`); validator = constraints/voice-leading (`src/core/music/voice_leading.*`, `src/inference/constraints.*`) with pins (`tests/test_constraints.cpp:34,44,53`, `tests/test_analysis.cpp:296-339`). The 2026-10-18 GAP (“**no model-compat manifest check** — `checkModelCompatible`/`model_manifest` grep in `src/inference` = zero hits; mismatched vocab loads silently (falls back to theory-only)”) is **CLOSED**: `src/inference/model_manifest.{h,cpp}` exists, `check_model_compatible()` (`src/inference/model_manifest.cpp:288`) REFUSES a model whose vocab/layout does not match the compiled `kVocab*` tables, and it is wired into both load paths (`src/inference/onnx_runner.cpp:54`, `src/inference/ort_logits.cpp:160`); the sidecar `training/model_manifest.json` ships with the weights, and a refused model stays unloaded → theory-only fallback. What is still open is the *product-level* pin on the logits the committed `training/model.logits.onnx` produces (declared GAP-1 / item B10 in `docs/INVARIANTS.md` + `docs/BACKLOG-phase-B.md`). → Task 2 |
| 9 | Seed, history, built-in preview | OK | Seed persisted undoably (`src/plugin/state/PluginState.h:42,55,77,91`, `src/plugin/state/PluginState.cpp:115-117,154-156`); history box + recall (`src/plugin/ui/CandidateBar.h:56-62` — the A/B/C/D buttons, the Regenerate/Regen-sel/Keep buttons and the `historyBox_`; pin `tests/test_selection.cpp:306` "seed history is bounded and ordered"); preview synth via lock-free queue (`src/plugin/audio/PreviewSynth.*`; pins `test_preview_synth`, `test_async_generate`) |

## SPEC §16 — Acceptance criteria (7)

| # | Criterion | Verdict | Proof |
|---|-----------|---------|-------|
| 1 | 8 bars (chords+melody+bass) in < 30 s | OK | Unit-level perf pin exists: `tests/test_inference.cpp:89` "perf: 8-bar predict well under SPEC budget" (`CHECK(ms < 2000.0)`, prints avg ms). Task 4 DONE 2026-10-18: E2E pin `test_candidates.cpp` [task4] "8-bar end-to-end generation carries Chord+Bass+Melody in budget" (measured 0.058 ms in-suite, `CHECK(ms < 30000.0)`; all 4 candidates carry non-empty Melody+Bass+Chords at strict_compliance 1.0). CLI: `render_midi --seed 7 --bars 8 --out x.mid --multi` = 0.078 s wall-clock, 72 notes / 697 bytes, sha256-identical across runs (`5da18593…` — a PRE-Pcg32 hash; see the dated note at the end of this file). Fix round 1: furthest GUI-free link pinned in `test_vertical_slice.cpp` [slice][task4] — Generate→candidates→ValueTree commit (incl. undo/redo)→snapshot→multitrack MIDI bytes, 50.7 ms in-suite, `CHECK(ms < 30000.0)` with type+compliance+caps. Remaining manual steps: PianoRoll widget paint (headless-excluded by the `test_note_cues` precedent) and audible/in-host playback (DSP side pinned by `test_preview_synth`). |
| 2 | All parts export via DnD without artefacts | PARTIAL | Same proof as §14.7 (code + `test_selection` smf1 round-trip/clamp pins). GAP: human FL confirmation missing (`docs/FL_SMOKE.md` NOT-RUN). Machine-side artefact coverage = round-trip + hostile-clamp + read-back (`test_midi_read` `read_smf` cases, INV-5). → Task 5 |
| 3 | Chord change auto-fixes dependent conflicts | OK | `PatternDocument::replaceChord` → `resolve_harmonic_conflicts` (`src/plugin/ui/PatternDocument.cpp:334-357`, the resolve call at `:345`; the other call site is the Keep path at `:431`); pin `tests/test_constraints.cpp:53` "Am7 to Fmaj7 repairs only conflicting notes" + `tests/test_analysis.cpp:296-339` (resolve → `strict_compliance == 1.0`) |
| 4 | Lock first bars, regenerate rest | OK | `setBarFrozen` / `setBarFrozenAllTracks` (`src/plugin/ui/PatternDocument.cpp:150-162`); pins `tests/test_selection.cpp:184` (bar-0 identical, bar-1 regenerated) + `:367` "frozen bar merge keeps start_tick order" |
| 5 | Same params + seed → identical result | PARTIAL | Pins exist and green per INV-2: `tests/test_candidates.cpp:81` "same seed gives bit-identical candidates", `tests/test_async_generate.cpp:127` "async completion is bit-identical to the sync path", CI double-render `render_midi --seed 7` + `fc /b`. **RNG (state as of 2026-10-21, corrected): the generation RNG is NOT `std::mt19937` any more — it is a `Pcg32` stream**: `Pcg32 rng(stream_seed(p, i))` at `src/inference/candidates.cpp:124`, seeded by `stream_seed()` (`src/inference/candidates.cpp:190-198` — FNV-1a over the scale mixed with seed/bars/tonic/mode/index), and the same `Pcg32&` is threaded by reference through `src/inference/candidate_base.cpp:39`, `src/inference/candidate_modes.cpp:133` and `src/inference/candidate_transforms.cpp:124`; the sampler is `Pcg32` too (`src/inference/sampler.cpp:419`). PCG-everywhere therefore LANDED (the Pcg32 commit `3589205`), and the golden MIDI pins landed with the v3 cube baseline (`docs/measurements/s0-sha-matrix-v3.csv`, 936 rows) — so the cross-stdlib bit-identity RISK the 2026-10-18 audit recorded is closed. The verdict is NOT re-raised here: the model leg still has no product-level pin (the logits the committed `training/model.logits.onnx` produces are pinned by no artifact in this repo — `docs/INVARIANTS.md` GAP-1, `docs/BACKLOG-phase-B.md` item B10), so byte-identity of the model path is still unproven; re-audit before raising it to OK |
| 6 | No DAW hangs during generation (background threads) | OK | `AsyncGenerateQueue` (`src/inference/async_generate.*`; `src/plugin/ui/PatternDocument.h:115-141` — regenerate submits, timer poll applies, supersede-by-id); pins `tests/test_async_generate.cpp:142,158` (supersede, fake-latency non-blocking); RT side: `PluginProcessor::processBlock` (`src/plugin/audio/PluginProcessor.cpp:44-68`) does only outbox-pop + preview render, guarded by `RtViolationCounter` pins (`tests/test_rt_violation_counter.cpp:34,58`); pluginval L5 `SUCCESS` (`docs/measurements/s0-pluginval.log`) |
| 7 | ≥90–95% notes match user constraints | OK | Pin `tests/test_selection.cpp:444` "strict compliance stays above the 90 percent gate" + `tests/test_candidates.cpp:50` "Strict output is 100% in-scale and strong-beat-safe" (+ `:62` across keys/modes). Human music-quality side (§17 scores) out of scope for ctest |

## UI → inference chain spot-check (per brief)

`CandidateBar[Regenerate]` (`src/plugin/ui/CandidateBar.h:22` `onRegenerate`)
→ `HarmonyForgeEditor::doRegenerate` (`src/plugin/audio/PluginEditor.cpp:459`, persists seed/bars undoably, builds `GenParams`)
→ `PatternDocument::regenerate` (background `AsyncGenerateQueue`, `src/plugin/ui/PatternDocument.h:115-141`)
→ A/B/C/D + history (`src/plugin/ui/CandidateBar.h:56-62`)
→ `Keep` → `keepCandidate` undoable commit → `PianoRoll`/`ChordTrack` repaint via `ChangeBroadcaster`
→ RT: processor reads only lock-free preview outbox snapshot (`src/plugin/audio/PluginProcessor.cpp:44-68`), never `ValueTree`
→ DnD: `startMidiDrag`/`finishDrag` → `performExternalDragDropOfFiles` (`src/plugin/audio/PluginEditor.cpp:519-546`).
Audition path `auditionCandidate` (`src/plugin/audio/PluginEditor.cpp:445`) previews without committing. Chain is fully wired; async-vs-sync bit-identity pinned (`tests/test_model_preview.cpp:106,121`).

Freeze byte-identity: `tests/test_selection.cpp:184-196` asserts bar-0 pitches exactly equal post-merge (frozen region byte-stable by construction of `merge_with_frozen`).
Seed repeat: `tests/test_candidates.cpp:81`.
8-bar <30 s method: time `tools/render_midi --seed 7 --bars 8 --out out.mid --multi` wall-clock (headless, no DAW) + cite `test_inference.cpp:89` avg-ms printout; pass bar = well under 30 s (SPEC §11 unit budgets 2 s / 5 s).

## Downstream mapping

- Task 1 (RT): soak test + strict scan; §16.6 already OK but un-soaked (random blocks/transport).
- Task 2 (Determinism): manifest + PCG + golden MIDI; unblocks §14.8→OK, §16.5→OK.
- Task 3 (Isolation/layers): no GAP impact; gates stay green.
- Task 4 (Vertical slice): selection-scoped regenerate (§14.6→OK), 8-bar E2E timing (§16.1→OK), freeze/seed pins re-verified. DONE 2026-10-18: 218/193 green, gates clean. Fix round 1 (same day): 221/195 green, gates clean.
- Task 5 (DnD/FL/pluginval): human FL smoke (§14.7/§16.2→OK), pluginval L5 re-run log.

## What changed since 2026-10-18 (annotated 2026-10-21)

This file is a dated audit: the VERDICTS and the ctest COUNTS above are the
2026-10-18 record and are kept as they were. The `file:line` citations inside
the audit were re-pointed at the current tree on 2026-10-21 (most of them no
longer resolved after the B1/B2/B3/B4b waves and the S9.3 layout extraction),
and the two statements that had become factually false about the CODE are
corrected in place. The rest of what moved:

| # | what the 2026-10-18 audit said | what is true now (2026-10-21) |
|---|---|---|
| 1 | §14.8 GAP: "**no model-compat manifest check** … `model_manifest` grep in `src/inference` = zero hits; mismatched vocab loads silently" | **CLOSED** — `src/inference/model_manifest.{h,cpp}` exists; `check_model_compatible()` (`src/inference/model_manifest.cpp:288`) refuses a vocab/layout mismatch and is wired into both load paths (`src/inference/onnx_runner.cpp:54`, `src/inference/ort_logits.cpp:160`). A refused model stays unloaded → theory-only fallback. Corrected in place. |
| 2 | §16.5 RISK: the generation RNG is `std::mt19937` (`candidates.cpp:120`) and only `sampler.cpp:42` has `Pcg32` | **CLOSED** — the composer RNG is a `Pcg32` stream (`src/inference/candidates.cpp:124`, seeded by `stream_seed()` at `:190-198`); PCG-everywhere landed in `3589205` and the golden MIDI pins landed with the v3 cube baseline. Corrected in place. |
| 3 | the ctest pairs 218/193, then 221/195 (both measured 2026-10-18) | The pair is now **273 (build-full/Release) / 233 (build-off/Debug)** — the build-full half MEASURED by CI run `39625770936` on commit `1552665`, the build-off half still the static expectation (`docs/measurements/ratchet.md` §7, `docs/INVARIANTS.md`). The numbers above stay the 2026-10-18 record. |
| 4 | the seed-7 render hash `5da18593…` (72 notes / 697 bytes) | **PRE-PCG32** — every `render_midi` cell changed in the Pcg32 commit (`576/576 DIFF`, `docs/measurements/cube-baseline-v3.md` §3). The current single-track seed-7 render hash is `ea7650b3…` (170 bytes, the `render_midi,7,Strict,OFF,OFF,onnx-on,0` row of `docs/measurements/s0-sha-matrix-v3.csv`). The 8-bar/multitrack hash was NOT re-measured here (this pass ran no build) — re-measure it before quoting it. |
| 5 | §14.7 GAP: the in-FL smoke rows live at `docs/FL_SMOKE.md:57-63` | The three `NOT-RUN` rows live at `docs/FL_SMOKE.md:81-83`; the 2026-10-18 pointer landed on the Case-1 checklist instead. Corrected in place. |

Nothing above was re-measured by this pass: it is a documentation-only pass, so
no build, no `ctest` and no pluginval run happened here. The current ctest pair
and the current determinism baseline are quoted from `docs/INVARIANTS.md`,
`docs/measurements/ratchet.md` and `docs/measurements/cube-baseline-v3.md`.
