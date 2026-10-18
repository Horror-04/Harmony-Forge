// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate per-index character transforms TU (S3 slice 2):
// `apply_candidate_transform` moved byte-identically from
// `src/inference/candidates.cpp` (pre-cut 228-306; see tools/check_bodies_s3.json).
// Shared names resolve to `detail/` via the using-directive below, so the
// moved body carries zero edits; `GenParams`/`GenMode` arrive via the narrow
// `detail/candidate_params.h` (never the candidates.h re-export header).
#include "candidate_transforms.h"

#include <algorithm>
#include <vector>

#include "core/model/note.h"
#include "core/music/ranges.h"
#include "core/music/scale.h"
#include "detail/candidate_helpers.h"
#include "detail/candidate_params.h"
#include "pcg.h"

namespace hf::infer {
namespace {

using namespace detail;

}  // namespace

void apply_candidate_transform(core::Pattern& pat, const GenParams& p, int index,
                               const std::vector<int>& iv, Pcg32& rng) {
  const int n = static_cast<int>(iv.size());
  core::Track* melody = nullptr;
  for (auto& t : pat.tracks)
    if (t.type == core::TrackType::Melody) melody = &t;
  if (melody == nullptr) return;

  if (index == 1) {
    // Catchy: 8th-note pulse (second 8th repeats), hook = bar-0 head
    // transposed by the bar-root delta and snapped to scale.
    std::vector<core::Note> eighths;
    eighths.reserve(melody->notes.size() * 2);
    for (const auto& m : melody->notes) {
      eighths.push_back(core::Note{m.pitch, m.start_tick, 240, 92});
      eighths.push_back(core::Note{m.pitch, m.start_tick + 240, 240, 80});
    }
    melody->notes = std::move(eighths);
    if (melody->notes.size() >= 2) {
      const int head0 = melody->notes[0].pitch;
      const int head1 = melody->notes[1].pitch;
      for (int b = 1; b < p.bars; ++b) {
        const int base = b * kBarTicks;
        for (auto& m : melody->notes) {
          if (m.start_tick == base)
            m.pitch = hf::music::ScaleDatabase::snap_to_scale(head0, p.tonic, p.scale);
          else if (m.start_tick == base + 240)
            m.pitch = hf::music::ScaleDatabase::snap_to_scale(head1, p.tonic, p.scale);
        }
      }
    }
  } else if (index == 2) {
    // Complex: last beat of each bar becomes a 4x16th scalar run upward.
    std::vector<core::Note> out;
    out.reserve(melody->notes.size() + 3 * p.bars);
    for (const auto& m : melody->notes) {
      const int pos = m.start_tick % kBarTicks;
      if (pos == 3 * 480) {
        int d = hf::music::ScaleDatabase::degree(m.pitch, p.tonic, p.scale);
        if (d < 0)
          d = hf::music::ScaleDatabase::degree(
              hf::music::ScaleDatabase::snap_to_scale(m.pitch, p.tonic, p.scale),
              p.tonic, p.scale);
        if (d < 0) d = 0;
        const int center = m.pitch - (iv[d % n] - iv[0]);
        for (int k = 0; k < 4; ++k) {
          const int dd = d + k;
          int pp = center + (iv[dd % n] - iv[0]) + 12 * (dd / n);
          pp = octave_pull(pp, kMelodyLo, kMelodyHi);
          out.push_back(core::Note{pp, m.start_tick + k * 120, 120, 85});
        }
      } else {
        out.push_back(m);
      }
    }
    melody->notes = std::move(out);
  } else if (index == 3) {
    // Unexpected: seeded octave jumps + 8th-offbeat syncopation (in-bar).
    for (auto& m : melody->notes) {
      if (rng.uniform(3) == 0) {
        const int up = rng.uniform(2) == 0;
        int cand = m.pitch + (up ? 12 : -12);
        if (!hf::music::in_register(core::TrackType::Melody, cand) ||
            cand < 0 || cand > 127)
          cand = m.pitch - (up ? 12 : -12);
        if (hf::music::in_register(core::TrackType::Melody, cand) && cand >= 0 &&
            cand <= 127)
          m.pitch = cand;
      }
      if (rng.uniform(4) == 0) {
        const int pos = m.start_tick % kBarTicks;
        if (pos + 240 < kBarTicks) {
          m.start_tick += 240;  // stays on the 16th grid, stays in-bar
          m.duration_ticks = std::max(120, std::min(m.duration_ticks, kBarTicks - pos - 240));
        }
      }
    }
  }
}

}  // namespace hf::infer
