// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// B3: the runner/sampler seed is a named single-source derivation.
//
// WHAT: `runner_seed(p, i)` replaces the five inline
// `static_cast<unsigned>(p.seed + i)` sites (the facade's greedy runner stage
// and candidate_model.cpp's greedy fallback + `sseed`). B3 is a PURE
// REFACTOR: the default value is still the additive form, so the 12
// run-captured digests in test_s4b_seed_binding stay green. This test pins
// that value and the properties of the non-default D-B3 flip candidate,
// `runner_seed_domain`.
//
// WHY THE DOMAIN VARIANT EXISTS: the additive binding collides whenever the
// per-seed windows overlap - candidate i of seed s and candidate i-1 of seed
// s+1 get the same seed (e.g. (s,3) vs (s+3,0), pinned below).
// `runner_seed_domain` hashes (seed, index) from a private domain tag so that
// overlap and the brief's (s,i) vs (s+3,i+3) pair no longer collide. It is NOT
// wired into production: flipping it moves pinned bytes and needs the re-bank
// procedure appended to the B3 section of docs/BACKLOG-phase-B.md.
#include <catch2/catch_test_macros.hpp>

#include <cstdint>

#include "candidates.h"
#include "seed_derivation.h"

namespace {

hf::infer::GenParams b3_params(int seed) {
  hf::infer::GenParams p;
  p.mode = hf::infer::GenMode::Strict;
  p.seed = seed;
  p.bars = 4;
  p.tonic = 60;
  p.scale = "major";
  return p;
}

}  // namespace

TEST_CASE("B3 runner_seed keeps today's additive value", "[seed][b3]") {
  // (a) Refactor pin over a table: the named derivation must equal the
  // expression it replaced, including negative seeds.
  for (int seed = -3; seed <= 67; ++seed) {
    for (int index = 0; index < 6; ++index) {
      const hf::infer::GenParams p = b3_params(seed);
      INFO("seed " << seed << " index " << index);
      CHECK(hf::infer::runner_seed(p, index) ==
            static_cast<unsigned>(p.seed + index));
    }
  }

  // The derivation depends on seed+index only, exactly like the inline form
  // (the runner stage never saw bars/tonic/scale/mode through this value).
  hf::infer::GenParams other = b3_params(7);
  other.bars = 16;
  other.tonic = 57;
  other.scale = "natural_minor";
  other.mode = hf::infer::GenMode::Experimental;
  CHECK(hf::infer::runner_seed(other, 2) ==
        hf::infer::runner_seed(b3_params(7), 2));

  // The additive form collides whenever the per-seed windows overlap:
  // candidate i of seed s and candidate i-1 of seed s+1 receive the same
  // runner seed (e.g. seed s candidate 3 and seed s+3 candidate 0 are both
  // s+3, while the literal (s,i) vs (s+3,i+3) pair is s+i vs s+i+6 and is
  // NOT equal). This pins the concrete D-B3 motivation.
  for (int seed = 0; seed < 8; ++seed) {
    for (int index = 1; index < 4; ++index) {
      INFO("seed " << seed << " index " << index);
      CHECK(hf::infer::runner_seed(b3_params(seed), index) ==
            hf::infer::runner_seed(b3_params(seed + 1), index - 1));
    }
  }
}

TEST_CASE("B3 runner_seed_domain is deterministic and domain-separated",
          "[seed][b3]") {
  for (int seed = -3; seed <= 67; ++seed) {
    for (int index = 0; index < 6; ++index) {
      const hf::infer::GenParams p = b3_params(seed);
      INFO("seed " << seed << " index " << index);
      const unsigned domain = hf::infer::runner_seed_domain(p, index);
      // Deterministic: same params -> same value, every call.
      CHECK(hf::infer::runner_seed_domain(p, index) == domain);
      // Separated from BOTH other derivations.
      CHECK(domain != hf::infer::runner_seed(p, index));
      CHECK(domain != static_cast<unsigned>(hf::infer::stream_seed(p, index)));
      // And from the brief's motivating pair (s,i) vs (s+3,i+3), plus the
      // real additive overlap pair (s,i) vs (s+1,i-1) for i >= 1.
      CHECK(domain !=
            hf::infer::runner_seed_domain(b3_params(seed + 3), index + 3));
      if (index >= 1)
        CHECK(domain !=
              hf::infer::runner_seed_domain(b3_params(seed + 1), index - 1));
    }
  }
}
