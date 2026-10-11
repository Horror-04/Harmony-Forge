// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Model-path sanitise rule. See model_path.h. Pure C++20, no JUCE.
#include "model_path.h"

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <system_error>

namespace hf::infer {
namespace {

bool has_onnx_extension(const std::string& path) {
  if (path.size() < 5) return false;
  std::string tail = path.substr(path.size() - 5);
  std::transform(tail.begin(), tail.end(), tail.begin(),
                 [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
  return tail == ".onnx";
}

}  // namespace

bool is_usable_model_path(const std::string& path) noexcept {
  if (path.empty()) return false;  // empty is *valid* (fallback), not *usable*
  if (!has_onnx_extension(path)) return false;
  std::error_code ec;
  const std::filesystem::file_status st =
      std::filesystem::status(std::filesystem::path(path), ec);
  if (ec) return false;
  return std::filesystem::is_regular_file(st);
}

std::string sanitised_model_path(const std::string& path) noexcept {
  if (path.empty()) return path;
  return is_usable_model_path(path) ? path : std::string{};
}

std::string model_display_name(const std::string& sanitised_path) noexcept {
  if (sanitised_path.empty()) return "No model (deterministic)";
  try {
    const std::string base = std::filesystem::path(sanitised_path).filename().string();
    return base.empty() ? sanitised_path : base;
  } catch (...) {
    return sanitised_path;
  }
}

const char* model_rejection_hint() noexcept {
  return "Model not set: choose an existing .onnx file.";
}

}  // namespace hf::infer
