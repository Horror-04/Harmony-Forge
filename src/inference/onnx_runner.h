#pragma once

#include <memory>
#include <vector>

#include "inference_runner.h"

namespace hf::infer {

// ONNX Runtime-backed runner (Sprint 2: committed mock model; real weights later).
//
// Never called from the real-time audio thread. All ORT API use stays on
// background threads; every entry point is no-throw (failures surface as
// `loaded() == false` / empty outputs, never exceptions).
//
// The mock model (`training/model.onnx`) is a deterministic pass-through, so
// `predict` with a fixed seed returns identical outputs. `cfg.seed` is carried
// for future sampling use; `cfg.max_tokens` truncates input and output.
class OnnxRunner : public IInferenceRunner {
 public:
  explicit OnnxRunner(const InferenceConfig& cfg) noexcept;  // throws nothing: use status
  ~OnnxRunner() override;
  OnnxRunner(const OnnxRunner&) = delete;
  OnnxRunner& operator=(const OnnxRunner&) = delete;

  bool loaded() const noexcept;
  std::vector<int> predict(const std::vector<int>& input,
                           const InferenceConfig& cfg) override;

 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace hf::infer
