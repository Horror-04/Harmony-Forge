// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Tree-wide pitch helpers (phase-B B4a): the pitch-class residue, the
// octave pull and the melody/bass register windows.
//
// This is the ONE definition site for the whole tree. Before B4a the same
// three bodies were copy-pasted into 12 translation units
// (`mod12` / `mod12int` / `pc_of`), 2 more places defined `octave_pull`, and
// the four register constants were declared twice. All of those copies were
// byte-identical duplicates of the bodies below, so the move is a pure move:
// no constant, comparison, order or behaviour changed.
//
// Header-only and `inline`, so there is no TU and no link change (same shape
// as the `ranges.h` precedent next door: `kMiddleC` + `in_register`).
// Reachable from `src/core`, `src/inference` and `src/plugin` without
// breaking the layer gate (owner decision D-B4).
#pragma once

namespace hf::music {

// Pitch class of a MIDI pitch: the residue class modulo 12, normalised to
// 0..11 (negative inputs included).
inline int mod12(int v) noexcept { return ((v % 12) + 12) % 12; }

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

}  // namespace hf::music
