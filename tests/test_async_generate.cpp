// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include <catch2/catch_test_macros.hpp>

#include <array>
#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <thread>
#include <vector>

#include "async_generate.h"
#include "candidates.h"
#include "core/model/note.h"
#include "core/serialization/tokenizer.h"
#include "inference_runner.h"
#include "model_path.h"

// Path to the committed mock model, injected by CMake (same as test_inference).
#ifndef HARMONY_FORGE_MOCK_MODEL
#define HARMONY_FORGE_MOCK_MODEL "training/model.onnx"
#endif

namespace {

hf::infer::GenParams seed7_params() {
  hf::infer::GenParams p;
  p.mode = hf::infer::GenMode::Strict;
  p.seed = 7;
  p.bars = 4;
  p.tonic = 60;
  p.scale = "major";
  return p;
}

std::array<std::vector<int>, 4> encoded(
    const std::array<hf::core::Pattern, 4>& cands) {
  std::array<std::vector<int>, 4> out;
  for (int i = 0; i < 4; ++i) out[i] = hf::ser::encode_pattern(cands[i]);
  return out;
}

bool same_progression(const hf::core::ChordProgression& a,
                      const hf::core::ChordProgression& b) {
  if (a.size() != b.size()) return false;
  for (size_t i = 0; i < a.size(); ++i) {
    if (a[i].root != b[i].root || a[i].type != b[i].type ||
        a[i].inversion != b[i].inversion || a[i].tension != b[i].tension)
      return false;
  }
  return true;
}

// Poll until `take()` yields a value or the deadline passes.
template <typename Take>
auto poll_until(Take&& take, std::chrono::milliseconds budget = std::chrono::seconds(30)) {
  using Opt = decltype(take());
  const auto deadline = std::chrono::steady_clock::now() + budget;
  for (;;) {
    if (auto got = take()) return got;
    if (std::chrono::steady_clock::now() >= deadline) return Opt{};
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
}

// Item D: test-only 50 ms fake-latency stub at the IInferenceRunner seam.
// Returns empty (== deterministic fallback, same as the unloaded runner),
// but only after a delay, so the test can prove submit is non-blocking.
class FakeLatencyRunner : public hf::infer::IInferenceRunner {
 public:
  std::vector<int> predict(const std::vector<int>& /*input*/,
                           const hf::infer::InferenceConfig& /*cfg*/) override {
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
    return {};
  }
};

// S5a-R2: gate runner pins the worker inside job 1's predict until released,
// so jobs 2/3 are still queued when shutdown runs. Lets the test prove
// shutdown waits for the in-flight job but drops queued-but-unstarted jobs.
class GateRunner : public hf::infer::IInferenceRunner {
 public:
  std::atomic<bool> started{false};
  std::atomic<bool> release{false};
  std::vector<int> predict(const std::vector<int>& /*input*/,
                           const hf::infer::InferenceConfig& /*cfg*/) override {
    started.store(true, std::memory_order_release);
    while (!release.load(std::memory_order_acquire))
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    return {};
  }
};

}  // namespace

TEST_CASE("GenParams defaults to empty model path (current behavior)", "[async]") {
  const hf::infer::GenParams p;
  CHECK(p.model_path.empty());
}

TEST_CASE("model path sanitise keeps only existing .onnx files", "[async]") {
  CHECK(hf::infer::sanitised_model_path("").empty());
  CHECK(hf::infer::sanitised_model_path("no-such-file.onnx").empty());
  CHECK(hf::infer::sanitised_model_path("model.txt").empty());

  const auto dir = std::filesystem::temp_directory_path();
  const auto good = dir / "hf_task4_good.onnx";
  const auto wrong_ext = dir / "hf_task4_wrong.txt";
  const auto upper_ext = dir / "hf_task4_upper.ONNX";
  {
    std::ofstream(good) << "x";
    std::ofstream(wrong_ext) << "x";
    std::ofstream(upper_ext) << "x";
  }
  CHECK(hf::infer::sanitised_model_path(good.string()) == good.string());
  CHECK(hf::infer::sanitised_model_path(wrong_ext.string()).empty());
  CHECK(hf::infer::sanitised_model_path(upper_ext.string()) == upper_ext.string());
  CHECK(hf::infer::is_usable_model_path(good.string()));
  CHECK_FALSE(hf::infer::is_usable_model_path(""));
  std::error_code ec;
  std::filesystem::remove(good, ec);
  std::filesystem::remove(wrong_ext, ec);
  std::filesystem::remove(upper_ext, ec);
}

TEST_CASE("async completion is bit-identical to the sync path", "[async][inv1]") {
  const auto params = seed7_params();  // empty model path == fallback
  const auto expected = hf::infer::generate_candidates(params);
  const auto expected_prog = hf::infer::progression_for_params(params);

  hf::infer::AsyncGenerateQueue q(1);
  const hf::infer::GenJobId id = q.generate_async(params);
  auto got = poll_until([&] { return q.try_take_completed(); });
  REQUIRE(got.has_value());
  CHECK(got->id == id);
  CHECK(encoded(got->candidates) == encoded(expected));
  CHECK(same_progression(got->progression, expected_prog));
  CHECK(got->params.seed == params.seed);
}

TEST_CASE("rapid regenerates supersede: latest wins, no crash", "[async]") {
  auto first = seed7_params();
  auto latest = seed7_params();
  latest.seed = 8;

  hf::infer::AsyncGenerateQueue q(1);
  (void)q.generate_async(first);
  const hf::infer::GenJobId want = q.generate_async(latest);

  // Stale completions for `first` are dropped; only `latest` is returned.
  auto got = poll_until([&] { return q.try_take_latest(want); });
  REQUIRE(got.has_value());
  CHECK(got->id == want);
  CHECK(encoded(got->candidates) == encoded(hf::infer::generate_candidates(latest)));
}

TEST_CASE("fake-latency runner proves the flow is non-blocking", "[async][inv1]") {
  auto runner = std::make_shared<FakeLatencyRunner>();
  hf::infer::AsyncGenerateQueue q(runner, 1);

  const auto params = seed7_params();
  const auto expected = hf::infer::generate_candidates(params);  // sync fallback
  const hf::infer::GenJobId id = q.generate_async(params);

  // The worker sleeps 50 ms, so an immediate poll must find nothing: submit
  // returned without running inference on this thread.
  CHECK_FALSE(q.try_take_completed().has_value());

  auto got = poll_until([&] { return q.try_take_latest(id); });
  REQUIRE(got.has_value());
  CHECK(got->id == id);
  CHECK(encoded(got->candidates) == encoded(expected));
}

TEST_CASE("model path threads into generation deterministically", "[async][inv2]") {
  auto params = seed7_params();
  params.model_path = HARMONY_FORGE_MOCK_MODEL;

  const auto a = hf::infer::generate_candidates(params);
  const auto b = hf::infer::generate_candidates(params);
  CHECK(encoded(a) == encoded(b));  // fixed seed -> identical outputs

  hf::infer::AsyncGenerateQueue q(1);
  const hf::infer::GenJobId id = q.generate_async(params);
  auto got = poll_until([&] { return q.try_take_latest(id); });
  REQUIRE(got.has_value());
  CHECK(encoded(got->candidates) == encoded(a));  // async == sync with model
}

TEST_CASE("shutdown waits for the in-flight job, drops queued jobs", "[async]") {
  auto runner = std::make_shared<GateRunner>();
  hf::infer::AsyncGenerateQueue q(runner, 1);
  const auto params = seed7_params();
  const hf::infer::GenJobId id1 = q.generate_async(params);
  (void)q.generate_async(params);
  (void)q.generate_async(params);

  // Wait until the worker is blocked inside job 1's predict, so jobs 2/3
  // are still queued when shutdown runs.
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(30);
  while (!runner->started.load(std::memory_order_acquire)) {
    REQUIRE(std::chrono::steady_clock::now() < deadline);
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }

  std::thread releaser([&] {
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    runner->release.store(true, std::memory_order_release);
  });
  q.shutdown();  // must return once job 1 finishes; jobs 2/3 never run
  releaser.join();

  auto got = q.try_take_completed();
  REQUIRE(got.has_value());
  CHECK(got->id == id1);
  CHECK_FALSE(q.try_take_completed().has_value());  // dropped jobs complete never
  CHECK(q.pending() == 0);
}
