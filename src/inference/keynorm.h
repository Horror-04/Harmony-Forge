// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <cstddef>
#include <string>

#include "core/model/note.h"

namespace hf::infer {

// Key-normalized inference views (Phase 9 Task 5b): C++ mirror of
// training/keynorm.py (behavior 1:1 — pinned by tests/test_keynorm.cpp
// python-parity vectors). JUCE-free, never throws (see sampler.h style).
//
// Canonical keys: major -> C (tonic pc 0), every other scale ->
// A-natural-minor reference (tonic pc 9), PRESERVING the mode (pure
// transposition, no conversion). Drums (TrackType::Drums) are NEVER
// transposed. Melody/Bass get octave_pull into 60..84 / 24..60
// (mirroring candidates.cpp); all other pitched tracks only shift +
// clamp to 0..127.
//
// THREADING (hard gate, same as sampler.h): background threads ONLY —
// drive exclusively through the background generate path
// (generate_candidates_impl, reached via generate_candidates /
// generate_candidates_with_runner / AsyncGenerateQueue). NEVER call from
// processBlock (real-time audio thread).
//
// CONTRACT: `shift` is the minimal signed transpose in -6..+5 taking
// `tonic` to the canonical pitch class. Wrap caveat (documented, tested
// both sides): the minimal shift wraps at +-6, so exact transpositions a
// fourth/fifth apart can normalize an octave apart; pitch CLASSES are
// always invariant, absolute ids exactly for wrap-free pairs.

// Canonical tonic pitch class for a scale name ("major" -> 0, else 9).
// Never throws.
int keynorm_canonical_pc(const std::string& scale) noexcept;

// Minimal signed shift in -6..+5 taking tonic pc to the canonical pc.
// Never throws.
int keynorm_canonical_shift(int tonic, const std::string& scale) noexcept;

// Flat-codec transpose to the canonical key ([count, 6-tuples]); writes
// exactly `n` words to `out`, `shift` receives the applied transpose.
// False on bad buffers (nulls, short cap, length/count mismatch); never
// throws. Caller-owned fixed buffers (no allocation in here).
bool keynorm_to_canonical(const int* ids, size_t n, int tonic,
                          const std::string& scale, int* out, size_t cap,
                          int& shift) noexcept;

// Exact inverse (shifts back by -shift, no octave pull, drums untouched).
// Same buffer contract as above; never throws.
bool keynorm_from_canonical(const int* ids, size_t n, int shift, int* out,
                            size_t cap) noexcept;

// Pattern-level hook used by the background generate path: transpose `pat`
// to canonical in place (returns the applied shift), and its inverse.
// Never throws (failure -> shift 0 / best-effort no-op).
int shift_pattern_to_canonical(core::Pattern& pat, int tonic,
                               const std::string& scale) noexcept;
void shift_pattern_from_canonical(core::Pattern& pat, int shift) noexcept;

}  // namespace hf::infer
