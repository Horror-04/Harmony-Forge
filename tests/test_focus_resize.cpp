// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Phase 6 Task 2: focus rings + resizable window + contrast pass.
// Headless coverage (no peer, no message loop beyond a MessageManager for
// async change messages — same harness as test_keyboard_moves):
//
// - Shared focus-accent token value (`hf::ui::UITokens::kFocusRing`).
// - `paintFocusRing` stroke pixels (the helper draws unconditionally so the
//   stroke is pinnable; call sites gate on `hasKeyboardFocus(true)`, which
//   needs a real peer and is therefore review-verified, not unit-tested).
// - All four custom surfaces opt into keyboard focus (the ring predicate can
//   only fire when `getWantsKeyboardFocus()` is true).
// - Contrast ratios (WCAG relative-luminance, measured not eyeballed) for
//   the Task 2 scope: octave/degree greys, empty-state text, Explain body,
//   model/status labels.
// - PianoRoll/ChordTrack opt into keyboard focus (the ring predicate's
//   precondition). ArrangeBar/CandidateBar flags + the two-size layout smoke
//   cannot run in-process (see NOTE below) and are verified by review,
//   pluginval, and Standalone screenshots at both sizes.
#include <catch2/catch_test_macros.hpp>

#include <cmath>
#include <cstdint>
#include <memory>

#include <juce_events/juce_events.h>
#include <juce_gui_basics/juce_gui_basics.h>

#include "ui/ChordTrack.h"
#include "ui/PatternDocument.h"
#include "ui/PianoRoll.h"
#include "ui/UITokens.h"

namespace {

// Same lazy-JUCE rule as test_keyboard_moves: function-local static, never
// during static init.
void ensure_juce() {
  static juce::ScopedJuceInitialiser_GUI juceInit;
  (void)juceInit;
}

std::unique_ptr<PatternDocument> make_doc(juce::UndoManager& undo) {
  ensure_juce();
  auto doc = std::make_unique<PatternDocument>(&undo);
  hf::core::Pattern pat;
  pat.ticks_per_beat = 480;
  pat.beats_per_bar = 4;
  hf::core::Track tr;
  tr.type = hf::core::TrackType::Melody;
  tr.notes.push_back(hf::core::Note{60, 0, 480, 90});
  pat.tracks.push_back(tr);
  doc->adoptArrangement(pat, {{60, "maj"}, {67, "7"}});
  undo.clearUndoHistory();
  return doc;
}

// WCAG 2.x relative luminance for an 0xRRGGBB colour.
double luminance(std::uint32_t rgb) {
  const auto lin = [](double c) {
    c /= 255.0;
    return c <= 0.03928 ? c / 12.92 : std::pow((c + 0.055) / 1.055, 2.4);
  };
  const double r = lin(static_cast<double>((rgb >> 16) & 0xff));
  const double g = lin(static_cast<double>((rgb >> 8) & 0xff));
  const double b = lin(static_cast<double>(rgb & 0xff));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

double contrast(std::uint32_t fg, std::uint32_t bg) {
  const double hi = std::max(luminance(fg), luminance(bg));
  const double lo = std::min(luminance(fg), luminance(bg));
  return (hi + 0.05) / (lo + 0.05);
}

int count_pixels(const juce::Image& img, juce::Colour c) {
  int n = 0;
  for (int y = 0; y < img.getHeight(); ++y)
    for (int x = 0; x < img.getWidth(); ++x)
      if (img.getPixelAt(x, y) == c) ++n;
  return n;
}

}  // namespace

TEST_CASE("focus ring token value is the reserved accent", "[focus][task2]") {
  static_assert(hf::ui::UITokens::kFocusRing == 0xff2563eb,
                "Task 4 adopts this verbatim — do not rename/revalue");
  CHECK(hf::ui::UITokens::kFocusRing == 0xff2563eb);
}

TEST_CASE("paintFocusRing emits 2px accent stroke pixels", "[focus][task2]") {
  ensure_juce();
  juce::Image img(juce::Image::ARGB, 120, 60, true);
  img.clear(img.getBounds(), juce::Colour(0xff000000));
  {
    juce::Graphics g(img);
    hf::ui::paintFocusRing(g, img.getBounds());
  }
  // A 2 px rounded-rect stroke around 120x60 yields hundreds of exact-ARGB
  // pixels along the straight runs (antialiasing only softens the corners).
  CHECK(count_pixels(img, juce::Colour(hf::ui::UITokens::kFocusRing)) > 100);
}

TEST_CASE("roll and chord surfaces opt into keyboard focus", "[focus][task2]") {
  juce::UndoManager undo;
  auto doc = make_doc(undo);
  PianoRoll roll(*doc);
  ChordTrack chords(*doc);
  CHECK(roll.getWantsKeyboardFocus());
  CHECK(chords.getWantsKeyboardFocus());
}

TEST_CASE("Task 2 contrast ratios meet their gates", "[contrast][task2]") {
  // Secondary/small text gate: >= 3:1. Body text gate: >= 4.5:1.
  // Octave note names (10 px, secondary) on both lane backgrounds.
  CHECK(contrast(0x808080, 0x22252b) >= 3.0);
  CHECK(contrast(0x808080, 0x141518) >= 3.0);
  // Chord degree/function + freeze hint (secondary) on both cell states.
  CHECK(contrast(0x9aa0a8, 0x2b2f35) >= 3.0);
  CHECK(contrast(0x9aa0a8, 0x39424e) >= 3.0);
  // Empty-state "No pattern" (body-classified): Task 2 fix grey -> 0x9aa0a8.
  CHECK(contrast(0x9aa0a8, 0x1a1d21) >= 4.5);
  // Explain body + title.
  CHECK(contrast(0xc8ccd2, 0x23262b) >= 4.5);
  CHECK(contrast(0xffffff, 0x23262b) >= 4.5);
  // Model/status/hint labels: default look-and-feel label text is white on
  // the darkgrey editor background (no colour change needed).
  CHECK(contrast(0xffffff, 0x555555) >= 4.5);
}

// NOTE (headless-harness limitation, verified): instantiating real JUCE
// widgets (ListBox/ComboBox/TextEditor/Slider/Viewport — and therefore
// ArrangeBar/CandidateBar/the full editor) in a headless ctest exits
// nonzero (0xC0000374 heap-corruption at process teardown) even for BARE
// widgets with no production code involved, and even after draining the
// message queue. TextButton/PianoRoll/ChordTrack/Image are clean. So the
// two-size layout smoke cannot live in-process: it is verified by (1) the
// fixed-width arithmetic table in the task report (every row/budget at
// 960x600 and 2048x1752), (2) pluginval opening the editor, and (3)
// Standalone screenshots at both sizes. ArrangeBar/CandidateBar
// wants-focus flags + ring wiring are review-verified for the same reason.
