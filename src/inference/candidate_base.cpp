// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate base composer TU (S3 slice 1, step 1): `compose_base` + its
// TU-local helpers, moved byte-identically from `src/inference/candidates.cpp`
// (pre-cut 118-174 + helper 108-114; see tools/check_bodies_s3.json).
// Shared names resolve to `detail/candidate_helpers.h` via the using-directive
// below, so the moved bodies carry zero edits.
#include "candidate_base.h"

#include <algorithm>
#include <cstdint>
#include <string>
#include <vector>

#include "candidates.h"
#include "core/music/chord.h"
#include "detail/candidate_helpers.h"

namespace hf::infer {
namespace {

using namespace detail;

// Chord-tone pitch classes for a progression chord (empty for unknown type).
std::vector<int> tone_pcs(const core::ChordSymbol& c) {
  const auto iv = hf::music::chord_intervals(c);
  std::vector<int> out;
  out.reserve(iv.size());
  for (int s : iv) out.push_back(mod12(c.root + s));
  return out;
}

}  // namespace

// Deterministic quarter-note base: scale-walk melody with chord-tone bias,
// roots-and-fifths bass, sustained triads. All starts on the 16th grid.
core::Pattern compose_base(const GenParams& p, const core::ChordProgression& prog,
                           const std::vector<int>& iv, std::mt19937& rng) {
  core::Pattern pat;
  pat.ticks_per_beat = 480;
  pat.beats_per_bar = kBeatsPerBar;
  const int n = static_cast<int>(iv.size());

  int center = std::clamp(p.tonic, 0, 127);
  while (center + 12 <= kMelodyHi) center += 12;
  while (center < kMelodyLo) center += 12;
  while (center > kMelodyHi) center -= 12;

  core::Track melody, bass, chords;
  melody.type = core::TrackType::Melody;
  bass.type = core::TrackType::Bass;
  chords.type = core::TrackType::Chords;

  int deg = static_cast<int>(rng() % static_cast<uint32_t>(2 * n));
  for (int b = 0; b < p.bars; ++b) {
    const core::ChordSymbol& ch = prog[static_cast<size_t>(b)];
    const std::vector<int> pcs = tone_pcs(ch);
    for (int q = 0; q < kBeatsPerBar; ++q) {
      int pitch;
      if (!pcs.empty() && (rng() % 100) < 70) {
        // Chord-tone bias: nearest pitch to center with a chord-tone class.
        const int want = pcs[rng() % pcs.size()];
        const int delta = mod12(want - mod12(center));
        const int signed_delta = (delta <= 6) ? delta : delta - 12;
        pitch = octave_pull(center + signed_delta, kMelodyLo, kMelodyHi);
      } else {
        deg = std::clamp(deg + static_cast<int>(rng() % 5) - 2, 0, 2 * n - 1);
        pitch = center + (iv[deg % n] - iv[0]) + 12 * (deg / n);
        pitch = octave_pull(pitch, kMelodyLo, kMelodyHi);
      }
      melody.notes.push_back(
          core::Note{pitch, b * kBarTicks + q * 480, 480, 88 + (q == 0 ? 8 : 0)});
    }
    // Bass: root on beat 0, fifth (or root) on beat 2.
    int root = ch.root;
    while (root > kBassHi) root -= 12;
    while (root < kBassLo) root += 12;
    bass.notes.push_back(core::Note{root, b * kBarTicks, 480, 96});
    const int fifth = root + 7;
    bass.notes.push_back(
        core::Note{fifth <= kBassHi ? fifth : root, b * kBarTicks + 960, 480, 84});
    // Chords: sustained triad voicing near the bass.
    const auto offsets = hf::music::chord_intervals(ch);
    int cr = ch.root;
    while (cr > kBassHi) cr -= 12;
    while (cr < 36) cr += 12;
    for (int s : offsets)
      chords.notes.push_back(
          core::Note{std::clamp(cr + s, 0, 127), b * kBarTicks, kBarTicks, 70});
  }
  pat.tracks = {melody, bass, chords};
  return pat;
}

}  // namespace hf::infer
