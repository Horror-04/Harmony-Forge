// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// S3.0 Phase 2 (C4) characterization: the sampler call-site seed (`sseed`
// at candidates.cpp:491-492, consumed at the single `sample_continue`
// call-site :497) is unreachable in build-off — the stub logits provider
// is never available, so `material_via_sampler_or_greedy` falls back to
// greedy bytes before :497 (SITE=0 in every cube leg and unit suite).
// No build-off test can pin the index→sseed binding itself. This test
// pins the property that binding exists to provide — seed-sensitivity —
// on the DIRECT `sample_continue` path (ENTER, stub-runnable): different
// seeds must drive different continuations, same seed identical bytes.
// Green on the clean tree; red when the ENTER seed is ignored
// (e.g. `Pcg32 rng(seed)` → `Pcg32 rng(0)` in sampler.cpp).
#include <catch2/catch_test_macros.hpp>

#include <array>
#include <cstdint>
#include <vector>

#include "candidates.h"
#include "core/serialization/tokenizer.h"
#include "pcg.h"
#include "sampler.h"

namespace {

using hf::infer::ISamplerLogits;
using hf::infer::SamplerCfg;
using hf::infer::SamplerMeta;
using hf::infer::SamplerScratch;
using hf::infer::SamplerStats;

class S30Lcg {
 public:
  explicit S30Lcg(uint64_t s) : s_(s ? s : 1) {}
  uint64_t next() {
    s_ = s_ * 6364136223846793005ULL + 1442695040888963407ULL;
    return s_ >> 11;
  }

 private:
  uint64_t s_;
};

// Deterministic uniform stub in [-2, 2] (mirrors test_sampler.cpp).
class S30UniformStub : public ISamplerLogits {
 public:
  explicit S30UniformStub(uint64_t seed) : rng_(seed) {}
  bool get_logits(const int* /*seq*/, size_t /*n*/, float* out) noexcept override {
    try {
      for (int i = 0; i < hf::infer::kSamplerVocab; ++i) {
        const double u = (rng_.next() % 1000000) / 1000000.0;
        out[i] = static_cast<float>(-2.0 + 4.0 * u);
      }
      return true;
    } catch (...) {
      return false;
    }
  }

 private:
  S30Lcg rng_;
};

SamplerMeta s30_meta() {
  SamplerMeta m;
  m.tonic = 60;
  m.scale = "major";
  hf::core::ChordSymbol c;
  c.root = 48;
  c.type = "maj";
  m.chords = {c};
  m.memo = nullptr;
  return m;
}

SamplerCfg s30_cfg() {
  SamplerCfg c;
  c.temperature = 1.0f;
  c.top_p = 0.95f;
  c.memo_block_run = 2;
  c.strict_mask = true;
  c.fsm_mask = true;
  c.lambda_theory = 0.0f;
  c.use_sampling = true;
  return c;
}

std::vector<int> s30_run(ISamplerLogits& stub, uint64_t seed) {
  const std::vector<int> prefix = {1, 0, 0, 1, 60, 4, 4};
  std::array<int, 2048> out{};
  size_t out_n = 0;
  SamplerStats stats;
  SamplerScratch scratch;
  const bool ok = hf::infer::sample_continue(stub, prefix.data(), prefix.size(),
                                             s30_meta(), s30_cfg(), seed,
                                             out.data(), out.size(), out_n,
                                             stats, scratch);
  REQUIRE(ok);
  REQUIRE(out_n == prefix.size() + static_cast<size_t>(hf::infer::kSamplerGenTokens));
  return std::vector<int>(out.begin(), out.begin() + out_n);
}

}  // namespace

TEST_CASE("s30 sampler ENTER path is seed-sensitive", "[sampler][s30]") {
  S30UniformStub s7a(42), s7b(42), s8(42);
  const auto a = s30_run(s7a, 7);
  const auto b = s30_run(s7b, 7);
  CHECK(a == b);  // determinism anchor: same seed, identical bytes
  const auto c = s30_run(s8, 8);
  CHECK(a != c);  // seed-sensitivity: the ENTER seed must move the draw
}

// Task 2 (determinism hardening): the single generation RNG. Pcg32 is pure
// integer arithmetic (no stdlib distribution), so the same seed yields the
// identical stream on every stdlib — unlike std::mt19937 +
// std::uniform_int_distribution, whose mapping is implementation-defined.
TEST_CASE("s30 Pcg32 stream is pinned and stdlib-independent", "[sampler][s30]") {
  // Same seed, two instances: identical streams (1000 draws).
  hf::infer::Pcg32 a(7), b(7);
  for (int i = 0; i < 1000; ++i) CHECK(a.next() == b.next());
  // Reference draws (captured from the implementation; pure uint64
  // arithmetic, so these hold on every stdlib by construction).
  hf::infer::Pcg32 r7(7);
  CHECK(r7.next() == 0x457b47f0u);
  CHECK(r7.next() == 0xef48e6bdu);
  hf::infer::Pcg32 r42(42);
  CHECK(r42.next() == 0x8daf78a1u);
  CHECK(r42.next() == 0x78625b1au);
  // unit() draws stay in [0, 1).
  hf::infer::Pcg32 u(7);
  for (int i = 0; i < 100; ++i) {
    const double v = u.unit();
    CHECK(v >= 0.0);
    CHECK(v < 1.0);
  }
  // Bounded draw: exact-modulo, always in range, seed-sensitive.
  hf::infer::Pcg32 m1(7), m2(7), m3(8);
  for (int i = 0; i < 200; ++i) {
    const auto x = m1.uniform(100);
    const auto y = m2.uniform(100);
    CHECK(x == y);  // same seed, same position: identical draws
    CHECK(x < 100);
  }
  bool any_differs = false;
  for (int i = 0; i < 200; ++i) any_differs |= (m1.uniform(100) != m3.uniform(100));
  CHECK(any_differs);
}

// Task 2: the candidates path consumes the same Pcg32 (no std::mt19937 in
// generation). Same params + seed -> bit-identical 4 patterns, and seed 7
// keeps the four distinct characters (mirrors the test_candidates pin at
// the Task-2-owned boundary).
TEST_CASE("s30 candidates path is Pcg32-deterministic", "[sampler][s30]") {
  hf::infer::GenParams p;
  p.mode = hf::infer::GenMode::Strict;
  p.seed = 7;
  p.bars = 4;
  p.tonic = 60;
  p.scale = "major";
  const auto a = hf::infer::generate_candidates(p);
  const auto b = hf::infer::generate_candidates(p);
  for (int i = 0; i < 4; ++i)
    CHECK(hf::ser::encode_pattern(a[i]) == hf::ser::encode_pattern(b[i]));
}
