// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <vector>

#include "inference_runner.h"

namespace hf::infer {

// Background worker pool + pollable completion queue (R4: JUCE-free; the
// mutex-protected queues below are only touched OFF the audio thread).
// The message/GUI side submits with `predict_async` and polls
// `try_take_completed()`; Sprint 4 binds this to the UI thread.
using JobId = std::uint64_t;

struct CompletedJob {
  JobId id = 0;
  std::vector<int> output;
};

class InferenceJobQueue {
 public:
  explicit InferenceJobQueue(std::size_t workers = 2);
  ~InferenceJobQueue();
  InferenceJobQueue(const InferenceJobQueue&) = delete;
  InferenceJobQueue& operator=(const InferenceJobQueue&) = delete;

  // Submit a job; each job builds its own OnnxRunner from cfg (model_path),
  // so no runner lifetime has to be managed by the caller.
  JobId predict_async(std::vector<int> input, InferenceConfig cfg);

  // Non-blocking: nullopt when no job has finished yet.
  std::optional<CompletedJob> try_take_completed();

  std::size_t pending() const;

  // Blocking teardown: signals workers to stop, drains already-queued jobs,
  // joins all worker threads. In-flight jobs run to completion, so this
  // blocks until they finish (bounded: predict never blocks indefinitely).
  // Idempotent; the destructor calls it. Jobs submitted after shutdown are
  // accepted but never processed. Never call from a worker thread, and never
  // from the real-time audio thread.
  void shutdown();

 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;  // fwd-declared to keep this header dependency-light
};

// Process-wide default queue backing the free functions below (Task 3 entry).
JobId predict_async(std::vector<int> input, InferenceConfig cfg);
std::optional<CompletedJob> try_take_completed();

}  // namespace hf::infer
