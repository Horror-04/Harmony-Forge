// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "core/music/key_detect.h"

#include <array>
#include <string_view>
#include <vector>

#include "core/music/pitch_class.h"
#include "core/music/scale.h"

namespace hf::music {
namespace {

// Scales in fixed priority order: used for deterministic tie-breaking
// (first wins) and to enumerate every scale ScaleDatabase supports.
constexpr std::array<std::string_view, 11> kScales = {
    "major",         "natural_minor", "dorian",       "phrygian",
    "lydian",        "mixolydian",    "locrian",      "harmonic_minor",
    "melodic_minor", "major_pent",    "minor_pent",
};

}  // namespace

KeyEstimate detect_key(const hf::core::Pattern& p) {
  std::array<double, 12> hist{};
  double total = 0.0;
  for (const auto& t : p.tracks) {
    if (t.type == hf::core::TrackType::Drums) continue;  // unpitched map
    for (const auto& n : t.notes) {
      const double w = n.duration_ticks > 0 ? n.duration_ticks : 1;
      hist[mod12(n.pitch)] += w;
      total += w;
    }
  }
  if (total <= 0.0) return KeyEstimate{};

  KeyEstimate best;  // default: tonic 60, "major", confidence 0
  double best_score = -1.0;
  for (int tonic_pc = 0; tonic_pc < 12; ++tonic_pc) {
    for (std::string_view scale : kScales) {
      const std::vector<int> iv = ScaleDatabase::intervals(scale);
      if (iv.empty()) continue;
      double score = 0.0;
      double in_scale = 0.0;
      for (int pc = 0; pc < 12; ++pc) {
        if (hist[pc] == 0.0) continue;
        const int rel = mod12(pc - tonic_pc);
        bool member = false;
        for (int s : iv) {
          if (s == rel) {
            member = true;
            break;
          }
        }
        if (!member) continue;
        in_scale += hist[pc];
        score += hist[pc] * (rel == 0 ? 1.5 : 1.0);  // tonic emphasis
      }
      if (score > best_score) {
        best_score = score;
        best.tonic = 60 + tonic_pc;
        best.scale = std::string(scale);
        best.confidence = static_cast<float>(in_scale / total);
      }
    }
  }
  return best;
}

}  // namespace hf::music
