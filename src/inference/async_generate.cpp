// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// AsyncGenerateQueue: worker pool + pollable generation completions.
// See async_generate.h. Pure C++20, no JUCE; mirrors job_queue.cpp.
#include "async_generate.h"

#include <atomic>
#include <condition_variable>
#include <deque>
#include <mutex>
#include <queue>
#include <thread>
#include <utility>

namespace hf::infer {

struct GenTask {
  GenJobId id = 0;
  GenParams params;
};

struct AsyncGenerateQueue::Impl {
  std::mutex tasks_mutex;
  std::condition_variable tasks_cv;
  std::queue<GenTask> tasks;
  std::mutex done_mutex;
  std::deque<CompletedGeneration> done;
  std::vector<std::thread> workers;
  std::atomic<GenJobId> next_id{1};
  std::atomic<bool> shut{false};
  bool stop = false;  // under tasks_mutex
  int active = 0;     // running jobs, under tasks_mutex
  std::shared_ptr<IInferenceRunner> runner;  // null == production path

  CompletedGeneration run_task(const GenTask& task) {
    CompletedGeneration result;
    result.id = task.id;
    result.params = task.params;
    try {
      if (runner) {
        result.candidates = generate_candidates_with_runner(task.params, *runner);
      } else {
        result.candidates = generate_candidates(task.params);
      }
      result.progression = progression_for_params(task.params);
    } catch (...) {
      // Unreachable by contract (the pipeline never throws), but a worker
      // thread must never let an exception escape (that would terminate).
      // Retry once on the deterministic fallback, else complete empty.
      try {
        GenParams fb = task.params;
        fb.model_path.clear();
        result.candidates = generate_candidates(fb);
        result.progression = progression_for_params(fb);
      } catch (...) {
        result.candidates = {};
        result.progression.clear();
      }
    }
    return result;
  }

  void worker_main() {
    for (;;) {
      GenTask task;
      {
        std::unique_lock<std::mutex> lock(tasks_mutex);
        tasks_cv.wait(lock, [&] { return stop || !tasks.empty(); });
        if (stop && tasks.empty()) return;
        if (tasks.empty()) continue;
        task = std::move(tasks.front());
        tasks.pop();
        ++active;
      }
      CompletedGeneration finished = run_task(task);
      {
        std::unique_lock<std::mutex> lock(tasks_mutex);
        --active;
      }
      {
        std::lock_guard<std::mutex> lock(done_mutex);
        done.push_back(std::move(finished));
      }
      tasks_cv.notify_all();  // wakes drain waiters in the destructor
    }
  }
};

AsyncGenerateQueue::AsyncGenerateQueue(std::size_t workers)
    : impl_(std::make_unique<Impl>()) {
  if (workers == 0) workers = 1;
  try {
    for (std::size_t i = 0; i < workers; ++i)
      impl_->workers.emplace_back([impl = impl_.get()] { impl->worker_main(); });
  } catch (...) {
    {
      std::lock_guard<std::mutex> lock(impl_->tasks_mutex);
      impl_->stop = true;
    }
    impl_->tasks_cv.notify_all();
    for (auto& t : impl_->workers)
      if (t.joinable()) t.join();
    throw;
  }
}

AsyncGenerateQueue::AsyncGenerateQueue(std::shared_ptr<IInferenceRunner> runner,
                                       std::size_t workers)
    : AsyncGenerateQueue(workers) {
  impl_->runner = std::move(runner);
}

AsyncGenerateQueue::~AsyncGenerateQueue() { shutdown(); }

void AsyncGenerateQueue::shutdown() {
  bool expected = false;
  if (!impl_->shut.compare_exchange_strong(expected, true)) return;  // idempotent
  {
    std::lock_guard<std::mutex> lock(impl_->tasks_mutex);
    impl_->stop = true;
    // S5a-R2 close-path bound: drop queued-but-unstarted jobs so the join
    // below waits for at most the one in-flight job. The worker pops and
    // marks active under this same lock, so a job is either dropped here
    // (never runs, no completion is ever posted) or already running (runs
    // to completion, bounded); it cannot be both or neither. Submits after
    // this point behave as before (picked up only if a worker has not yet
    // exited, else orphaned until destruction — teardown submits nothing:
    // the editor timer is stopped before queue members are destroyed).
    impl_->tasks = std::queue<GenTask>{};
  }
  impl_->tasks_cv.notify_all();
  for (auto& t : impl_->workers)
    if (t.joinable()) t.join();
}

GenJobId AsyncGenerateQueue::generate_async(GenParams params) {
  const GenJobId id = impl_->next_id.fetch_add(1);
  {
    std::lock_guard<std::mutex> lock(impl_->tasks_mutex);
    impl_->tasks.push(GenTask{id, std::move(params)});
  }
  impl_->tasks_cv.notify_one();
  return id;
}

std::optional<CompletedGeneration> AsyncGenerateQueue::try_take_completed() {
  std::lock_guard<std::mutex> lock(impl_->done_mutex);
  if (impl_->done.empty()) return std::nullopt;
  CompletedGeneration job = std::move(impl_->done.front());
  impl_->done.pop_front();
  return job;
}

std::optional<CompletedGeneration> AsyncGenerateQueue::try_take_latest(GenJobId want) {
  std::lock_guard<std::mutex> lock(impl_->done_mutex);
  std::optional<CompletedGeneration> match;
  for (auto& job : impl_->done)
    if (job.id == want) match = std::move(job);  // keep the (unique) match
  impl_->done.clear();  // stale superseded completions are dropped here
  return match;
}

std::size_t AsyncGenerateQueue::pending() const {
  std::lock_guard<std::mutex> lock(impl_->tasks_mutex);
  return impl_->tasks.size() + static_cast<std::size_t>(impl_->active);
}

}  // namespace hf::infer
