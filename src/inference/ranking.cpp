// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Stub ranking: deterministic fractions over Melody+Bass. See ranking.h.
#include "ranking.h"

#include <algorithm>

#include "core/music/chord.h"
#include "core/music/pitch_class.h"
#include "core/music/ranges.h"
#include "core/music/scale.h"
#include "strong_beat.h"

namespace hf::infer {
namespace {

bool is_pitched_counted(hf::core::TrackType t) {
  return t == hf::core::TrackType::Melody || t == hf::core::TrackType::Bass;
}

// The strong-beat rub check is projection 2 of the rule, which has ONE home
// in strong_beat.h (phase-B B4b): start_tick % 480 == 0, bar-indexed chord,
// pitch-class distance 1. Its body used to be a TU-local copy here and
// moved byte-for-byte; both callers below keep their text.
struct Fractions {
  float in_scale = 0.0f;
  float strong_safe = 0.0f;
  float in_register = 0.0f;
  int total = 0;
};

Fractions measure(const core::Pattern& p, const core::ChordProgression& chords, int tonic,
                  const std::string& scale) {
  Fractions f;
  int ok_scale = 0, ok_safe = 0, ok_reg = 0;
  for (const auto& t : p.tracks) {
    if (!is_pitched_counted(t.type)) continue;
    for (const auto& n : t.notes) {
      ++f.total;
      if (hf::music::ScaleDatabase::is_in_scale(n.pitch, tonic, scale)) ++ok_scale;
      if (!strong_beat_rub(n, p, chords)) ++ok_safe;
      if (hf::music::in_register(t.type, n.pitch)) ++ok_reg;
    }
  }
  if (f.total == 0) return f;
  f.in_scale = static_cast<float>(ok_scale) / f.total;
  f.strong_safe = static_cast<float>(ok_safe) / f.total;
  f.in_register = static_cast<float>(ok_reg) / f.total;
  return f;
}

GenParams normalized(GenParams params) {
  params.bars = std::clamp(params.bars, 1, 16);
  params.tonic = std::clamp(params.tonic, 0, 127);
  if (hf::music::ScaleDatabase::intervals(params.scale).empty()) params.scale = "major";
  return params;
}

}  // namespace

float strict_compliance(const core::Pattern& p, const core::ChordProgression& chords,
                        int tonic, const std::string& scale) {
  int total = 0, good = 0;
  for (const auto& t : p.tracks) {
    if (!is_pitched_counted(t.type)) continue;
    for (const auto& n : t.notes) {
      ++total;
      if (!hf::music::ScaleDatabase::is_in_scale(n.pitch, tonic, scale)) continue;
      if (strong_beat_rub(n, p, chords)) continue;
      ++good;
    }
  }
  if (total == 0) return 1.0f;
  return static_cast<float>(good) / total;
}

float rank_candidate(const core::Pattern& p, const GenParams& params) {
  const GenParams q = normalized(params);
  const Fractions f = measure(p, progression_for_params(q), q.tonic, q.scale);
  if (f.total == 0) return 0.0f;
  return 0.5f * f.in_scale + 0.3f * f.strong_safe + 0.2f * f.in_register;
}

}  // namespace hf::infer
