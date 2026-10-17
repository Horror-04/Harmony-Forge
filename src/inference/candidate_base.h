// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate base composer TU (S3 slice 1): `compose_base` + its TU-local
// helpers. Re-exported through `candidates.h`; declarations stay valid.
#pragma once

#include <random>
#include <vector>

#include "core/model/note.h"

namespace hf::infer {

// Forward declaration (defined in detail/candidate_params.h): only referenced here,
// never named by value, so no include cycle with the candidates.h re-export.
struct GenParams;

// Deterministic quarter-note base: scale-walk melody with chord-tone bias,
// roots-and-fifths bass, sustained triads. All starts on the 16th grid.
core::Pattern compose_base(const GenParams& p, const core::ChordProgression& prog,
                           const std::vector<int>& iv, std::mt19937& rng);

}  // namespace hf::infer
