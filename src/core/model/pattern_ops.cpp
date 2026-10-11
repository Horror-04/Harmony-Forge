// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "core/model/pattern_ops.h"

#include <algorithm>

#include "core/music/quantizer.h"
#include "core/music/scale.h"

namespace hf::core {

void transpose_pattern(Pattern& p, int semitones) {
  for (auto& t : p.tracks) {
    if (t.type == TrackType::Drums) continue;
    for (auto& n : t.notes) {
      n.pitch = std::clamp(n.pitch + semitones, 0, 127);
    }
  }
}

void quantize_pattern(Pattern& p, int grid, int strength_percent) {
  for (auto& t : p.tracks) {
    for (auto& n : t.notes) {
      n.start_tick = hf::music::quantize_tick(n.start_tick, grid, strength_percent);
    }
  }
}

void snap_pattern_to_scale(Pattern& p, int tonic, std::string_view scale_name) {
  for (auto& t : p.tracks) {
    if (t.type == TrackType::Drums) continue;
    for (auto& n : t.notes) {
      n.pitch = std::clamp(
          hf::music::ScaleDatabase::snap_to_scale(n.pitch, tonic, scale_name), 0,
          127);
    }
  }
}

}  // namespace hf::core
