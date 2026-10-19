// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <array>
#include <string>

#include "core/model/note.h"
#include "inference_runner.h"

// `GenMode`/`GenParams` are part of THIS facade's own public API
// (`generate_candidates(const GenParams&)`, `progression_for_params`), so the
// facade legitimately includes the narrow params header. This is a real
// dependency, NOT a compatibility shim.
#include "detail/candidate_params.h"

namespace hf::infer {

// Diatonic triad-per-bar progression for `params` (degrees I-V-vi-IV cycled,
// quality derived from the scale thirds/fifths; always known chord types, so
// every generated bar has a judging chord). Bar count is params.bars clamped
// to 1..16; unknown scales yield an empty progression. Shared by generation
// and ranking so scores judge what generation targeted.
core::ChordProgression progression_for_params(const GenParams& params);

// Four deterministic candidates: index 0 Safe, 1 Catchy, 2 Complex,
// 3 Unexpected (SPEC §5.2).
//
// Determinism: SAME params + SAME seed -> bit-identical patterns. Candidates
// are built from OnnxRunner output (the mock model echoes its input) plus
// deterministic seeded transforms, so the property holds regardless of the
// model behind the runner; with no model path configured (Sprint 4 wires the
// real path from JUCE state) the runner stage falls back to the deterministic
// composer, identically in ONNX-ON and WITH_ONNX=OFF builds.
//
// Modes:
// - Strict: melody/bass snapped to (tonic, scale), then
//   resolve_harmonic_conflicts -> 100% in-scale AND strong-beat chord-safe.
// - Creative: Strict base plus chromatic passing tones on weak beats
//   (semitone approach to the next melody note, inserted only on 16th-grid
//   weak ticks); weak-beat tension survives resolve_harmonic_conflicts.
// - Experimental: modal-borrowing color. Melody/bass snap to the union of
//   (tonic, scale) and the parallel major/natural-minor pcs, and ~25%
//   (seeded) of weak-beat melody scale thirds/sixths/sevenths are
//   flattened (major-family scales: pc 4/9/11 -> 3/8/10) or sharpened
//   (minor-family: 3/8/10 -> 4/9/11; minor-family = names containing
//   "minor" plus dorian/phrygian/locrian/minor_pent). Strong-beat
//   minor-2nd rubs are still resolved in every mode.
//
// Caps: bars clamp to 1..16, unknown scales fall back to "major", and every
// output respects the codec caps (bars <= 16, notes <= 170, pitch 0..127,
// velocity 1..127, start >= 0, duration > 0). Never throws.
std::array<core::Pattern, 4> generate_candidates(const GenParams& params);

// Test/integration seam (Phase 2 Task 4, item D): the identical pipeline,
// but the runner stage delegates to `runner` instead of the OnnxRunner built
// from `params.model_path`. A stub returning empty reproduces the
// deterministic fallback; a fake-latency stub proves the async message flow
// without touching production timing. Never throws provided `runner` itself
// never throws (production OnnxRunner::predict catches everything and falls
// back to empty output; a throwing custom runner propagates to the caller —
// only the AsyncGenerateQueue worker path is unconditionally no-throw).
// Stable alongside generate_candidates for arrangement/distribution tasks.
std::array<core::Pattern, 4> generate_candidates_with_runner(const GenParams& params,
                                                             IInferenceRunner& runner);

}  // namespace hf::infer
