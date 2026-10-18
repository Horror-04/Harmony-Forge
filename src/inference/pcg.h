// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Single generation RNG (Task 2 determinism hardening): integer PCG32
// (XSH-RR) + 53-bit unit draw. Moved verbatim from `sampler.cpp:42-63`
// (the pre-Task-2 definition); every generation TU shares this ONE type —
// no `std::mt19937`, no `std::*_distribution` in the generation path.
//
// WHY: `std::mt19937`'s stream is portable, but every `std::uniform_*_
// distribution` mapping is implementation-defined, so the same seed can
// diverge across stdlibs. Pcg32 below is pure integer arithmetic, hence
// bit-identical on every stdlib by construction (pinned by
// `tests/test_s30_sampler_seed.cpp`). THREADING: background threads only —
// never `processBlock`. ALLOCATION: none (two uint64s of state).
#pragma once

#include <cstdint>

namespace hf::infer {

// Integer PCG32 (XSH-RR). Same seed -> identical stream (exact
// token-identity with python's random.Random is NOT required — the RNGs
// differ by design — but same-seed determinism is pinned by test).
struct Pcg32 {
  std::uint64_t state;
  std::uint64_t inc;
  explicit Pcg32(std::uint64_t seed) noexcept
      : state(0), inc((seed << 1u) | 1u) {
    next();
    state += seed + 0x9e3779b97f4a7c15ULL;
    next();
  }
  std::uint32_t next() noexcept {
    const std::uint64_t old = state;
    state = old * 6364136223846793005ULL + inc;
    const std::uint32_t xs = static_cast<std::uint32_t>(((old >> 18u) ^ old) >> 27u);
    const std::uint32_t rot = static_cast<std::uint32_t>(old >> 59u);
    return (xs >> rot) | (xs << ((32u - rot) & 31u));
  }
  double unit() noexcept {  // [0, 1)
    const std::uint64_t x =
        (static_cast<std::uint64_t>(next()) << 32) | static_cast<std::uint64_t>(next());
    return static_cast<double>(x >> 11) * (1.0 / 9007199254740992.0);
  }
  // Bounded draw in [0, n) by exact modulo (n == 0 yields the raw draw).
  // uint32 modulo is fully defined, so this is cross-stdlib stable by
  // construction; residual modulo bias is documented and irrelevant here
  // (seeded character draws, never statistical sampling).
  std::uint32_t uniform(std::uint32_t n) noexcept {
    const std::uint32_t r = next();
    return n == 0 ? r : static_cast<std::uint32_t>(r % n);
  }
};

}  // namespace hf::infer
