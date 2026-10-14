// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Keynorm tests (Phase 9 Task 5b, item C). TDD: written before keynorm.h.
// Contract: canonical transpose mirrors training/keynorm.py EXACTLY
// (major -> C/pc 0, everything else -> A/pc 9, mode preserved; drums
// TrackType::Drums NEVER transposed; Melody 60..84 / Bass 24..60
// octave_pull mirroring candidates.cpp; chord roots shift identically).
// Cross-language parity vectors below were produced by
// training/keynorm.py (see task report) and are pinned byte-identical.
#include <catch2/catch_test_macros.hpp>

#include <array>
#include <string>
#include <vector>

#include "candidates.h"
#include "core/model/note.h"
#include "core/serialization/tokenizer.h"
#include "inference_runner.h"
#include "keynorm.h"

namespace {

int drums_id() { return static_cast<int>(hf::core::TrackType::Drums); }  // 5

// Echo runner: predict returns its input (proves the normalize/inverse
// plumbing without a model; v1 weights stay untouched in this task).
class EchoRunner : public hf::infer::IInferenceRunner {
 public:
  std::vector<int> predict(const std::vector<int>& input,
                           const hf::infer::InferenceConfig&) override {
    return input;
  }
};

hf::infer::GenParams gmajor_params() {
  hf::infer::GenParams p;
  p.mode = hf::infer::GenMode::Strict;
  p.seed = 7;
  p.bars = 2;
  p.tonic = 55;  // G: minimal shift +5 to C
  p.scale = "major";
  return p;
}

}  // namespace

TEST_CASE("keynorm canonical shift matches python over all tonics", "[keynorm]") {
  for (int tonic = 0; tonic < 128; ++tonic) {
    // Independent oracle: shift takes tonic pc to 0 / 9.
    CHECK(((tonic + hf::infer::keynorm_canonical_shift(tonic, "major")) % 12 + 12) %
              12 ==
          0);
    CHECK(((tonic + hf::infer::keynorm_canonical_shift(tonic, "natural_minor")) % 12 +
           12) %
              12 ==
          9);
    CHECK(((tonic + hf::infer::keynorm_canonical_shift(tonic, "dorian")) % 12 + 12) %
              12 ==
          9);
    CHECK(((tonic + hf::infer::keynorm_canonical_shift(tonic, "mixolydian")) % 12 +
           12) %
              12 ==
          9);
  }
  CHECK(hf::infer::keynorm_canonical_shift(60, "major") == 0);
  CHECK(hf::infer::keynorm_canonical_shift(55, "major") == 5);
  CHECK(hf::infer::keynorm_canonical_shift(57, "natural_minor") == 0);
}

TEST_CASE("keynorm python parity vectors are byte-identical", "[keynorm]") {
  // Produced by training/keynorm.py to_canonical([3, 0,0,1,67,4,5,
  // 0,4,5,38,1,3, 0,0,2,48,4,6], 55, 'major') -> shift 5.
  const std::vector<int> ids = {3, 0, 0, 1, 67, 4, 5, 0, 4, 5, 38,
                                1, 3, 0, 0, 2, 48, 4, 6};
  const std::vector<int> want = {3, 0, 0, 1, 72, 4, 5, 0, 4, 5, 38,
                                 1, 3, 0, 0, 2, 53, 4, 6};
  std::vector<int> out(ids.size(), -1);
  int shift = 0;
  REQUIRE(hf::infer::keynorm_to_canonical(ids.data(), ids.size(), 55, "major",
                                          out.data(), out.size(), shift));
  CHECK(shift == 5);
  CHECK(out == want);
  // Drums (track 5) untouched: pitch 38 survived.
  CHECK(out[9] == 38);
  // Inverse restores the input exactly.
  std::vector<int> back(ids.size(), -1);
  REQUIRE(hf::infer::keynorm_from_canonical(out.data(), out.size(), shift,
                                            back.data(), back.size()));
  CHECK(back == ids);
  // A-minor reference is already canonical: shift 0, identity.
  int shift0 = 99;
  std::vector<int> same(ids.size(), -1);
  REQUIRE(hf::infer::keynorm_to_canonical(ids.data(), ids.size(), 57, "natural_minor",
                                          same.data(), same.size(), shift0));
  CHECK(shift0 == 0);
  CHECK(same == ids);
}

TEST_CASE("keynorm round-trip keeps drums and structure, bounds registers",
          "[keynorm]") {
  // Melody above range + bass below range + counter-melody + drums.
  const std::vector<int> ids = {4, 0, 0, 1, 90, 4, 5, 0, 1, 2, 20, 2, 3,
                                0, 2, 4, 100, 8, 2, 0, 3, 5, 42, 1, 1};
  std::vector<int> norm(ids.size(), -1);
  int shift = 0;
  REQUIRE(hf::infer::keynorm_to_canonical(ids.data(), ids.size(), 60, "major",
                                          norm.data(), norm.size(), shift));
  CHECK(shift == 0);
  // octave_pull: melody 90 -> 78, bass 20 -> 32; others only clamped.
  CHECK(norm[4] == 78);
  CHECK(norm[10] == 32);
  CHECK(norm[16] == 100);
  CHECK(norm[22] == 42);  // drums byte-identical
  for (size_t k = 0; k < 4; ++k) {
    CHECK(norm[1 + k * 6] == ids[1 + k * 6]);
    CHECK(norm[1 + k * 6 + 1] == ids[1 + k * 6 + 1]);
    CHECK(norm[1 + k * 6 + 2] == ids[1 + k * 6 + 2]);
  }
  std::vector<int> back(ids.size(), -1);
  REQUIRE(hf::infer::keynorm_from_canonical(norm.data(), norm.size(), shift,
                                            back.data(), back.size()));
  CHECK(back[22] == 42);
  // Pitch classes survive the round trip everywhere.
  for (size_t k = 0; k < 4; ++k) {
    const int a = ids[1 + k * 6 + 3];
    const int b = back[1 + k * 6 + 3];
    CHECK(((a - b) % 12 + 12) % 12 == 0);
  }
}

TEST_CASE("keynorm C-vs-G invariance on identical normalized ids", "[keynorm]") {
  // Same note content in C (tonic 60) and G-below (tonic 55, -5):
  // wrap-free, so normalized ids are identical.
  const std::vector<int> c = {2, 0, 0, 1, 67, 4, 5, 0, 0, 2, 48, 4, 6};
  const std::vector<int> g = {2, 0, 0, 1, 62, 4, 5, 0, 0, 2, 43, 4, 6};
  std::vector<int> nc(c.size(), -1), ng(g.size(), -1);
  int sc = 0, sg = 0;
  REQUIRE(hf::infer::keynorm_to_canonical(c.data(), c.size(), 60, "major", nc.data(),
                                          nc.size(), sc));
  REQUIRE(hf::infer::keynorm_to_canonical(g.data(), g.size(), 55, "major", ng.data(),
                                          ng.size(), sg));
  CHECK(sc == 0);
  CHECK(sg == 5);
  CHECK(nc == ng);
}

TEST_CASE("keynorm rejects bad buffers without throwing", "[keynorm]") {
  std::vector<int> out(32, -1);
  int shift = 0;
  const std::vector<int> ids = {1, 0, 0, 1, 60, 4, 4};
  CHECK_FALSE(hf::infer::keynorm_to_canonical(nullptr, ids.size(), 60, "major",
                                              out.data(), out.size(), shift));
  CHECK_FALSE(hf::infer::keynorm_to_canonical(ids.data(), ids.size(), 60, "major",
                                              nullptr, out.size(), shift));
  CHECK_FALSE(hf::infer::keynorm_to_canonical(ids.data(), ids.size(), 60, "major",
                                              out.data(), 3, shift));
  CHECK_FALSE(hf::infer::keynorm_from_canonical(nullptr, ids.size(), 0, out.data(),
                                                out.size()));
  CHECK_FALSE(hf::infer::keynorm_from_canonical(ids.data(), 4, 0, out.data(),
                                                out.size()));
}

TEST_CASE("keynorm flag-off generate path is bit-identical to pre-task output",
          "[keynorm]") {
  // Default flag OFF: the hook is inert, so existing golden behavior cannot
  // drift (pinned here against the with_runner echo path too).
  hf::infer::GenParams off = gmajor_params();
  CHECK_FALSE(off.keynorm_use_canonical);
  EchoRunner echo;
  const auto a = hf::infer::generate_candidates(off);
  const auto b = hf::infer::generate_candidates_with_runner(off, echo);
  for (int i = 0; i < 4; ++i)
    CHECK(hf::ser::encode_pattern(a[i]) == hf::ser::encode_pattern(b[i]));
}

TEST_CASE("keynorm flag-on echo round-trips C-major candidates exactly",
          "[keynorm]") {
  // Shift-0 params (C major, tonic 60): normalize is identity, so flag-ON
  // with an echo runner must equal flag-OFF exactly. Proves the hook
  // plumbing (normalize before runner, inverse after) without a model.
  EchoRunner echo;
  hf::infer::GenParams off = gmajor_params();
  off.tonic = 60;  // shift 0
  hf::infer::GenParams on = off;
  on.keynorm_use_canonical = true;
  const auto a = hf::infer::generate_candidates_with_runner(off, echo);
  const auto b = hf::infer::generate_candidates_with_runner(on, echo);
  for (int i = 0; i < 4; ++i)
    CHECK(hf::ser::encode_pattern(a[i]) == hf::ser::encode_pattern(b[i]));
}

TEST_CASE("keynorm flag-on echo keeps G-major candidates pc-equivalent",
          "[keynorm]") {
  // Nonzero shift (G major, +5): echo output must be pitch-class-equivalent
  // to flag-OFF with drums byte-identical (octave_pull may move octaves).
  EchoRunner echo;
  hf::infer::GenParams off = gmajor_params();
  hf::infer::GenParams on = off;
  on.keynorm_use_canonical = true;
  const auto a = hf::infer::generate_candidates_with_runner(off, echo);
  const auto b = hf::infer::generate_candidates_with_runner(on, echo);
  for (int i = 0; i < 4; ++i) {
    const auto ea = hf::ser::encode_pattern(a[i]);
    const auto eb = hf::ser::encode_pattern(b[i]);
    REQUIRE(ea.size() == eb.size());
    REQUIRE(!ea.empty() && ea[0] == eb[0]);
    for (size_t k = 0; k < static_cast<size_t>(ea[0]); ++k) {
      const int tt = ea[1 + k * 6 + 2];
      CHECK(eb[1 + k * 6 + 2] == tt);
      const int pa = ea[1 + k * 6 + 3];
      const int pb = eb[1 + k * 6 + 3];
      if (tt == drums_id()) {
        CHECK(pb == pa);
      } else {
        CHECK(((pa - pb) % 12 + 12) % 12 == 0);
      }
    }
  }
}
