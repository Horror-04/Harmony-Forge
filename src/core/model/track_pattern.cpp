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

}  // namespace hf::core
