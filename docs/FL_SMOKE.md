# FL Studio Drag-and-Drop Smoke Procedure (manual, Phase 2 Task 1)

Manual in-FL check for Harmony Forge multitrack MIDI drag-and-drop
(SPEC §7). No FL Studio licence exists on the dev machine, so this
procedure is written but NOT RUN — the result table below stays
`NOT-RUN` until a licenced host is available. This does not block
stabilization; the byte-level export path is covered by ctest
(`write_smf1` round-trip/clamp tests) and the render-hash tripwire.

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

## Results

| Case | Date | FL version | Result | Notes |
| ---- | ---- | ---------- | ------ | ----- |
| 1 single part | — | — | NOT-RUN | no FL licence on this machine |
| 2 multitrack | — | — | NOT-RUN | no FL licence on this machine |
| 3 8-bar loop | — | — | NOT-RUN | no FL licence on this machine |

Fill one row per run: PASS/FAIL + FL build + plugin commit. Any FAIL
files a bug with the `.mid` attached (reproducible via
`render_midi --seed 7 --bars N --multi`).
