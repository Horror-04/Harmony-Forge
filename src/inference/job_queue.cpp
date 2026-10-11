// InferenceJobQueue: worker pool + pollable completions. See job_queue.h.
#include "job_queue.h"

#include <atomic>
#include <condition_variable>
#include <mutex>
#include <queue>
#include <thread>

#include "onnx_runner.h"

namespace hf::infer {

struct Task {
  JobId id = 0;
  std::vector<int> input;
  InferenceConfig cfg;
};

struct InferenceJobQueue::Impl {
  std::mutex tasks_mutex;
  std::condition_variable tasks_cv;
  std::queue<Task> tasks;
  std::mutex done_mutex;
  std::queue<CompletedJob> done;
  std::vector<std::thread> workers;
  std::atomic<JobId> next_id{1};
  bool stop = false;  // under tasks_mutex
  int active = 0;     // running jobs, under tasks_mutex

  void worker_main() {
    for (;;) {
      Task task;
      {
        std::unique_lock<std::mutex> lock(tasks_mutex);
        tasks_cv.wait(lock, [&] { return stop || !tasks.empty(); });
        if (stop && tasks.empty()) return;
        if (tasks.empty()) continue;
        task = std::move(tasks.front());
        tasks.pop();
        ++active;
      }
      std::vector<int> out;
      try {
        OnnxRunner runner(task.cfg);
        out = runner.predict(task.input, task.cfg);
      } catch (...) {
        out.clear();  // never let exceptions escape the worker thread
      }
      {
        std::unique_lock<std::mutex> lock(tasks_mutex);
        --active;
      }
      {
        std::lock_guard<std::mutex> lock(done_mutex);
        done.push(CompletedJob{task.id, std::move(out)});
      }
      tasks_cv.notify_all();  // wakes drain waiters in the destructor
    }
  }
};

InferenceJobQueue::InferenceJobQueue(std::size_t workers)
    : impl_(std::make_unique<Impl>()) {
  if (workers == 0) workers = 1;
  try {
    for (std::size_t i = 0; i < workers; ++i)
      impl_->workers.emplace_back([impl = impl_.get()] { impl->worker_main(); });
  } catch (...) {
    // If thread creation fails, shut down what started and rethrow: callers
    // are off the audio thread, where throwing from setup code is acceptable.
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

InferenceJobQueue::~InferenceJobQueue() {
  // Drain submitted jobs so no result is silently lost, then stop.
  {
    std::unique_lock<std::mutex> lock(impl_->tasks_mutex);
    impl_->tasks_cv.wait(lock, [&] { return impl_->tasks.empty() && impl_->active == 0; });
    impl_->stop = true;
  }
  impl_->tasks_cv.notify_all();
  for (auto& t : impl_->workers)
    if (t.joinable()) t.join();
}

JobId InferenceJobQueue::predict_async(std::vector<int> input, InferenceConfig cfg) {
  const JobId id = impl_->next_id.fetch_add(1);
  {
    std::lock_guard<std::mutex> lock(impl_->tasks_mutex);
    impl_->tasks.push(Task{id, std::move(input), std::move(cfg)});
  }
  impl_->tasks_cv.notify_one();
  return id;
}

std::optional<CompletedJob> InferenceJobQueue::try_take_completed() {
  std::lock_guard<std::mutex> lock(impl_->done_mutex);
  if (impl_->done.empty()) return std::nullopt;
  CompletedJob job = std::move(impl_->done.front());
  impl_->done.pop();
  return job;
}

std::size_t InferenceJobQueue::pending() const {
  std::lock_guard<std::mutex> lock(impl_->tasks_mutex);
  return impl_->tasks.size() + static_cast<std::size_t>(impl_->active);
}

namespace {
InferenceJobQueue& global_queue() {
  static InferenceJobQueue queue(2);
  return queue;
}
}  // namespace

JobId predict_async(std::vector<int> input, InferenceConfig cfg) {
  return global_queue().predict_async(std::move(input), std::move(cfg));
}

std::optional<CompletedJob> try_take_completed() { return global_queue().try_take_completed(); }

}  // namespace hf::infer
