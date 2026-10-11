// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>

#include "candidates.h"
#include "core/model/note.h"
#include "inference_runner.h"

namespace hf::infer {

// Generation-level async queue (Phase 2 Task 4, item C).
//
// Same threading contract as InferenceJobQueue (R4: JUCE-free; the
// mutex-protected queues below are only touched OFF the audio thread; the
// message side submits and polls, workers generate):
//   - submit with `generate_async` on the message thread (never blocks on
//     inference; only a short queue lock),
//   - poll with `try_take_completed` / `try_take_latest` on the message
//     thread (existing Timer tick is fine),
//   - apply the completion on the message thread.
//
// Why a dedicated queue instead of token-level `predict_async` jobs: a full
// regeneration is `generate_candidates(params)` end to end. Splitting it
// into token jobs would duplicate the compose/encode/decode/transform
// assembly in a second place and risk sync/async divergence; running the
// IDENTICAL function on a worker makes "async == sync bit-identical"
// structural (asserted by tests), for empty and model paths alike.
//
// Cancel-safe supersede: the worker pool is FIFO and in-flight jobs run to
// completion (bounded: generation never blocks indefinitely), so a second
// Regenerate does NOT cancel — it supersedes. The caller tracks the latest
// id and collects with `try_take_latest(want)`, which drops stale
// completions for any other id.
//
// Ownership: callers own an instance (e.g. PatternDocument); there is
// deliberately no process-wide default queue, so lifetime and shutdown stay
// explicit. Stable interface for arrangement/distribution tasks.
using GenJobId = std::uint64_t;

struct CompletedGeneration {
  GenJobId id = 0;
  GenParams params;  ///< echo of the submitted params
  std::array<core::Pattern, 4> candidates;
  core::ChordProgression progression;  ///< progression_for_params(params)
};

class AsyncGenerateQueue {
 public:
  explicit AsyncGenerateQueue(std::size_t workers = 1);
  // Test seam (item D): every job delegates its runner stage to `runner`
  // (e.g. a 50 ms fake-latency stub proving the message flow is async).
  // Production uses the single-arg ctor (runner built per job from
  // GenParams.model_path). `runner` must outlive nothing: the queue holds
  // a copy of the shared_ptr; with workers > 1 it must be thread-safe.
  explicit AsyncGenerateQueue(std::shared_ptr<IInferenceRunner> runner,
                              std::size_t workers = 1);
  ~AsyncGenerateQueue();
  AsyncGenerateQueue(const AsyncGenerateQueue&) = delete;
  AsyncGenerateQueue& operator=(const AsyncGenerateQueue&) = delete;

  // Submit a regeneration; returns its id. Never blocks on inference.
  GenJobId generate_async(GenParams params);

  // Non-blocking: oldest finished generation, or nullopt when none.
  std::optional<CompletedGeneration> try_take_completed();

  // Non-blocking supersede collector: drains everything finished so far,
  // returns the completion with id == `want` when present, drops the rest
  // (stale superseded jobs). Nullopt when `want` has not finished yet.
  std::optional<CompletedGeneration> try_take_latest(GenJobId want);

  std::size_t pending() const;

  // Blocking teardown, idempotent; the destructor calls it. Same semantics
  // as InferenceJobQueue::shutdown: in-flight jobs run to completion
  // (bounded), queued jobs drain, threads join. Never call from a worker
  // thread, and never from the real-time audio thread.
  void shutdown();

 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace hf::infer
