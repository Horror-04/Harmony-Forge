// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <string>
#include <vector>

#include "core/model/note.h"
#include "core/music/key_detect.h"

namespace hf::music {

// Reference-MIDI analysis (Phase 5 Task 2, SPEC §2 steps 2-3: analyse the
// loaded reference's key, chords, density). JUCE-free, pure C++20; never
// throws. Pitches use 0..127, C3 = 60; only the key's pitch class carries
// meaning (tonic = 60 + pitch class). Drum tracks are excluded from all
// pitched analysis (unpitched map) and counted separately.
struct AnalysisReport {
  KeyEstimate key;                  // hf::music (detect_key; default when !enough_data)
  std::vector<core::ChordSymbol> chords;  // per-bar recognition, empty if none
  double density_notes_per_bar = 0.0;
  int drum_note_count = 0;
  bool enough_data = false;  // false on empty/single-note: NO invented key
};

// Analyse an imported reference pattern (typically from read_smf).
//
// - Pitched notes are notes on non-Drums tracks. Fewer than 2 pitched
//   notes -> enough_data=false, key = default (tonic 60, "major",
//   confidence 0), chords empty, density 0. Otherwise key = detect_key(p).
// - chords has one entry per bar (pattern_num_bars): bars containing
//   pitched-note onsets carry recognize_chord(pitches); bars with no
//   pitched material (or unrecognized content) carry root 60 / "unknown"
//   placeholders, so index == bar. Adopters skip "unknown" entries
//   (missing bars stay untouched).
// - density = all notes (pitched + drums) / bar count, 0 when there are
//   no bars. drum_note_count = notes on Drums tracks.
AnalysisReport analyze_reference(const core::Pattern& p);

}  // namespace hf::music
