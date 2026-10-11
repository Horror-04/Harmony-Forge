#pragma once

#include <string>

namespace hf::infer {

// Model-path sanitise rule (Phase 2 Task 4, item B; shared by the JUCE state
// layer and unit tests so the rule stays identical in both).
//
// Empty means "no model configured" and is VALID: generation falls back to
// the deterministic composer (the pre-Task-4 behavior). A non-empty path is
// usable only when it names an existing regular file with a `.onnx`
// extension (matched case-insensitively: Windows file systems are
// case-insensitive). Everything else sanitises to empty. Never throws;
// filesystem errors (permissions, races) count as unusable, never propagate.
bool is_usable_model_path(const std::string& path) noexcept;

// Returns `path` unchanged when usable, else empty.
std::string sanitised_model_path(const std::string& path) noexcept;

}  // namespace hf::infer
