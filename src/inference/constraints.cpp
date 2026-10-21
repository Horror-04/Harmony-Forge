// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "constraints.h"

#include <algorithm>
#include <vector>

#include "core/music/chord.h"
#include "core/music/pitch_class.h"
#include "core/music/quantizer.h"
#include "core/music/ranges.h"
#include "strong_beat.h"

namespace hf::infer {
namespace {

constexpr int kGrid = 120;  // 16th-note grid at 480 PPQ

// The pitch-class residue has ONE tree-wide definition
// (core/music/pitch_class.h, phase-B B4a); re-exported here.
using hf::music::mod12;

// Nearest pitch in 0..127 whose pitch class is in `pcs` (non-empty).
// Ties round up, mirroring ScaleDatabase::snap_to_scale.
int nearest_pc_pitch(int pitch, const std::vector<int>& pcs) {
  const int clamped = std::clamp(pitch, 0, 127);
  bool wanted[12] = {};
  for (int s : pcs) wanted[mod12(s)] = true;
  if (wanted[mod12(clamped)]) return clamped;
  for (int d = 1; d <= 12; ++d) {
    if (clamped + d <= 127 && wanted[mod12(clamped + d)]) return clamped + d;
    if (clamped - d >= 0 && wanted[mod12(clamped - d)]) return clamped - d;
  }
  return clamped;  // unreachable: a full pc cycle fits in +/-12
}

// Minimal move into register: clamp to 0..127, then to the part boundary
// (Bass ceiling / Melody floor at middle C). Chords/Arpeggio accept any
// valid MIDI pitch, so only the 0..127 clamp applies to them.
int clamp_to_register(hf::core::TrackType type, int pitch) {
  pitch = std::clamp(pitch, 0, 127);
  switch (type) {
    case hf::core::TrackType::Bass:
      return std::min(pitch, hf::music::kMiddleC);
    case hf::core::TrackType::Melody:
    case hf::core::TrackType::CounterMelody:
      return std::max(pitch, hf::music::kMiddleC);
    default:
      return pitch;
  }
}

}  // namespace

void resolve_harmonic_conflicts(core::Pattern& pattern,
                                const core::ChordProgression& chords) {
  const int bar_ticks = pattern.ticks_per_beat * pattern.beats_per_bar;
  for (auto& t : pattern.tracks) {
    if (t.type == hf::core::TrackType::Drums) continue;
    for (auto& n : t.notes) {
      // 1. Grid snap (16th grid, full strength).
      n.start_tick = hf::music::quantize_tick(n.start_tick, kGrid, 100);
      // 2. Register clamp (minimal move into register).
      n.pitch = clamp_to_register(t.type, n.pitch);
      // 3. Strong-beat minor-2nd resolution against the bar-indexed chord.
      //    Projection 3 of the rule (strong_beat.h) answers "which chord must
      //    this note be repaired against?"; nullptr means keep the note.
      const hf::core::ChordSymbol* chord =
          strong_beat_repair_target(n.start_tick, bar_ticks, chords, n.pitch);
      if (chord == nullptr) continue;  // weak beat / no bar chord / no rub: keep
      const std::vector<int> iv = hf::music::chord_intervals(*chord);
      std::vector<int> tone_pcs;
      tone_pcs.reserve(iv.size());
      for (int s : iv) tone_pcs.push_back(mod12(chord->root) + s);
      n.pitch = nearest_pc_pitch(n.pitch, tone_pcs);
      // Backstop: the nearest tone can sit just outside the part register
      // (e.g. Melody 60 -> 59). Octave shifts preserve pitch class, hence
      // chord-tone membership; the boundary clamp below is a last resort.
      while (!hf::music::in_register(t.type, n.pitch)) {
        if (t.type == hf::core::TrackType::Bass && n.pitch > hf::music::kMiddleC) {
          if (n.pitch - 12 < 0) break;
          n.pitch -= 12;
        } else if ((t.type == hf::core::TrackType::Melody ||
                    t.type == hf::core::TrackType::CounterMelody) &&
                   n.pitch < hf::music::kMiddleC) {
          if (n.pitch + 12 > 127) break;
          n.pitch += 12;
        } else {
          break;
        }
      }
      n.pitch = clamp_to_register(t.type, n.pitch);
    }
  }
}

}  // namespace hf::infer
