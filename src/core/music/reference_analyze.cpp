// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "core/music/reference_analyze.h"

#include "core/model/track_pattern.h"
#include "core/music/chord_detect.h"

namespace hf::music {

AnalysisReport analyze_reference(const core::Pattern& p) {
  AnalysisReport rep;
  for (const auto& t : p.tracks) {
    if (t.type == hf::core::TrackType::Drums)
      rep.drum_note_count += static_cast<int>(t.notes.size());
  }

  int pitched = 0;
  for (const auto& t : p.tracks) {
    if (t.type == hf::core::TrackType::Drums) continue;
    pitched += static_cast<int>(t.notes.size());
  }
  if (pitched < 2) return rep;  // default key, empty chords, density 0

  rep.enough_data = true;
  rep.key = detect_key(p);

  const int bars = hf::core::pattern_num_bars(p);
  const int bar_ticks = p.ticks_per_beat * p.beats_per_bar;
  rep.chords.reserve(static_cast<size_t>(bars > 0 ? bars : 0));
  for (int b = 0; b < bars; ++b) {
    std::vector<int> pitches;
    if (bar_ticks > 0) {
      for (const auto& t : p.tracks) {
        if (t.type == hf::core::TrackType::Drums) continue;
        for (const auto& n : t.notes) {
          if (n.start_tick >= 0 && n.start_tick / bar_ticks == b)
            pitches.push_back(n.pitch);
        }
      }
    }
    // recognize_chord drops out-of-range pitches and maps empty input to
    // root 60 / "unknown" (the missing-bar placeholder, skipped by adopt).
    rep.chords.push_back(recognize_chord(pitches));
  }

  if (bars > 0) {
    rep.density_notes_per_bar = static_cast<double>(hf::core::pattern_note_count(p)) /
                                static_cast<double>(bars);
  }
  return rep;
}

}  // namespace hf::music
