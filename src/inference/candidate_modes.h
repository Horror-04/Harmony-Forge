// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate mode post-processing TU (S3 slice 3): `apply_mode` + its
// modes-only helpers (`snap_to_pcs`, `is_minor_family`, `kGrid`;
// `scale_or_major` is facade-called, so it lives in `detail/` — see
// docs/measurements/s3-remainder.md). Re-exported through `candidates.h`;
// declarations stay valid.
#pragma once

#include <random>
#include <vector>

#include "core/model/note.h"

namespace hf::infer {

// Forward declaration (defined in detail/candidate_params.h): only referenced
// here, never named by value, so no include cycle with the candidates.h
// re-export.
struct GenParams;

// Mode post-processing (deterministic via rng): Strict snaps to scale,
// Creative adds weak-beat chromatic passing tones, Experimental snaps to the
// scale/parallel union with weak-beat modal-borrowing color. Signature
// unchanged from the pre-cut definition (rng arrives by reference; no
// `noexcept` was present, none added).
void apply_mode(core::Pattern& pat, const GenParams& p, const core::ChordProgression& prog,
                const std::vector<int>& iv, std::mt19937& rng);

}  // namespace hf::infer
