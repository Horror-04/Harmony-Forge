// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <string>
#include <vector>

#include "core/model/note.h"

namespace hf::music {

// Key estimate from a pattern's pitch content. Never throws.
struct KeyEstimate {
  int tonic = 60;            ///< MIDI note, pitch class carries the key (60..71)
  std::string scale = "major";  ///< lowercase scale name from ScaleDatabase
  float confidence = 0.0f;   ///< 0..1 fraction of note weight on scale tones
};

// Template match over all 12 tonics x all ScaleDatabase scales.
// Drum tracks are skipped (unpitched map, would skew the histogram).
// Each note votes with weight = duration_ticks (min 1); the tonic pitch
// class gets a 1.5x emphasis so C-heavy white-note material reads C major
// while A-heavy material reads A natural_minor. Ties resolve deterministically
// (lowest tonic pitch class, then fixed scale order with major first).
// Empty patterns (or zero total weight) return the default with confidence 0.
KeyEstimate detect_key(const hf::core::Pattern& p);

}  // namespace hf::music
