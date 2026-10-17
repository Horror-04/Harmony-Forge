// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate composer: deterministic base + seeded per-index transforms +
// mode post-processing. See candidates.h. Never throws; pure C++20, no JUCE.
#include "candidates.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <mutex>
#include <random>
#include <vector>

#include "constraints.h"
#include "core/model/pattern_ops.h"
#include "core/music/chord.h"
#include "detail/candidate_helpers.h"
#include "core/music/ranges.h"
#include "core/music/scale.h"
#include "core/serialization/tokenizer.h"
#include "core/serialization/vocab_layout.gen.h"
#include "inference_runner.h"
#include "keynorm.h"
#include "memo_filter.h"
#include "onnx_runner.h"
#include "ort_logits.h"
#include "sampler.h"

namespace hf::infer {
namespace {

// Shared composer constants/helpers (S3 slice 1): kBeatsPerBar/kBarTicks, the
// melody/bass registers, mod12/octave_pull now live in
// detail/candidate_helpers.h (single inline definitions shared with
// candidate_base.cpp); the using-directive keeps every remaining body below
// text-identical.
using namespace detail;

constexpr int kMaxBars = hf::ser::kVocabMaxBars;
constexpr int kMaxNotes = hf::ser::kVocabMaxNotes;  // codec cap: 170 notes / 1024 ids

// FNV-1a: deterministic across compilers (std::hash<string> is not).
uint64_t fnv1a(const std::string& s) {
  uint64_t h = 1469598103934665603ULL;
  for (unsigned char c : s) {
    h ^= c;
    h *= 1099511628211ULL;
  }
  return h;
}

uint64_t mix64(uint64_t h, uint64_t v) {
  h ^= v + 0x9e3779b97f4a7c15ULL + (h << 6) + (h >> 2);
  return h;
}

uint32_t stream_seed(const GenParams& p, int index) {
  uint64_t h = fnv1a(p.scale);
  h = mix64(h, static_cast<uint64_t>(static_cast<uint32_t>(p.seed)));
  h = mix64(h, static_cast<uint64_t>(static_cast<uint32_t>(p.bars)));
  h = mix64(h, static_cast<uint64_t>(static_cast<uint32_t>(p.tonic)));
  h = mix64(h, static_cast<uint64_t>(static_cast<int>(p.mode)));
  h = mix64(h, static_cast<uint64_t>(static_cast<uint32_t>(index)));
  return static_cast<uint32_t>(h ^ (h >> 32));
}

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


// Per-index character transforms now live in candidate_transforms.cpp
// (S3 slice 2, moved byte-identically; the declaration comes from
// candidate_transforms.h via candidates.h).

// Mode post-processing now lives in candidate_modes.cpp
// (S3 slice 3, moved byte-identically; the declaration comes from
// candidate_modes.h via candidates.h).

// Final guard: codec caps (drop/skip, never UB) + hard clamps.
void enforce_caps(core::Pattern& pat, int bars) {
  const int total_ticks = bars * kBarTicks;
  int kept = 0;
  for (auto& t : pat.tracks) {
    std::vector<core::Note> out;
    out.reserve(t.notes.size());
    for (auto& m : t.notes) {
      if (kept >= kMaxNotes) break;
      if (m.start_tick < 0) m.start_tick = 0;
      if (m.start_tick / kBarTicks >= kMaxBars) continue;  // 16-bar cap: drop
      if (m.start_tick >= total_ticks) continue;           // past the request: drop
      m.pitch = std::clamp(m.pitch, 0, 127);
      m.velocity = std::clamp(m.velocity, 1, 127);
      m.duration_ticks = std::max(1, std::min(m.duration_ticks, total_ticks - m.start_tick));
      out.push_back(m);
      ++kept;
    }
    t.notes = std::move(out);
  }
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

// Shared pipeline behind generate_candidates / with_runner (ADD, Task 4).
// The empty model path (default) runs the verbatim pre-Task-4 statements,
// so default output cannot drift; model/override paths share the same core
// with their runner choice made explicit. The two public entry points keep
// their exact signatures; this helper is file-local.
std::array<core::Pattern, 4> generate_candidates_impl(const GenParams& params,
                                                      IInferenceRunner* runner_override) {
  GenParams p = params;
  p.bars = std::clamp(p.bars, 1, kMaxBars);
  p.tonic = std::clamp(p.tonic, 0, 127);
  if (hf::music::ScaleDatabase::intervals(p.scale).empty()) p.scale = "major";
  const core::ChordProgression prog = progression_for_params(p);
  const std::vector<int> iv = scale_or_major(p.scale);

  std::array<core::Pattern, 4> out;
  for (int i = 0; i < 4; ++i) {
    std::mt19937 rng(stream_seed(p, i));
    core::Pattern base = compose_base(p, prog, iv, rng);
    // Phase 9 Task 5b: key-normalized inference (flag-gated, default OFF).
    // When enabled, the runner feed is transposed to the canonical key
    // before the runner stage and the decoded material is shifted back
    // after, so a model trained on canonical views sees canonical input.
    // Drums are untouched both ways; Melody/Bass octave_pull mirrors the
    // composer registers. Flag OFF == verbatim pre-task statements below.
    core::Pattern feed = base;
    int kn_shift = 0;
    if (p.keynorm_use_canonical)
      kn_shift = shift_pattern_to_canonical(feed, p.tonic, p.scale);
    // Empty model path (the default) runs the verbatim pre-Task-4 statements
    // so default output cannot drift; model/override paths share the same
    // core with their runner choice made explicit.
    // F1: the resolved runner state keys the §10 hook below — material from
    // any runner (real model OR override) is filter-eligible; only the pure
    // deterministic fallback (no runner, empty path) stays unfiltered.
    const bool runner_path =
        (runner_override != nullptr || !p.model_path.empty());
    // Phase 10 Task 2: sampling branch AROUND the greedy path below (no
    // refactor of it). Flag ON with a live provider continues the encoded
    // feed through sample_continue; every other case — flag OFF, override
    // seam (which carries an IInferenceRunner, not logits), provider
    // unavailable, undecodable continuation — runs the EXACT statements
    // below, so flag-OFF history bytes cannot move a single bit.
    core::Pattern material;
    if (p.use_sampling && runner_override == nullptr) {
      material = material_via_sampler_or_greedy(feed, p, prog, kn_shift, i);
    } else {
      material =
          runner_path
              ? material_from_runner_with(feed, static_cast<unsigned>(p.seed + i), p.model_path,
                                          runner_override)
              : material_from_runner(feed, static_cast<unsigned>(p.seed + i));
    }
    if (p.keynorm_use_canonical) shift_pattern_from_canonical(material, kn_shift);
    // Decoded runner output regroups tracks by type; generation below only
    // needs the Melody track to exist, base already guarantees the rest.
    apply_candidate_transform(material, p, i, iv, rng);
    apply_mode(material, p, prog, iv, rng);
    enforce_caps(material, p.bars);
    // Phase 3 Task 3 (item C): runtime §10 memo-filter on the FINAL
    // candidate. The filter MUST run here, not in material_from_runner:
    // (a) the seeded transforms + mode post-processing above add notes
    // after the material stage, so a material-stage check cannot guarantee
    // the shipped output (probed: residual runs of 4-5 windows survived a
    // material-stage hook); (b) the no-model fallback is fixed composer
    // code, not a memorizing model, so it is never filtered (empty
    // model path -> no-op -> default output bit-identical everywhere).
    // With a real model configured the sibling memo_index.bin next to the
    // weights is enforced; a bare filename falls back to the working
    // directory (F2); missing/unreadable index -> no-op + one-time stderr
    // diagnostic for non-empty model paths.
    apply_memo_filter_for_model(material, p.model_path, runner_path);
    out[i] = std::move(material);
  }
  return out;
}

}  // namespace

// Deterministic quarter-note base + chord-tone helper now live in
// candidate_base.cpp (S3 slice 1, moved byte-identically; the declaration
// comes from candidate_base.h via candidates.h).

core::ChordProgression progression_for_params(const GenParams& params) {
  const int bars = std::clamp(params.bars, 1, kMaxBars);
  const auto iv = hf::music::ScaleDatabase::intervals(params.scale);
  core::ChordProgression out;
  if (iv.empty()) return out;
  static const int kDegrees[] = {0, 4, 5, 3};  // I V vi IV
  const int n = static_cast<int>(iv.size());
  for (int b = 0; b < bars; ++b) {
    const int deg = kDegrees[b % 4] % n;
    const int third = (iv[(deg + 2) % n] - iv[deg] + 12) % 12;
    const int fifth = (iv[(deg + 4) % n] - iv[deg] + 12) % 12;
    std::string type = "maj";
    if (third == 3 && fifth == 6)
      type = "dim";
    else if (third == 3)
      type = "min";
    else if (fifth == 8)
      type = "aug";
    core::ChordSymbol c;
    c.root = std::clamp(params.tonic + iv[deg], 0, 127);
    c.type = type;
    out.push_back(c);
  }
  return out;
}

std::array<core::Pattern, 4> generate_candidates_with_runner(const GenParams& params,
                                                             IInferenceRunner& runner) {
  return generate_candidates_impl(params, &runner);
}

std::array<core::Pattern, 4> generate_candidates(const GenParams& params) {
  return generate_candidates_impl(params, nullptr);
}

}  // namespace hf::infer
