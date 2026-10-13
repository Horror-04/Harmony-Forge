// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <cstdint>

#include <juce_gui_basics/juce_gui_basics.h>

// Phase 6 Task 2 (Stage A, A2): shared focus-accent token.
//
// `kFocusRing` is reserved verbatim for Task 4 (single-source `UITokens`
// migration) — do NOT rename. It is the raw ARGB value (not a
// `juce::Colour`) because `juce::Colour(uint32)` is not constexpr; paint
// code wraps it as `juce::Colour(hf::ui::UITokens::kFocusRing)` or calls
// `hf::ui::paintFocusRing` below.
namespace hf::ui {

struct UITokens {
  static constexpr std::uint32_t kFocusRing = 0xff2563eb;
};

// 2 px accent rounded-rect outline, inset 1 px so the full stroke stays
// inside the component. Call sites gate on `hasKeyboardFocus(true)`; the
// helper itself draws unconditionally so the stroke is unit-pinnable.
inline void paintFocusRing(juce::Graphics& g, juce::Rectangle<int> bounds) {
  g.setColour(juce::Colour(UITokens::kFocusRing));
  g.drawRoundedRectangle(bounds.toFloat().reduced(1.0f), 4.0f, 2.0f);
}

}  // namespace hf::ui
