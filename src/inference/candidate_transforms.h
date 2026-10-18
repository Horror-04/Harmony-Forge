// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate per-index character transforms TU (S3 slice 2):
// `apply_candidate_transform` + transforms-only helpers (none: the body calls
// only shared `detail/` names + core music libs — see
// docs/measurements/s3-helpers-transforms.md). Re-exported through
// `candidates.h`; declarations stay valid.
#pragma once

#include <vector>

#include "core/model/note.h"
#include "pcg.h"

namespace hf::infer {

// Forward declaration (defined in detail/candidate_params.h): only referenced
// here, never named by value, so no include cycle with the candidates.h
// re-export.
struct GenParams;

// Per-index character transforms (deterministic via rng): idx0 untouched,
// idx1 catchy 8th-note pulse, idx2 complex scalar runs, idx3 seeded octave
// jumps + syncopation. Signature unchanged from the pre-cut definition
// (rng arrives by reference; no `noexcept` was present, none added).
void apply_candidate_transform(core::Pattern& pat, const GenParams& p, int index,
                               const std::vector<int>& iv, Pcg32& rng);

}  // namespace hf::infer
