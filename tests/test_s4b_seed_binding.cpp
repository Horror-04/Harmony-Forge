// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// S4b slice 1 (T3): index->seed binding pin (`p.seed+i` per candidate).
//
// WHAT: `generate_candidates` with the sampler engaged (mock weights +
// `use_sampling`) must hand candidate `i` the sampler seed `p.seed+i`
// (bound at `candidate_model.cpp:191-192`, consumed at the single
// `sample_continue` call-site `:197`). This test pins the exact per-index
// output bytes at seed 0 (the first seed in 0-63 where permuting the
// per-candidate sampler seeds moves output bytes — see the sweep table in
// the task report), so a binding corruption (e.g. `p.seed+(index+1)%4`,
// the S3-4a pair-probe) reddens rows 0-2 there; proven by the swap run in
// the task report (red) and its revert (green).
//
// A1 EXTENSION: seed 0 alone cannot see a dropped `p.seed` (`0+i == i`), so
// the pin now also covers nonzero seeds 10 and 11 — the first seeds in
// 0-63 where the sseed swap moves ALL FOUR rows (see the A1 sweep table in
// its task report), each verified swap-sensitive by the sseed-swap scratch
// BEFORE banking (clean vs swapped bytes differ per seed — no banking on
// faith). Dropping the seed (`p.seed+i` -> `i`) is silent at seed 0 by
// construction and reddens via seeds 10/11; `p.seed^i` coincides with
// `p.seed+i` at seed 0 (`0^i == i`) and fires at 10/11. All four battery
// mutations (`->i`, `+1`, `-i`, `^i`) are proven live per seed in the A1
// report (red) with reverts (green).
//
// WHY GOLDEN (not relational): a relational pin (material with a test-owned
// provider vs direct `sample_continue` with seed `p.seed+i`) is unobservable
// on the required old revs — PROVEN BY READING, not assumed:
//   (a) `material_via_sampler_or_greedy` is internal-linkage on both old
//       revs: 880bb15 `candidates.cpp:462` sits inside the anonymous
//       namespace (lines 32-593); refactor/s3-3 (10c85c5) `:226` inside its
//       anonymous namespace (lines 33-357). No test TU can name it there
//       (it becomes header-public only in S3 slice 4a, `candidate_model.h`).
//   (b) at the `generate_candidates` boundary the per-index sampler bytes
//       are post-processed before return (`apply_candidate_transform` +
//       `apply_mode` + `enforce_caps` + the memo hook), so the pre-decode
//       `buf`/`fin` are not observable through the public API on any rev.
// Hence the golden fallback: in-test hashes (NEW entries; the frozen
// bitmap/manifest and tests/golden/ are untouched — slice 2 owns those).
//
// OLD-CODE EQUIVALENCE: every symbol used here is verified identical on
// 880bb15 AND refactor/s3-3 (10c85c5): `generate_candidates` (public on
// both), `GenParams{mode,seed,bars,tonic,scale,model_path,
// keynorm_use_canonical,use_sampling}` (same fields/defaults),
// `encode_pattern` (untouched by the S3 split: zero src/core delta
// 880bb15..HEAD), `OrtLogitsProvider(path)` + `available()` (same decl).
// The whole generate pipeline 880bb15..HEAD is moves-only (S3 slices byte-
// identical + S3-4b include drops), so these bytes transfer; proven by run
// (see report) with the symbol-dep list as minimum. A1 adds no new symbols
// (same 4 symbols, seed arguments only), so this proof stands unre-verified
// for the extension.
//
// CONFIGS: build-full (real provider) runs the full pin. build-off (stub
// provider, sampler unreachable by construction) runs determinism only and
// returns early — the same structural-blindness discipline as the wiring
// fallback test. No existing test modified.
#include <catch2/catch_test_macros.hpp>

#include <array>
#include <cstdint>
#include <string>
#include <vector>

#include "candidates.h"
#include "core/serialization/tokenizer.h"
#include "ort_logits.h"

#ifndef HARMONY_FORGE_MOCK_MODEL
#define HARMONY_FORGE_MOCK_MODEL "training/model.onnx"
#endif

namespace {

std::uint64_t s4b_fnv1a_ids(const std::vector<int>& v) {
  std::uint64_t h = 1469598103934665603ULL;
  for (int x : v) {
    const auto u = static_cast<std::uint32_t>(x);
    for (int b = 0; b < 4; ++b) {
      h ^= static_cast<unsigned char>((u >> (8 * b)) & 0xffu);
      h *= 1099511628211ULL;
    }
  }
  return h;
}

std::string s4b_hex64(std::uint64_t h) {
  static const char* k = "0123456789abcdef";
  std::string s(16, '0');
  for (int i = 15; i >= 0; --i) {
    s[static_cast<size_t>(i)] = k[h & 0xfu];
    h >>= 4;
  }
  return s;
}

hf::infer::GenParams s4b_params(int seed) {
  hf::infer::GenParams p;
  p.mode = hf::infer::GenMode::Strict;
  p.seed = seed;
  p.bars = 4;
  p.tonic = 60;
  p.scale = "major";
  p.model_path = HARMONY_FORGE_MOCK_MODEL;
  p.use_sampling = true;
  return p;
}

std::vector<std::vector<int>> s4b_encoded(
    const std::array<hf::core::Pattern, 4>& cands) {
  std::vector<std::vector<int>> out;
  for (const auto& c : cands) out.push_back(hf::ser::encode_pattern(c));
  return out;
}

}  // namespace

TEST_CASE("s4b sampler index-seed binding is pinned per candidate",
          "[sampler][s4b]") {
  // Pinned seeds: 0 (original pin, kept) + 10/11 (first nonzero seeds where
  // the sseed swap moves all four rows; swap-sensitivity verified per seed
  // in the A1 report before banking).
  static const int kSeeds[3] = {0, 10, 11};
  // Determinism anchor per seed (both configs: greedy fallback is
  // deterministic too).
  for (int s = 0; s < 3; ++s) {
    INFO("seed " << kSeeds[s]);
    const auto a =
        s4b_encoded(hf::infer::generate_candidates(s4b_params(kSeeds[s])));
    const auto b =
        s4b_encoded(hf::infer::generate_candidates(s4b_params(kSeeds[s])));
    for (int i = 0; i < 4; ++i) CHECK(a[static_cast<size_t>(i)] ==
                                      b[static_cast<size_t>(i)]);
  }

  hf::infer::OrtLogitsProvider probe(HARMONY_FORGE_MOCK_MODEL);
  if (!probe.available()) {
    INFO("logits sidecar unavailable: sampler unreachable, binding unpinned "
         "in this config (structural, same as the wiring fallback test)");
    return;
  }

  for (int s = 0; s < 3; ++s) {
    INFO("seed " << kSeeds[s]);
    const auto a =
        s4b_encoded(hf::infer::generate_candidates(s4b_params(kSeeds[s])));
    // Engagement: the sampler path must move bytes vs greedy, else the pin
    // below is vacuous (it would pin fallback bytes, not the binding).
    hf::infer::GenParams g = s4b_params(kSeeds[s]);
    g.use_sampling = false;
    const auto greedy = s4b_encoded(hf::infer::generate_candidates(g));
    bool any_differs = false;
    for (int i = 0; i < 4; ++i)
      any_differs |= (a[static_cast<size_t>(i)] != greedy[static_cast<size_t>(i)]);
    CHECK(any_differs);

    // Sensitivity: an adjacent seed must move bytes, else a binding
    // corruption may be silent and the golden proves nothing. NOTE: this
    // check is CONFOUNDED — seed s vs s+1 also shifts the greedy material
    // seeds and the transform RNG streams, not just the sampler seed — so
    // it is a smoke check only. The real binding guarantee is the external
    // sseed-swap proof in the task reports (permuted sampler seeds alone
    // redden rows 0-2 at seed 0 and all four rows at seeds 10/11; reverts
    // return green).
    const auto c =
        s4b_encoded(hf::infer::generate_candidates(s4b_params(kSeeds[s] + 1)));
    bool any_moves = false;
    for (int i = 0; i < 4; ++i)
      any_moves |= (a[static_cast<size_t>(i)] != c[static_cast<size_t>(i)]);
    CHECK(any_moves);
  }

  // Binding goldens: exact per-index bytes per pinned seed (candidate i runs
  // the sampler with p.seed+i). The sseed-swap corruption reddens rows 0-2
  // at seed 0 and all four rows at seeds 10/11; per-mutation reddened rows
  // for the full battery are recorded in the A1 report.
  // Captured from the clean tree (see task reports for the values + proofs).
  // NOTE: all four rows are distinct at seed 0; row 3 is swap-invariant at
  // that point (its draws don't move under the sseed permutation), so the
  // seed-0 pin holds per index via rows 0-2 (proven by the swap run in the
  // report). Seeds 10/11 move all four rows under the swap. Two observed
  // coincidences are harmless sampler-draw collisions, not aliasing: seed-10
  // row 0 reuses the seed-0 row-0 bytes, and seed-10 row 2 reuses the
  // swapped-seed-0 row-2 bytes — the pins still hold via the rows that move
  // (exact per-mutation reddened rows are recorded in the A1 report).
  static const char* kPinned[3][4] = {
      {
          "90b4f4ca574fb78a",
          "65929b4fa690ee2c",
          "dc2d5cde23041fcf",
          "2eefc7f5b81708b1",
      },
      {
          "90b4f4ca574fb78a",
          "b6110c63d00a781a",
          "d526dc1c6f511221",
          "be1b30264e0c6157",
      },
      {
          "e6783270c193c0a8",
          "6f0142ddf934b202",
          "85360914d0925088",
          "c404fe98418f506a",
      },
  };
  for (int s = 0; s < 3; ++s) {
    INFO("seed " << kSeeds[s]);
    const auto a =
        s4b_encoded(hf::infer::generate_candidates(s4b_params(kSeeds[s])));
    for (int i = 0; i < 4; ++i)
      CHECK(s4b_hex64(s4b_fnv1a_ids(a[static_cast<size_t>(i)])) == kPinned[s][i]);
  }
}
