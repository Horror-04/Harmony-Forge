// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "core/model/track_pattern.h"

namespace hf::core {

int pattern_num_bars(const Pattern& p) {
  if (p.tracks.empty()) return 0;
  int last_end = 0;
  for (const auto& t : p.tracks) {
    for (const auto& n : t.notes) {
      const int end = n.start_tick + n.duration_ticks;
      if (end > last_end) last_end = end;
    }
  }
  const int bar_ticks = p.ticks_per_beat * p.beats_per_bar;
  if (bar_ticks <= 0) return 0;
  return (last_end + bar_ticks - 1) / bar_ticks;
}

int pattern_note_count(const Pattern& p) {
  int n = 0;
  for (const auto& t : p.tracks) n += static_cast<int>(t.notes.size());
  return n;
}

namespace {

bool same_chord(const ChordSymbol& a, const ChordSymbol& b) {
  return a.root == b.root && a.type == b.type && a.inversion == b.inversion &&
         a.tension == b.tension;
}

}  // namespace

ChordMergeResult merge_reference_chords(const ChordProgression& existing,
                                        const std::vector<ChordSymbol>& ref) {
  ChordMergeResult out;
  out.merged = existing;
  for (size_t i = 0; i < ref.size(); ++i) {
    if (ref[i].type == "unknown") continue;  // missing bar: untouched
    if (i < out.merged.size()) {
      if (!same_chord(out.merged[i], ref[i])) {
        out.merged[i] = ref[i];
        out.changed = true;
      }
    } else {
      out.merged.push_back(ref[i]);
      out.changed = true;
    }
  }
  return out;
}

}  // namespace hf::core
