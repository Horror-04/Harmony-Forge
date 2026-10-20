// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate composer shared helpers (S3 slice 1): grid constants + the
// TU-shared small functions, all `inline` so every candidate TU sees exactly
// one definition.
//
// Phase-B B4a: the pitch-class helper (`mod12`), the octave pull
// (`octave_pull`) and the melody/bass register constants had ONE tree-wide
// definition in `core/music/pitch_class.h` (reachable from core AND
// inference, owner decision D-B4); the copies that used to live here and in
// keynorm.cpp were byte-identical, so they were moved, not rewritten. The
// using-declarations below re-export the shared names into
// `hf::infer::detail` so the candidate TUs keep their
// `using namespace detail` bodies text-identical.
#pragma once

#include <string>
#include <vector>

#include "core/music/pitch_class.h"

namespace hf::infer::detail {

constexpr int kBeatsPerBar = 4;
constexpr int kBarTicks = 480 * kBeatsPerBar;  // 1920

using hf::music::kBassHi;
using hf::music::kBassLo;
using hf::music::kMelodyHi;
using hf::music::kMelodyLo;
using hf::music::mod12;
using hf::music::octave_pull;

}  // namespace hf::infer::detail
