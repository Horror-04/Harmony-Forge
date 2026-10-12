// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Phase 4 Task 4: real-model + committed-index C++ end-to-end.
//
// Closes the loop between the Python eval guarantees (`training/evaluate.py`
// over the shipped 0.907 weights) and the stub-based C++ mechanics tests:
// this test drives the REAL committed `training/model.onnx` through the REAL
// `generate_candidates` pipeline with the REAL committed
// `training/memo_index.bin` filter path, and asserts the shipped §10
// guarantee (verbatim run < 4 on final candidates) + determinism
// (two runs -> identical encodes).
//
// EXCLUSION (mandatory): this test is hidden from the default fast `ctest`
// suite by TWO independent mechanisms:
//   1. The TEST_CASE carries the Catch2 `[.]` tag, so even a bare run of
//      this binary skips it.
//   2. `tests/CMakeLists.txt` builds the `test_memo_e2e` binary WITHOUT
//      `catch_discover_tests`, so `ctest -N` never lists it and the default
//      `ctest` count + wall time are unchanged (proven in the task report).
// Explicit (nightly) run from the repo root:
//   .\build-full\tests\Release\test_memo_e2e "[.]"
#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <string>
#include <vector>

#include "candidates.h"
#include "core/model/note.h"
#include "core/model/track_pattern.h"
#include "core/serialization/tokenizer.h"
#include "memo_filter.h"
#include "onnx_runner.h"

// Committed artifact paths, injected by CMake (absolute, no user paths).
#ifndef HARMONY_FORGE_REAL_MODEL
#define HARMONY_FORGE_REAL_MODEL "training/model.onnx"
#endif
#ifndef HARMONY_FORGE_MEMO_INDEX
#define HARMONY_FORGE_MEMO_INDEX "training/memo_index.bin"
#endif

namespace {

// Committed 0.907 weight file size (bytes). Guards against silent weight
// substitution: the exact bytes are owned by git (see task report for the
// full sha256, verified at commit time). `model.quant.onnx` is NOT accepted.
constexpr std::uintmax_t kCommittedModelBytes = 3146034;

constexpr int kWindow = 8;  // must match training/export_memo_index.py
constexpr int kMaxVerbatimRun = 4;  // SPEC §10: runs of >= 4 are truncated

// Mirror of training/evaluate.py::longest_verbatim_run (floor 0: the whole
// pattern counts as generated post-hoc). Same helper as
// tests/test_memo_filter.cpp::longest_run.
int longest_run(const std::vector<int>& ids, const hf::infer::MemoIndex& idx) {
  int best = 0, cur = 0;
  for (size_t k = 0; k + kWindow <= ids.size(); ++k) {
    std::array<int32_t, kWindow> w;
    for (int i = 0; i < kWindow; ++i) w[static_cast<size_t>(i)] = ids[k + i];
    cur = idx.contains(w) ? cur + 1 : 0;
    best = std::max(best, cur);
  }
  return best;
}

hf::infer::GenParams e2e_params() {
  hf::infer::GenParams p;
  p.mode = hf::infer::GenMode::Strict;
  p.seed = 7;  // fixed seed: the determinism leg of this test
  p.bars = 4;
  p.tonic = 60;
  p.scale = "major";
  p.model_path = HARMONY_FORGE_REAL_MODEL;
  return p;
}

}  // namespace

TEST_CASE("real model + committed index end-to-end", "[.]") {
#ifndef HARMONY_FORGE_WITH_ONNX
  SUCCEED("offline stub build: real-model e2e not applicable");
  return;
#else
  const std::string model = HARMONY_FORGE_REAL_MODEL;
  const std::string index_path = HARMONY_FORGE_MEMO_INDEX;

  // A. Committed-weights identity: exact byte size of the shipped 0.907 set.
  // (Full sha256 is verified outside the test at commit time; see report.)
  std::error_code ec;
  const auto size = std::filesystem::file_size(model, ec);
  REQUIRE(!ec);
  INFO("model bytes = " << size << " (committed 0.907 set = " << kCommittedModelBytes << ")");
  REQUIRE(size == kCommittedModelBytes);

  // B. The real weights load through the shipped OnnxRunner path.
  hf::infer::InferenceConfig cfg;
  cfg.model_path = model;
  hf::infer::OnnxRunner runner(cfg);
  REQUIRE(runner.loaded());

  // C. The committed memo index loads.
  auto idx = hf::infer::load_memo_index(index_path);
  REQUIRE(idx.has_value());
  CHECK(idx->size() > 1000);  // exact count owned by the exporter
  std::printf("[e2e] model=%s index_ngrams=%zu\n", model.c_str(), idx->size());

  // D. Fixed params + fixed seed through the production entry point, twice.
  const auto params = e2e_params();
  const auto t0 = std::chrono::steady_clock::now();
  const auto first = hf::infer::generate_candidates(params);
  const auto second = hf::infer::generate_candidates(params);
  const double ms = std::chrono::duration<double, std::milli>(
                        std::chrono::steady_clock::now() - t0)
                        .count();
  std::printf("[e2e] 2x generate_candidates(4-bar strict, seed 7): %.1f ms\n", ms);

  // E. Determinism: run twice -> identical encodes on all 4 candidates.
  // F. §10 guarantee: verbatim run < 4 on every FINAL candidate, measured
  // against the committed index (the filter already ran inside
  // generate_candidates via the weights-sibling index path).
  for (int i = 0; i < 4; ++i) {
    const auto a = hf::ser::encode_pattern(first[i]);
    const auto b = hf::ser::encode_pattern(second[i]);
    CHECK(b == a);
    REQUIRE(hf::core::pattern_note_count(first[i]) > 0);
    const int run = longest_run(a, *idx);
    INFO("candidate " << i << ": notes=" << hf::core::pattern_note_count(first[i])
                      << " ids=" << a.size() << " verbatim_run=" << run);
    CHECK(run < kMaxVerbatimRun);
  }
#endif
}
