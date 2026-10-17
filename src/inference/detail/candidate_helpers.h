// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate composer shared helpers (S3 slice 1): grid/register constants +
// TU-shared small functions, all `inline` so every candidate TU sees exactly
// one definition. Bodies are verbatim copies of the pre-cut
// `src/inference/candidates.cpp` anonymous-namespace originals; the exported
// names live in `hf::infer::detail` and the candidate TUs pull them in with a
// `using namespace detail` directive, so moved bodies need zero edits.
#pragma once

#include <string>
#include <vector>

#include "core/music/scale.h"

namespace hf::infer::detail {

constexpr int kBeatsPerBar = 4;
constexpr int kBarTicks = 480 * kBeatsPerBar;  // 1920
constexpr int kMelodyLo = 60;                  // C3 register floor
constexpr int kMelodyHi = 84;
constexpr int kBassLo = 24;
constexpr int kBassHi = 60;  // C3 register ceiling

inline int mod12(int v) { return ((v % 12) + 12) % 12; }

inline int octave_pull(int pitch, int lo, int hi) {
  while (pitch > hi) pitch -= 12;
  while (pitch < lo) pitch += 12;
  return pitch;
}

// Facade-called scale lookup with major fallback (S3 slice 3): the single
// caller is `generate_candidates_impl`, which passes the result into the
// mode/transform stages as `iv`. Body verbatim from the pre-cut
// `src/inference/candidates.cpp` anonymous-namespace original.
inline std::vector<int> scale_or_major(const std::string& scale) {
  auto iv = hf::music::ScaleDatabase::intervals(scale);
  if (!iv.empty()) return iv;
  return hf::music::ScaleDatabase::intervals("major");
}

}  // namespace hf::infer::detail
