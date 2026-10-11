#include "core/music/scale.h"

#include <unordered_map>

namespace hf::music {
namespace {

const std::unordered_map<std::string_view, std::vector<int>>& table() {
  static const std::unordered_map<std::string_view, std::vector<int>> k = {
      {"major", {0, 2, 4, 5, 7, 9, 11}},
      {"dorian", {0, 2, 3, 5, 7, 9, 10}},
      {"phrygian", {0, 1, 3, 5, 7, 8, 10}},
      {"lydian", {0, 2, 4, 6, 7, 9, 11}},
      {"mixolydian", {0, 2, 4, 5, 7, 9, 10}},
      {"natural_minor", {0, 2, 3, 5, 7, 8, 10}},
      {"locrian", {0, 1, 3, 5, 6, 8, 10}},
      {"harmonic_minor", {0, 2, 3, 5, 7, 8, 11}},
      {"melodic_minor", {0, 2, 3, 5, 7, 9, 11}},
      {"major_pent", {0, 2, 4, 7, 9}},
      {"minor_pent", {0, 3, 5, 7, 10}},
  };
  return k;
}

int mod12(int v) { return ((v % 12) + 12) % 12; }

}  // namespace

std::vector<int> ScaleDatabase::intervals(std::string_view scale_name) {
  const auto it = table().find(scale_name);
  if (it == table().end()) return {};
  return it->second;
}

bool ScaleDatabase::is_in_scale(int pitch, int tonic, std::string_view scale_name) {
  return degree(pitch, tonic, scale_name) >= 0;
}

int ScaleDatabase::degree(int pitch, int tonic, std::string_view scale_name) {
  const auto iv = intervals(scale_name);
  if (iv.empty()) return -1;
  const int pc = mod12(pitch - tonic);
  for (size_t i = 0; i < iv.size(); ++i) {
    if (iv[i] == pc) return static_cast<int>(i);
  }
  return -1;
}

int ScaleDatabase::snap_to_scale(int pitch, int tonic, std::string_view scale_name) {
  const auto iv = intervals(scale_name);
  if (iv.empty()) return pitch;
  const int base = pitch - mod12(pitch - tonic);
  const int pc = mod12(pitch - tonic);
  int best_up = 12, best_down = -12;
  for (int s : iv) {
    const int d = s - pc;
    if (d >= 0 && d < best_up) best_up = d;
    if (d <= 0 && d > best_down) best_down = d;
  }
  // Tie (symmetric gap, e.g. semitone both sides) rounds up.
  const int delta = (-best_down < best_up) ? best_down : best_up;
  return base + pc + delta;
}

}  // namespace hf::music
