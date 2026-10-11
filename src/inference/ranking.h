#pragma once

#include <string>

#include "candidates.h"
#include "core/model/note.h"

namespace hf::infer {

// Automated Strict-compliance measurement (SPEC §16: >= 0.90-0.95 of notes
// respect user constraints): fraction (0..1) of Melody+Bass notes that are
// BOTH in (tonic, scale) AND free of strong-beat (start_tick % 480 == 0)
// minor-2nd rubs against the bar-indexed chord. Bars without a known chord
// count as safe (consistent with resolve_harmonic_conflicts leaving them
// untouched). Patterns with no Melody/Bass notes score 1.0 (vacuous).
// Deterministic pure function; never throws.
float strict_compliance(const core::Pattern& p, const core::ChordProgression& chords,
                        int tonic, const std::string& scale);

// Deterministic stub scorer (SPEC §8 Ranking Model placeholder):
//   0.5 * in-scale fraction + 0.3 * strong-beat-safe fraction
//   + 0.2 * in-register fraction
// over Melody+Bass notes, judging against progression_for_params(params).
// Patterns with no Melody/Bass notes score 0.0. Sprint 4 replaces the stub
// with a trained model; the signature stays. Never throws.
float rank_candidate(const core::Pattern& p, const GenParams& params);

}  // namespace hf::infer
