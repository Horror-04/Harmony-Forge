// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate mode post-processing TU (S3 slice 3): `apply_mode` + its
// modes-only helpers (`snap_to_pcs`, `is_minor_family`, `kGrid`).
// Included directly by its consumers; declarations stay valid.
//
// B9 (phase-B tranche C, 2026-10-19): the body was dissected into named,
// file-local stages (`is_modal_color`, `snap_to_parallel_union`,
// `apply_modal_color`, `insert_chromatic_passing_tones`); the public
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

// Mode post-processing (deterministic via rng): Strict snaps to scale,
// Creative adds weak-beat chromatic passing tones, Experimental snaps to the
// scale/parallel union with weak-beat modal-borrowing color. Signature
// unchanged from the pre-cut definition (rng arrives by reference; no
// `noexcept` was present, none added).
void apply_mode(core::Pattern& pat, const GenParams& p, const core::ChordProgression& prog,
                const std::vector<int>& iv, Pcg32& rng);

}  // namespace hf::infer
