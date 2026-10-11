// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <string>
#include <vector>

namespace hf::infer {

struct InferenceConfig {
  std::string model_path;
  int max_tokens = 1024;
  unsigned seed = 0;
};

/// Background-thread inference interface (Sprint 3 binds ONNX Runtime).
/// Never called from the real-time audio thread.
class IInferenceRunner {
 public:
  virtual ~IInferenceRunner() = default;
  virtual std::vector<int> predict(const std::vector<int>& input, const InferenceConfig& cfg) = 0;
};

}  // namespace hf::infer
