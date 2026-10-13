// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "HFLookAndFeel.h"

namespace hf::ui {

void HFLookAndFeel::drawButtonBackground(
    juce::Graphics& g, juce::Button& button,
    const juce::Colour& /*backgroundColour*/,
    bool shouldDrawButtonAsHighlighted, bool shouldDrawButtonAsDown) {
  // NOTE: backgroundColour (from findColour) is intentionally ignored — all
  // fills come from UITokens so the palette has a single source.
  const auto bounds = button.getLocalBounds().toFloat().reduced(0.5f);
  const float radius = static_cast<float>(UITokens::kRadius);
  const bool primary = isPrimary(button);
  const bool enabled = button.isEnabled();

  juce::Colour bg(UITokens::kBgCard);
  if (!enabled) {
    bg = juce::Colour(UITokens::kBgCard);  // no interaction paint
  } else if (primary) {
    bg = juce::Colour(shouldDrawButtonAsDown ? UITokens::kAccentDim
                                             : UITokens::kAccent);
  } else if (shouldDrawButtonAsDown) {
    bg = juce::Colour(UITokens::kAccentDim);
  } else if (shouldDrawButtonAsHighlighted) {
    bg = juce::Colour(UITokens::kBgCardHover);
  }

  g.setColour(bg);
  g.fillRoundedRectangle(bounds, radius);

  if (!primary) {
    // Toggled-on state keeps its selection cue (audition/tab buttons).
    const bool toggled =
        (button.getToggleState() && enabled && !shouldDrawButtonAsDown);
    g.setColour(juce::Colour(toggled ? UITokens::kAccent : UITokens::kBorder));
    g.drawRoundedRectangle(bounds, radius, toggled ? 1.5f : 1.0f);
  }

  // Brief-mandated 1 px kFocusRing outline when keyboard-focused. (UITokens
  // also carries a 2 px paintFocusRing helper used by the container rings;
  // buttons use the 1 px variant per the brief — see the Task 2 report.)
  if (button.hasKeyboardFocus(true)) {
    g.setColour(juce::Colour(UITokens::kFocusRing));
    g.drawRoundedRectangle(bounds, radius, 1.0f);
  }
}

void HFLookAndFeel::drawButtonText(juce::Graphics& g, juce::TextButton& button,
                                   bool /*shouldDrawButtonAsHighlighted*/,
                                   bool /*shouldDrawButtonAsDown*/) {
  const bool primary = isPrimary(button);
  const bool enabled = button.isEnabled();
  g.setColour(juce::Colour(!enabled      ? UITokens::kTextDim
                           : primary    ? UITokens::kBgApp
                                        : UITokens::kTextBody));
  g.setFont(getTextButtonFont(button, button.getHeight()));
  constexpr int kTextInset = 4;
  g.drawText(button.getButtonText(), button.getLocalBounds().reduced(kTextInset, 0),
             juce::Justification::centred, true);
}

void HFLookAndFeel::drawComboBox(juce::Graphics& g, int width, int height,
                                 bool /*isButtonDown*/, int buttonX, int buttonY,
                                 int buttonW, int buttonH, juce::ComboBox& box) {
  const auto bounds =
      juce::Rectangle<int>(0, 0, width, height).toFloat().reduced(0.5f);
  const float radius = static_cast<float>(UITokens::kRadius);
  g.setColour(juce::Colour(UITokens::kBgInput));
  g.fillRoundedRectangle(bounds, radius);
  g.setColour(juce::Colour(box.isEnabled() ? UITokens::kBorderStrong
                                           : UITokens::kBorder));
  g.drawRoundedRectangle(bounds, radius, 1.0f);

  // Triangular arrow, centred in the button zone, in kTextBody.
  const float cx = static_cast<float>(buttonX) + static_cast<float>(buttonW) * 0.5f;
  const float cy = static_cast<float>(buttonY) + static_cast<float>(buttonH) * 0.5f;
  constexpr float kArrowHalfW = 4.5f;
  constexpr float kArrowHalfH = 3.0f;
  juce::Path arrow;
  arrow.addTriangle(cx - kArrowHalfW, cy - kArrowHalfH, cx + kArrowHalfW,
                    cy - kArrowHalfH, cx, cy + kArrowHalfH);
  g.setColour(juce::Colour(box.isEnabled() ? UITokens::kTextBody
                                           : UITokens::kTextDim));
  g.fillPath(arrow);
}

void HFLookAndFeel::drawLinearSlider(
    juce::Graphics& g, int x, int y, int width, int height, float sliderPos,
    float minSliderPos, float maxSliderPos, juce::Slider::SliderStyle style,
    juce::Slider& slider) {
  if (style != juce::Slider::LinearHorizontal &&
      style != juce::Slider::LinearBar) {
    LookAndFeel_V4::drawLinearSlider(g, x, y, width, height, sliderPos,
                                     minSliderPos, maxSliderPos, style, slider);
    return;
  }
  const bool enabled = slider.isEnabled();
  const float cy = static_cast<float>(y) + static_cast<float>(height) * 0.5f;
  constexpr float kTrackH = 3.0f;
  const float trackX0 = juce::jmin(minSliderPos, maxSliderPos);
  const float trackX1 = juce::jmax(minSliderPos, maxSliderPos);
  const juce::Rectangle<float> track(trackX0, cy - kTrackH * 0.5f,
                                     trackX1 - trackX0, kTrackH);
  g.setColour(juce::Colour(UITokens::kBorder));
  g.fillRoundedRectangle(track, kTrackH * 0.5f);

  const float fillX1 = juce::jlimit(trackX0, trackX1, sliderPos);
  if (fillX1 > trackX0) {
    g.setColour(juce::Colour(enabled ? UITokens::kAccent : UITokens::kTextDim));
    g.fillRoundedRectangle(
        juce::Rectangle<float>(trackX0, track.getY(), fillX1 - trackX0, kTrackH),
        kTrackH * 0.5f);
  }

  // Round 10 px thumb with a kBorder outline; no tick marks.
  constexpr float kThumbD = 10.0f;
  const juce::Rectangle<float> thumb(sliderPos - kThumbD * 0.5f,
                                     cy - kThumbD * 0.5f, kThumbD, kThumbD);
  g.setColour(juce::Colour(enabled ? UITokens::kTextBright : UITokens::kTextDim));
  g.fillEllipse(thumb);
  g.setColour(juce::Colour(UITokens::kBorder));
  g.drawEllipse(thumb, 1.0f);
}

void HFLookAndFeel::drawScrollbar(
    juce::Graphics& g, juce::ScrollBar& /*bar*/, int x, int y, int width,
    int height, bool isScrollbarVertical, int thumbStartPosition, int thumbSize,
    bool isMouseOver, bool isMouseDown) {
  juce::Rectangle<float> thumb =
      isScrollbarVertical
          ? juce::Rectangle<float>(static_cast<float>(x),
                                   static_cast<float>(thumbStartPosition),
                                   static_cast<float>(width),
                                   static_cast<float>(thumbSize))
          : juce::Rectangle<float>(static_cast<float>(thumbStartPosition),
                                   static_cast<float>(y),
                                   static_cast<float>(thumbSize),
                                   static_cast<float>(height));
  thumb = thumb.reduced(1.0f);
  if (thumb.isEmpty()) return;
  g.setColour(juce::Colour((isMouseOver || isMouseDown) ? UITokens::kTextDim
                                                       : UITokens::kBorderStrong));
  g.fillRoundedRectangle(thumb, 4.0f);
}

void HFLookAndFeel::drawTooltip(juce::Graphics& g, const juce::String& text,
                                int width, int height) {
  // The 0xCC000000 fill is brief-mandated verbatim (no UITokens entry for
  // tooltip black); everything else is tokens.
  g.fillAll(juce::Colour(0xCC000000));
  g.setColour(juce::Colour(UITokens::kBorder));
  g.drawRect(0, 0, width, height, 1);
  g.setColour(juce::Colour(UITokens::kTextBody));
  g.setFont(juce::Font(
      juce::FontOptions(UITokens::kFontCaption).withStyle("Light")));
  constexpr int kPadX = 8;
  constexpr int kPadY = 4;
  g.drawFittedText(text, juce::Rectangle<int>(kPadX, kPadY, width - 2 * kPadX,
                                              height - 2 * kPadY),
                   juce::Justification::topLeft, 8, 1.0f);
}

void HFLookAndFeel::drawProgressBar(juce::Graphics& g, juce::ProgressBar& /*bar*/,
                                    int width, int height, double progress,
                                    const juce::String& /*textToShow*/) {
  const auto bounds =
      juce::Rectangle<int>(0, 0, width, height).toFloat().reduced(0.5f);
  const float radius = static_cast<float>(UITokens::kRadius);
  g.setColour(juce::Colour(UITokens::kBgInput));
  g.fillRoundedRectangle(bounds, radius);
  const float inner = bounds.getWidth();
  if (inner <= 0.0f) return;
  if (progress >= 0.0) {
    const float w = inner * static_cast<float>(juce::jlimit(0.0, 1.0, progress));
    if (w > 0.0f) {
      g.setColour(juce::Colour(UITokens::kAccent));
      g.fillRoundedRectangle(
          juce::Rectangle<float>(bounds.getX(), bounds.getY(), w,
                                 bounds.getHeight()),
          radius);
    }
  } else {
    // Indeterminate: a 40 % accent block cycling on wall-clock (pure paint,
    // no state). Unreached in the app today (no ProgressBar in use).
    const double t = static_cast<double>(juce::Time::getMillisecondCounter() % 1500) / 1500.0;
    const float w = inner * 0.4f;
    const float px = bounds.getX() + static_cast<float>(t) * (inner - w);
    g.setColour(juce::Colour(UITokens::kAccent));
    g.fillRoundedRectangle(
        juce::Rectangle<float>(px, bounds.getY(), w, bounds.getHeight()), radius);
  }
}

juce::Font HFLookAndFeel::getLabelFont(juce::Label& /*label*/) {
  return juce::Font(
      juce::FontOptions(UITokens::kFontBody).withStyle("Light"));
}

juce::Font HFLookAndFeel::getComboBoxFont(juce::ComboBox& /*box*/) {
  return juce::Font(
      juce::FontOptions(UITokens::kFontSmall).withStyle("Light"));
}

juce::Font HFLookAndFeel::getTextButtonFont(juce::TextButton& /*button*/,
                                            int /*buttonHeight*/) {
  return juce::Font(
      juce::FontOptions(UITokens::kFontBody).withStyle("Light"));
}

}  // namespace hf::ui
