// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate shared parameter types (S3 slice 2): `GenMode` + `GenParams`,
// moved verbatim from `candidates.h` so the candidate TUs (`candidate_base`,
// `candidate_transforms`, modes, facade) share one narrow header instead of
// the mega-header. This header is the facade's OWN public-API dependency:
// `GenMode`/`GenParams` appear in the facade's signatures
// (`generate_candidates(const GenParams&)`, `progression_for_params`), so the
// facade includes it directly; the candidate TUs include it directly as well
// (their headers only forward-declare `GenParams`).
#pragma once

#include <cctype>
#include <optional>
#include <string>
#include <string_view>

namespace hf::infer {

// Generation modes (SPEC §5.1).
enum class GenMode { Strict, Creative, Experimental };

// Canonical display/persistence name ("Strict", "Creative", "Experimental").
// Phase-B B2: the arrange state stores the mode by this name, so the UI
// label, the saved property and the GenParams value cannot drift apart.
inline const char* gen_mode_name(GenMode m) {
  switch (m) {
    case GenMode::Strict:
      return "Strict";
    case GenMode::Creative:
      return "Creative";
    case GenMode::Experimental:
      return "Experimental";
  }
  return "Strict";
}

// Case-insensitive parse of the canonical names; nullopt for anything else
// (callers clamp, never guess). Empty/all-whitespace input is not a mode.
inline std::optional<GenMode> gen_mode_from_name(std::string_view name) {
  std::string lower;
  lower.reserve(name.size());
  for (const char c : name)
    lower.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
  if (lower == "strict") return GenMode::Strict;
  if (lower == "creative") return GenMode::Creative;
  if (lower == "experimental") return GenMode::Experimental;
  return std::nullopt;
}

struct GenParams {
  GenMode mode = GenMode::Strict;
  int seed = 0;
  int bars = 4;
  int tonic = 60;             ///< MIDI pitch anchor (pitch class = tonic % 12)
  std::string scale = "major";  ///< lowercase scale name (see ScaleDatabase)
  /// Model file wired from state (Phase 2 Task 4, item A). Default empty ==
  /// pre-Task-4 behavior: the runner stage is unloaded and generation falls
  /// back to the deterministic composer. Non-empty builds OnnxRunner with
  /// this path (real weights). Deliberately EXCLUDED from the candidate
  /// stream seeds, so empty-path output is bit-identical to before.
  std::string model_path;
  /// Key-normalized inference (Phase 9 Task 5b): when true, the background
  /// generate path transposes the runner feed to the canonical key (major
  /// -> C, else -> A, drums untouched) before the runner stage and shifts
  /// the decoded material back after. Default false == pre-task behavior
  /// (the hook is inert; output bit-identical). Deliberately EXCLUDED from
  /// the candidate stream seeds (same rationale as model_path): the flag
  /// changes pitches, not the RNG streams. Background threads only.
  bool keynorm_use_canonical = false;
  /// Token-level sampling (Phase 10 Task 2): when true, the background
  /// generate path continues the encoded feed through `sample_continue`
  /// with the production `OrtLogitsProvider` instead of the greedy runner
  /// stage. Default false == pre-task behavior (the hook is inert; output
  /// bit-identical — flag OFF is a blocker-grade property). Provider
  /// unavailable (missing/corrupt sidecar) falls back to the greedy bytes
  /// silently-safe (one-time background diagnostic only). Deliberately
  /// EXCLUDED from the candidate stream seeds (same rationale as
  /// model_path): the flag selects the continuation engine, not the RNG
  /// streams. Background threads only — never processBlock.
  bool use_sampling = false;
};

}  // namespace hf::infer
