// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate model-material TU (S3 slice 4a): greedy runner material
// (`material_from_runner`, `material_with_runner`,
// `material_from_runner_with`) + the sampler-adjacent model group
// (`sampler_provider_cache`, `sampler_provider_for`,
// `sampling_unavailable_once`, `production_sampler_cfg`,
// `material_via_sampler_or_greedy`, which holds the single
// `sample_continue` call-site), moved byte-identically from
// `src/inference/candidates.cpp` (pre-cut 186-225 + 404-515; see
// tools/check_bodies_s3.json). Re-exported through `candidates.h`;
// declarations stay valid. Narrow includes only (never candidates.h).
#pragma once

#include <string>

#include "core/model/note.h"
#include "inference_runner.h"

namespace hf::infer {

// Forward declaration (defined in detail/candidate_params.h): only referenced
// here, never named by value, so no include cycle with the candidates.h
// re-export.
struct GenParams;

// Runner stage: encode the base, run the model, decode (empty model path
// keeps the unloaded-runner fallback). Signature unchanged from the pre-cut
// definition.
core::Pattern material_from_runner(const core::Pattern& base, unsigned seed);

// Task 4 runner stage: `model_path` selects the weights, non-null
// `runner_override` replaces OnnxRunner for the call. Signature unchanged
// from the pre-cut definition.
core::Pattern material_from_runner_with(const core::Pattern& base, unsigned seed,
                                        const std::string& model_path,
                                        IInferenceRunner* runner_override);

// Sampling material stage with greedy fallback (holds the single
// `sample_continue` call-site). Signature unchanged from the pre-cut
// definition.
core::Pattern material_via_sampler_or_greedy(const core::Pattern& feed, const GenParams& p,
                                             const core::ChordProgression& prog,
                                             int kn_shift, int index);

}  // namespace hf::infer
