// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Phase 6 Task 5: visual-polish pins (plugin-ON only, same headless rules as
// test_focus_resize.cpp: ArrangeBar/CandidateBar/the editor own real widgets
// and cannot be instantiated headless - only their pure logic is pinned).
//
// - ArrangeBar::countTextFor: live-count text (plural/singular/zero).
// - ExplainView wrap: narrowing the view grows contentHeight (rows wrap
//   instead of clipping); widening restores it (no accumulation); two wide
//   widths agree (fully unwrapped == legacy single-line stack); a narrow
//   paint reaches the measured bottom (pixel proxy for no clipping).
// - ChordTrack empty state: 64 px allocation kept, honest empty line paints
//   (launch-condition probe for the strip hidden behind the launch scroll;
//   see the task report concern).
#include <catch2/catch_test_macros.hpp>

#include <memory>

#include <juce_events/juce_events.h>
#include <juce_gui_basics/juce_gui_basics.h>

#include "ui/ArrangeBar.h"
#include "ui/ChordTrack.h"
#include "ui/ExplainView.h"
#include "ui/PatternDocument.h"
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
  // A held semitone rub (60 vs 61) plus a fifth: exercises the key, chord,
  // conflict and recommendation rows with non-trivial line lengths.
  tr.notes.push_back(hf::core::Note{60, 0, 480, 90});
  tr.notes.push_back(hf::core::Note{61, 0, 480, 90});
  tr.notes.push_back(hf::core::Note{67, 480, 480, 90});
  pat.tracks.push_back(tr);
  // A dominant-type chord forces the long "secondary dominant" explain line.
  doc->adoptArrangement(pat, {{62, "7"}, {67, "7"}});
  undo.clearUndoHistory();
  return doc;
}

}  // namespace

TEST_CASE("arrange live count text is honest", "[polish][task5]") {
  ensure_juce();
  CHECK(ArrangeBar::countTextFor(3, 20) == "Arrange: 3 sections, 20 bars");
  CHECK(ArrangeBar::countTextFor(1, 4) == "Arrange: 1 section, 4 bars");
  CHECK(ArrangeBar::countTextFor(0, 0) == "Arrange: 0 sections, 0 bars");
  CHECK(ArrangeBar::countTextFor(1, 1) == "Arrange: 1 section, 1 bar");
}

TEST_CASE("explain empty state has a legacy single-line height", "[polish][task5]") {
  ensure_juce();
  juce::UndoManager undo;
  PatternDocument doc(&undo);  // empty: no notes, no chords
  ExplainView view(doc);
  // Title + one body row, all floors (width 0: no measuring possible).
  // 8 + 24 + 8 + 20 + 8 = 68.
  CHECK(view.contentHeight() == 68);
}

TEST_CASE("explain rows wrap instead of clipping", "[polish][task5]") {
  juce::UndoManager undo;
  auto doc = make_doc(undo);
  ExplainView view(*doc);

  view.setSize(2000, 10);
  const int wide = view.contentHeight();
  CHECK(wide > 0);

  // Two wide widths agree: nothing exceeds ~1984 px, so every row renders
  // single-line (the legacy stack) in both.
  view.setSize(4000, wide);
  CHECK(view.contentHeight() == wide);

  // Narrowing wraps long rows (title alone is 30 chars) instead of clipping.
  view.setSize(200, view.contentHeight());
  const int narrow = view.contentHeight();
  CHECK(narrow > wide);

  // Widening restores the stack exactly (no height accumulation across
  // relayout passes).
  view.setSize(2000, narrow);
  CHECK(view.contentHeight() == wide);
}

TEST_CASE("chord empty state paints honestly", "[polish][task5]") {
  // Launch-condition probe: with no chords the strip keeps its 64 px
  // allocation (setSize-driven, untouched) and paints the honest empty line
  // instead of a "-" cell + freeze hint. Headless paint is assertion-safe
  // (teardown artifact only - this binary already runs explicitly).
  ensure_juce();
  juce::UndoManager undo;
  PatternDocument doc(&undo);  // empty: no notes, no chords
  ChordTrack strip(doc);
  CHECK(strip.getHeight() == 64);
  const int w = 400;
  strip.setSize(w, 64);
  juce::Image img(juce::Image::ARGB, w, 64, true);
  img.clear(img.getBounds(), juce::Colour(hf::ui::UITokens::kBgPanel));
  {
    juce::Graphics g(img);
    strip.paint(g);
  }
  const juce::Colour bg(hf::ui::UITokens::kBgPanel);
  int drawnPixels = 0;
  for (int y = 0; y < 30; ++y)
    for (int x = 0; x < 300; ++x)
      if (img.getPixelAt(x, y) != bg) ++drawnPixels;
  CHECK(drawnPixels > 20);
}

TEST_CASE("explain wrapped rows reach the measured bottom", "[polish][task5]") {
  // Pixel proxy for "no clipping": paint narrow into an Image and require
  // drawn (non-background) pixels in the bottom content band. If wrapped rows
  // drew only their first line (or metrics/draw disagreed), the bottom would
  // be bare background. Headless paint is assertion-safe (teardown artifact only,
  // same as test_note_cues - this binary already runs explicitly).
  juce::UndoManager undo;
  auto doc = make_doc(undo);
  ExplainView view(*doc);
  view.setSize(200, 10);
  const int h = view.contentHeight();
  CHECK(h > 0);
  juce::Image img(juce::Image::ARGB, 200, h, true);
  img.clear(img.getBounds(), juce::Colour(hf::ui::UITokens::kBgPanel));
  {
    juce::Graphics g(img);
    view.paint(g);
  }
  const int pad = hf::ui::UITokens::kRhythmPx;
  // Last ~28 px (one full text line plus slop): a wrapped last row fills it
  // from the top, a single-line last row sits centred in its 20 px floor -
  // either way drawn text reaches it. Count any non-background pixel (robust
  // to antialiasing: edge pixels are blends, never bare background).
  const juce::Colour bg(hf::ui::UITokens::kBgPanel);
  int drawnPixels = 0;
  for (int y = h - pad - 28; y < h - pad; ++y)
    for (int x = 0; x < 200; ++x)
      if (img.getPixelAt(x, y) != bg) ++drawnPixels;
  CHECK(drawnPixels > 20);
}
