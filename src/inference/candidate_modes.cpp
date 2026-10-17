// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate mode post-processing TU (S3 slice 3): `apply_mode` moved
// byte-identically from `src/inference/candidates.cpp` (pre-cut 311-364;
// see tools/check_bodies_s3.json) with its modes-only helpers
// (`snap_to_pcs`, `is_minor_family`, `kGrid`; `scale_or_major` is
// facade-called and lives in `detail/candidate_helpers.h`). Shared names
// resolve to `detail/` via the using-directive below, so the moved bodies
// carry zero edits; `GenParams`/`GenMode` arrive via the narrow
// `detail/candidate_params.h` (never the candidates.h re-export header).
#include "candidate_modes.h"

#include <algorithm>
#include <cstdlib>
#include <random>
#include <string>
#include <vector>

#include "constraints.h"
#include "core/model/note.h"
#include "core/model/pattern_ops.h"
#include "core/music/ranges.h"
#include "core/music/scale.h"
#include "detail/candidate_helpers.h"
#include "detail/candidate_params.h"

namespace hf::infer {
namespace {

using namespace detail;

constexpr int kGrid = 120;                     // 16th note

// Nearest pitch to `pitch` whose class (relative to tonic) is in
// `allowed_pcs`. Ties round up. Result clamped to 0..127.
int snap_to_pcs(int pitch, int tonic, const std::vector<int>& allowed_pcs) {
  if (allowed_pcs.empty()) return std::clamp(pitch, 0, 127);
  bool wanted[12] = {};
  for (int s : allowed_pcs) wanted[mod12(s)] = true;
  const int pc = mod12(pitch - tonic);
  if (wanted[pc]) return std::clamp(pitch, 0, 127);
  for (int d = 1; d <= 12; ++d) {
    if (wanted[mod12(pc + d)] && pitch + d <= 127) return pitch + d;
    if (wanted[mod12(pc - d)] && pitch - d >= 0) return pitch - d;
  }
  // Unreachable: for any pitch in 0..127 one of the two directions always
  // fits within d <= 11 (d_up + d_down == 12, so a blocked upward step
  // implies room downward and vice versa).
  return std::clamp(pitch, 0, 127);
}

bool is_minor_family(const std::string& scale) {
  if (scale.find("minor") != std::string::npos) return true;
  return scale == "dorian" || scale == "phrygian" || scale == "locrian" ||
         scale == "minor_pent";
}

}  // namespace

void apply_mode(core::Pattern& pat, const GenParams& p, const core::ChordProgression& prog,
                const std::vector<int>& iv, std::mt19937& rng) {
  if (p.mode == GenMode::Experimental) {
    const std::vector<int> parallel = is_minor_family(p.scale)
                                          ? hf::music::ScaleDatabase::intervals("major")
                                          : hf::music::ScaleDatabase::intervals("natural_minor");
    std::vector<int> allowed = iv;
    allowed.insert(allowed.end(), parallel.begin(), parallel.end());
    for (auto& t : pat.tracks) {
      if (t.type == hf::core::TrackType::Drums) continue;
      for (auto& m : t.notes)
        m.pitch = snap_to_pcs(m.pitch, p.tonic, allowed);
    }
    // Modal-borrowing color on weak beats only (strong beats stay safe).
    const bool minor = is_minor_family(p.scale);
    for (auto& t : pat.tracks) {
      if (t.type != hf::core::TrackType::Melody) continue;
      for (auto& m : t.notes) {
        if (m.start_tick % 480 == 0) continue;
        const int rel = mod12(m.pitch - p.tonic);
        const bool color = minor ? (rel == 3 || rel == 8 || rel == 10)
                                 : (rel == 4 || rel == 9 || rel == 11);
        if (!color || (rng() % 100) >= 25) continue;
        const int cand = m.pitch + (minor ? 1 : -1);
        if (cand >= 0 && cand <= 127 &&
            hf::music::in_register(core::TrackType::Melody, cand))
          m.pitch = cand;
      }
    }
  } else {
    hf::core::snap_pattern_to_scale(pat, p.tonic, p.scale);
    if (p.mode == GenMode::Creative) {
      // Chromatic passing tones: semitone approach to the next melody note,
      // inserted at the midpoint when it lands on a weak 16th-grid tick.
      for (auto& t : pat.tracks) {
        if (t.type != hf::core::TrackType::Melody) continue;
        std::vector<core::Note> extra;
        for (size_t i = 0; i + 1 < t.notes.size(); ++i) {
          const auto& a = t.notes[i];
          const auto& b = t.notes[i + 1];
          if (a.start_tick / kBarTicks != b.start_tick / kBarTicks) continue;
          const int gap = b.pitch - a.pitch;
          if (std::abs(gap) < 3) continue;
          const int mid = (a.start_tick + b.start_tick) / 2;
          if (mid % kGrid != 0 || mid % 480 == 0) continue;
          const int approach = b.pitch - (gap > 0 ? 1 : -1);
          extra.push_back(core::Note{std::clamp(approach, 0, 127), mid, 120, 70});
        }
        t.notes.insert(t.notes.end(), extra.begin(), extra.end());
      }
    }
  }
  resolve_harmonic_conflicts(pat, prog);
}

}  // namespace hf::infer
