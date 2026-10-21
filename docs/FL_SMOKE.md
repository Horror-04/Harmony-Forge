# FL Studio Drag-and-Drop Smoke Procedure (manual, Phase 2 Task 1)

Document status: **RECORD** — true as of the dates it states (later changes annotated at the end).
Manual in-FL check for Harmony Forge multitrack MIDI drag-and-drop (SPEC §7). No FL Studio licence
exists on the dev machine, so the in-host rows below stay `NOT-RUN` until a licenced host is available.
Steps tagged HUMAN require a person in FL Studio; steps tagged MACHINE
are verified headless in CI/ctest (Task 5, 2026-10-18).
This does not block stabilization; the byte-level export path is
covered by ctest (`write_smf1` round-trip/clamp tests) and the
render-hash tripwire.

## Machine-verified export path (MACHINE — no host needed, Task 5 DONE)

- DnD code path (`src/plugin/audio/PluginEditor.cpp:519-546`): working
  pattern (or state-fallback Safe candidate) → `assign_default_channels`
  → `write_smf1(copy, 480)` → temp `HarmonyForge-drag.mid` →
  `performExternalDragDropOfFiles`. Entry points are `mouseDown`
  (`src/plugin/audio/PluginEditor.cpp:381-387`) and the drag button's `onClick`
  (`src/plugin/audio/PluginEditor.cpp:99-112`) only — both message thread; `processBlock`
  (`src/plugin/audio/PluginProcessor.cpp:44-68`) touches only the lock-free outbox + preview synth + transport snapshot (no DnD contact).
- Byte-level export pins (ctest, 221/221 full + 195/195 off, 2026-10-18):
  `test_vertical_slice.cpp` [slice][task4] — Generate→candidates→commit→
  `write_smf1` deterministic (format-1 header, track count, 480 PPQ);
  `test_selection.cpp` — smf1 round-trip + hostile-clamp + read-back
  (`test_midi_read`, INV-5); CLI `render_midi --seed 7 --bars 8 --multi` =
  72 notes / 697 bytes, sha256 `5da18593…a16187` identical across runs (a PRE-Pcg32 hash — see the dated note at the end of this file).
- Host-compat proxy: pluginval strictness-5 `SUCCESS`
  (`docs/measurements/s5-pluginval.log`, seed 0x3e23d5d, exit 0).

## Prerequisites

- FL Studio 21+ (licenced), empty project, 4/4, 120 BPM.
- Plugin built from `phase-2-stabilization` (or later):
  `build-full\src\plugin\HarmonyForge_artefacts\Release\VST3\Harmony Forge.vst3`
  (pluginval strictness-5 SUCCESS — see task report).
- Companion script `src/companion/fl_dispatcher.py` at hand.

## Setup (every case)

1. Load Harmony Forge VST3 on an empty channel.
2. Generate: Seed 7, Bars per case, Root C (60), Scale major → Regenerate →
   Keep candidate A (Safe).
3. Drag the export control onto the FL Channel Rack (drops
   `HarmonyForge-drag.mid`: multitrack SMF Type-1, 480 PPQ, default
   channels Melody 0 / Bass 1 / Chords 2 / Drums 9).
4. In FL `VIEW > Script output > Interpreter`: `import fl_dispatcher;
   fl_dispatcher.apply_layout(fl_dispatcher.DEFAULT_LAYOUT)` — channels
   should read `HF Melody / HF Bass / HF Chords / HF Drums`.

## Case 1 — single part (melody only)

1. In the plugin Piano Roll, show track 0 (Melody), mute or delete other
   tracks if the UI offers it; otherwise drag and use only the imported
   `HF Melody` channel (mute the rest).
2. Press play from bar 0, listen through twice.
3. Check: melody pitches match the plugin roll (C3 = 60 anchor: middle-C
   plays middle-C); note starts on the grid (no flam/offset vs metronome);
   no extra notes (no artefacts).

## Case 2 — multitrack (all parts)

1. Full drag as in Setup (4 bars, all tracks).
2. Unmute all `HF *` channels, play from bar 0.
3. Check: Bass on beats 0/2 under the melody, Chords sustain whole bars,
   Drums (if present) on channel-10 map; no missing parts; run the
   dispatcher and confirm all four channels renamed (Drums entry skipped
   cleanly on 3-track exports with no drums).

## Case 3 — 8-bar loop

1. Regenerate with Bars 8, Keep A, drag, set the FL playlist loop to
   bars 1–8, loop 4x.
2. Check: seamless wrap at the loop end (no gap/overlap note), total
   length exactly 8 bars; stop mid-loop and confirm silence within
   ~100 ms (no hanging notes — every note-on has its note-off).

## Results (HUMAN — each row needs a person in FL Studio)

| Case | Date | FL version | Result | Notes |
| ---- | ---- | ---------- | ------ | ----- |
| 1 single part (HUMAN) | — | — | NOT-RUN | no FL licence on this machine |
| 2 multitrack (HUMAN) | — | — | NOT-RUN | no FL licence on this machine |
| 3 8-bar loop (HUMAN) | — | — | NOT-RUN | no FL licence on this machine |

Fill one row per run: PASS/FAIL + FL build + plugin commit. Any FAIL
files a bug with the `.mid` attached (reproducible via
`render_midi --seed 7 --bars N --multi`).

## What changed since 2026-10-18 (annotated 2026-10-21)

- The three HUMAN rows above are still `NOT-RUN` — unchanged, and still the
  reason §14.7 / §16.2 stay PARTIAL.
- The ctest pair quoted on line 21 (221/221 full + 195/195 off) is the
  2026-10-18 measurement and stays as the record. The current pair is
  **273 (build-full/Release) / 233 (build-off/Debug)** — the build-full half
  is MEASURED (CI run `39625770936` on commit `1552665`), the build-off half
  is still the static expectation (`docs/measurements/ratchet.md` §7,
  `docs/INVARIANTS.md`).
- The seed-7 render hash `5da18593…a16187` quoted above is a **PRE-Pcg32**
  hash: the Pcg32 commit `3589205` changed every `render_midi` cell
  (`576/576 DIFF`, `docs/measurements/cube-baseline-v3.md` §3). The live
  determinism baseline is `docs/measurements/s0-sha-matrix-v3.csv` (936 rows);
  its current seed-7 single-track render hash is `ea7650b3…` (170 bytes).
  The 8-bar/multitrack hash was NOT re-measured here (this pass ran no
  build) — re-measure it before quoting it.
- The `file:line` pointers were re-pointed at the current tree on 2026-10-21
  (the DnD path moved when the S9.3 layout extraction landed, and the
  Pattern→bytes encode moved into the JUCE-free `src/app` controller):
  `startMidiDrag` / `finishDrag` are `src/plugin/audio/PluginEditor.cpp:519-546`,
  the drag entry points are `mouseDown` `:381-387` and the drag button's
  `onClick` `:99-112`, and the encode is `hf::app::export_pattern_bytes`
  (`src/app/midi_exporter.cpp:9-13` = `assign_default_channels` +
  `write_smf1(copy, 480)`).
