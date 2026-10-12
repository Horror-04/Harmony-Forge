// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include "core/model/note.h"

namespace hf::core {

// Track/Pattern helpers (pure data ops, no JUCE).
// Currently header-only declarations; trivial helpers live in track_pattern.cpp.

/// Total bars in pattern given 4/4 assumption (ticks_per_beat * beats_per_bar per bar).
int pattern_num_bars(const Pattern& p);

/// Total note count across all tracks.
int pattern_note_count(const Pattern& p);

// Result of merging per-bar reference chords into a working progression.
struct ChordMergeResult {
  ChordProgression merged;
  bool changed = false;
};

/// Merge per-bar reference chords (analyze_reference output: index == bar,
/// "unknown" = missing bar) into an existing progression. Known-type entries
/// replace the bar in place or extend the progression when the report is
/// longer; "unknown" entries leave that bar untouched. Never throws.
ChordMergeResult merge_reference_chords(const ChordProgression& existing,
                                        const std::vector<ChordSymbol>& ref);

}  // namespace hf::core
