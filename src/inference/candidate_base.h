// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate base composer TU (S3 slice 1): `compose_base` + its TU-local
// helpers. Included directly by its consumers; declarations stay valid.
#pragma once

#include <vector>

#include "core/model/note.h"
#include "pcg.h"

namespace hf::infer {

// Forward declaration (defined in detail/candidate_params.h): only referenced here,
// never named by value, so this header stays independent of the facade
// (no include cycle).
struct GenParams;

// Deterministic quarter-note base: scale-walk melody with chord-tone bias,
// roots-and-fifths bass, sustained triads. All starts on the 16th grid.
core::Pattern compose_base(const GenParams& p, const core::ChordProgression& prog,
                           const std::vector<int>& iv, Pcg32& rng);

}  // namespace hf::infer
