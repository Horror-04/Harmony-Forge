// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <thread>

#include "core/serialization/tokenizer.h"
#include "job_queue.h"
#include "onnx_runner.h"

// Path to the committed mock model, injected by CMake.
#ifndef HARMONY_FORGE_MOCK_MODEL
#define HARMONY_FORGE_MOCK_MODEL "training/model.onnx"
#endif

using hf::infer::InferenceConfig;

namespace {

InferenceConfig mock_cfg() {
  InferenceConfig cfg;
  cfg.model_path = HARMONY_FORGE_MOCK_MODEL;
  cfg.max_tokens = 1024;
  cfg.seed = 1234;
  return cfg;
}

std::vector<int> sample_input() {
  // 4-bar mock context: 8 sixteenth-notes on Melody.
  std::vector<int> ids{8};
  for (int i = 0; i < 8; ++i) {
    const int bar = i / 16, sub = i % 16;
    ids.insert(ids.end(), {bar, sub, 1, 60 + (i % 8), 1, 6});
  }
  return ids;
}

}  // namespace

TEST_CASE("mock model loads", "[inference]") {
  hf::infer::OnnxRunner runner(mock_cfg());
#ifdef HARMONY_FORGE_WITH_ONNX
  CHECK(runner.loaded());
#else
  CHECK_FALSE(runner.loaded());  // OFFLINE stub: never loaded, never throws
#endif
}

TEST_CASE("fixed seed gives identical outputs", "[inference]") {
  hf::infer::OnnxRunner runner(mock_cfg());
  const auto in = sample_input();
  const auto a = runner.predict(in, mock_cfg());
  const auto b = runner.predict(in, mock_cfg());
#ifdef HARMONY_FORGE_WITH_ONNX
  CHECK_FALSE(a.empty());
  CHECK(a == b);
#else
  CHECK(a.empty());
  CHECK(b.empty());
#endif
}

TEST_CASE("predict on empty input returns empty, never throws", "[inference]") {
  hf::infer::OnnxRunner runner(mock_cfg());
  CHECK_NOTHROW(runner.predict({}, mock_cfg()));
  CHECK(runner.predict({}, mock_cfg()).empty());
}

TEST_CASE("async job completes with the sync result", "[inference]") {
  const auto in = sample_input();
  const auto expected = hf::infer::OnnxRunner(mock_cfg()).predict(in, mock_cfg());

  const hf::infer::JobId id = hf::infer::predict_async(in, mock_cfg());
  std::optional<hf::infer::CompletedJob> got;
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(30);
  while (std::chrono::steady_clock::now() < deadline) {
    got = hf::infer::try_take_completed();
    if (got.has_value()) break;
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
  REQUIRE(got.has_value());
  CHECK(got->id == id);
  CHECK(got->output == expected);
}

TEST_CASE("perf: 8-bar predict well under SPEC budget", "[inference]") {
  // SPEC §11: 4-8 bars local <= 2 s. Real weights are far below; print the number.
  std::vector<int> in{128};
  for (int i = 0; i < 128; ++i)
    in.insert(in.end(), {i / 16, i % 16, 1, 60 + (i % 12), 1, 6});
  hf::infer::OnnxRunner runner(mock_cfg());
  constexpr int kReps = 5;
  const auto t0 = std::chrono::steady_clock::now();
  for (int r = 0; r < kReps; ++r) {
    const auto out = runner.predict(in, mock_cfg());
#ifdef HARMONY_FORGE_WITH_ONNX
    // Phase 2 Task 3 (R6): real weights predict per-position next tokens,
    // they do NOT echo the input. Contract: same length, ids in [0, 256).
    CHECK(out.size() == in.size());
    CHECK(std::all_of(out.begin(), out.end(), [](int v) { return v >= 0 && v < 256; }));
#else
    CHECK(out.empty());
#endif
  }
  const double ms =
      std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count() /
      kReps;
  std::printf("[perf] predict 8-bar/769-token: %.3f ms avg (%d reps)\n", ms, kReps);
  CHECK(ms < 2000.0);
}
