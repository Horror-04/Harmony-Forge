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

// Phase 3 Task 4, item A/C: picker display policy. Pure and JUCE-free so
// the stored-path -> label/hint mapping is unit-testable; the JUCE editor
// calls these to fill its labels, keeping the transition table identical
// in both places.
//
// Display name for a SANITISED (stored) path: empty (no model configured)
// maps to a fixed placeholder naming the deterministic fallback, otherwise
// the file's basename (never the full path: weights often live in deep
// directories). Never throws (unparseable input falls back to itself).
std::string model_display_name(const std::string& sanitised_path) noexcept;

// User-facing rejection hint for a chosen file that fails the sanitise
// rule (must exist + `.onnx`): the picker shows this instead of silently
// ignoring the selection. Fixed text shared by the UI and the tests.
const char* model_rejection_hint() noexcept;

}  // namespace hf::infer
