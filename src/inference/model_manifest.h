// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Model-compat manifest gate (Task 2 determinism hardening): refuses models
// whose vocab/layout does not match the compiled `kVocab*` tables, instead
// of loading them silently. A refused model degrades to the theory-only
// deterministic fallback (the runner stays unloaded; generation falls back
// to the deterministic composer / greedy bytes).
//
// Background threads ONLY (file I/O + hashing at load/setup time) — never
// `processBlock`. Pure C++20, no JUCE. Never throws.
#pragma once

#include <optional>
#include <string>

namespace hf::infer {

// Canonical vocab descriptor: pure function of the compiled
// `hf::ser::kVocab*` tables (spec version, caps, per-slot [lo, hi) bounds).
// The shipped sidecar (`training/model_manifest.json`, next to the weights)
// records the same descriptor hash produced from `training/vocab_spec.py`.
std::string compiled_vocab_descriptor();

// Lowercase hex sha256 of `compiled_vocab_descriptor()` (64 chars, empty on
// internal failure — never throws).
std::string expected_vocab_hash() noexcept;

// Test/tooling seam: lowercase hex sha256 of arbitrary text (64 chars,
// empty on internal failure). Same primitive the manifest check uses;
// covered by the FIPS vectors in test_model_manifest. Never throws.
std::string sha256_hex_text(const std::string& text) noexcept;

// Strict compat check for a model file. `nullopt` == compatible and the
// caller may load; a value == human-readable reason and the caller MUST NOT
// load (stay unloaded -> theory-only fallback). Empty path is vacuous
// (fallback already) -> `nullopt`. Never throws.
std::optional<std::string> check_model_compatible(
    const std::string& model_path) noexcept;

// One-time stderr diagnostic for a refused model (background threads only:
// lock-free flag, no-throw C I/O; the silent-safe fallback is the caller's
// unloaded stub). Never throws.
void note_manifest_refusal(const std::string& model_path,
                           const std::string& reason) noexcept;

}  // namespace hf::infer
