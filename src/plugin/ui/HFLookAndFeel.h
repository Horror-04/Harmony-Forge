// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <juce_gui_basics/juce_gui_basics.h>

#include "UITokens.h"

namespace hf::ui {

// Phase 7 Task 2: core visual identity (design 2026-10-13-visual-redesign
// section 2.3). Paint-only: no component callbacks are touched; every colour
// and size comes from UITokens (zero raw hex here — including the tooltip
// fill, which reads kTooltipBg since Task 5).
//
// Primary CTA variant: tag a TextButton ONCE at creation with
//   getProperties().set (HFLookAndFeel::kPrimaryProperty, true)
// (Generate/Regenerate, Keep, Build, Preview only). The LookAndFeel reads the
// tag at paint time, so no per-button subclassing or callback changes.
class HFLookAndFeel : public juce::LookAndFeel_V4 {
 public:
  // Component property (bool) selecting the primary CTA variant.
  static constexpr const char* kPrimaryProperty = "hfPrimary";

  static bool isPrimary(const juce::Button& b) {
    return static_cast<bool>(
        b.getProperties().getWithDefault(kPrimaryProperty, false));
  }

  HFLookAndFeel() = default;
  ~HFLookAndFeel() override = default;

  // Design 2.3 button: rounded rect r=kRadius. Normal bg kBgCard / border
  // kBorder; hover kBgCardHover; pressed kAccentDim; primary bg kAccent with
  // no border; disabled bg kBgCard with no interaction paint. Toggled-on
  // (non-primary) buttons keep their selection cue via a kAccent border
  // (CandidateBar audition + Edit/Explain tabs rely on toggle paint).
  void drawButtonBackground(juce::Graphics& g, juce::Button& button,
                            const juce::Colour& /*backgroundColour*/,
                            bool shouldDrawButtonAsHighlighted,
                            bool shouldDrawButtonAsDown) override;
  // Normal text kTextBody; primary text dark (kBgApp); disabled kTextDim.
  void drawButtonText(juce::Graphics& g, juce::TextButton& button,
                      bool shouldDrawButtonAsHighlighted,
                      bool shouldDrawButtonAsDown) override;

  // ComboBox: bg kBgInput, border kBorder, r=kRadius, triangular arrow path
  // in kTextBody.
  void drawComboBox(juce::Graphics& g, int width, int height, bool isButtonDown,
                    int buttonX, int buttonY, int buttonW, int buttonH,
                    juce::ComboBox& box) override;

  // Horizontal linear slider only (all app sliders are horizontal; anything
  // else delegates to the base class): 3 px kBorder track behind, kAccent
  // filled part, 10 px round kTextBright thumb with kBorder outline.
  void drawLinearSlider(juce::Graphics& g, int x, int y, int width, int height,
                        float sliderPos, float minSliderPos, float maxSliderPos,
                        juce::Slider::SliderStyle style,
                        juce::Slider& slider) override;

  // ScrollBar: 8 px (see getDefaultScrollbarWidth), thumb kBorderStrong r=4,
  // hover/pressed kTextDim. Both orientations.
  int getDefaultScrollbarWidth() override { return 8; }
  void drawScrollbar(juce::Graphics& g, juce::ScrollBar& bar, int x, int y,
                     int width, int height, bool isScrollbarVertical,
                     int thumbStartPosition, int thumbSize, bool isMouseOver,
                     bool isMouseDown) override;

  // Tooltip: 11 px (kFontCaption) kTextBody on kTooltipBg (design 2.3
  // #000000CC) with a kBorder outline.
  void drawTooltip(juce::Graphics& g, const juce::String& text, int width,
                   int height) override;

  // ProgressBar: background kBgInput, fill kAccent, r=kRadius. NOTE: no
  // ProgressBar exists in the app yet (preview/export busy state is a
  // status-label ellipsis) — this override is forward cover, currently N/A.
  // Repaint-driver note (Task 5): an indeterminate bar only animates behind a
  // repaint driver (e.g. a Timer calling repaint); wire one up if a bar is
  // ever added, otherwise the cycling block above paints exactly once.
  void drawProgressBar(juce::Graphics& g, juce::ProgressBar& bar, int width,
                       int height, double progress,
                       const juce::String& textToShow) override;

  // Token sizes (kFontSmall/kFontBody), light weights ("Light" named style;
  // falls back to the default face where no Light instance exists).
  juce::Font getLabelFont(juce::Label& label) override;
  juce::Font getComboBoxFont(juce::ComboBox& box) override;
  juce::Font getTextButtonFont(juce::TextButton& button,
                               int buttonHeight) override;
};

}  // namespace hf::ui
