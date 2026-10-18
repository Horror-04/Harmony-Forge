// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// OrtLogitsProvider: production ISamplerLogits over the logits sidecar.
// See ort_logits.h. Pure C++20, no JUCE. Never throws.
#include "ort_logits.h"

#include "core/serialization/vocab_layout.gen.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <mutex>
#include <system_error>
#include <utility>
#include <vector>

#include "model_manifest.h"

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
namespace {

constexpr const char* kSidecarFile = "model.logits.onnx";
constexpr const char* kLogitsOutput = "logits";
// Codec cap (tokenizer.py): the sidecar keeps the dynamic batch/seq
// contract, but prefixes longer than the codec can never occur.
// S2b step 4a: single-sourced from vocab_layout.gen.h (was 1024 literal).
constexpr size_t kMaxIds = hf::ser::kVocabMaxTokens;

bool names_sidecar(const std::string& path) {
  try {
    return std::filesystem::path(path).filename().string() == kSidecarFile;
  } catch (...) {
    return false;
  }
}

std::string resolve_impl(const std::string& model_path) {
  if (model_path.empty()) return std::string{};
  if (names_sidecar(model_path)) return model_path;
  const std::filesystem::path mp(model_path);
  const std::filesystem::path parent = mp.parent_path();
  if (!parent.empty()) return (parent / kSidecarFile).string();
  // Bare filename: no sibling to name, read as relative to the working
  // directory (same F2 rule as memo_index_path_for_model).
  std::error_code ec;
  const std::filesystem::path cwd = std::filesystem::current_path(ec);
  if (ec) return std::string{};
  return (cwd / kSidecarFile).string();
}

}  // namespace

struct OrtLogitsProvider::Impl {
  bool loaded = false;
  int loads = 0;
#ifdef HARMONY_FORGE_WITH_ONNX
  Ort::Env env{ORT_LOGGING_LEVEL_WARNING, "harmony-forge-logits"};
  Ort::Session session{nullptr};
  std::string input_name;
  std::mutex run_mutex;  // serialize Run for determinism (as in onnx_runner)
#endif
};

OrtLogitsProvider::OrtLogitsProvider(const std::string& model_path) noexcept
    : impl_(nullptr) {
#ifdef HARMONY_FORGE_WITH_ONNX
  // Same DAW-hardening note as OnnxRunner: Impl's Ort::Env queries the
  // loaded onnxruntime.dll at construction; a mismatched inbox DLL makes
  // Env throw, and the throw must NEVER escape this noexcept ctor.
  // Failure degrades to the unavailable stub. Never throws.
  try {
    auto impl = std::make_unique<Impl>();
    const std::string sidecar = resolve_impl(model_path);
    // Task 2 manifest gate (strict): an incompatible sidecar is NEVER
    // loaded — the provider stays unavailable and the sampler path falls
    // back to greedy bytes (theory-only). Empty/unresolvable path keeps the
    // historical unavailable stub (check is vacuous for empty input).
    bool loadable = !sidecar.empty();
    if (loadable) {
      if (const auto reason = check_model_compatible(sidecar);
          reason.has_value()) {
        note_manifest_refusal(sidecar, *reason);
        loadable = false;
      }
    }
    if (loadable) {
      Ort::SessionOptions opts;
      opts.SetIntraOpNumThreads(1);
      opts.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_BASIC);
#ifdef _WIN32
      const int need =
          ::MultiByteToWideChar(CP_UTF8, 0, sidecar.c_str(), -1, nullptr, 0);
      if (need > 0) {
        std::wstring wpath(static_cast<size_t>(need), L'\0');
        if (::MultiByteToWideChar(CP_UTF8, 0, sidecar.c_str(), -1, wpath.data(),
                                  need) > 0) {
          Ort::Session session{impl->env, wpath.c_str(), opts};
          Ort::AllocatorWithDefaultOptions alloc;
          Ort::AllocatedStringPtr in_name = session.GetInputNameAllocated(0, alloc);
          impl->input_name = in_name.get();
          impl->session = std::move(session);
          impl->loaded = true;
          impl->loads = 1;
        }
      }
#else
      Ort::Session session{impl->env, sidecar.c_str(), opts};
      Ort::AllocatorWithDefaultOptions alloc;
      Ort::AllocatedStringPtr in_name = session.GetInputNameAllocated(0, alloc);
      impl->input_name = in_name.get();
      impl->session = std::move(session);
      impl->loaded = true;
      impl->loads = 1;
#endif
    }
    impl_ = std::move(impl);
  } catch (...) {
    impl_ = nullptr;  // unavailable stub: available()==false, fills false
  }
#else
  (void)model_path;  // OFFLINE stub: never loaded, never throws
#endif
}

OrtLogitsProvider::~OrtLogitsProvider() = default;

bool OrtLogitsProvider::available() const noexcept {
  return impl_ != nullptr && impl_->loaded;
}

int OrtLogitsProvider::load_count() const noexcept {
  return impl_ != nullptr ? impl_->loads : 0;
}

bool OrtLogitsProvider::get_logits(const int* seq, size_t n, float* out) noexcept {
  try {
    if (impl_ == nullptr || !impl_->loaded) return false;
    if (out == nullptr) return false;
    if (n == 0 || n > kMaxIds) return false;
    if (seq == nullptr) return false;
#ifdef HARMONY_FORGE_WITH_ONNX
    const std::lock_guard<std::mutex> lock(impl_->run_mutex);
    if (!impl_->loaded) return false;
    std::vector<std::int64_t> ids(n);
    for (size_t i = 0; i < n; ++i) ids[i] = static_cast<std::int64_t>(seq[i]);
    const std::array<std::int64_t, 2> shape{1, static_cast<std::int64_t>(n)};
    const Ort::MemoryInfo mem =
        Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    Ort::Value in_tensor = Ort::Value::CreateTensor<std::int64_t>(
        mem, ids.data(), ids.size(), shape.data(), shape.size());
    const char* in_names[] = {impl_->input_name.c_str()};
    const char* out_names[] = {kLogitsOutput};
    std::vector<Ort::Value> results = impl_->session.Run(
        Ort::RunOptions{nullptr}, in_names, &in_tensor, 1, out_names, 1);
    if (results.empty() || !results[0].IsTensor()) return false;
    const auto info = results[0].GetTensorTypeAndShapeInfo();
    if (info.GetElementType() != ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT)
      return false;
    if (info.GetShape() != std::vector<std::int64_t>{1, static_cast<std::int64_t>(n),
                                                     kSamplerVocab})
      return false;
    const float* data = results[0].GetTensorData<float>();
    if (data == nullptr) return false;
    // Last-position row into caller-owned scratch (no allocation here:
    // `ids`/`results` above are per-call setup on the background thread,
    // same setup-time allowance sampler.h grants the provider).
    std::memcpy(out, data + (n - 1) * kSamplerVocab,
                static_cast<size_t>(kSamplerVocab) * sizeof(float));
    for (int i = 0; i < kSamplerVocab; ++i)
      if (!std::isfinite(static_cast<double>(out[i]))) return false;
    return true;
#else
    return false;
#endif
  } catch (...) {
    return false;  // failure is per-call, never fatal, never throws
  }
}

std::string logits_sidecar_path_for_model(const std::string& model_path) noexcept {
  try {
    return resolve_impl(model_path);
  } catch (...) {
    return std::string{};
  }
}

}  // namespace hf::infer
