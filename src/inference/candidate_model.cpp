// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate model-material TU (S3 slice 4a): greedy runner material + the
// sampler-adjacent model group moved byte-identically from
// `src/inference/candidates.cpp` (pre-cut 186-225 + 404-515; see
// tools/check_bodies_s3.json). `GenParams` arrives via the narrow
// `detail/candidate_params.h` (directly included; the candidates.h
// re-export shim was removed in S10.2).
// Same ONNX-gating as before: none of these bodies carries a conditional
// directive (the file-level guard set is empty — the ONNX/stub split lives
// in onnx_runner.cpp/ort_logits.cpp behind these includes), so there is
// nothing to replicate; both build configs compile this TU unchanged.
#include "candidate_model.h"

#include <array>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include "core/serialization/tokenizer.h"
#include "core/serialization/vocab_layout.gen.h"
#include "detail/candidate_params.h"
#include "inference_runner.h"
#include "keynorm.h"
#include "onnx_runner.h"
#include "ort_logits.h"
#include "sampler.h"

namespace hf::infer {
namespace {

// Shared encode/predict/decode core over an already-chosen runner.
core::Pattern material_with_runner(const core::Pattern& base, const InferenceConfig& cfg,
                                   IInferenceRunner& runner) {
  const std::vector<int> ids = hf::ser::encode_pattern(base);
  const std::vector<int> out = runner.predict(ids, cfg);
  if (const auto decoded = hf::ser::decode_tokens(out)) {
    if (!decoded->tracks.empty()) return *decoded;
  }
  return base;
}

// Phase 10 Task 2: sampling worker context. The production logits provider
// is owned HERE (one instance per model-path configuration, reused across
// the 4 candidates of a generate call and across calls while the config is
// unchanged — never constructed per candidate). Lookup/construction is
// mutex-guarded; per-fill ORT serialization is the provider's own run mutex
// (Task-1 shape: single background worker; no concurrent fills are
// introduced — the AsyncGenerateQueue runs one worker and the sync
// message-thread fallbacks are serial; a worker/message overlap would
// serialize inside the provider). Background/message threads ONLY — never
// processBlock (this whole translation unit is off the audio thread).
struct SamplerProviderCache {
  std::mutex mutex;
  std::string model_path;
  std::shared_ptr<OrtLogitsProvider> provider;
};

SamplerProviderCache& sampler_provider_cache() {
  static SamplerProviderCache c;
  return c;
}

std::shared_ptr<OrtLogitsProvider> sampler_provider_for(const std::string& model_path) {
  SamplerProviderCache& c = sampler_provider_cache();
  const std::lock_guard<std::mutex> lock(c.mutex);
  if (c.provider == nullptr || c.model_path != model_path) {
    c.model_path = model_path;
    c.provider = std::make_shared<OrtLogitsProvider>(model_path);
  }
  return c.provider;
}

// One-time stderr diagnostic for sampling requested but unsatisfiable
// (missing/corrupt sidecar): same discipline as the memo-filter hook —
// background threads only, lock-free flag, no-throw C I/O, silent-safe
// fallback to greedy bytes.
void sampling_unavailable_once(const std::string& model_path) noexcept {
  try {
    static std::atomic_flag warned;
    if (!warned.test_and_set(std::memory_order_relaxed)) {
      const std::string sidecar = logits_sidecar_path_for_model(model_path);
      const std::string msg =
          "[harmony-forge] sampling requested but the logits sidecar is "
          "unavailable for model '" +
          model_path + "' (tried '" + sidecar +
          "'); falling back to greedy bytes for this session.\n";
      std::fwrite(msg.c_str(), 1, msg.size(), stderr);
    }
  } catch (...) {
  }
}

// Production SamplerCfg (mirrors python decode.Cfg field order; the struct
// itself keeps it 1:1): full-distribution T=1.0 sampling under the shipped
// Strict + FSM hard masks, theory prior off, memo_block_run=2 conventional
// (REQUIRED, no default). Stats is an out-param only. The memo index is left
// null here (sampler anti-memo block disabled): §10 enforcement stays at the
// existing final-candidate hook below (apply_memo_filter_for_model), which
// already sees the sampled material.
SamplerCfg production_sampler_cfg() {
  SamplerCfg cfg;
  cfg.temperature = 1.0f;
  cfg.top_p = 1.0f;
  cfg.memo_block_run = 2;
  cfg.strict_mask = true;
  cfg.fsm_mask = true;
  cfg.lambda_theory = 0.0f;
  cfg.use_sampling = true;
  return cfg;
}

}  // namespace

// Runner stage: encode the base, run the model, decode. The mock model
// echoes its input (decode then yields ~base with binned velocities); with
// no model path the runner is unloaded and predict returns empty, so decode
// fails and the deterministic base is kept. Identical behavior in ONNX-ON
// and WITH_ONNX=OFF builds; never throws.
//
// Phase 2 Task 4 (item A) keeps this two-arg form VERBATIM for the empty
// model path (the default: `generate_candidates_impl` calls it exactly as
// before, so default output cannot drift). Non-empty paths and test seams
// go through `material_from_runner_with` below.
core::Pattern material_from_runner(const core::Pattern& base, unsigned seed) {
  InferenceConfig cfg;
  cfg.max_tokens = hf::ser::kVocabMaxTokens;
  cfg.seed = seed;
  OnnxRunner runner(cfg);
  const std::vector<int> ids = hf::ser::encode_pattern(base);
  const std::vector<int> out = runner.predict(ids, cfg);
  if (const auto decoded = hf::ser::decode_tokens(out)) {
    if (!decoded->tracks.empty()) return *decoded;
  }
  return base;
}

// Task 4 runner stage (item A: `model_path` selects the weights — empty
// keeps the unloaded-runner fallback; item D: non-null `runner_override`
// replaces OnnxRunner for the call, letting test-only latency stubs prove
// the async flow without touching production timing). Never throws: runner
// failures surface as empty output -> deterministic base.
core::Pattern material_from_runner_with(const core::Pattern& base, unsigned seed,
                                        const std::string& model_path,
                                        IInferenceRunner* runner_override) {
  InferenceConfig cfg;
  cfg.model_path = model_path;
  cfg.max_tokens = hf::ser::kVocabMaxTokens;
  cfg.seed = seed;
  if (runner_override != nullptr) return material_with_runner(base, cfg, *runner_override);
  OnnxRunner runner(cfg);
  return material_with_runner(base, cfg, runner);
}

// Sampling material stage with greedy fallback. On ANY failure (no provider,
// sample_continue false, undecodable continuation) returns the EXACT greedy
// bytes (same leaf calls as the pre-Task-2 path). Never throws. Background
// threads only.
core::Pattern material_via_sampler_or_greedy(const core::Pattern& feed, const GenParams& p,
                                             const core::ChordProgression& prog,
                                             int kn_shift, int index) {
  const auto greedy = [&] {
    return !p.model_path.empty()
               ? material_from_runner_with(feed, static_cast<unsigned>(p.seed + index),
                                           p.model_path, nullptr)
               : material_from_runner(feed, static_cast<unsigned>(p.seed + index));
  };
  try {
    const auto provider = sampler_provider_for(p.model_path);
    if (provider == nullptr || !provider->available()) {
      sampling_unavailable_once(p.model_path);
      return greedy();
    }
    const std::vector<int> prefix = hf::ser::encode_pattern(feed);
    SamplerMeta meta;
    meta.tonic = p.tonic;
    meta.scale = p.scale;
    meta.chords = prog;
    meta.memo = nullptr;
    if (p.keynorm_use_canonical && kn_shift != 0) {
      // Canonical-space consumer (keynorm.h ledger): the feed above is
      // canonical-shifted, so the Strict mask must see the shifted pair.
      // Keynorm stays OFF this phase; this arm is forward cover only.
      meta.tonic = p.tonic + kn_shift;
      shift_chords_to_canonical(meta.chords, kn_shift);
    }
    const SamplerCfg cfg = production_sampler_cfg();
    // B7 guard - do NOT paste the record's one-line MUTATION form here: the
    // inner-expression mutations recorded in docs/measurements/s3-quirks.md
    // (status CAUSE UNESTABLISHED) fail under MSVC with an opaque
    // `error C2059: syntax error: ')'` and no pointer to the reason. Use the
    // two-statement split the record lists. The balanced one-line form
    // compiles; the compiler probe tools/c2059_probe/probe_c2059.py pins
    // both outcomes and self-retires loudly when MSVC stops emitting C2059.
    const std::uint64_t sseed =
        static_cast<std::uint64_t>(static_cast<unsigned>(p.seed + index));
    std::array<int, kSamplerMaxTokens - 1> buf{};
    size_t out_n = 0;
    SamplerStats stats;
    SamplerScratch scratch;
    if (!sample_continue(*provider, prefix.data(), prefix.size(), meta, cfg, sseed,
                         buf.data(), buf.size(), out_n, stats, scratch))
      return greedy();
    // Finalize (evaluate.finalize mirror): repair the count head and cut to
    // whole notes for decode; the continuation may end mid-note.
    if (out_n == 0) return greedy();
    const size_t n = (out_n - 1) / 6;
    std::vector<int> fin;
    fin.reserve(1 + n * 6);
    fin.push_back(static_cast<int>(n));
    for (size_t k = 1; k < 1 + n * 6 && k < out_n; ++k) fin.push_back(buf[k]);
    if (const auto decoded = hf::ser::decode_tokens(fin)) {
      if (!decoded->tracks.empty()) return *decoded;
    }
    return greedy();
  } catch (...) {
    return greedy();
  }
}

}  // namespace hf::infer
