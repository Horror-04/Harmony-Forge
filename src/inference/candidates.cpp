// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Candidate composer: deterministic base + seeded per-index transforms +
// mode post-processing. See candidates.h. Never throws; pure C++20, no JUCE.
#include "candidates.h"

#include <algorithm>
#include <cstdint>
#include <string_view>
#include <vector>

#include "core/music/chord.h"
#include "detail/candidate_helpers.h"
#include "core/music/scale.h"
#include "core/serialization/vocab_layout.gen.h"
#include "candidate_base.h"
#include "candidate_model.h"
#include "candidate_modes.h"
#include "candidate_transforms.h"
#include "inference_runner.h"
#include "keynorm.h"
#include "memo_filter.h"
#include "pcg.h"
#include "seed_derivation.h"

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
// constexpr so the B3 domain tag below folds to a constant (no allocation).
constexpr uint64_t fnv1a(std::string_view s) {
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

// B3: domain tag for runner_seed_domain. FNV-1a of the literal at compile
// time, so the two hash derivations start from disjoint states without any
// per-call string work.
constexpr uint64_t kRunnerSeedDomainSalt = fnv1a("hf.runner_seed.v1");

// Facade-called scale lookup with major fallback (sole caller is
// `generate_candidates_impl`; TU-local per the single-consumer rule).
std::vector<int> scale_or_major(const std::string& scale) {
  auto iv = hf::music::ScaleDatabase::intervals(scale);
  if (!iv.empty()) return iv;
  return hf::music::ScaleDatabase::intervals("major");
}

// Runner-stage material now lives in candidate_model.cpp
// (S3 slice 4a, moved byte-identically; the declaration comes from
// candidate_model.h, included directly above).


// Per-index character transforms now live in candidate_transforms.cpp
// (S3 slice 2, moved byte-identically; the declaration comes from
// candidate_transforms.h, included directly above).

// Mode post-processing now lives in candidate_modes.cpp
// (S3 slice 3, moved byte-identically; the declaration comes from
// candidate_modes.h, included directly above).

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

// Sampler-adjacent model group now lives in candidate_model.cpp
// (S3 slice 4a, moved byte-identically, including the single
// `sample_continue` call-site; the declaration comes from
// candidate_model.h, included directly above).

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
    Pcg32 rng(stream_seed(p, i));
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
      const unsigned seed = runner_seed(p, i);
      material = runner_path ? material_from_runner_with(feed, seed, p.model_path,
                                                         runner_override)
                             : material_from_runner(feed, seed);
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

// Seed derivations (B3): the only definitions of the composer stream seed and
// the runner/sampler seed; declared in seed_derivation.h so this TU,
// candidate_model.cpp and the B3 unit test share them (no second copy).
// `stream_seed` keeps its pre-B3 body byte-for-byte - it is exported only so
// the B3 test can compare runner_seed_domain against it.
std::uint32_t stream_seed(const GenParams& p, int index) {
  uint64_t h = fnv1a(p.scale);
  h = mix64(h, static_cast<uint64_t>(static_cast<uint32_t>(p.seed)));
  h = mix64(h, static_cast<uint64_t>(static_cast<uint32_t>(p.bars)));
  h = mix64(h, static_cast<uint64_t>(static_cast<uint32_t>(p.tonic)));
  h = mix64(h, static_cast<uint64_t>(static_cast<int>(p.mode)));
  h = mix64(h, static_cast<uint64_t>(static_cast<uint32_t>(index)));
  return static_cast<uint32_t>(h ^ (h >> 32));
}

// TODAY'S runner/sampler seed value, verbatim from the five inline
// `static_cast<unsigned>(p.seed + index)` sites this function replaced (B3).
// B3 is a pure refactor: this body MUST NOT change without the full re-bank
// procedure documented in the B3 section of docs/BACKLOG-phase-B.md.
unsigned runner_seed(const GenParams& p, int index) {
  return static_cast<unsigned>(p.seed + index);
}

// D-B3 domain-separated variant (construction documented in
// seed_derivation.h). Deliberately NOT called from any production path.
unsigned runner_seed_domain(const GenParams& p, int index) {
  uint64_t h = kRunnerSeedDomainSalt;
  h = mix64(h, static_cast<uint64_t>(static_cast<uint32_t>(p.seed)));
  h = mix64(h, static_cast<uint64_t>(static_cast<uint32_t>(index)));
  return static_cast<unsigned>(static_cast<uint32_t>(h ^ (h >> 32)));
}

// Deterministic quarter-note base + chord-tone helper now live in
// candidate_base.cpp (S3 slice 1, moved byte-identically; the declaration
// comes from candidate_base.h, included directly above).

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
