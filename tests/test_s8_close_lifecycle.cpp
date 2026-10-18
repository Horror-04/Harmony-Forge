// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// S8-SKIP item 1: close-path lifecycle characterization — destruction with an
// in-flight job.
//
// What this pins (and why it is characterization, not a fix): NOBODY in
// src/plugin calls AsyncGenerateQueue::shutdown() explicitly (grep: zero
// hits) — editor close and PatternDocument destruction both rely on the
// IMPLICIT path `~AsyncGenerateQueue() { shutdown(); }`
// (src/inference/async_generate.cpp:113) via member reverse-destruction
// (editor previewGen_ at src/plugin/audio/PluginEditor.h:312, doc
// gen_queue_ at src/plugin/ui/PatternDocument.h:180, created
// src/plugin/ui/PatternDocument.cpp:85). The existing
// "shutdown waits for the in-flight job, drops queued jobs"
// (test_async_generate.cpp:191) proves the EXPLICIT shutdown() semantics;
// these two cases prove the DESTRUCTOR path the close path actually uses.
// Green on the untouched tree by construction (the dtor already calls
// shutdown(); the tests only pin it).
//
// Determinism: GateRunner pins the worker inside predict until released
// (the established test_async_generate.cpp pattern — bounded waits, no
// wall-clock assumptions). Editor-close WITH a host/message loop is NOT
// covered here (needs a host; deliberately not shipped as a timing-flaky
// test — see docs/measurements/s8-skip.md).
#include <catch2/catch_test_macros.hpp>

#include <atomic>
#include <chrono>
#include <memory>
#include <thread>
#include <vector>

#include "async_generate.h"
#include "candidates.h"
#include "inference_runner.h"

namespace {

// GateRunner (same pattern as tests/test_async_generate.cpp): pins the
// worker inside predict until released. Additionally counts predict entries
// and records completion, so destruction-path tests can observe what the
// joined worker did without polling the (already destroyed) queue.
//
// NOTE (found red on first run): the runner seam is per-PREDICT, not
// per-job — one fallback job makes several predict calls (4 for the seed-7
// params below). Tests therefore calibrate the per-job call count with a
// free-running synchronous run first, then assert the destruction run made
// exactly one job's worth.
class GateRunner : public hf::infer::IInferenceRunner {
 public:
  std::atomic<bool> started{false};
  std::atomic<bool> release{false};
  std::atomic<bool> finished{false};
  std::atomic<int> predict_calls{0};
  std::vector<int> predict(const std::vector<int>& /*input*/,
                           const hf::infer::InferenceConfig& /*cfg*/) override {
    predict_calls.fetch_add(1, std::memory_order_acq_rel);
    started.store(true, std::memory_order_release);
    while (!release.load(std::memory_order_acquire))
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    finished.store(true, std::memory_order_release);
    return {};
  }
};

// Free-running counter: calibrates how many predict calls one job with the
// given params makes (deterministic: same params + same empty returns).
class CountingRunner : public hf::infer::IInferenceRunner {
 public:
  std::atomic<int> predict_calls{0};
  std::vector<int> predict(const std::vector<int>& /*input*/,
                           const hf::infer::InferenceConfig& /*cfg*/) override {
    predict_calls.fetch_add(1, std::memory_order_acq_rel);
    return {};
  }
};

hf::infer::GenParams seed7_params() {
  hf::infer::GenParams p;
  p.mode = hf::infer::GenMode::Strict;
  p.seed = 7;
  p.bars = 4;
  p.tonic = 60;
  p.scale = "major";
  return p;
}

// Bounded wait on the gate (never a wall-clock sleep assumption).
template <typename Cond>
bool wait_until(Cond&& cond,
                std::chrono::milliseconds budget = std::chrono::seconds(30)) {
  const auto deadline = std::chrono::steady_clock::now() + budget;
  for (;;) {
    if (cond()) return true;
    if (std::chrono::steady_clock::now() >= deadline) return false;
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
}

}  // namespace

TEST_CASE("queue destructor joins the in-flight job (close-path bound)",
          "[async][s8-close]") {
  // One job's worth of predict calls (see NOTE on the runner above).
  CountingRunner probe;
  (void)hf::infer::generate_candidates_with_runner(seed7_params(), probe);
  const int per_job = probe.predict_calls.load(std::memory_order_acquire);
  REQUIRE(per_job > 0);

  auto runner = std::make_shared<GateRunner>();
  auto q = std::make_unique<hf::infer::AsyncGenerateQueue>(runner, 1);
  (void)q->generate_async(seed7_params());

  // The worker is pinned inside the job's predict: destruction below MUST
  // block until the releaser lets it finish (the editor-close join).
  REQUIRE(wait_until(
      [&] { return runner->started.load(std::memory_order_acquire); }));

  std::thread releaser([&] {
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    runner->release.store(true, std::memory_order_release);
  });
  const auto t0 = std::chrono::steady_clock::now();
  q.reset();  // ~AsyncGenerateQueue -> shutdown() -> join (no explicit call)
  const auto elapsed = std::chrono::steady_clock::now() - t0;
  releaser.join();

  // The in-flight job ran to completion INSIDE the destructor join (not
  // abandoned: abandoning it would be the close-with-inflight
  // use-after-free — the worker touches Impl state the dtor frees).
  // Exactly one job's worth of predicts ran: the job finished, nothing
  // extra started.
  CHECK(runner->finished.load(std::memory_order_acquire));
  CHECK(runner->predict_calls.load(std::memory_order_acquire) == per_job);
  // Bounded close: the join waited for one job (100 ms releaser + margin),
  // never the 30 s watchdog scale (a hung join fails here, not in ctest).
  CHECK(elapsed < std::chrono::seconds(30));
}

TEST_CASE("queue destructor drops queued-but-unstarted jobs", "[async][s8-close]") {
  CountingRunner probe;
  (void)hf::infer::generate_candidates_with_runner(seed7_params(), probe);
  const int per_job = probe.predict_calls.load(std::memory_order_acquire);
  REQUIRE(per_job > 0);

  auto runner = std::make_shared<GateRunner>();
  auto q = std::make_unique<hf::infer::AsyncGenerateQueue>(runner, 1);
  (void)q->generate_async(seed7_params());
  (void)q->generate_async(seed7_params());
  (void)q->generate_async(seed7_params());

  // Job 1 is pinned inside predict, so jobs 2/3 are still queued when the
  // destructor runs (same setup as the explicit-shutdown test).
  REQUIRE(wait_until(
      [&] { return runner->started.load(std::memory_order_acquire); }));

  std::thread releaser([&] {
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    runner->release.store(true, std::memory_order_release);
  });
  const auto t0 = std::chrono::steady_clock::now();
  q.reset();  // queued jobs are dropped here; only job 1 runs to completion
  const auto elapsed = std::chrono::steady_clock::now() - t0;
  releaser.join();

  CHECK(runner->finished.load(std::memory_order_acquire));
  CHECK(runner->predict_calls.load(std::memory_order_acquire) == per_job);
  CHECK(elapsed < std::chrono::seconds(30));
}
