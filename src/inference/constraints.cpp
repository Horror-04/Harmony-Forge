#include "constraints.h"

#include <algorithm>
#include <cstdlib>
#include <vector>

#include "core/music/chord.h"
#include "core/music/quantizer.h"
#include "core/music/ranges.h"

namespace hf::infer {
namespace {

constexpr int kStrongBeatMod = 480;  // every quarter-note line at 480 PPQ
constexpr int kGrid = 120;           // 16th-note grid at 480 PPQ

int mod12(int v) { return ((v % 12) + 12) % 12; }

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

bool is_minor_2nd_rub(int pitch, const std::vector<int>& chord_intervals, int root_pc) {
  const int pc = mod12(pitch);
  for (int s : chord_intervals) {
    const int tone_pc = mod12(root_pc + s);
    const int d = std::abs(pc - tone_pc);
    if (std::min(d, 12 - d) == 1) return true;
  }
  return false;
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
      if (n.start_tick % kStrongBeatMod != 0) continue;  // weak beat: keep
      if (bar_ticks <= 0) continue;
      const int bar = n.start_tick / bar_ticks;
      if (bar < 0 || bar >= static_cast<int>(chords.size())) continue;  // no chord: keep
      const auto& chord = chords[static_cast<size_t>(bar)];
      const std::vector<int> iv = hf::music::chord_intervals(chord);
      if (iv.empty()) continue;  // unknown chord: leave bar untouched
      if (!is_minor_2nd_rub(n.pitch, iv, mod12(chord.root))) continue;
      std::vector<int> tone_pcs;
      tone_pcs.reserve(iv.size());
      for (int s : iv) tone_pcs.push_back(mod12(chord.root) + s);
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
