// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Tree-wide pitch helpers (phase-B B4a): the pitch-class residue, the
// octave pull and the melody/bass register windows.
//
// This is the ONE definition site for the whole tree. Before B4a the same
// three bodies were copy-pasted into 12 definitions spread over 12 files
// (`mod12` / `mod12int` / `pc_of`; one of them, detail/candidate_helpers.h,
// was already a shared inline header), 2 more places defined `octave_pull`,
// and the four register constants were declared twice. All of those copies
// were byte-identical duplicates of the bodies below, so the move is a pure
// move: no constant, comparison, order or behaviour changed.
//
// Header-only and `inline`, so there is no TU and no link change (same shape
// as the `ranges.h` precedent next door: `kMiddleC` + `in_register`).
// Reachable from `src/core`, `src/inference` and `src/plugin` without
// breaking the layer gate (owner decision D-B4).
#pragma once

namespace hf::music {

// Pitch class of a MIDI pitch: the residue class modulo 12, normalised to
// 0..11 (negative inputs included). `constexpr` (phase-B B4b) so the name
// accessor below can be a constant expression; the body is unchanged.
constexpr int mod12(int v) noexcept { return ((v % 12) + 12) % 12; }

// Nearest pitch to `pitch` that lies inside [lo, hi] and differs from it by
// whole octaves.
inline int octave_pull(int pitch, int lo, int hi) noexcept {
  while (pitch > hi) pitch -= 12;
  while (pitch < lo) pitch += 12;
  return pitch;
}

// Register windows (MIDI pitches): melody 60..84, bass 24..60.
constexpr int kMelodyLo = 60;  // C3 register floor
constexpr int kMelodyHi = 84;
constexpr int kBassLo = 24;
constexpr int kBassHi = 60;  // C3 register ceiling

// The 12 pitch-class NAMES, sharp spelling, C == 0 -- the ONE name table in
// the tree (phase-B B4b; the B4a name-table residual). Before B4b the same
// 12 strings were copy-pasted into four places
// (`src/core/music/explain.cpp` kPcNames, `src/plugin/ui/ChordTrack.cpp`
// kNames, `src/plugin/ui/ExplainView.cpp` kNames,
// `src/plugin/audio/PluginEditor.cpp` kNames); all four copies were
// byte-identical, so the fold changes no string. Names only: there is no
// pitch-class arithmetic here beyond the accessor's normalisation.
// Index THROUGH `pitch_class_name`, never the array: the accessor is what
// normalises an out-of-range or negative pitch.
inline constexpr const char* kPitchClassNames[12] = {
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"};

// Name of `pc`'s pitch class, sharp spelling ("C", "C#", ... "B").
constexpr const char* pitch_class_name(int pc) noexcept { return kPitchClassNames[mod12(pc)]; }

}  // namespace hf::music
