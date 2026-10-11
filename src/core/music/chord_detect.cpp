#include "core/music/chord_detect.h"

#include <array>
#include <string_view>

#include "core/music/chord.h"

namespace hf::music {
namespace {

// Candidate chord types, most specific first so exact-match search prefers
// the richest spelling (13 before 7 before triad). Order among equal-size
// templates is fixed for determinism.
constexpr std::array<std::string_view, 16> kTypes = {
    "13",  "11",   "m9",  "9",    "maj7", "m7",  "7",   "add9",
    "6",   "m6",   "dim", "aug",  "sus2", "sus4", "maj", "min",
};

int mod12(int v) { return ((v % 12) + 12) % 12; }

// Lowest input pitch carrying pitch class root_pc; falls back to a
// 60-anchored pitch when no input pitch carries that class.
int root_pitch(int bass, int root_pc, const std::vector<int>& valid) {
  if (mod12(bass) == root_pc) return bass;
  int out = 60 + root_pc;
  for (int p : valid) {
    if (mod12(p) == root_pc && p < out) out = p;
  }
  return out;
}

}  // namespace

hf::core::ChordSymbol recognize_chord(const std::vector<int>& pitches) {
  // Pitch is 0..127 per project convention; out-of-range values carry no
  // pitch class and are ignored. Nothing usable -> safe root-60 anchor.
  std::vector<int> valid;
  valid.reserve(pitches.size());
  for (int p : pitches) {
    if (p >= 0 && p <= 127) valid.push_back(p);
  }
  if (valid.empty()) return hf::core::ChordSymbol{60, "unknown"};

  int bass = valid[0];
  for (int p : valid)
    if (p < bass) bass = p;
  const int bass_pc = mod12(bass);

  std::array<bool, 12> pcs{};
  int distinct = 0;
  for (int p : valid) {
    const int c = mod12(p);
    if (!pcs[c]) {
      pcs[c] = true;
      ++distinct;
    }
  }
  if (distinct < 2) return hf::core::ChordSymbol{bass, "unknown"};

  // Root candidates: bass pitch class first, then the rest ascending.
  // Deterministic; the bass-first order resolves C6/Am7-style ambiguity.
  std::array<int, 12> roots{};
  roots[0] = bass_pc;
  int n = 1;
  for (int c = 0; c < 12; ++c) {
    if (c == bass_pc) continue;
    roots[n++] = c;
  }

  int best_size = -1;
  hf::core::ChordSymbol best{bass, "unknown"};
  for (int root_pc : roots) {
    for (std::string_view type : kTypes) {
      const std::vector<int> iv =
          chord_intervals(hf::core::ChordSymbol{60, std::string(type)});
      if (iv.empty()) continue;
      bool contained = true;
      for (int s : iv) {
        if (!pcs[mod12(root_pc + s)]) {
          contained = false;
          break;
        }
      }
      if (!contained) continue;
      const int size = static_cast<int>(iv.size());
      // Exact matches (size == distinct) beat supersets; first hit at a
      // given specificity wins (bass root first, richer types first).
      if (size == distinct) {
        return hf::core::ChordSymbol{root_pitch(bass, root_pc, valid), std::string(type)};
      }
      if (size > best_size) {
        best_size = size;
        best = hf::core::ChordSymbol{root_pitch(bass, root_pc, valid), std::string(type)};
      }
    }
  }
  return best;
}

}  // namespace hf::music
