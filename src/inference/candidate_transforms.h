// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate per-index character transforms TU (S3 slice 2):
// `apply_candidate_transform` + transforms-only helpers (none: the body calls
// only shared `detail/` names + core music libs — see
// docs/measurements/s3-helpers-transforms.md). Included directly by its
// consumers; declarations stay valid.
//
// B9 (phase-B tranche C, 2026-10-19): the body was dissected into named,
// file-local stages (`find_melody_track`, `apply_catchy_transform`,
// `apply_complex_transform`, `apply_unexpected_transform`); the public
// signature below is UNCHANGED.
#pragma once

#include <vector>

#include "core/model/note.h"
#include "pcg.h"

namespace hf::infer {

// Forward declaration (defined in detail/candidate_params.h): only referenced
// here, never named by value, so this header stays independent of the facade
// (no include cycle).
struct GenParams;

// Per-index character transforms (deterministic via rng): idx0 untouched,
// idx1 catchy 8th-note pulse, idx2 complex scalar runs, idx3 seeded octave
// jumps + syncopation. Signature unchanged from the pre-cut definition
// (rng arrives by reference; no `noexcept` was present, none added).
void apply_candidate_transform(core::Pattern& pat, const GenParams& p, int index,
                               const std::vector<int>& iv, Pcg32& rng);

}  // namespace hf::infer
