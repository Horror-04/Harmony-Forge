// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <string>
#include <vector>

#include "core/serialization/vocab_layout.gen.h"

namespace hf::infer {

struct InferenceConfig {
  std::string model_path;
  int max_tokens = hf::ser::kVocabMaxTokens;  // S2b step 4a: codec cap (was 1024 literal)
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
