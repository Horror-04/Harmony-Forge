// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// OrtLogitsProvider tests (Phase 10 Task 1, item B). TDD: written before
// ort_logits.h. Follows tests/test_sampler.cpp patterns (Catch2, frozen
// fixtures recorded in-test, background-thread-only provider use).
//
// Contract under test (brief item A):
// - ctor(model_path) loads the logits sidecar ONCE (direct sidecar path or
//   the sibling model.logits.onnx next to the weights path).
// - Missing/corrupt sidecar -> available()==false, fill==false, no throw.
// - fill runs one ORT step into caller-owned scratch; failure is per-call.
// - Session reuse asserted via the visible load_count() hook, never timing.
#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <array>
#include <cstddef>
#include <filesystem>
#include <fstream>
#include <string>
#include <system_error>
#include <vector>

#include "onnx_runner.h"
#include "ort_logits.h"
#include "sampler.h"

#ifndef HARMONY_FORGE_LOGITS_MODEL
#define HARMONY_FORGE_LOGITS_MODEL "training/model.logits.onnx"
#endif
#ifndef HARMONY_FORGE_MOCK_MODEL
#define HARMONY_FORGE_MOCK_MODEL "training/model.onnx"
#endif

namespace {

using hf::infer::OrtLogitsProvider;

int argmax256(const float* v) {
  int best = 0;
  for (int i = 1; i < hf::infer::kSamplerVocab; ++i)
    if (v[i] > v[best]) best = i;
  return best;
}

// Frozen val-head prefixes (training/corpus/val.jsonl, midpoint cut per
// training/validate_logits.py::_prefix), recorded in-test 2026-10-15.
std::vector<std::vector<int>> frozen_prefixes() {
  return {
      // composed-O-k0 (91 ids -> 43-id prefix).
      {15, 0, 0, 1, 74, 4, 5, 0, 4, 1, 72, 4, 5, 0, 8, 1, 71, 4, 5, 0, 12, 1,
       72, 4, 5, 1, 0, 1, 74, 4, 5, 1, 4, 1, 76, 4, 5, 1, 8, 1, 74, 8, 5},
      // composed-O-k1 (91 ids -> 43-id prefix).
      {15, 0, 0, 1, 79, 4, 5, 0, 4, 1, 77, 4, 5, 0, 8, 1, 76, 4, 5, 0, 12, 1,
       77, 4, 5, 1, 0, 1, 79, 4, 5, 1, 4, 1, 81, 4, 5, 1, 8, 1, 79, 8, 5},
      // composed-P-k0 (91 ids -> 43-id prefix).
      {15, 0, 0, 1, 71, 4, 5, 0, 4, 1, 72, 4, 5, 0, 8, 1, 74, 4, 5, 0, 12, 1,
       76, 4, 5, 1, 0, 1, 74, 4, 5, 1, 4, 1, 72, 4, 5, 1, 8, 1, 71, 8, 5},
  };
}

// Procedural whole-note prefixes (valid slot ids throughout), recorded
// in-test alongside the frozen heads.
std::vector<std::vector<int>> procedural_prefixes() {
  std::vector<std::vector<int>> out;
  out.push_back({1, 0, 0, 1, 60, 4, 4});
  std::vector<int> four = {4};
  for (int k = 0; k < 4; ++k) {
    const int note[6] = {0, 0, 1, 60, 4, 4};
    four.insert(four.end(), note, note + 6);
  }
  out.push_back(four);
  return out;
}

}  // namespace

TEST_CASE("ort logits unavailable path never throws, fill is false", "[ort_logits]") {
  OrtLogitsProvider missing("Z:/definitely/not/here/model.onnx");
  CHECK_FALSE(missing.available());
  CHECK(missing.load_count() == 0);
  std::array<float, 256> lg{};
  const std::vector<int> pre = {1, 0, 0, 1, 60, 4, 4};
  CHECK_FALSE(missing.get_logits(pre.data(), pre.size(), lg.data()));
  CHECK_FALSE(missing.get_logits(nullptr, 0, lg.data()));
  CHECK_FALSE(missing.get_logits(pre.data(), pre.size(), nullptr));
  CHECK(missing.load_count() == 0);

  OrtLogitsProvider bare("no-such-model-ort-logits-probe.onnx");
  CHECK_FALSE(bare.available());
  CHECK(bare.load_count() == 0);
  CHECK_FALSE(bare.get_logits(pre.data(), pre.size(), lg.data()));

  OrtLogitsProvider empty("");
  CHECK_FALSE(empty.available());
  CHECK(empty.load_count() == 0);
  CHECK_FALSE(empty.get_logits(pre.data(), pre.size(), lg.data()));
}

TEST_CASE("ort logits corrupt sidecar is unavailable, never throws", "[ort_logits]") {
  // Hermetic corrupt probe: garbage bytes in a file that directly names the
  // sidecar (exercises the "given path names the sidecar" branch with an
  // unloadable file). Both modes must report unavailable, never throw.
  namespace fs = std::filesystem;
  const fs::path dir = fs::temp_directory_path() / "hf-ort-logits-probe";
  std::error_code ec;
  fs::create_directories(dir, ec);
  const fs::path bad = dir / "model.logits.onnx";
  {
    std::ofstream f(bad, std::ios::binary | std::ios::trunc);
    f << "not an onnx model, only a corrupt-sidecar probe";
  }
  OrtLogitsProvider prov(bad.string());
  CHECK_FALSE(prov.available());
  CHECK(prov.load_count() == 0);
  std::array<float, 256> lg{};
  const std::vector<int> pre = {1, 0, 0, 1, 60, 4, 4};
  CHECK_FALSE(prov.get_logits(pre.data(), pre.size(), lg.data()));
  CHECK(prov.load_count() == 0);
  fs::remove(bad, ec);
  fs::remove(dir, ec);
}

TEST_CASE("ort logits resolves the sidecar next to the weights path", "[ort_logits]") {
  // The weights path names model.onnx, NOT the sidecar: the provider must
  // pick up the sibling model.logits.onnx (same rule as the memo-index
  // sibling in memo_filter.h).
  OrtLogitsProvider prov(HARMONY_FORGE_MOCK_MODEL);
#ifdef HARMONY_FORGE_WITH_ONNX
  CHECK(prov.available());
  CHECK(prov.load_count() == 1);
  std::array<float, 256> lg{};
  const std::vector<int> pre = {1, 0, 0, 1, 60, 4, 4};
  CHECK(prov.get_logits(pre.data(), pre.size(), lg.data()));
#else
  CHECK_FALSE(prov.available());
  CHECK(prov.load_count() == 0);
#endif
}

#ifdef HARMONY_FORGE_WITH_ONNX
TEST_CASE("ort logits argmax matches greedy model.onnx on frozen + procedural prefixes",
          "[ort_logits]") {
  OrtLogitsProvider prov(HARMONY_FORGE_LOGITS_MODEL);
  REQUIRE(prov.available());

  hf::infer::InferenceConfig cfg;
  cfg.model_path = HARMONY_FORGE_MOCK_MODEL;
  cfg.max_tokens = 1024;
  hf::infer::OnnxRunner greedy(cfg);
  REQUIRE(greedy.loaded());

  auto fixtures = frozen_prefixes();
  const auto procedural = procedural_prefixes();
  fixtures.insert(fixtures.end(), procedural.begin(), procedural.end());
  REQUIRE(fixtures.size() >= 5);
  for (const auto& pre : fixtures) {
    std::array<float, 256> lg{};
    REQUIRE(prov.get_logits(pre.data(), pre.size(), lg.data()));
    const std::vector<int> g = greedy.predict(pre, cfg);
    REQUIRE(!g.empty());
    CHECK(argmax256(lg.data()) == g.back());
  }
}

TEST_CASE("ort logits loads once across fills (visible load counter)", "[ort_logits]") {
  OrtLogitsProvider prov(HARMONY_FORGE_LOGITS_MODEL);
  REQUIRE(prov.available());
  CHECK(prov.load_count() == 1);
  std::array<float, 256> a{}, b{};
  const std::vector<int> pre = {1, 0, 0, 1, 60, 4, 4};
  REQUIRE(prov.get_logits(pre.data(), pre.size(), a.data()));
  REQUIRE(prov.get_logits(pre.data(), pre.size(), b.data()));
  CHECK(prov.load_count() == 1);  // two fills, one load (no timing involved)
  CHECK(a == b);                  // deterministic: same input, same bytes
}

TEST_CASE("ort logits fill failure is per-call, provider stays usable", "[ort_logits]") {
  OrtLogitsProvider prov(HARMONY_FORGE_LOGITS_MODEL);
  REQUIRE(prov.available());
  std::array<float, 256> lg{};
  CHECK_FALSE(prov.get_logits(nullptr, 7, lg.data()));  // null seq, n > 0
  const std::vector<int> pre = {1, 0, 0, 1, 60, 4, 4};
  CHECK_FALSE(prov.get_logits(pre.data(), 0, lg.data()));  // empty prefix
  CHECK_FALSE(prov.get_logits(pre.data(), pre.size(), nullptr));
  CHECK(prov.available());  // failures were per-call, not fatal
  CHECK(prov.load_count() == 1);
  CHECK(prov.get_logits(pre.data(), pre.size(), lg.data()));  // good fill works
}

// B10 (phase-B tranche G, D-B10.1): the slot-range guard is a REJECTION at
// the ORT boundary. The ranges are the frozen layout's (the generated
// vocab_layout.gen.h): position 0 is the count head (0..kVocabMaxNotes),
// position i>0 is body slot (i-1) % 6 with bounds [lo, hi).
TEST_CASE("ort logits rejects a prefix that violates a named slot range", "[ort_logits]") {
  OrtLogitsProvider prov(HARMONY_FORGE_LOGITS_MODEL);
  REQUIRE(prov.available());
  std::array<float, 256> lg{};

  // The legal 7-id prefix (count head 1, then bar 0, subbeat 0, track 1,
  // pitch 60, duration 4, vel_bin 4) with ONE id pushed out of range.
  // The PITCH slot (position 4) is [0,128): 200 is outside it.
  std::vector<int> bad_pitch = procedural_prefixes().front();
  bad_pitch[4] = 200;
  CHECK_FALSE(prov.get_logits(bad_pitch.data(), bad_pitch.size(), lg.data()));

  // The TRACK slot (position 3) is [0,6): 6 is outside it.
  std::vector<int> bad_track = procedural_prefixes().front();
  bad_track[3] = 6;
  CHECK_FALSE(prov.get_logits(bad_track.data(), bad_track.size(), lg.data()));

  // The DURATION slot (position 5) is [1,65): 0 is outside it.
  std::vector<int> bad_dur = procedural_prefixes().front();
  bad_dur[5] = 0;
  CHECK_FALSE(prov.get_logits(bad_dur.data(), bad_dur.size(), lg.data()));

  // The VEL_BIN slot (position 6) is [0,8): 8 is outside it.
  std::vector<int> bad_vel = procedural_prefixes().front();
  bad_vel[6] = 8;
  CHECK_FALSE(prov.get_logits(bad_vel.data(), bad_vel.size(), lg.data()));

  // The BAR slot (position 1) is [0,16): 16 is outside it.
  std::vector<int> bad_bar = procedural_prefixes().front();
  bad_bar[1] = 16;
  CHECK_FALSE(prov.get_logits(bad_bar.data(), bad_bar.size(), lg.data()));

  // The SUBBEAT slot (position 2) is [0,16): 16 is outside it.
  std::vector<int> bad_sub = procedural_prefixes().front();
  bad_sub[2] = 16;
  CHECK_FALSE(prov.get_logits(bad_sub.data(), bad_sub.size(), lg.data()));

  // The COUNT HEAD (position 0) is 0..kVocabMaxNotes: 171 is outside it.
  std::vector<int> bad_head = procedural_prefixes().front();
  bad_head[0] = hf::ser::kVocabMaxNotes + 1;
  CHECK_FALSE(prov.get_logits(bad_head.data(), bad_head.size(), lg.data()));

  // The failure is PER-CALL: the provider stays loaded and usable.
  CHECK(prov.available());
  CHECK(prov.load_count() == 1);
  const std::vector<int> ok = procedural_prefixes().front();
  CHECK(prov.get_logits(ok.data(), ok.size(), lg.data()));
}

TEST_CASE("ort logits accepts every legal prefix (the slot-range guard is a no-op)",
          "[ort_logits]") {
  OrtLogitsProvider prov(HARMONY_FORGE_LOGITS_MODEL);
  REQUIRE(prov.available());
  std::array<float, 256> lg{};

  // The frozen val-head prefixes and the procedural ones are all legal:
  // the guard must not reject any of them.
  auto fixtures = frozen_prefixes();
  const auto procedural = procedural_prefixes();
  fixtures.insert(fixtures.end(), procedural.begin(), procedural.end());
  REQUIRE(fixtures.size() >= 5);
  for (const auto& pre : fixtures) {
    REQUIRE(prov.get_logits(pre.data(), pre.size(), lg.data()));
  }

  // The guard's boundary is EXACTLY the frozen layout's: the lowest and
  // the highest legal id of every slot are accepted, the id just outside
  // each bound is rejected. Slot s occupies position s+1 (position 0 is
  // the count head).
  for (int slot = 0; slot < hf::ser::kVocabSlotCount; ++slot) {
    const int lo = hf::ser::kVocabSlotLo[slot];
    const int hi = hf::ser::kVocabSlotHi[slot];
    const std::size_t pos = static_cast<std::size_t>(slot) + 1;
    for (int id : {lo, hi - 1}) {          // legal: inside [lo, hi)
      std::vector<int> p = procedural_prefixes().front();
      p[pos] = id;
      REQUIRE(prov.get_logits(p.data(), p.size(), lg.data()));
    }
    for (int id : {lo - 1, hi}) {          // illegal: outside [lo, hi)
      std::vector<int> p = procedural_prefixes().front();
      p[pos] = id;
      CHECK_FALSE(prov.get_logits(p.data(), p.size(), lg.data()));
    }
  }
  // The count head's bounds are 0..kVocabMaxNotes.
  for (int id : {0, hf::ser::kVocabMaxNotes}) {
    std::vector<int> p = procedural_prefixes().front();
    p[0] = id;
    REQUIRE(prov.get_logits(p.data(), p.size(), lg.data()));
  }
  for (int id : {-1, hf::ser::kVocabMaxNotes + 1}) {
    std::vector<int> p = procedural_prefixes().front();
    p[0] = id;
    CHECK_FALSE(prov.get_logits(p.data(), p.size(), lg.data()));
  }
}
#else
TEST_CASE("ort logits unavailable without ORT (offline stub)", "[ort_logits]") {
  OrtLogitsProvider prov(HARMONY_FORGE_LOGITS_MODEL);
  CHECK_FALSE(prov.available());
  CHECK(prov.load_count() == 0);
  std::array<float, 256> lg{};
  const std::vector<int> pre = {1, 0, 0, 1, 60, 4, 4};
  CHECK_FALSE(prov.get_logits(pre.data(), pre.size(), lg.data()));
  CHECK(prov.load_count() == 0);  // fills never load (reuse holds trivially)
}
#endif
