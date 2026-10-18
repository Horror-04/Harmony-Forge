# MVP Gap Audit (Task 0, read-only)

Date: 2026-10-18. Scope: SPEC §14 (9 MVP items) × §16 (7 acceptance criteria).
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
| 2 | Chord, Melody, Bass generators | OK | `src/inference/candidates.cpp:104-218` — `generate_candidates[_impl]` returns 4 `Pattern`s (Safe/Catchy/Complex/Unexpected); `src/plugin/ui/PatternDocument.h:166` — compose base `{melody, bass, chords}`; pins in `test_candidates` (`tests/test_candidates.cpp:49,61,80,104,125`) |
| 3 | Piano Roll + Chord Track | OK | `src/plugin/ui/PianoRoll.cpp`, `src/plugin/ui/ChordTrack.cpp` exist; `test_chordtrack_pin` (`tests/test_chordtrack_pin.cpp:76,84`), `test_keyboard_moves` (9 cases, plugin-ON). Note: `test_note_cues` / `test_visual_polish` deliberately unregistered (headless teardown, see `tests/CMakeLists.txt:120-166`) — paint evidence only |
| 4 | Key auto-detection | OK | `src/core/music/key_detect.cpp:26` — `detect_key()`; consumed by `src/plugin/ui/ExplainView.cpp:71` and `src/core/music/reference_analyze.cpp:25`; pins `test_analysis` (`tests/test_analysis.cpp:50,57,64`) |
| 5 | Freeze by tracks and bars | OK | `src/core/model/selection.h:77-92` + `selection.cpp:90-173` (track/bar/note freeze, rhythm-vs-pitch axis); `src/plugin/ui/PatternDocument.h:74-80` + `PatternDocument.cpp:146-174`; pins `test_selection` (`tests/test_selection.cpp:146,183,212,366`) |
| 6 | Regenerate selected region (4 candidates) | OK | Task 4 DONE 2026-10-18: selection-scoped regenerate via `PatternDocument::regenerateSelection` (`PatternDocument.h:124-131`, `PatternDocument.cpp:462-476`) = whole-pattern regenerate merged under (user freeze UNION `freeze_complement_of_selection`) (`selection.h:95-111`, `selection.cpp:298-355`); UI: CandidateBar "Regen sel" (`CandidateBar.h:25,190`) + `doRegenerateSelection` (`PluginEditor.cpp:752-767`). Pins: `test_selection.cpp` [task4] complement/track/note/union + merge byte-identity; `test_candidates.cpp` [task4] frozen-track byte-identical. Fix round 1: doc-level scoping + determinism in `test_vertical_slice.cpp` [slice][task4]; union merged-effect byte-identity + empty-selection==legacy pins in `test_selection.cpp`. |
| 7 | Drag-and-drop MIDI to FL + multitrack export | PARTIAL | Code path exists: `src/plugin/audio/PluginEditor.cpp:789-816` (`startMidiDrag` → `finishDrag` → `write_smf1(copy, 480)` → temp `HarmonyForge-drag.mid` → `performExternalDragDropOfFiles`); multitrack channels via `assign_default_channels`; `src/companion/fl_dispatcher.py` (dry-run capable, API-verified list `:16-28`); byte-level pins `test_selection` (`tests/test_selection.cpp:323,343,386,421`). GAP: manual in-FL smoke NOT-RUN — `docs/FL_SMOKE.md:57-63` all 3 cases `NOT-RUN` (no FL licence on dev machine). → Task 5 |
| 8 | Local ONNX model + Music Theory Validator | PARTIAL | `training/model.onnx` + `model.logits.onnx` + `memo_index.bin` shipped; `OnnxRunner` pins `test_inference` (`tests/test_inference.cpp:43,52`); validator = constraints/voice-leading (`src/core/music/voice_leading.*`, `src/inference/constraints.*`) with pins (`tests/test_constraints.cpp:34,44,53`, `tests/test_analysis.cpp:296-339`). GAP: **no model-compat manifest check** — `checkModelCompatible`/`model_manifest` grep in `src/inference` = zero hits; mismatched vocab loads silently (falls back to theory-only). → Task 2 |
| 9 | Seed, history, built-in preview | OK | Seed persisted undoably (`src/plugin/state/PluginState.h:13,35`, `PluginState.cpp:104-144`); history box + recall (`src/plugin/ui/CandidateBar.h:63-73,154-171`; pin `tests/test_selection.cpp:305` "seed history is bounded and ordered"); preview synth via lock-free queue (`src/plugin/audio/PreviewSynth.*`; pins `test_preview_synth`, `test_async_generate`) |

## SPEC §16 — Acceptance criteria (7)

| # | Criterion | Verdict | Proof |
|---|-----------|---------|-------|
| 1 | 8 bars (chords+melody+bass) in < 30 s | OK | Unit-level perf pin exists: `tests/test_inference.cpp:89` "perf: 8-bar predict well under SPEC budget" (`CHECK(ms < 2000.0)`, prints avg ms). Task 4 DONE 2026-10-18: E2E pin `test_candidates.cpp` [task4] "8-bar end-to-end generation carries Chord+Bass+Melody in budget" (measured 0.058 ms in-suite, `CHECK(ms < 30000.0)`; all 4 candidates carry non-empty Melody+Bass+Chords at strict_compliance 1.0). CLI: `render_midi --seed 7 --bars 8 --out x.mid --multi` = 0.078 s wall-clock, 72 notes / 697 bytes, sha256-identical across runs (`5da18593…`). Fix round 1: furthest GUI-free link pinned in `test_vertical_slice.cpp` [slice][task4] — Generate→candidates→ValueTree commit (incl. undo/redo)→snapshot→multitrack MIDI bytes, 50.7 ms in-suite, `CHECK(ms < 30000.0)` with type+compliance+caps. Remaining manual steps: PianoRoll widget paint (headless-excluded by the `test_note_cues` precedent) and audible/in-host playback (DSP side pinned by `test_preview_synth`). |
| 2 | All parts export via DnD without artefacts | PARTIAL | Same proof as §14.7 (code + `test_selection` smf1 round-trip/clamp pins). GAP: human FL confirmation missing (`docs/FL_SMOKE.md` NOT-RUN). Machine-side artefact coverage = round-trip + hostile-clamp + read-back (`test_midi_read` `read_smf` cases, INV-5). → Task 5 |
| 3 | Chord change auto-fixes dependent conflicts | OK | `PatternDocument::replaceChord` → `resolve_harmonic_conflicts` (`src/plugin/ui/PatternDocument.cpp:335-346`; same in `applyInversion :361` / bar ops `:432`); pin `tests/test_constraints.cpp:53` "Am7 to Fmaj7 repairs only conflicting notes" + `tests/test_analysis.cpp:296-339` (resolve → `strict_compliance == 1.0`) |
| 4 | Lock first bars, regenerate rest | OK | `setBarFrozen` / `setBarFrozenAllTracks` (`PatternDocument.cpp:152-162`); pins `tests/test_selection.cpp:183` (bar-0 identical, bar-1 regenerated) + `:366` "frozen bar merge keeps start_tick order" |
| 5 | Same params + seed → identical result | PARTIAL | Pins exist and green per INV-2: `tests/test_candidates.cpp:80` "same seed gives bit-identical candidates", `tests/test_async_generate.cpp:110` "async completion is bit-identical to the sync path", CI double-render `render_midi --seed 7` + `fc /b`. RISK (→ Task 2): generation RNG is `std::mt19937` (`src/inference/candidates.cpp:120`, threaded through `candidate_base.cpp:38`, `candidate_modes.cpp:60`, `candidate_transforms.cpp:29`) while only `sampler.cpp:42` has `Pcg32` — cross-stdlib bit-identity is NOT guaranteed. Downgraded to PARTIAL until PCG-everywhere + golden MIDI pins land |
| 6 | No DAW hangs during generation (background threads) | OK | `AsyncGenerateQueue` (`src/inference/async_generate.*`; `PatternDocument.h:113-131` — regenerate submits, timer poll applies, supersede-by-id); pins `tests/test_async_generate.cpp:125,141` (supersede, fake-latency non-blocking); RT side: `PluginProcessor::processBlock` (`src/plugin/audio/PluginProcessor.cpp:31-51`) does only outbox-pop + preview render, guarded by `RtViolationCounter` pins (`tests/test_rt_violation_counter.cpp:34,58`); pluginval L5 `SUCCESS` (`docs/measurements/s0-pluginval.log`) |
| 7 | ≥90–95% notes match user constraints | OK | Pin `tests/test_selection.cpp:443` "strict compliance stays above the 90 percent gate" + `tests/test_candidates.cpp:49` "Strict output is 100% in-scale and strong-beat-safe" (+ `:61` across keys/modes). Human music-quality side (§17 scores) out of scope for ctest |

## UI → inference chain spot-check (per brief)

`CandidateBar[Regenerate]` (`CandidateBar.h:39-41` `onRegenerate`)
→ `HarmonyForgeEditor::doRegenerate` (`PluginEditor.cpp:733-749`, persists seed/bars undoably, builds `GenParams`)
→ `PatternDocument::regenerate` (background `AsyncGenerateQueue`, `PatternDocument.h:113-131`)
→ A/B/C/D + history (`CandidateBar.h:154-171`)
→ `Keep` → `keepCandidate` undoable commit → `PianoRoll`/`ChordTrack` repaint via `ChangeBroadcaster`
→ RT: processor reads only lock-free preview outbox snapshot (`PluginProcessor.cpp:41-51`), never `ValueTree`
→ DnD: `startMidiDrag`/`finishDrag` → `performExternalDragDropOfFiles` (`PluginEditor.cpp:789-816`).
Audition path `auditionCandidate` (`PluginEditor.cpp:719-731`) previews without committing. Chain is fully wired; async-vs-sync bit-identity pinned (`test_model_preview.cpp:106,121`).

Freeze byte-identity: `test_selection.cpp:183-195` asserts bar-0 pitches exactly equal post-merge (frozen region byte-stable by construction of `merge_with_frozen`).
Seed repeat: `test_candidates.cpp:80`.
8-bar <30 s method: time `tools/render_midi --seed 7 --bars 8 --out out.mid --multi` wall-clock (headless, no DAW) + cite `test_inference.cpp:89` avg-ms printout; pass bar = well under 30 s (SPEC §11 unit budgets 2 s / 5 s).

## Downstream mapping

- Task 1 (RT): soak test + strict scan; §16.6 already OK but un-soaked (random blocks/transport).
- Task 2 (Determinism): manifest + PCG + golden MIDI; unblocks §14.8→OK, §16.5→OK.
- Task 3 (Isolation/layers): no GAP impact; gates stay green.
- Task 4 (Vertical slice): selection-scoped regenerate (§14.6→OK), 8-bar E2E timing (§16.1→OK), freeze/seed pins re-verified. DONE 2026-10-18: 218/193 green, gates clean. Fix round 1 (same day): 221/195 green, gates clean.
- Task 5 (DnD/FL/pluginval): human FL smoke (§14.7/§16.2→OK), pluginval L5 re-run log.
