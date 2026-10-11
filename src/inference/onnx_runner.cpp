// OnnxRunner: ORT session wrapper (ON) / offline stub (OFF). See onnx_runner.h.
#include "onnx_runner.h"

#include <algorithm>
#include <cstdint>
#include <limits>
#include <mutex>
#include <string>
#include <utility>

#ifdef HARMONY_FORGE_WITH_ONNX
#include <onnxruntime_cxx_api.h>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif
#endif

namespace hf::infer {

struct OnnxRunner::Impl {
  bool loaded = false;
#ifdef HARMONY_FORGE_WITH_ONNX
  Ort::Env env{ORT_LOGGING_LEVEL_WARNING, "harmony-forge"};
  Ort::Session session{nullptr};
  std::string input_name;
  std::string output_name;
  std::mutex run_mutex;  // ORT Run is re-entrant, but serialize for determinism
#endif
};

OnnxRunner::OnnxRunner(const InferenceConfig& cfg) noexcept
    : impl_(std::make_unique<Impl>()) {
#ifdef HARMONY_FORGE_WITH_ONNX
  try {
    if (cfg.model_path.empty()) return;
    Ort::SessionOptions opts;
    opts.SetIntraOpNumThreads(1);
    opts.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_BASIC);
#ifdef _WIN32
    const std::string& utf8 = cfg.model_path;
    const int need =
        ::MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, nullptr, 0);
    if (need <= 0) return;
    std::wstring wpath(static_cast<size_t>(need), L'\0');
    if (::MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, wpath.data(), need) <= 0) return;
    Ort::Session session{impl_->env, wpath.c_str(), opts};
#else
    Ort::Session session{impl_->env, cfg.model_path.c_str(), opts};
#endif
    Ort::AllocatorWithDefaultOptions alloc;
    Ort::AllocatedStringPtr in_name = session.GetInputNameAllocated(0, alloc);
    Ort::AllocatedStringPtr out_name = session.GetOutputNameAllocated(0, alloc);
    impl_->input_name = in_name.get();
    impl_->output_name = out_name.get();
    impl_->session = std::move(session);
    impl_->loaded = true;
  } catch (...) {
    impl_->loaded = false;
  }
#else
  (void)cfg;
#endif
}

OnnxRunner::~OnnxRunner() = default;

bool OnnxRunner::loaded() const noexcept { return impl_ != nullptr && impl_->loaded; }

std::vector<int> OnnxRunner::predict(const std::vector<int>& input,
                                     const InferenceConfig& cfg) {
  std::vector<int> out;
  if (input.empty() || impl_ == nullptr) return out;
#ifdef HARMONY_FORGE_WITH_ONNX
  try {
    std::lock_guard<std::mutex> lock(impl_->run_mutex);
    if (!impl_->loaded) return out;
    size_t n = input.size();
    if (cfg.max_tokens > 0) n = std::min(n, static_cast<size_t>(cfg.max_tokens));
    if (n == 0) return out;
    std::vector<std::int64_t> ids(input.begin(), input.begin() + n);
    const std::array<std::int64_t, 2> shape{1, static_cast<std::int64_t>(n)};
    const Ort::MemoryInfo mem =
        Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    Ort::Value in_tensor = Ort::Value::CreateTensor<std::int64_t>(
        mem, ids.data(), ids.size(), shape.data(), shape.size());
    const char* in_names[] = {impl_->input_name.c_str()};
    const char* out_names[] = {impl_->output_name.c_str()};
    std::vector<Ort::Value> results = impl_->session.Run(Ort::RunOptions{nullptr}, in_names,
                                                         &in_tensor, 1, out_names, 1);
    if (results.empty() || !results[0].IsTensor()) return out;
    const std::int64_t* data = results[0].GetTensorData<std::int64_t>();
    size_t count = results[0].GetTensorTypeAndShapeInfo().GetElementCount();
    if (cfg.max_tokens > 0) count = std::min(count, static_cast<size_t>(cfg.max_tokens));
    out.reserve(count);
    for (size_t i = 0; i < count; ++i) {
      const std::int64_t v = data[i];
      out.push_back(v < static_cast<std::int64_t>((std::numeric_limits<int>::min)())
                        ? (std::numeric_limits<int>::min)()
                    : v > static_cast<std::int64_t>((std::numeric_limits<int>::max)())
                        ? (std::numeric_limits<int>::max)()
                        : static_cast<int>(v));
    }
  } catch (...) {
    return std::vector<int>{};  // no exceptions escape: failure == empty output
  }
#else
  (void)cfg;
#endif
  return out;
}

}  // namespace hf::infer
