// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "core/music/voice_leading.h"

#include <algorithm>
#include <cstdlib>
#include <map>
#include <vector>

#include "core/music/chord.h"
#include "core/music/ranges.h"

namespace hf::music {
namespace {

int mod12(int v) { return ((v % 12) + 12) % 12; }

int sign_of(int v) { return (v > 0) - (v < 0); }

// Single project-wide strong-beat definition, shared with
// resolve_harmonic_conflicts and strict_compliance/strong_beat_rub:
// every quarter-note line at 480 PPQ.
constexpr int kStrongBeatMod = 480;

}  // namespace

VoiceReport validate_voice_leading(const hf::core::Pattern& p,
                                   const hf::core::ChordProgression& chords) {
  VoiceReport report;

  // Range audit: every pitched note against its track's register.
  // Drum tracks are skipped (unpitched map).
  for (const auto& t : p.tracks) {
    if (t.type == hf::core::TrackType::Drums) continue;
    for (const auto& n : t.notes) {
      if (!in_register(t.type, n.pitch)) ++report.range_violations;
    }
  }

  // Slice audit: start_tick -> per-track lowest pitch. Drum tracks are
  // skipped (columns stay absent), so unpitched hits never form parallels.
  std::map<int, std::vector<int>> slices;  // tick -> pitch per track (-1 absent)
  for (size_t ti = 0; ti < p.tracks.size(); ++ti) {
    if (p.tracks[ti].type == hf::core::TrackType::Drums) continue;
    for (const auto& n : p.tracks[ti].notes) {
      auto& row = slices[n.start_tick];
      if (row.empty()) row.assign(p.tracks.size(), -1);
      if (row[ti] < 0 || n.pitch < row[ti]) row[ti] = n.pitch;
    }
  }

  for (auto it = slices.begin(); it != slices.end(); ++it) {
    const auto nxt = std::next(it);
    if (nxt == slices.end()) break;
    const std::vector<int>& a = it->second;
    const std::vector<int>& b = nxt->second;
    for (size_t i = 0; i < p.tracks.size(); ++i) {
      for (size_t j = i + 1; j < p.tracks.size(); ++j) {
        if (a[i] < 0 || a[j] < 0 || b[i] < 0 || b[j] < 0) continue;
        const int move_i = b[i] - a[i];
        const int move_j = b[j] - a[j];
        if (move_i == 0 || move_j == 0) continue;
        if (sign_of(move_i) != sign_of(move_j)) continue;
        const int interval = std::abs(b[j] - b[i]);
        if (interval % 12 == 7) {
          ++report.parallel_fifths;
        } else if (interval > 0 && interval % 12 == 0) {
          ++report.parallel_octaves;
        }
      }
    }
  }

  // Strong-beat dissonance audit against one-chord-per-bar mapping.
  // Strong beat is start_tick % 480 == 0 (kStrongBeatMod above).
  const int bar_ticks = p.ticks_per_beat * p.beats_per_bar;
  if (bar_ticks > 0 && !chords.empty()) {
    for (const auto& t : p.tracks) {
      if (t.type == hf::core::TrackType::Drums) continue;  // unpitched map
      for (const auto& n : t.notes) {
        if (n.start_tick % kStrongBeatMod != 0) continue;  // weak beat: skip
        const int bar = n.start_tick / bar_ticks;
        if (bar < 0 || bar >= static_cast<int>(chords.size())) continue;
        const auto& chord = chords[static_cast<size_t>(bar)];
        const std::vector<int> iv = chord_intervals(chord);
        if (iv.empty()) continue;  // unknown chord: cannot judge
        const int root_pc = mod12(chord.root);
        for (int s : iv) {
          const int tone_pc = mod12(root_pc + s);
          const int d = std::abs(mod12(n.pitch) - tone_pc);
          const int pc_dist = std::min(d, 12 - d);
          if (pc_dist == 1) {
            ++report.strong_beat_dissonances;
            break;
          }
        }
      }
    }
  }

  return report;
}

}  // namespace hf::music
